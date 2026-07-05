import asyncio
import contextlib
import logging
from typing import AsyncIterator, Callable, List, Optional

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
# Wire-protocol major version. Bumped only on incompatible frame-layout
# changes. Both sides reject a connection when the major digits differ.
CROSSDESK_PROTOCOL_VERSION = "1"
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
        on_agent_version: Optional[Callable[[str], None]] = None,
        on_session_ready: Optional[Callable[[], None]] = None,
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
        # Called once per successful handshake with the agent's version string
        # (from ClientHello.host_version). MgmtState hooks this to keep
        # StatusFrame.agent_version fresh without the servicer needing to
        # import the management module.
        self.on_agent_version = on_agent_version
        # Fired each time a handshake reaches READY. The daemon hooks this to
        # run the post-install steady-state finalize (redefine the domain so a
        # later hard_destroy can't reboot the install ISO — see
        # installer.steady_state). Idempotent + retrying on the callee side, so
        # firing on every reconnect is fine.
        self.on_session_ready = on_session_ready

    async def _handle_hello(
        self,
        hello: control_pb2.ClientHello,
        outbound: "asyncio.Queue[Optional[control_pb2.ServerFrame]]",
        context: grpc.aio.ServicerContext,
    ) -> bool:
        """Validate ClientHello and emit ServerAccept or reject.

        Returns True when the handshake was accepted (caller transitions
        to READY). Returns False after pushing an AuthFailure frame and
        calling ``context.abort()`` — the caller's stream will terminate.
        """
        # Wire-protocol major version first. A major mismatch means the
        # frame layout itself may be incompatible; reject before semver.
        if hello.protocol_version and hello.protocol_version[0] != CROSSDESK_PROTOCOL_VERSION[0]:
            reason = (
                f"protocol major mismatch: agent sent {hello.protocol_version!r}, "
                f"host speaks {CROSSDESK_PROTOCOL_VERSION!r}"
            )
            await self._reject_hello(outbound, context, reason)
            return False

        compat = is_compatible(hello.host_version, self.host_version)
        if not compat.accepted:
            logger.warning(
                "ControlService Hello rejected: %s (client_says=%s, host_actual=%s)",
                compat.reason,
                hello.host_version,
                self.host_version,
            )
            await self._reject_hello(outbound, context, compat.reason)
            return False

        negotiated = negotiate_features(
            self.supported_features, hello.supported_features
        )
        logger.info(
            "ControlService Hello accepted: client_says=%s host=%s "
            "protocol_version=%s features=%s",
            hello.host_version,
            self.host_version,
            hello.protocol_version or "(not sent)",
            negotiated,
        )
        if self.on_agent_version is not None:
            self.on_agent_version(hello.host_version)
        await outbound.put(
            control_pb2.ServerFrame(
                accept=control_pb2.ServerAccept(
                    guest_version=self.host_version,
                    negotiated_features=negotiated,
                    guest_smbios_uuid=hello.host_domain_uuid,
                    protocol_version=CROSSDESK_PROTOCOL_VERSION,
                )
            )
        )
        return True

    async def _reject_hello(
        self,
        outbound: "asyncio.Queue[Optional[control_pb2.ServerFrame]]",
        context: grpc.aio.ServicerContext,
        reason: str,
    ) -> None:
        """Common rejection path: emit AuthFailure frame + abort context."""
        logger.warning("ControlService Hello rejected: %s", reason)
        await outbound.put(
            control_pb2.ServerFrame(
                auth_failure=control_pb2.AuthFailure(
                    code=control_pb2.AuthFailure.Code.CODE_FEATURE_NEGOTIATION_FAILED,
                    detail=reason,
                )
            )
        )
        await context.abort(
            grpc.StatusCode.FAILED_PRECONDITION,
            f"version incompatible: {reason}",
        )

    async def _handle_launch(
        self,
        launch: control_pb2.AppLaunchRequest,
        outbound: "asyncio.Queue[Optional[control_pb2.ServerFrame]]",
    ) -> None:
        """Acknowledge an AppLaunchRequest with a stub AppLaunched frame.

        Real PID allocation lands when Phase 4 wires the RAIL session to
        a real FreeRDP spawn — until then 9999 is a placeholder that
        keeps the proto contract honest.
        """
        logger.info(f"AppLaunchRequest: {launch.executable_guest_path}")
        await outbound.put(
            control_pb2.ServerFrame(
                launched=control_pb2.AppLaunched(
                    request_id=launch.request_id,
                    process_id=9999,
                )
            )
        )

    def _handle_verify_credentials_result(
        self,
        result: control_pb2.VerifyCredentialsResult,
    ) -> None:
        """Route the agent's verify-credentials response to the coordinator.

        Logs a warning when no coordinator is wired so the result isn't
        silently dropped — that would manifest as a stuck rail-launch
        gate downstream.
        """
        if self.verify_coordinator is not None:
            self.verify_coordinator.deliver(result)
        else:
            logger.warning(
                "Got verify_credentials_result with no coordinator wired; "
                "request_id=%s",
                result.request_id,
            )

    async def _handle_terminate(
        self,
        outbound: "asyncio.Queue[Optional[control_pb2.ServerFrame]]",
    ) -> None:
        """Acknowledge a SessionTerminate by emitting SessionClosed."""
        logger.info("SessionTerminate requested by Guest.")
        await outbound.put(
            control_pb2.ServerFrame(
                closed=control_pb2.SessionClosed(
                    reason=control_pb2.SessionTerminate.Reason.REASON_USER_QUIT,
                    detail="Acknowledged",
                )
            )
        )

    async def _dispatch_frame(
        self,
        client_frame: control_pb2.ClientFrame,
        outbound: "asyncio.Queue[Optional[control_pb2.ServerFrame]]",
        context: grpc.aio.ServicerContext,
        state: str,
    ) -> str:
        """Route a single ClientFrame to the right handler based on state.

        Returns the new state. Raises via ``context.abort()`` only on
        protocol violations (HANDSHAKE expected ClientHello, got X).
        Terminates the loop by setting state to ``"DRAINING"``.
        """
        payload_type = client_frame.WhichOneof("payload")

        if state == "HANDSHAKE":
            if payload_type != "hello":
                await context.abort(
                    grpc.StatusCode.FAILED_PRECONDITION,
                    f"Expected ClientHello, got {payload_type}",
                )
            if await self._handle_hello(client_frame.hello, outbound, context):
                logger.info("Session state: READY")
                if self.verify_coordinator is not None:
                    self.verify_coordinator.register_session(outbound)
                if self.on_session_ready is not None:
                    self.on_session_ready()
                return "READY"
            return state

        if payload_type == "launch":
            await self._handle_launch(client_frame.launch, outbound)
            return "APP_RUNNING"
        if payload_type == "rail_event":
            self.rail_manager.handle_rail_event(client_frame.rail_event)
            return state
        if payload_type == "verify_credentials_result":
            self._handle_verify_credentials_result(
                client_frame.verify_credentials_result
            )
            return state
        if payload_type == "terminate":
            await self._handle_terminate(outbound)
            return "DRAINING"

        logger.warning(f"Unhandled payload in {state}: {payload_type}")
        return state

    async def _consume_session(
        self,
        request_iterator: AsyncIterator[control_pb2.ClientFrame],
        outbound: "asyncio.Queue[Optional[control_pb2.ServerFrame]]",
        context: grpc.aio.ServicerContext,
    ) -> None:
        """Drain ClientFrames from the agent and dispatch them.

        Outermost loop over the request iterator. Each frame's
        AuthContext is verified, then dispatched via _dispatch_frame.
        The finally block guarantees cleanup of stream nonce + verify
        coordinator registration, and signals the outbound generator
        to exit via the ``None`` sentinel.
        """
        state = "HANDSHAKE"
        stream_nonce: Optional[bytes] = None
        registered_outbound = False
        try:
            async for client_frame in request_iterator:
                await self.auth_validator.verify_auth_context(
                    context, client_frame.auth
                )
                if stream_nonce is None:
                    stream_nonce = client_frame.auth.stream_nonce

                previous_state = state
                state = await self._dispatch_frame(
                    client_frame, outbound, context, state
                )
                if previous_state == "HANDSHAKE" and state == "READY":
                    registered_outbound = self.verify_coordinator is not None
                if state == "DRAINING":
                    return
        except grpc.RpcError as e:
            logger.error(f"RPC Error in OpenSession consume: {e}")
        finally:
            if stream_nonce is not None:
                self.auth_validator.remove_stream(stream_nonce)
            if registered_outbound and self.verify_coordinator is not None:
                self.verify_coordinator.unregister_session(outbound)
            # Wake up the main loop so it exits cleanly.
            await outbound.put(None)

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
        consume_task = asyncio.create_task(
            self._consume_session(request_iterator, outbound, context)
        )
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
