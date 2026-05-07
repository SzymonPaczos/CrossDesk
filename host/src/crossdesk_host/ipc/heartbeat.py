import logging
import asyncio
import time
from typing import AsyncIterator
import grpc

from crossdesk_host.proto.crossdesk.v1 import heartbeat_pb2
from crossdesk_host.proto.crossdesk.v1 import heartbeat_pb2_grpc
from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.ipc.auth import AuthValidator

logger = logging.getLogger(__name__)

class HeartbeatServiceServicer(heartbeat_pb2_grpc.HeartbeatServiceServicer):
    def __init__(self, auth_validator: AuthValidator, libvirt_ctl: LibvirtController):
        self.auth_validator = auth_validator
        self.libvirt_ctl = libvirt_ctl

    async def Channel(self, request_iterator: AsyncIterator[heartbeat_pb2.GuestFrame], context: grpc.aio.ServicerContext) -> AsyncIterator[heartbeat_pb2.HostFrame]:
        logger.info("Heartbeat Channel opened.")

        state = "HEALTHY"
        miss_count = 0
        miss_threshold = 3
        seq = 1
        try:
            while True:
                start_ns = time.monotonic_ns()
                
                # Wysyłamy PING
                yield heartbeat_pb2.HostFrame(
                    ping=heartbeat_pb2.Ping(
                        sequence=seq,
                        host_send_monotonic_ns=start_ns,
                    )
                )
                
                # Oczekujemy PONG
                try:
                    # Timeout 2 sekundy na Ping
                    guest_frame = await asyncio.wait_for(request_iterator.__anext__(), timeout=2.0)
                    await self.auth_validator.verify_auth_context(context, guest_frame.auth)
                    
                    if guest_frame.WhichOneof('payload') == 'pong':
                        rtt_ns = time.monotonic_ns() - start_ns
                        logger.debug(f"Received Pong seq={seq}, RTT={rtt_ns / 1_000_000:.2f}ms")
                        
                        if state != "HEALTHY":
                            logger.info(f"Recovered from {state} to HEALTHY")
                            state = "HEALTHY"
                            miss_count = 0
                    else:
                        logger.warning("Expected pong, got different frame")
                        
                except asyncio.TimeoutError:
                    miss_count += 1
                    logger.warning(f"Missed heartbeat! Count: {miss_count}")
                    
                    if state == "SOFT_RECOVERY" and miss_count > miss_threshold + 5:
                        logger.critical("Guest completely dead. Initiating HARD_DESTROY")
                        self.libvirt_ctl.hard_destroy()
                        break
                    elif state == "PROBING" and miss_count > miss_threshold + 2:
                        logger.error("Guest unresponsive. Transitioning to SOFT_RECOVERY")
                        state = "SOFT_RECOVERY"
                        self.libvirt_ctl.graceful_shutdown()
                    elif state == "DEGRADED" and miss_count > miss_threshold:
                        state = "PROBING"
                    elif state == "HEALTHY":
                        state = "DEGRADED"
                        
                except StopAsyncIteration:
                    logger.info("Client closed heartbeat channel")
                    break
                    
                seq += 1
                await asyncio.sleep(1.0) # Ping interval
                
        except grpc.RpcError as e:
            logger.error(f"Heartbeat RPC Error: {e}")
