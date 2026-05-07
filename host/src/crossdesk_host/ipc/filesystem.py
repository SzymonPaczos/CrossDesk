import asyncio
import logging
import uuid
from typing import AsyncIterator, Dict

import grpc
from google.protobuf.duration_pb2 import Duration

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.proto.crossdesk.v1 import filesystem_pb2, filesystem_pb2_grpc

logger = logging.getLogger(__name__)

# 32 bytes (SHA-256). Guests sending a longer token would let a malicious
# peer balloon host memory by stamping every frame with a multi-MB blob.
MOUNT_TOKEN_LEN = 32


class FilesystemServiceServicer(filesystem_pb2_grpc.FilesystemServiceServicer):
    def __init__(self, auth_validator: AuthValidator, libvirt_ctl: LibvirtController):
        self.auth_validator = auth_validator
        self.libvirt_ctl = libvirt_ctl
        self.command_queue: asyncio.Queue[filesystem_pb2.ShareHostFrame] = asyncio.Queue()
        self.active_shares: Dict[str, str] = {}

    async def ShareChannel(
        self,
        request_iterator: AsyncIterator[filesystem_pb2.ShareGuestFrame],
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[filesystem_pb2.ShareHostFrame]:
        peer_identity = context.peer()
        logger.info(f"[{peer_identity}] Filesystem channel established")

        async def consume_incoming() -> None:
            async for frame in request_iterator:
                # Per-frame validation: without this, ShareChannel would let any peer
                # holding a TLS handshake push MountResult/ReleaseAck and detach shares.
                await self.auth_validator.verify_auth_context(context, frame.auth)
                self._process_guest_frame(frame)

        consumer_task = asyncio.create_task(consume_incoming())

        try:
            # `cancelled()` is the public grpc-python equivalent of the
            # internal `core_context.aborted()` that earlier code used —
            # the latter lives on a private cython attribute that does
            # not exist in current grpcio releases.
            while not context.cancelled() and not consumer_task.done():
                try:
                    frame = await asyncio.wait_for(self.command_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                yield frame
        finally:
            consumer_task.cancel()
            try:
                await consumer_task
            except (asyncio.CancelledError, Exception):
                pass
            logger.info(f"[{peer_identity}] Filesystem channel closed")

    def _process_guest_frame(self, frame: filesystem_pb2.ShareGuestFrame) -> None:
        """Dispatch a single Guest-side frame to its state-mutation path.

        Extracted from the nested consume_incoming coroutine so unit tests can
        drive it directly without instantiating a full bidi gRPC stream.
        """
        payload_type = frame.WhichOneof("payload")

        if payload_type == "mount_result":
            res = frame.mount_result
            if not self._token_ok(res.mount_token, "mount_result", res.share_id):
                return
            logger.info(f"[Filesystem] MountResult for share {res.share_id}: {res.status}")
            if res.status == filesystem_pb2.MountResult.Status.STATUS_MOUNTED:
                self.active_shares[res.share_id] = "MOUNTED"

        elif payload_type == "lock_report":
            rep = frame.lock_report
            if not self._token_ok(rep.mount_token, "lock_report", rep.share_id):
                return
            logger.debug(
                "[Filesystem] LockReport for share %s: %d open handles, %d bytes pending",
                rep.share_id,
                rep.open_handles,
                rep.pending_writes_bytes,
            )

        elif payload_type == "release_ack":
            ack = frame.release_ack
            if not self._token_ok(ack.mount_token, "release_ack", ack.share_id):
                return
            logger.info(f"[Filesystem] ReleaseAck received for share {ack.share_id}. Detaching...")
            self.libvirt_ctl.detach_virtiofs(ack.share_id)

            if ack.share_id in self.active_shares:
                del self.active_shares[ack.share_id]

        elif payload_type == "incident":
            inc = frame.incident
            logger.error(f"[Filesystem] Incident on share {inc.share_id}: {inc.kind} - {inc.detail}")

        else:
            logger.warning(f"Unhandled payload type: {payload_type}")

    @staticmethod
    def _token_ok(token: bytes, frame_kind: str, share_id: str) -> bool:
        if len(token) != MOUNT_TOKEN_LEN:
            logger.error(
                "[Filesystem] %s for share %s rejected: mount_token len=%d (expected %d)",
                frame_kind, share_id, len(token), MOUNT_TOKEN_LEN,
            )
            return False
        return True

    async def trigger_mount(self, host_path: str, focal_filename: str) -> str:
        """Hot-plug a virtiofs share for `host_path` and queue a MountRequest for the guest.

        Returns the freshly-minted `share_id` so callers can correlate the
        eventual MountResult back to this attach.
        """
        share_id = str(uuid.uuid4())
        logger.info(
            "Triggering mount for %s (focal: %s) -> share %s",
            host_path, focal_filename, share_id,
        )

        self.libvirt_ctl.attach_virtiofs(share_id, host_path)
        self.active_shares[share_id] = "ATTACHED"

        # 32-byte random token bound to this share. Real deployments rotate
        # via HMAC over (share_id, libvirt domain UUID) — for now any
        # cryptographically random 32 bytes satisfy the wire contract.
        mount_token = uuid.uuid4().bytes + uuid.uuid4().bytes

        req = filesystem_pb2.MountRequest(
            share_id=share_id,
            guest_drive_letter="X:",
            access_mode=filesystem_pb2.MountRequest.AccessMode.ACCESS_READ_WRITE,
            focal_filename=focal_filename,
            idle_release_after=Duration(seconds=5),
            mount_token=mount_token,
        )

        await self.command_queue.put(filesystem_pb2.ShareHostFrame(mount=req))
        return share_id
