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
from typing import AsyncIterator, Awaitable, Callable, Optional

import grpc
from google.protobuf import duration_pb2

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.lifecycle.error_notifications import notify_forced_stop
from crossdesk_host.lifecycle.notifications import Notifier
from crossdesk_host.proto.crossdesk.v1 import heartbeat_pb2, heartbeat_pb2_grpc
from crossdesk_host.watchdog import (
    FsmConfig,
    HeartbeatFsm,
    RecoveryAction,
    State,
    TickInput,
    TickOutput,
)

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
    ) -> None:
        self.auth_validator = auth_validator
        self.libvirt_ctl = libvirt_ctl
        self.config = config or FsmConfig()
        self.ping_interval_seconds = ping_interval_seconds
        self.pong_timeout_seconds = pong_timeout_seconds
        self.boot_probe = boot_probe
        self.notifier = notifier

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

    async def Channel(
        self,
        request_iterator: AsyncIterator[heartbeat_pb2.GuestFrame],
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[heartbeat_pb2.HostFrame]:
        logger.info("heartbeat_channel_opened")

        fsm = HeartbeatFsm(self.config)
        seq = 1
        last_state: State = fsm.state
        probe_already_run = False
        # Missed-PrepareForSleep heuristic state (FOLLOWUPS:677):
        # remembers wall-clock-equivalent monotonic when we last left
        # HEALTHY and whether the FSM armed a recovery action during
        # the outage. A fast HEALTHY → recovery-armed → HEALTHY round
        # trip means the host very likely suspended without firing a
        # PrepareForSleep D-Bus signal — the FSM did the right thing
        # but the warning lets operators fix the missing subscription.
        healthy_left_at_ns: Optional[int] = None
        recovery_armed_during_outage = False
        missed_sleep_threshold_seconds = 30.0

        try:
            while True:
                start_ns = time.monotonic_ns()
                yield heartbeat_pb2.HostFrame(
                    ping=heartbeat_pb2.Ping(
                        sequence=seq,
                        host_send_monotonic_ns=start_ns,
                    )
                )

                try:
                    guest_frame = await asyncio.wait_for(
                        request_iterator.__anext__(),
                        timeout=self.pong_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    out = fsm.tick(TickInput(pong_received=False))
                except StopAsyncIteration:
                    logger.info("heartbeat_client_closed")
                    break
                else:
                    await self.auth_validator.verify_auth_context(
                        context, guest_frame.auth
                    )
                    if guest_frame.WhichOneof("payload") == "pong":
                        rtt_ns = time.monotonic_ns() - start_ns
                        out = fsm.tick(TickInput(pong_received=True, rtt_ns=rtt_ns))
                    else:
                        logger.info(
                            "heartbeat_unexpected_payload kind=%s",
                            guest_frame.WhichOneof("payload"),
                        )
                        out = fsm.tick(TickInput(pong_received=False))

                state_changed = out.state != last_state
                if state_changed:
                    logger.info(
                        "heartbeat_state_transition from=%s to=%s miss=%d ewma_rtt_ns=%s",
                        last_state.value,
                        out.state.value,
                        out.consecutive_miss_count,
                        out.ewma_rtt_ns,
                    )
                    # Missed-PrepareForSleep tracker: stamp wall-clock
                    # on HEALTHY exit; clear it (and warn) on return
                    # to HEALTHY if recovery was armed during the
                    # outage AND the round trip was fast.
                    if last_state == State.HEALTHY and out.state != State.HEALTHY:
                        healthy_left_at_ns = time.monotonic_ns()
                        recovery_armed_during_outage = False
                    if out.state in (
                        State.SOFT_RECOVERY,
                        State.HARD_DESTROY,
                    ):
                        recovery_armed_during_outage = True
                    if (
                        out.state == State.HEALTHY
                        and healthy_left_at_ns is not None
                    ):
                        outage_s = (
                            time.monotonic_ns() - healthy_left_at_ns
                        ) / 1_000_000_000
                        if (
                            recovery_armed_during_outage
                            and outage_s < missed_sleep_threshold_seconds
                        ):
                            logger.warning(
                                "heartbeat_possible_missed_prepare_for_sleep "
                                "outage_s=%.1f hint=check_dbus_listener_subscription",
                                outage_s,
                            )
                        healthy_left_at_ns = None
                        recovery_armed_during_outage = False
                    last_state = out.state
                    # First-time entry into PROBING: fire the optional
                    # boot-probe so an asymmetric break (VSOCK listener
                    # bound but guest agent hung) shows up in logs even
                    # if heartbeat misses are still incrementing.
                    if (
                        out.state == State.PROBING
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

                if (
                    out.recovery_action
                    == RecoveryAction.RECOVERY_ACTION_GRACEFUL_SHUTDOWN
                ):
                    logger.warning(
                        "heartbeat_graceful_shutdown_dispatched attempt=%d backoff_s=%s",
                        out.soft_attempts,
                        out.next_action_after_seconds,
                    )
                    self.libvirt_ctl.graceful_shutdown()
                elif out.recovery_action == RecoveryAction.RECOVERY_ACTION_HARD_DESTROY:
                    logger.critical("heartbeat_hard_destroy_dispatched")
                    self.libvirt_ctl.hard_destroy()
                    if self.notifier is not None:
                        notify_forced_stop(
                            self.notifier,
                            reason="Heartbeat watchdog exhausted soft "
                            "recovery attempts (HARD_DESTROY).",
                        )
                    break

                seq += 1
                await asyncio.sleep(self.ping_interval_seconds)

        except grpc.RpcError as e:
            logger.error("heartbeat_rpc_error error=%s", e)
