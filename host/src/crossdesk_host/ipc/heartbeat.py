"""HeartbeatService gRPC servicer.

Stage 2 wired the pure ``HeartbeatFsm`` into the servicer; Stage 3 (this
file, Week 6) adds the ``AdaptiveProfile`` broadcast that the proto
contract demands the host emit ``BEFORE`` firing a recovery action so
a supervisor can veto (e.g. user actively interacting). Profiles are
also emitted on state changes as advisory hints so the guest can adapt
its scheduling — keeping plain HEALTHY ticks quiet to avoid wire churn.

Why the FSM stays sync and the broadcast lives here: ``HeartbeatFsm``
returns a ``TickOutput`` snapshot per tick; the servicer translates
that snapshot into proto messages on the wire. Keeping the snapshot →
``AdaptiveProfile`` mapping in one place means future proto fields
(``jitter``, additional recovery hints) only need wiring here, not in
the FSM core.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable, List, NamedTuple, Optional

import grpc
from google.protobuf import duration_pb2

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.libvirt_ctl import libvirt_call
from crossdesk_host.lifecycle.error_notifications import notify_forced_stop
from crossdesk_host.lifecycle.notifications import Notifier
from crossdesk_host.observability.metrics import REGISTRY, MetricNames, Registry
from crossdesk_host.proto.crossdesk.v1 import heartbeat_pb2, heartbeat_pb2_grpc
from crossdesk_host.watchdog import (
    FsmConfig,
    HeartbeatFsm,
    RecoveryAction,
    State,
    TickInput,
    TickOutput,
)


@dataclass
class _MissedSleepTracker:
    """Per-channel state for the missed-PrepareForSleep heuristic
    (FOLLOWUPS:677).

    Remembers when the FSM last left HEALTHY and whether a recovery
    action was armed during that outage. A fast HEALTHY → armed →
    HEALTHY round-trip (under ~30s) means the host very likely
    suspended without firing a PrepareForSleep D-Bus signal.
    """

    healthy_left_at_ns: Optional[int] = None
    recovery_armed_during_outage: bool = False
    threshold_seconds: float = 30.0


class _FrameOutcome(NamedTuple):
    """What one turn of the channel loop got from the guest.

    ``tick`` drives the FSM (``None`` = the client closed, break out).
    ``stream_nonce`` is the nonce of the frame behind it, if there was one —
    carried out so the channel can deregister it from the AuthValidator when
    the stream ends.
    """

    tick: Optional[TickInput]
    stream_nonce: Optional[bytes]


BootProbe = Callable[[], Awaitable[bool]]
"""Optional async predicate invoked once per Channel when the FSM
first enters PROBING. Truthy = guest agent is responsive (probe
round-trip succeeded); falsy or raised = asymmetric break suspected
(VSOCK listener up but agent stuck). The probe is fire-and-forget
from the channel loop's perspective — its only effect is a structured
log line — so a slow probe never blocks heartbeat ticks."""

# Stdlib logger (not the structlog facade) so the per-call
# ``configure_logging`` from tests + production reconfigures the live
# stream. The facade caches its factory on import; see the same comment
# in verify_coordinator.py.
logger = logging.getLogger(__name__)


def _ns_to_duration(ns: Optional[int]) -> duration_pb2.Duration:
    if ns is None or ns < 0:
        return duration_pb2.Duration(seconds=0, nanos=0)
    seconds, nanos = divmod(int(ns), 1_000_000_000)
    return duration_pb2.Duration(seconds=seconds, nanos=nanos)


def _seconds_to_duration(s: float) -> duration_pb2.Duration:
    if s < 0:
        return duration_pb2.Duration(seconds=0, nanos=0)
    seconds = int(s)
    nanos = int((s - seconds) * 1_000_000_000)
    return duration_pb2.Duration(seconds=seconds, nanos=nanos)


class HeartbeatServiceServicer(heartbeat_pb2_grpc.HeartbeatServiceServicer):
    def __init__(
        self,
        auth_validator: AuthValidator,
        libvirt_ctl: LibvirtController,
        config: Optional[FsmConfig] = None,
        ping_interval_seconds: float = 1.0,
        pong_timeout_seconds: float = 2.0,
        boot_probe: Optional[BootProbe] = None,
        notifier: Optional[Notifier] = None,
        metrics: Optional[Registry] = None,
    ) -> None:
        self.auth_validator = auth_validator
        self.libvirt_ctl = libvirt_ctl
        self.config = config or FsmConfig()
        self.ping_interval_seconds = ping_interval_seconds
        self.pong_timeout_seconds = pong_timeout_seconds
        self.boot_probe = boot_probe
        self.notifier = notifier
        # Defaults to the process-wide registry the management GetMetrics RPC
        # serves; tests inject a fresh one to avoid cross-test pollution.
        self.metrics = metrics or REGISTRY
        # Active per-Channel FSMs. AutopauseController / LifecycleCoordinator
        # call :meth:`suspend` / :meth:`resume` here to propagate to every
        # in-flight channel — a freshly-paused VM stops sending heartbeats,
        # so the FSM must already be in SUSPENDED before the pause lands or
        # missed pongs will escalate to false-positive HARD_DESTROY.
        self._active_fsms: List[HeartbeatFsm] = []
        self._suspended: bool = False

    @property
    def suspended(self) -> bool:
        """``True`` between :meth:`suspend` and :meth:`resume`. Newly-opened
        Channels inherit this state so a freshly-attached guest doesn't
        immediately tick its FSM toward DEGRADED while the VM is still
        paused."""
        return self._suspended

    def suspend(self) -> None:
        """Move every active FSM into SUSPENDED. Idempotent.

        Called from AutopauseController (idle-timeout pause) or
        LifecycleCoordinator (host suspend via D-Bus). Must precede the
        ``libvirt_ctl.suspend()`` call at the call site — see
        :mod:`crossdesk_host.lifecycle.coordinator` for the ordering.
        """
        if self._suspended:
            return
        self._suspended = True
        for fsm in self._active_fsms:
            fsm.suspend()
        logger.info(
            "heartbeat_suspend_propagated active_channels=%d",
            len(self._active_fsms),
        )

    def resume(self) -> None:
        """Move every active FSM out of SUSPENDED back into PROBING.

        FSMs re-enter through PROBING (not HEALTHY) so the next pongs
        have to demonstrate liveness — defends against the resume-and-
        immediately-launch race. Idempotent.
        """
        if not self._suspended:
            return
        self._suspended = False
        for fsm in self._active_fsms:
            fsm.resume()
        logger.info(
            "heartbeat_resume_propagated active_channels=%d",
            len(self._active_fsms),
        )

    async def _run_boot_probe(self, probe: BootProbe) -> None:
        timeout_s = self.config.boot_probe_timeout_seconds
        try:
            result = await asyncio.wait_for(probe(), timeout=timeout_s)
        except asyncio.TimeoutError:
            logger.warning(
                "heartbeat_boot_probe_timeout timeout_s=%.1f", timeout_s
            )
            return
        except Exception as exc:
            logger.warning("heartbeat_boot_probe_error error=%s", exc)
            return
        logger.info("heartbeat_boot_probe_result success=%s", bool(result))

    def _build_profile(self, out: TickOutput) -> heartbeat_pb2.AdaptiveProfile:
        return heartbeat_pb2.AdaptiveProfile(
            ewma_rtt=_ns_to_duration(out.ewma_rtt_ns),
            current_ping_interval=_seconds_to_duration(self.ping_interval_seconds),
            miss_threshold=_seconds_to_duration(self.pong_timeout_seconds),
            consecutive_miss_count=out.consecutive_miss_count,
            next_action=out.recovery_action,
            next_action_after=_seconds_to_duration(out.next_action_after_seconds),
        )

    async def _await_pong_or_timeout(
        self,
        request_iterator: AsyncIterator[heartbeat_pb2.GuestFrame],
        context: grpc.aio.ServicerContext,
        start_ns: int,
    ) -> "_FrameOutcome":
        """Wait for a guest frame; return the FSM's TickInput plus the frame's
        stream nonce.

        ``tick is None`` signals the channel should break out (client closed
        cleanly). Timeout → TickInput(pong_received=False). Unexpected payload
        → False with a structured log.

        The nonce rides along only so ``Channel`` can deregister it from the
        AuthValidator when the stream ends; a tick without a frame behind it
        (timeout, clean close) carries ``None``.
        """
        try:
            guest_frame = await asyncio.wait_for(
                request_iterator.__anext__(),
                timeout=self.pong_timeout_seconds,
            )
        except asyncio.TimeoutError:
            return _FrameOutcome(TickInput(pong_received=False), None)
        except StopAsyncIteration:
            logger.info("heartbeat_client_closed")
            return _FrameOutcome(None, None)

        await self.auth_validator.verify_auth_context(context, guest_frame.auth)
        nonce = guest_frame.auth.stream_nonce or None
        if guest_frame.WhichOneof("payload") == "pong":
            rtt_ns = time.monotonic_ns() - start_ns
            # The FSM folds this into an EWMA, which is the right input for
            # *deciding* liveness but throws the distribution away. Criterion N1.4
            # is stated as a p50, so the raw sample goes into the histogram too --
            # otherwise `crossdesk metrics` reports "no metrics registered" and the
            # budget is unmeasurable through the product's own instrumentation.
            self.metrics.histogram(MetricNames.HEARTBEAT_RTT_SECONDS).observe(
                rtt_ns / 1e9
            )
            return _FrameOutcome(
                TickInput(pong_received=True, rtt_ns=rtt_ns),
                nonce,
            )
        logger.info(
            "heartbeat_unexpected_payload kind=%s",
            guest_frame.WhichOneof("payload"),
        )
        return _FrameOutcome(TickInput(pong_received=False), nonce)

    def _track_state_transition(
        self,
        last_state: State,
        out: TickOutput,
        tracker: _MissedSleepTracker,
    ) -> None:
        """Log the transition and update the missed-PrepareForSleep
        heuristic tracker in place. No-op when ``out.state == last_state``.
        """
        if out.state == last_state:
            return
        logger.info(
            "heartbeat_state_transition from=%s to=%s miss=%d ewma_rtt_ns=%s",
            last_state.value,
            out.state.value,
            out.consecutive_miss_count,
            out.ewma_rtt_ns,
        )
        if last_state == State.HEALTHY and out.state != State.HEALTHY:
            tracker.healthy_left_at_ns = time.monotonic_ns()
            tracker.recovery_armed_during_outage = False
        if out.state in (State.SOFT_RECOVERY, State.HARD_DESTROY):
            tracker.recovery_armed_during_outage = True
        if out.state == State.HEALTHY and tracker.healthy_left_at_ns is not None:
            outage_s = (
                time.monotonic_ns() - tracker.healthy_left_at_ns
            ) / 1_000_000_000
            if (
                tracker.recovery_armed_during_outage
                and outage_s < tracker.threshold_seconds
            ):
                logger.warning(
                    "heartbeat_possible_missed_prepare_for_sleep "
                    "outage_s=%.1f hint=check_dbus_listener_subscription",
                    outage_s,
                )
            tracker.healthy_left_at_ns = None
            tracker.recovery_armed_during_outage = False

    async def _dispatch_recovery_action(self, out: TickOutput) -> bool:
        """Execute the FSM's prescribed recovery action.

        Returns ``True`` when the caller should break out of the channel
        loop (HARD_DESTROY recycles the domain; the current Channel
        terminates and the agent will reconnect when the new domain
        boots).

        The blocking libvirt calls run in a thread with a deadline so a
        hung domain can't stall the event loop.
        """
        if out.recovery_action == RecoveryAction.RECOVERY_ACTION_GRACEFUL_SHUTDOWN:
            logger.warning(
                "heartbeat_graceful_shutdown_dispatched attempt=%d backoff_s=%s",
                out.soft_attempts,
                out.next_action_after_seconds,
            )
            try:
                await libvirt_call(self.libvirt_ctl.graceful_shutdown)
            except asyncio.TimeoutError:
                logger.warning("heartbeat_graceful_shutdown_timeout")
                # The FSM escalates on continued misses — self-healing.
            return False
        if out.recovery_action == RecoveryAction.RECOVERY_ACTION_HARD_DESTROY:
            logger.critical("heartbeat_hard_destroy_dispatched")
            try:
                await libvirt_call(self.libvirt_ctl.hard_destroy)
            except asyncio.TimeoutError:
                logger.critical("heartbeat_hard_destroy_timeout")
                # Domain state unknown; break the channel anyway so the next
                # channel's FSM re-evaluates from scratch.
            if self.notifier is not None:
                notify_forced_stop(
                    self.notifier,
                    reason="Heartbeat watchdog exhausted soft "
                    "recovery attempts (HARD_DESTROY).",
                )
            return True
        return False

    async def Channel(
        self,
        request_iterator: AsyncIterator[heartbeat_pb2.GuestFrame],
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[heartbeat_pb2.HostFrame]:
        logger.info("heartbeat_channel_opened")

        fsm = HeartbeatFsm(self.config)
        # If the servicer is currently in suspended mode (autopause /
        # lifecycle decided so before this Channel attached), inherit the
        # state immediately — otherwise this fresh FSM would start
        # incrementing miss counts the moment the first ping times out.
        if self._suspended:
            fsm.suspend()
        self._active_fsms.append(fsm)
        seq = 1
        last_state: State = fsm.state
        probe_already_run = False
        tracker = _MissedSleepTracker()
        stream_nonce: Optional[bytes] = None

        try:
            while True:
                start_ns = time.monotonic_ns()
                yield heartbeat_pb2.HostFrame(
                    ping=heartbeat_pb2.Ping(
                        sequence=seq,
                        host_send_monotonic_ns=start_ns,
                    )
                )

                tick_in, frame_nonce = await self._await_pong_or_timeout(
                    request_iterator, context, start_ns
                )
                if stream_nonce is None:
                    stream_nonce = frame_nonce
                if tick_in is None:
                    break
                out = fsm.tick(tick_in)

                state_changed = out.state != last_state
                self._track_state_transition(last_state, out, tracker)
                last_state = out.state

                # First-time entry into PROBING: fire the optional
                # boot-probe so an asymmetric break (VSOCK listener
                # bound but guest agent hung) shows up in logs even
                # if heartbeat misses are still incrementing.
                if (
                    state_changed
                    and out.state == State.PROBING
                    and self.boot_probe is not None
                    and not probe_already_run
                ):
                    probe_already_run = True
                    asyncio.create_task(self._run_boot_probe(self.boot_probe))

                # AdaptiveProfile broadcast: emit BEFORE any libvirt action so
                # a supervisor (or the guest itself) can observe the impending
                # recovery and react. Also emit on state changes as advisory
                # hints; skip plain HEALTHY ticks to avoid wire churn.
                if (
                    state_changed
                    or out.recovery_action != RecoveryAction.RECOVERY_ACTION_NONE
                ):
                    yield heartbeat_pb2.HostFrame(
                        profile_update=self._build_profile(out)
                    )

                if await self._dispatch_recovery_action(out):
                    break

                seq += 1
                await asyncio.sleep(self.ping_interval_seconds)

        except grpc.RpcError as e:
            logger.error("heartbeat_rpc_error error=%s", e)
        finally:
            # Identity removal: HeartbeatFsm is a dataclass so equality
            # alone could match a sibling channel's freshly-built FSM.
            self._active_fsms = [
                existing for existing in self._active_fsms if existing is not fsm
            ]
            # Deregister the stream nonce, as the control plane does. Without
            # it the validator's per-stream sequence map grows by one entry per
            # reconnect and never shrinks — and the guest reconnects routinely
            # (agent re-dial, VM recovery), so it is a slow leak for the life
            # of the daemon rather than a rare one.
            if stream_nonce is not None:
                self.auth_validator.remove_stream(stream_nonce)
