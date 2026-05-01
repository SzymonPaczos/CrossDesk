import logging
import asyncio
from typing import AsyncIterable, Optional, Dict
import time
import uuid

import grpc
from crossdesk_host.proto.crossdesk.v1 import filesystem_pb2
from crossdesk_host.proto.crossdesk.v1 import filesystem_pb2_grpc
from crossdesk_host.proto.crossdesk.v1 import common_pb2
from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from google.protobuf.duration_pb2 import Duration

logger = logging.getLogger(__name__)

class FilesystemServiceServicer(filesystem_pb2_grpc.FilesystemServiceServicer):
    """
    Obsługa maszyny stanów cyklu życia dysków JIT VirtioFS.
    """
    def __init__(self, auth_validator: AuthValidator, libvirt_ctl: LibvirtControllerMock):
        self.auth_validator = auth_validator
        self.libvirt_ctl = libvirt_ctl
        self.command_queue: asyncio.Queue[filesystem_pb2.ShareHostFrame] = asyncio.Queue()
        self.active_shares: Dict[str, str] = {} # share_id -> state

    async def _producer_task(self, context: grpc.aio.ServicerContext) -> AsyncIterable[filesystem_pb2.ShareHostFrame]:
        """Czyta z kolejki komend i wysyła do Guesta."""
        try:
            while not context.core_context.aborted():
                frame = await self.command_queue.get()
                yield frame
        except asyncio.CancelledError:
            pass

    async def ShareChannel(self, request_iterator: AsyncIterable[filesystem_pb2.ShareGuestFrame], context: grpc.aio.ServicerContext) -> AsyncIterable[filesystem_pb2.ShareHostFrame]:
        peer_identity = context.peer()
        logger.info(f"[{peer_identity}] Filesystem channel established")

        # Uruchamiamy task produkujący ramki z kolejki
        import collections
        
        # Generator asynchroniczny z queue
        async def yield_from_queue():
            while True:
                # Polling queue with cancellation check
                get_task = asyncio.create_task(self.command_queue.get())
                done, pending = await asyncio.wait(
                    [get_task], timeout=1.0, return_when=asyncio.FIRST_COMPLETED
                )
                if get_task in done:
                    yield get_task.result()
                if context.core_context.aborted():
                    if get_task in pending:
                        get_task.cancel()
                    break

        producer_gen = yield_from_queue()
        
        # W celu odbierania i odpowiadania równolegle użyjemy asyncio.gather/create_task
        # lub po prostu odpowiadamy yield z pętli. Pętla w python grpc może yieldować
        # bezpośrednio.
        
        async def consume_incoming():
            async for frame in request_iterator:
                payload_type = frame.WhichOneof("payload")
                
                if payload_type == "mount_result":
                    res = frame.mount_result
                    logger.info(f"[Filesystem] MountResult for share {res.share_id}: {res.status}")
                    if res.status == filesystem_pb2.MountResult.Status.STATUS_MOUNTED:
                        self.active_shares[res.share_id] = "MOUNTED"

                elif payload_type == "lock_report":
                    rep = frame.lock_report
                    logger.debug(f"[Filesystem] LockReport for share {rep.share_id}: {rep.open_handles} open handles, {rep.pending_writes_bytes} bytes pending")

                elif payload_type == "release_ack":
                    ack = frame.release_ack
                    logger.info(f"[Filesystem] ReleaseAck received for share {ack.share_id}. Detaching...")
                    self.libvirt_ctl.detach_virtiofs(ack.share_id)
                    
                    if ack.share_id in self.active_shares:
                        del self.active_shares[ack.share_id]

                elif payload_type == "incident":
                    inc = frame.incident
                    logger.error(f"[Filesystem] Incident on share {inc.share_id}: {inc.kind} - {inc.detail}")
                    
                else:
                    logger.warning(f"Unhandled payload type: {payload_type}")

        # Start consuming in background
        consumer_task = asyncio.create_task(consume_incoming())

        try:
            async for out_frame in producer_gen:
                yield out_frame
        finally:
            consumer_task.cancel()
            logger.info(f"[{peer_identity}] Filesystem channel closed")

    async def trigger_mount(self, host_path: str, focal_filename: str):
        """Metoda testowa do zasymulowania kliknięcia pliku w UI."""
        share_id = str(uuid.uuid4())
        logger.info(f"Triggering mount for {host_path} (focal: {focal_filename}) -> share {share_id}")
        
        # 1. Hot plug libvirt
        self.libvirt_ctl.attach_virtiofs(share_id, host_path)
        self.active_shares[share_id] = "ATTACHED"

        # 2. Wysyłamy żądanie do Guesta
        req = filesystem_pb2.MountRequest(
            share_id=share_id,
            guest_drive_letter="X:",
            access_mode=filesystem_pb2.MountRequest.AccessMode.ACCESS_READ_WRITE,
            focal_filename=focal_filename,
            idle_release_after=Duration(seconds=5), # po 5 sekundach idle, oczekujemy detach
            mount_token=b"secure_token_123"
        )
        
        frame = filesystem_pb2.ShareHostFrame(
            payload=filesystem_pb2.ShareHostFrame.Mount(mount=req) # Payload to mount
        )
        # Z powodu buga z oneof generacją czasami przypisuje się kwargs: mount=req
        frame = filesystem_pb2.ShareHostFrame(mount=req)
        
        await self.command_queue.put(frame)
