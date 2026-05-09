"""HeartbeatService gRPC servicer.

Stage 2 of the Phase 3 watchdog: the servicer no longer carries its own
inline state machine. Each pong (or timeout) feeds ``HeartbeatFsm.tick``
and the FSM emits the next state plus an advisory ``RecoveryAction``
that the servicer dispatches against ``LibvirtController``.

What lives here vs. in ``crossdesk_host/watchdog/``: the FSM module is
purely synchronous and has no I/O; this servicer owns the asyncio
plumbing — sending pings, awaiting pongs with a timeout, calling
``libvirt_ctl.graceful_shutdown``/``hard_destroy`` when the FSM emits
the corresponding ``RecoveryAction``. ``AdaptiveProfile`` broadcast
back to the guest is queued for Stage 3 (Week 6).
"""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, Optional

import grpc

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.observability.log import get_logger
from crossdesk_host.proto.crossdesk.v1 import heartbeat_pb2, heartbeat_pb2_grpc
from crossdesk_host.watchdog import (
    FsmConfig,
    HeartbeatFsm,
    RecoveryAction,
    State,
    TickInput,
)

logger = get_logger("host.ipc.heartbeat")


class HeartbeatServiceServicer(heartbeat_pb2_grpc.HeartbeatServiceServicer):
    def __init__(
        self,
        auth_validator: AuthValidator,
        libvirt_ctl: LibvirtController,
        config: Optional[FsmConfig] = None,
        ping_interval_seconds: float = 1.0,
        pong_timeout_seconds: float = 2.0,
    ) -> None:
        self.auth_validator = auth_validator
        self.libvirt_ctl = libvirt_ctl
        self.config = config or FsmConfig()
        self.ping_interval_seconds = ping_interval_seconds
        self.pong_timeout_seconds = pong_timeout_seconds

    async def Channel(
        self,
        request_iterator: AsyncIterator[heartbeat_pb2.GuestFrame],
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[heartbeat_pb2.HostFrame]:
        logger.info("heartbeat_channel_opened")

        fsm = HeartbeatFsm(self.config)
        seq = 1
        last_state: State = fsm.state

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
                        # GuestSignal arrived in place of a Pong — counts as
                        # a missed measurement window; the signal kind is
                        # logged but doesn't bypass the FSM.
                        logger.info(
                            "heartbeat_unexpected_payload",
                            kind=guest_frame.WhichOneof("payload"),
                        )
                        out = fsm.tick(TickInput(pong_received=False))

                if out.state != last_state:
                    logger.info(
                        "heartbeat_state_transition",
                        from_state=last_state.value,
                        to_state=out.state.value,
                        miss_count=out.consecutive_miss_count,
                        ewma_rtt_ns=out.ewma_rtt_ns,
                    )
                    last_state = out.state

                if (
                    out.recovery_action
                    == RecoveryAction.RECOVERY_ACTION_GRACEFUL_SHUTDOWN
                ):
                    logger.warning(
                        "heartbeat_graceful_shutdown_dispatched",
                        attempt=out.soft_attempts,
                        backoff_seconds=out.next_action_after_seconds,
                    )
                    self.libvirt_ctl.graceful_shutdown()
                elif out.recovery_action == RecoveryAction.RECOVERY_ACTION_HARD_DESTROY:
                    logger.critical("heartbeat_hard_destroy_dispatched")
                    self.libvirt_ctl.hard_destroy()
                    break

                seq += 1
                await asyncio.sleep(self.ping_interval_seconds)

        except grpc.RpcError as e:
            logger.error("heartbeat_rpc_error", error=str(e))
