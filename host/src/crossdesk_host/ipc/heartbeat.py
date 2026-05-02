import logging
import asyncio
import time
from typing import AsyncIterable
import grpc

from crossdesk_host.proto.crossdesk.v1 import heartbeat_pb2
from crossdesk_host.proto.crossdesk.v1 import heartbeat_pb2_grpc
from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock

logger = logging.getLogger(__name__)

class HeartbeatServiceServicer(heartbeat_pb2_grpc.HeartbeatServiceServicer):
    def __init__(self, auth_validator: AuthValidator, libvirt_ctl: LibvirtControllerMock):
        self.auth_validator = auth_validator
        self.libvirt_ctl = libvirt_ctl

    async def Channel(self, request_iterator: AsyncIterable[heartbeat_pb2.GuestFrame], context: grpc.aio.ServicerContext) -> AsyncIterable[heartbeat_pb2.HostFrame]:
        logger.info("Heartbeat Channel opened.")
        
        # State machine
        state = "HEALTHY"
        miss_count = 0
        miss_threshold = 3
        
        # Pętla nasłuchująca Pongów z Guesta (uruchomiona w tle na tym strumieniu asynchronicznym)
        # Główne wyzwanie z gRPC bidirectional to wysyłanie asynchronicznych Pingów i czytanie Pongów 
        # w tym samym context managerze. Najprostszą implementacją w Pythonie z `yield` jest wrzucenie 
        # Pingów do kolejki, a czytanie z iteratora, co wymaga sprytnego użycia asyncio.
        
        # Ze względu na uproszczenie w fazie POC, zrealizujemy generator w sposób, w którym 
        # Host wysyła pinga, a zaraz po tym wymusza await na `request_iterator.__anext__()` 
        # (wzorzec lockstep). Dla pełnego duplexu używa się osobnego taska pushującego do Queue.
        
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
                    
                    if state == "HEALTHY":
                        state = "DEGRADED"
                    elif state == "DEGRADED" and miss_count > miss_threshold:
                        state = "PROBING"
                        
                    if state == "PROBING" and miss_count > miss_threshold + 2:
                        logger.error("Guest unresponsive. Transitioning to SOFT_RECOVERY")
                        state = "SOFT_RECOVERY"
                        self.libvirt_ctl.graceful_shutdown()
                        
                    if state == "SOFT_RECOVERY" and miss_count > miss_threshold + 5:
                        logger.critical("Guest completely dead. Initiating HARD_DESTROY")
                        self.libvirt_ctl.hard_destroy()
                        break
                        
                except StopAsyncIteration:
                    logger.info("Client closed heartbeat channel")
                    break
                    
                seq += 1
                await asyncio.sleep(1.0) # Ping interval
                
        except grpc.RpcError as e:
            logger.error(f"Heartbeat RPC Error: {e}")
