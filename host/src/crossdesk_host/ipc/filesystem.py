import asyncio
import contextlib
import hmac
import logging
import uuid
from typing import AsyncIterator, Dict

import grpc
from google.protobuf.duration_pb2 import Duration

from crossdesk_host.abstractions.filesystem import FilesystemController
from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.libvirt_ctl import libvirt_call
from crossdesk_host.proto.crossdesk.v1 import filesystem_pb2, filesystem_pb2_grpc

logger = logging.getLogger(__name__)

# 32 bytes (SHA-256). Guests sending a longer token would let a malicious
# peer balloon host memory by stamping every frame with a multi-MB blob.
MOUNT_TOKEN_LEN = 32


class FilesystemServiceServicer(filesystem_pb2_grpc.FilesystemServiceServicer):
    def __init__(
        self,
        auth_validator: AuthValidator,
        filesystem_ctl: FilesystemController,
    ):
        self.auth_validator = auth_validator
        self.filesystem_ctl = filesystem_ctl
        self.command_queue: asyncio.Queue[filesystem_pb2.ShareHostFrame] = (
            asyncio.Queue()
        )
        self.active_shares: Dict[str, str] = {}
        self.mount_tokens: Dict[str, bytes] = {}
        """``share_id`` → the token minted for it in :meth:`trigger_mount`.

        A frame's ``mount_token`` is compared against this, so a share the
        host never handed out cannot be acted on. Entries are dropped when
        the share is released."""

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
                await self._process_guest_frame(frame)

        consumer_task = asyncio.create_task(consume_incoming())

        try:
            # `cancelled()` is the public grpc-python equivalent of the
            # internal `core_context.aborted()` that earlier code used —
            # the latter lives on a private cython attribute that does
            # not exist in current grpcio releases.
            while not context.cancelled() and not consumer_task.done():
                try:
                    frame = await asyncio.wait_for(
                        self.command_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                yield frame
        finally:
            # Cancel the consumer if it's still running; surface any
            # other exception (e.g. AuthValidator's AbortError) so the
            # gRPC layer reports the rejection upstream. Pre-fix this
            # `except Exception: pass` swallowed auth aborts silently.
            consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await consumer_task
            logger.info(f"[{peer_identity}] Filesystem channel closed")

    async def _process_guest_frame(self, frame: filesystem_pb2.ShareGuestFrame) -> None:
        """Dispatch a single Guest-side frame to its state-mutation path.

        Extracted from the nested consume_incoming coroutine so unit tests can
        drive it directly without instantiating a full bidi gRPC stream.

        Async because the ReleaseAck path detaches a virtiofs share, a blocking
        libvirt call that must be offloaded off the event loop with a deadline.
        """
        payload_type = frame.WhichOneof("payload")

        if payload_type == "mount_result":
            res = frame.mount_result
            if not self._token_ok(res.mount_token, "mount_result", res.share_id):
                return
            logger.info(
                f"[Filesystem] MountResult for share {res.share_id}: {res.status}"
            )
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
            logger.info(
                f"[Filesystem] ReleaseAck received for share {ack.share_id}. Detaching..."
            )
            await libvirt_call(lambda: self.filesystem_ctl.detach_share(ack.share_id))

            if ack.share_id in self.active_shares:
                del self.active_shares[ack.share_id]
            # The token dies with the share: a replayed ReleaseAck now hits
            # the unknown-share branch instead of re-driving detach.
            self.mount_tokens.pop(ack.share_id, None)

        elif payload_type == "incident":
            inc = frame.incident
            logger.error(
                f"[Filesystem] Incident on share {inc.share_id}: {inc.kind} - {inc.detail}"
            )

        else:
            logger.warning(f"Unhandled payload type: {payload_type}")

    def _token_ok(self, token: bytes, frame_kind: str, share_id: str) -> bool:
        """Authorise a guest frame against the share it names.

        Three layers, cheapest first:

        1. **Length.** A multi-MB ``mount_token`` on every frame would balloon
           host memory, so a wrong length is dropped before anything else.
        2. **Known share.** The share must be one this host minted and has not
           released. Without it, a frame naming an arbitrary ``share_id`` could
           drive the detach path for a device we never attached.
        3. **Value.** The token must equal the one minted for *this* share,
           compared with :func:`hmac.compare_digest` so a wrong guess leaks
           nothing through timing. Length-checking alone — the previous
           behaviour — authorised nothing at all: any 32 bytes passed.
        """
        if len(token) != MOUNT_TOKEN_LEN:
            logger.error(
                "[Filesystem] %s for share %s rejected: mount_token len=%d (expected %d)",
                frame_kind,
                share_id,
                len(token),
                MOUNT_TOKEN_LEN,
            )
            return False
        expected = self.mount_tokens.get(share_id)
        if expected is None:
            logger.error(
                "[Filesystem] %s rejected: unknown share %r (never minted here, "
                "or already released)",
                frame_kind,
                share_id,
            )
            return False
        if not hmac.compare_digest(token, expected):
            logger.error(
                "[Filesystem] %s for share %s rejected: mount_token mismatch",
                frame_kind,
                share_id,
            )
            return False
        return True

    async def trigger_mount(self, host_path: str, focal_filename: str) -> str:
        """Hot-plug a virtiofs share for `host_path` and queue a MountRequest for the guest.

        Returns the freshly-minted `share_id` so callers can correlate the
        eventual MountResult back to this attach.

        Phase 5 SPOF: any path that enters the mount flow MUST go
        through ``validate_mount_path`` first; without that we'd be
        the bypass for docs/THREAT_MODEL.md TA3 (path traversal).
        """
        from crossdesk_host.jit_mount import MountPathError, validate_mount_path

        try:
            validated = validate_mount_path(host_path)
        except MountPathError as exc:
            logger.error("trigger_mount rejected %r: %s", host_path, exc)
            raise

        share_id = str(uuid.uuid4())
        logger.info(
            "Triggering mount for %s (focal: %s) -> share %s",
            validated.canonical,
            focal_filename,
            share_id,
        )

        await libvirt_call(lambda: self.filesystem_ctl.attach_share(share_id, str(validated.canonical)))
        self.active_shares[share_id] = "ATTACHED"

        # 32-byte random token bound to this share, remembered so guest frames
        # naming this share can be checked against it. Real deployments rotate
        # via HMAC over (share_id, libvirt domain UUID).
        mount_token = uuid.uuid4().bytes + uuid.uuid4().bytes
        self.mount_tokens[share_id] = mount_token

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
