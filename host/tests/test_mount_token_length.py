"""32-byte mount_token enforcement.

Per FilesystemServiceServicer._token_ok: every wire frame carrying
a mount_token (MountResult, LockReport, ReleaseAck) is dropped if
the token length is not exactly 32 bytes (SHA-256 / 256-bit equivalent).

Without this length check a malicious peer could ship a multi-megabyte
``mount_token`` field on every frame and balloon host memory. The
host code documents this in `MOUNT_TOKEN_LEN`; this test pins the
contract end-to-end across the three frame types.
"""

from __future__ import annotations

import pytest

from crossdesk_host.filesystem_ctl.mock import MockFilesystemController
from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.ipc.filesystem import (
    MOUNT_TOKEN_LEN,
    FilesystemServiceServicer,
)
from crossdesk_host.proto.crossdesk.v1 import filesystem_pb2


@pytest.fixture
def servicer() -> FilesystemServiceServicer:
    return FilesystemServiceServicer(AuthValidator(), MockFilesystemController())


def _frame_for(kind: str, token: bytes) -> filesystem_pb2.ShareGuestFrame:
    """Build a ShareGuestFrame whose oneof carries the requested
    payload kind and the supplied token."""
    if kind == "mount_result":
        return filesystem_pb2.ShareGuestFrame(
            mount_result=filesystem_pb2.MountResult(
                share_id="share-mt",
                status=filesystem_pb2.MountResult.Status.STATUS_MOUNTED,
                mount_token=token,
            )
        )
    if kind == "lock_report":
        return filesystem_pb2.ShareGuestFrame(
            lock_report=filesystem_pb2.LockReport(
                share_id="share-lr",
                open_handles=0,
                pending_writes_bytes=0,
                mount_token=token,
            )
        )
    if kind == "release_ack":
        return filesystem_pb2.ShareGuestFrame(
            release_ack=filesystem_pb2.ReleaseAck(
                share_id="share-ra",
                mount_token=token,
            )
        )
    raise AssertionError(f"unknown kind {kind!r}")


@pytest.mark.parametrize("kind", ["mount_result", "lock_report", "release_ack"])
@pytest.mark.parametrize("length", [0, 1, 16, 31, 33, 64])
def test_wrong_length_token_is_dropped(
    servicer: FilesystemServiceServicer, kind: str, length: int
) -> None:
    """For each of the three frame types and each rejection-worthy
    length, _process_guest_frame must early-return without mutating
    state. We assert via active_shares being unchanged on
    mount_result, and by detach_virtiofs not being called on
    release_ack."""
    token = b"\x00" * length
    pre_attached = set(servicer.filesystem_ctl.list_active_shares())
    pre_detach_calls = len(servicer.filesystem_ctl.hooks.detached_ids)

    servicer._process_guest_frame(_frame_for(kind, token))

    # mount_result side-effect would set active_shares — confirm it didn't.
    if kind == "mount_result":
        assert "share-mt" not in servicer.active_shares
    # release_ack would call detach_share — confirm it didn't.
    if kind == "release_ack":
        assert (
            len(servicer.filesystem_ctl.hooks.detached_ids) == pre_detach_calls
        )
    # No frame should alter the filesystem mock's attached set on a length reject.
    assert set(servicer.filesystem_ctl.list_active_shares()) == pre_attached


def test_exact_32_byte_mount_result_records_share(
    servicer: FilesystemServiceServicer,
) -> None:
    token = b"\x00" * MOUNT_TOKEN_LEN
    servicer._process_guest_frame(_frame_for("mount_result", token))
    assert servicer.active_shares["share-mt"] == "MOUNTED"


def test_mount_token_constant_is_32() -> None:
    """Pin the constant — changing it is a wire-format break that
    needs proto + threat-model + test review."""
    assert MOUNT_TOKEN_LEN == 32
