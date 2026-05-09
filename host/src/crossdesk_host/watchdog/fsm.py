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


@dataclass(frozen=True)
class FsmConfig:
    miss_threshold: int = 3
    probing_extra: int = 2
    max_soft_attempts: int = 3
    recovery_ticks: int = 3
    ewma_alpha: float = 0.125
    ewma_warmup: int = 10
    baseline_multiplier_k1: float = 3.0
    backoff_initial_seconds: float = 5.0
    backoff_max_seconds: float = 60.0


@dataclass(frozen=True)
class TickInput:
    pong_received: bool
    rtt_ns: Optional[int] = None
    now_monotonic_ns: int = 0


@dataclass(frozen=True)
class TickOutput:
    state: State
    recovery_action: "heartbeat_pb2.RecoveryAction.ValueType"
    consecutive_miss_count: int
    healthy_streak: int
    soft_attempts: int
    ewma_rtt_ns: Optional[int]
    baseline_rtt_ns: Optional[int]
    next_action_after_seconds: float


@dataclass
class HeartbeatFsm:
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
        return self._state

    def tick(self, input: TickInput) -> TickOutput:
        if input.pong_received:
            return self._handle_pong(input)
        return self._handle_miss(input)

    def _handle_pong(self, input: TickInput) -> TickOutput:
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
        if not self._ewma.is_warm():
            return False
        ewma_ns = self._ewma.value_ns
        baseline_ns = self._ewma.baseline_ns
        if ewma_ns is None or baseline_ns is None:
            return False
        return ewma_ns > self.config.baseline_multiplier_k1 * baseline_ns

    def _backoff_for_attempt(self, attempt: int) -> float:
        # exponential: initial * 2^(attempt-1), capped at max
        seconds: float = self.config.backoff_initial_seconds * float(2 ** (attempt - 1))
        return min(seconds, self.config.backoff_max_seconds)

    def _snapshot(
        self, action: "heartbeat_pb2.RecoveryAction.ValueType", next_after: float
    ) -> TickOutput:
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
