import logging
from typing import AsyncIterator, Optional

import grpc

from crossdesk_host.display.rail_manager import RailManager
from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.proto.crossdesk.v1 import control_pb2, control_pb2_grpc

logger = logging.getLogger(__name__)


class ControlServiceServicer(control_pb2_grpc.ControlServiceServicer):
    def __init__(self, auth_validator: AuthValidator, rail_manager: Optional[RailManager] = None) -> None:
        self.auth_validator = auth_validator
        self.rail_manager = rail_manager if rail_manager is not None else RailManager()

    async def OpenSession(
        self,
        request_iterator: AsyncIterator[control_pb2.ClientFrame],
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[control_pb2.ServerFrame]:
        peer_identity = context.peer()
        logger.info(f"New ControlSession stream initiated from {peer_identity}")

        state = "HANDSHAKE"
        stream_nonce: Optional[bytes] = None

        try:
            async for client_frame in request_iterator:
                await self.auth_validator.verify_auth_context(context, client_frame.auth)
                if stream_nonce is None:
                    stream_nonce = client_frame.auth.stream_nonce

                payload_type = client_frame.WhichOneof('payload')

                if state == "HANDSHAKE":
                    if payload_type == "hello":
                        state = "AUTHENTICATED"
                        logger.info(f"Received ClientHello: {client_frame.hello}")

                        # Zbuduj ServerAccept
                        yield control_pb2.ServerFrame(
                            accept=control_pb2.ServerAccept(
                                guest_version="v0.1.0",
                                negotiated_features=["rail.v1"],
                                guest_smbios_uuid="fake-uuid-dry-run",
                            )
                        )
                        state = "READY"
                        logger.info("Session state: READY")
                    else:
                        await context.abort(
                            grpc.StatusCode.FAILED_PRECONDITION,
                            f"Expected ClientHello, got {payload_type}",
                        )
                
                elif state == "READY" or state == "APP_RUNNING":
                    if payload_type == "launch":
                        logger.info(f"AppLaunchRequest: {client_frame.launch.executable_guest_path}")
                        # Tutaj wywołalibyśmy faktyczną logikę uruchamiania procesu
                        
                        yield control_pb2.ServerFrame(
                            launched=control_pb2.AppLaunched(
                                request_id=client_frame.launch.request_id,
                                process_id=9999,
                            )
                        )
                        state = "APP_RUNNING"
                        
                    elif payload_type == "rail_event":
                        self.rail_manager.handle_rail_event(client_frame.rail_event)
                        
                    elif payload_type == "terminate":
                        logger.info("SessionTerminate requested by Guest.")
                        state = "DRAINING"
                        yield control_pb2.ServerFrame(
                            closed=control_pb2.SessionClosed(
                                reason=control_pb2.SessionTerminate.Reason.REASON_USER_QUIT,
                                detail="Acknowledged",
                            )
                        )
                        break
                    
                    else:
                        logger.warning(f"Unhandled payload in {state}: {payload_type}")

        except grpc.RpcError as e:
            logger.error(f"RPC Error in OpenSession: {e}")
        finally:
            if stream_nonce is not None:
                self.auth_validator.remove_stream(stream_nonce)
            logger.info("ControlSession stream closed.")
