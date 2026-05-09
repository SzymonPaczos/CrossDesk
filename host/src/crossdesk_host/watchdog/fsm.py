"""Adaptive heartbeat FSM (Phase 3).

Pure state machine. Caller (servicer) provides one tick per heartbeat
window with ``pong_received`` and optional ``rtt_ns``; FSM emits the
next state, the advisory ``RecoveryAction`` to broadcast over the
``HostFrame.profile_update`` channel, and the ``next_action_after``
backoff for the caller to honor before firing the libvirt action.

State diagram (mirrors ``proto/crossdesk/v1/heartbeat.proto``):

    HEALTHY ──ewma_rtt > k1*baseline──▶ DEGRADED
       ▲                                    │
       │ N healthy ticks                    │ miss_count >= miss_threshold
       │                                    ▼
       └──────────────────────────────── PROBING
                                            │
                                            │ miss_count >= miss_threshold + probing_extra
                                            ▼
                                       SOFT_RECOVERY  (RecoveryAction.GRACEFUL_SHUTDOWN)
                                            │
                                            │ max_soft_attempts exhausted
                                            ▼
                                       HARD_DESTROY   (RecoveryAction.HARD_DESTROY)

The FSM never sleeps and never calls libvirt — it only computes "what
should happen and when". Stage 2 wires this into ``ipc/heartbeat.py``
where the servicer honors the backoff and dispatches the libvirt action.

Phase 3 SPOF (ROADMAP): false-positive HARD_DESTROY = ``virsh destroy``
during user work = data loss. False-negative = hung session, no recovery.
This module is the single place where those two failure modes are
priced; tune ``FsmConfig`` rather than scattering thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from crossdesk_host.proto.crossdesk.v1 import heartbeat_pb2
from crossdesk_host.watchdog.ewma import EwmaRtt

RecoveryAction = heartbeat_pb2.RecoveryAction


class State(Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    PROBING = "PROBING"
    SOFT_RECOVERY = "SOFT_RECOVERY"
    HARD_DESTROY = "HARD_DESTROY"
    # Entered when the host is suspending (e.g. laptop lid close); ticks
    # are no-ops while in this state so that the FSM can't false-positive
    # HARD_DESTROY just because heartbeats stalled across the sleep.
    SUSPENDED = "SUSPENDED"


@dataclass(frozen=True)
class FsmConfig:
    """Tuning knobs for the heartbeat FSM. Defaults are conservative;
    tighter thresholds raise false-positive HARD_DESTROY risk, looser
    ones raise false-negative hung-session risk."""

    miss_threshold: int = 3
    """Misses-in-DEGRADED required before transitioning to PROBING."""

    probing_extra: int = 2
    """Additional misses-in-PROBING required before SOFT_RECOVERY."""

    max_soft_attempts: int = 3
    """Graceful-shutdown retries before escalating to HARD_DESTROY."""

    recovery_ticks: int = 3
    """Consecutive healthy ticks required to recover from
    DEGRADED/PROBING/SOFT_RECOVERY back to HEALTHY."""

    ewma_alpha: float = 0.125
    """EWMA smoothing factor (RFC 6298 SRTT default)."""

    ewma_warmup: int = 10
    """Samples averaged into baseline before EWMA proper takes over."""

    baseline_multiplier_k1: float = 3.0
    """RTT-driven trip: HEALTHY→DEGRADED when ewma > k1 * baseline."""

    backoff_initial_seconds: float = 5.0
    """First graceful-shutdown wait before retry."""

    backoff_max_seconds: float = 60.0
    """Cap on the exponential backoff between retries."""


@dataclass(frozen=True)
class TickInput:
    """One observation feeding :meth:`HeartbeatFsm.tick`."""

    pong_received: bool
    """``True`` if a pong arrived in this tick window."""

    rtt_ns: Optional[int] = None
    """Round-trip time in nanoseconds when ``pong_received``; else ``None``."""

    now_monotonic_ns: int = 0
    """Caller's monotonic timestamp, advisory — passed through to
    :class:`TickOutput` for log correlation."""


@dataclass(frozen=True)
class TickOutput:
    """FSM's response to one tick. Caller (servicer) honours the
    :attr:`recovery_action` + :attr:`next_action_after_seconds` pair
    to decide when to fire the libvirt action."""

    state: State
    """State after this tick."""

    recovery_action: "heartbeat_pb2.RecoveryAction.ValueType"
    """Advisory action the caller should broadcast/dispatch."""

    consecutive_miss_count: int
    """Misses since last successful pong; resets on any pong."""

    healthy_streak: int
    """Consecutive healthy ticks; drives recovery from
    DEGRADED/PROBING/SOFT_RECOVERY back to HEALTHY."""

    soft_attempts: int
    """Graceful-shutdown attempts already issued in SOFT_RECOVERY."""

    ewma_rtt_ns: Optional[int]
    """Smoothed RTT in ns, or ``None`` before first pong."""

    baseline_rtt_ns: Optional[int]
    """Frozen baseline RTT (post-warmup), or ``None`` before warmup."""

    next_action_after_seconds: float
    """How long the caller should wait before honouring
    :attr:`recovery_action`. ``0.0`` means immediate."""


@dataclass
class HeartbeatFsm:
    """Adaptive heartbeat state machine. One instance per
    HeartbeatService.Channel call — caller feeds :meth:`tick` per
    ping interval and dispatches the emitted RecoveryAction."""

    config: FsmConfig = field(default_factory=FsmConfig)
    _state: State = State.HEALTHY
    _miss_count: int = 0
    _healthy_streak: int = 0
    _soft_attempts: int = 0
    _ewma: EwmaRtt = field(init=False)

    def __post_init__(self) -> None:
        self._ewma = EwmaRtt(
            alpha=self.config.ewma_alpha, warmup=self.config.ewma_warmup
        )

    @property
    def state(self) -> State:
        """Current FSM state. Read-only; mutate via tick/suspend/resume."""
        return self._state

    def suspend(self) -> None:
        """Move the FSM into ``SUSPENDED``. Ticks become no-ops until
        :meth:`resume` is called. Idempotent.
        """
        self._state = State.SUSPENDED
        self._healthy_streak = 0

    def resume(self) -> None:
        """Exit ``SUSPENDED`` and re-enter ``PROBING`` with a clean slate.

        Resume goes through PROBING (rather than straight to HEALTHY) so
        the next round of pongs has to actually demonstrate liveness
        before the system claims health — defends against the resume-
        and-immediately-launch race.
        """
        self._state = State.PROBING
        self._miss_count = 0
        self._healthy_streak = 0
        self._soft_attempts = 0

    def tick(self, input: TickInput) -> TickOutput:
        """Single FSM step. Routes to :meth:`_handle_pong` or
        :meth:`_handle_miss` based on ``input.pong_received``;
        SUSPENDED state short-circuits to a no-op so missed
        heartbeats across a host suspend don't trigger recovery."""
        if self._state == State.SUSPENDED:
            return self._snapshot(RecoveryAction.RECOVERY_ACTION_NONE, 0.0)
        if input.pong_received:
            return self._handle_pong(input)
        return self._handle_miss(input)

    def _handle_pong(self, input: TickInput) -> TickOutput:
        """Pong-received branch. Resets ``miss_count`` and either:

        - HEALTHY: stays HEALTHY unless EWMA(RTT) trips the
          ``> k1 * baseline`` threshold → DEGRADED.
        - DEGRADED/PROBING/SOFT_RECOVERY: counts the pong toward the
          ``healthy_streak`` only if RTT is also below the trip
          threshold. After ``recovery_ticks`` healthy ticks, returns
          to HEALTHY and resets ``soft_attempts``.
        - HARD_DESTROY: terminal, no recovery from this state.
        """
        if input.rtt_ns is not None:
            self._ewma.update(input.rtt_ns)
        self._miss_count = 0

        if self._state == State.HARD_DESTROY:
            return self._snapshot(RecoveryAction.RECOVERY_ACTION_NONE, 0.0)

        if self._state == State.HEALTHY:
            if self._is_rtt_threshold_tripped():
                self._state = State.DEGRADED
            return self._snapshot(RecoveryAction.RECOVERY_ACTION_NONE, 0.0)

        # In DEGRADED / PROBING / SOFT_RECOVERY: a tick only counts as healthy
        # if RTT also returned below the threshold; otherwise pongs alone could
        # unwind a trip that EWMA still considers degraded.
        if self._is_rtt_threshold_tripped():
            self._healthy_streak = 0
            return self._snapshot(RecoveryAction.RECOVERY_ACTION_NONE, 0.0)
        self._healthy_streak += 1
        if self._healthy_streak >= self.config.recovery_ticks:
            self._state = State.HEALTHY
            self._healthy_streak = 0
            self._soft_attempts = 0
        return self._snapshot(RecoveryAction.RECOVERY_ACTION_NONE, 0.0)

    def _handle_miss(self, input: TickInput) -> TickOutput:
        """Pong-missed branch. Resets ``healthy_streak``, increments
        ``miss_count``, and walks the recovery ladder:

        - HEALTHY → DEGRADED on the first miss.
        - DEGRADED → PROBING once ``miss_count >= miss_threshold``.
        - PROBING → SOFT_RECOVERY once
          ``miss_count >= miss_threshold + probing_extra``; emits
          GRACEFUL_SHUTDOWN with exponential backoff.
        - SOFT_RECOVERY: re-emits GRACEFUL_SHUTDOWN every
          ``probing_extra`` further misses with exponential backoff;
          escalates to HARD_DESTROY after ``max_soft_attempts``
          retries.
        - HARD_DESTROY: terminal.
        """
        self._healthy_streak = 0
        self._miss_count += 1

        if self._state == State.HARD_DESTROY:
            return self._snapshot(RecoveryAction.RECOVERY_ACTION_NONE, 0.0)

        if self._state == State.HEALTHY:
            self._state = State.DEGRADED
            return self._snapshot(RecoveryAction.RECOVERY_ACTION_NONE, 0.0)

        if self._state == State.DEGRADED:
            if self._miss_count >= self.config.miss_threshold:
                self._state = State.PROBING
                return self._snapshot(RecoveryAction.RECOVERY_ACTION_OBSERVE, 0.0)
            return self._snapshot(RecoveryAction.RECOVERY_ACTION_NONE, 0.0)

        if self._state == State.PROBING:
            soft_entry = self.config.miss_threshold + self.config.probing_extra
            if self._miss_count >= soft_entry:
                self._state = State.SOFT_RECOVERY
                self._soft_attempts = 1
                return self._snapshot(
                    RecoveryAction.RECOVERY_ACTION_GRACEFUL_SHUTDOWN,
                    self._backoff_for_attempt(self._soft_attempts),
                )
            return self._snapshot(RecoveryAction.RECOVERY_ACTION_NONE, 0.0)

        # SOFT_RECOVERY
        soft_entry = self.config.miss_threshold + self.config.probing_extra
        misses_since_soft = self._miss_count - soft_entry
        if misses_since_soft > 0 and misses_since_soft % self.config.probing_extra == 0:
            self._soft_attempts += 1
            if self._soft_attempts > self.config.max_soft_attempts:
                self._state = State.HARD_DESTROY
                return self._snapshot(RecoveryAction.RECOVERY_ACTION_HARD_DESTROY, 0.0)
            return self._snapshot(
                RecoveryAction.RECOVERY_ACTION_GRACEFUL_SHUTDOWN,
                self._backoff_for_attempt(self._soft_attempts),
            )
        return self._snapshot(RecoveryAction.RECOVERY_ACTION_NONE, 0.0)

    def _is_rtt_threshold_tripped(self) -> bool:
        """``True`` when EWMA RTT exceeds the ``k1 * baseline`` ceiling
        AND we're past warmup. Pre-warmup samples never trip — a
        single huge sample early shouldn't move us to DEGRADED."""
        if not self._ewma.is_warm():
            return False
        ewma_ns = self._ewma.value_ns
        baseline_ns = self._ewma.baseline_ns
        if ewma_ns is None or baseline_ns is None:
            return False
        return ewma_ns > self.config.baseline_multiplier_k1 * baseline_ns

    def _backoff_for_attempt(self, attempt: int) -> float:
        """Exponential backoff: ``initial * 2^(attempt-1)`` capped at
        ``backoff_max_seconds``. Attempt 1 → initial; attempt 2 → 2×
        initial; etc."""
        seconds: float = self.config.backoff_initial_seconds * float(2 ** (attempt - 1))
        return min(seconds, self.config.backoff_max_seconds)

    def _snapshot(
        self, action: "heartbeat_pb2.RecoveryAction.ValueType", next_after: float
    ) -> TickOutput:
        """Build a :class:`TickOutput` from the current FSM internals."""
        return TickOutput(
            state=self._state,
            recovery_action=action,
            consecutive_miss_count=self._miss_count,
            healthy_streak=self._healthy_streak,
            soft_attempts=self._soft_attempts,
            ewma_rtt_ns=self._ewma.value_ns,
            baseline_rtt_ns=self._ewma.baseline_ns,
            next_action_after_seconds=next_after,
        )
