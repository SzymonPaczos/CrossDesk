import asyncio
import contextlib
import logging
from typing import AsyncIterator, List, Optional

import grpc

from crossdesk_host.display.rail_manager import RailManager
from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.ipc.verify_coordinator import VerifyCoordinator
from crossdesk_host.ipc.version_negotiation import (
    is_compatible,
    negotiate_features,
)
from crossdesk_host.proto.crossdesk.v1 import control_pb2, control_pb2_grpc

logger = logging.getLogger(__name__)

HOST_VERSION = "v0.1.0"
# Feature flags the host advertises. The negotiation step intersects
# this with what the client claims and the result lands in
# ``ServerAccept.negotiated_features``.
HOST_SUPPORTED_FEATURES: List[str] = ["rail.v1", "virtiofs.jit"]


class ControlServiceServicer(control_pb2_grpc.ControlServiceServicer):
    def __init__(
        self,
        auth_validator: AuthValidator,
        rail_manager: Optional[RailManager] = None,
        host_version: str = HOST_VERSION,
        supported_features: Optional[List[str]] = None,
        verify_coordinator: Optional[VerifyCoordinator] = None,
    ) -> None:
        self.auth_validator = auth_validator
        self.rail_manager = rail_manager if rail_manager is not None else RailManager()
        self.host_version = host_version
        self.supported_features = (
            list(supported_features)
            if supported_features is not None
            else list(HOST_SUPPORTED_FEATURES)
        )
        self.verify_coordinator = verify_coordinator

    async def OpenSession(
        self,
        request_iterator: AsyncIterator[control_pb2.ClientFrame],
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[control_pb2.ServerFrame]:
        peer_identity = context.peer()
        logger.info(f"New ControlSession stream initiated from {peer_identity}")

        # Outbound queue lets the consume task and any external caller
        # (VerifyCoordinator) push ServerFrames; this generator drains
        # the queue and yields them on the wire. ``None`` is the close
        # sentinel — both the consume task's finally block and the
        # terminate handler push it so the generator exits cleanly.
        outbound: asyncio.Queue[Optional[control_pb2.ServerFrame]] = asyncio.Queue()
        registered = False

        async def consume() -> None:
            nonlocal registered
            state = "HANDSHAKE"
            stream_nonce: Optional[bytes] = None
            try:
                async for client_frame in request_iterator:
                    await self.auth_validator.verify_auth_context(
                        context, client_frame.auth
                    )
                    if stream_nonce is None:
                        stream_nonce = client_frame.auth.stream_nonce

                    payload_type = client_frame.WhichOneof("payload")

                    if state == "HANDSHAKE":
                        if payload_type == "hello":
                            hello = client_frame.hello
                            compat = is_compatible(hello.host_version, self.host_version)
                            if not compat.accepted:
                                logger.warning(
                                    "ControlService Hello rejected: %s "
                                    "(client_says=%s, host_actual=%s)",
                                    compat.reason,
                                    hello.host_version,
                                    self.host_version,
                                )
                                await outbound.put(
                                    control_pb2.ServerFrame(
                                        auth_failure=control_pb2.AuthFailure(
                                            code=control_pb2.AuthFailure.Code.CODE_FEATURE_NEGOTIATION_FAILED,
                                            detail=compat.reason,
                                        )
                                    )
                                )
                                await context.abort(
                                    grpc.StatusCode.FAILED_PRECONDITION,
                                    f"version incompatible: {compat.reason}",
                                )
                            negotiated = negotiate_features(
                                self.supported_features, hello.supported_features
                            )
                            logger.info(
                                "ControlService Hello accepted: client_says=%s host=%s features=%s",
                                hello.host_version,
                                self.host_version,
                                negotiated,
                            )
                            await outbound.put(
                                control_pb2.ServerFrame(
                                    accept=control_pb2.ServerAccept(
                                        guest_version=self.host_version,
                                        negotiated_features=negotiated,
                                        guest_smbios_uuid=hello.host_domain_uuid,
                                    )
                                )
                            )
                            state = "READY"
                            logger.info("Session state: READY")
                            if self.verify_coordinator is not None:
                                self.verify_coordinator.register_session(outbound)
                                registered = True
                        else:
                            await context.abort(
                                grpc.StatusCode.FAILED_PRECONDITION,
                                f"Expected ClientHello, got {payload_type}",
                            )

                    elif state == "READY" or state == "APP_RUNNING":
                        if payload_type == "launch":
                            logger.info(
                                f"AppLaunchRequest: {client_frame.launch.executable_guest_path}"
                            )
                            await outbound.put(
                                control_pb2.ServerFrame(
                                    launched=control_pb2.AppLaunched(
                                        request_id=client_frame.launch.request_id,
                                        process_id=9999,
                                    )
                                )
                            )
                            state = "APP_RUNNING"

                        elif payload_type == "rail_event":
                            self.rail_manager.handle_rail_event(client_frame.rail_event)

                        elif payload_type == "verify_credentials_result":
                            if self.verify_coordinator is not None:
                                self.verify_coordinator.deliver(
                                    client_frame.verify_credentials_result
                                )
                            else:
                                logger.warning(
                                    "Got verify_credentials_result with no coordinator wired; "
                                    "request_id=%s",
                                    client_frame.verify_credentials_result.request_id,
                                )

                        elif payload_type == "terminate":
                            logger.info("SessionTerminate requested by Guest.")
                            state = "DRAINING"
                            await outbound.put(
                                control_pb2.ServerFrame(
                                    closed=control_pb2.SessionClosed(
                                        reason=control_pb2.SessionTerminate.Reason.REASON_USER_QUIT,
                                        detail="Acknowledged",
                                    )
                                )
                            )
                            return

                        else:
                            logger.warning(f"Unhandled payload in {state}: {payload_type}")
            except grpc.RpcError as e:
                logger.error(f"RPC Error in OpenSession consume: {e}")
            finally:
                if stream_nonce is not None:
                    self.auth_validator.remove_stream(stream_nonce)
                if registered and self.verify_coordinator is not None:
                    self.verify_coordinator.unregister_session(outbound)
                # Wake up the main loop so it exits cleanly.
                await outbound.put(None)

        consume_task = asyncio.create_task(consume())
        try:
            while True:
                frame = await outbound.get()
                if frame is None:
                    break
                yield frame
        finally:
            consume_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await consume_task
            logger.info("ControlSession stream closed.")
