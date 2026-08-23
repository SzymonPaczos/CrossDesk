"""FilesystemService Share lifecycle tests.

Phase 5 SPOF: detach before flush = corrupt write; missed ReleaseAck = permanent
share leak (violates "NIE permanentny mount" invariant). These tests pin the
state-machine bookkeeping for MountResult / LockReport / ReleaseAck / Incident
plus the trigger_mount entrypoint that wires the host-initiated attach.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from crossdesk_host.ipc.filesystem import FilesystemServiceServicer
from crossdesk_host.proto.crossdesk.v1 import common_pb2, filesystem_pb2


@pytest.fixture
def fs_ctl() -> MagicMock:
    return MagicMock()


@pytest.fixture
def servicer(fs_ctl: MagicMock) -> FilesystemServiceServicer:
    return FilesystemServiceServicer(MagicMock(), fs_ctl)


# 32-byte placeholder; the wire contract enforces exactly this length so
# every test frame must carry one. Real deployments rotate per-share.
_TOKEN: bytes = b"\xab" * 32


def _auth() -> common_pb2.AuthContext:
    return common_pb2.AuthContext(
        peer_cert_fingerprint="ff" * 32, stream_nonce=b"fs", sequence=1
    )


# ---------------------------------------------------------------------------
# MountResult bookkeeping
# ---------------------------------------------------------------------------


def _mint(servicer: FilesystemServiceServicer, share_id: str) -> None:
    """Stand in for the trigger_mount that would have handed the guest this
    share and its token. Frames naming a share the host never minted are
    rejected, so a test frame has to be preceded by the mint."""
    servicer.mount_tokens[share_id] = _TOKEN


async def test_mount_result_status_mounted_marks_share_active(
    servicer: FilesystemServiceServicer,
) -> None:
    _mint(servicer, "share-1")
    frame = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        mount_result=filesystem_pb2.MountResult(
            share_id="share-1",
            status=filesystem_pb2.MountResult.Status.STATUS_MOUNTED,
            mount_token=_TOKEN,
        ),
    )
    await servicer._process_guest_frame(frame)
    assert servicer.active_shares["share-1"] == "MOUNTED"


async def test_mount_result_failure_does_not_register_share(
    servicer: FilesystemServiceServicer,
) -> None:
    """A failed mount (drive letter taken, permission denied, etc.) must NOT
    leave a phantom entry in active_shares — that would later block a retry."""
    for failed_status in (
        filesystem_pb2.MountResult.Status.STATUS_DRIVE_LETTER_TAKEN,
        filesystem_pb2.MountResult.Status.STATUS_PERMISSION_DENIED,
        filesystem_pb2.MountResult.Status.STATUS_DEVICE_NOT_PRESENT,
    ):
        _mint(servicer, f"share-{failed_status}")
        frame = filesystem_pb2.ShareGuestFrame(
            auth=_auth(),
            mount_result=filesystem_pb2.MountResult(
                share_id=f"share-{failed_status}",
                status=failed_status,
                mount_token=_TOKEN,
            ),
        )
        await servicer._process_guest_frame(frame)
        assert f"share-{failed_status}" not in servicer.active_shares


# ---------------------------------------------------------------------------
# ReleaseAck — the critical security-relevant path
# ---------------------------------------------------------------------------


async def test_release_ack_triggers_detach_and_removes_share(
    servicer: FilesystemServiceServicer, fs_ctl: MagicMock
) -> None:
    """ROADMAP Phase 5 happy path: ReleaseAck → libvirt detach + state cleanup."""
    _mint(servicer, "s1")
    servicer.active_shares["s1"] = "MOUNTED"

    ack = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        release_ack=filesystem_pb2.ReleaseAck(share_id="s1", mount_token=_TOKEN),
    )
    await servicer._process_guest_frame(ack)

    fs_ctl.detach_share.assert_called_once_with("s1")
    assert "s1" not in servicer.active_shares


async def test_release_ack_for_unknown_share_is_refused(
    servicer: FilesystemServiceServicer, fs_ctl: MagicMock
) -> None:
    """A ReleaseAck naming a share this host never minted must NOT reach the
    detach path.

    This inverts the earlier "still detach, libvirt is idempotent" stance.
    That reasoning bought nothing real: the production controller
    (``LibvirtFilesystemController.detach_share``) already returns False for
    an id outside its own ``_attached`` set, so the pass-through never
    detached anything anyway — it only handed a guest-supplied string to the
    device-XML builder.
    """
    ack = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        release_ack=filesystem_pb2.ReleaseAck(share_id="ghost", mount_token=_TOKEN),
    )
    await servicer._process_guest_frame(ack)

    fs_ctl.detach_share.assert_not_called()


async def test_release_ack_with_wrong_token_is_refused(
    servicer: FilesystemServiceServicer, fs_ctl: MagicMock
) -> None:
    """Right length, right share, wrong value — the case the length-only
    check waved through."""
    _mint(servicer, "s1")
    servicer.active_shares["s1"] = "MOUNTED"

    ack = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        release_ack=filesystem_pb2.ReleaseAck(
            share_id="s1", mount_token=b"\xcd" * 32
        ),
    )
    await servicer._process_guest_frame(ack)

    fs_ctl.detach_share.assert_not_called()
    assert servicer.active_shares == {"s1": "MOUNTED"}


async def test_a_replayed_release_ack_does_not_detach_twice(
    servicer: FilesystemServiceServicer, fs_ctl: MagicMock
) -> None:
    """The token dies with the share, so a resent (or captured) ReleaseAck
    hits the unknown-share branch instead of re-driving detach."""
    _mint(servicer, "s1")
    servicer.active_shares["s1"] = "MOUNTED"
    ack = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        release_ack=filesystem_pb2.ReleaseAck(share_id="s1", mount_token=_TOKEN),
    )

    await servicer._process_guest_frame(ack)
    await servicer._process_guest_frame(ack)

    fs_ctl.detach_share.assert_called_once_with("s1")
    assert "s1" not in servicer.mount_tokens


async def test_mount_result_for_an_unminted_share_is_refused(
    servicer: FilesystemServiceServicer,
) -> None:
    """State-mutating frames are authorised too, not just the detach path —
    otherwise a guest could populate active_shares with ids of its choosing."""
    frame = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        mount_result=filesystem_pb2.MountResult(
            share_id="not-ours",
            status=filesystem_pb2.MountResult.Status.STATUS_MOUNTED,
            mount_token=_TOKEN,
        ),
    )
    await servicer._process_guest_frame(frame)

    assert servicer.active_shares == {}


# ---------------------------------------------------------------------------
# LockReport / Incident — observe-only paths
# ---------------------------------------------------------------------------


async def test_lock_report_does_not_mutate_state(
    servicer: FilesystemServiceServicer, fs_ctl: MagicMock
) -> None:
    _mint(servicer, "s1")
    servicer.active_shares["s1"] = "MOUNTED"

    rep = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        lock_report=filesystem_pb2.LockReport(
            share_id="s1",
            open_handles=3,
            pending_writes_bytes=1024,
            mount_token=_TOKEN,
        ),
    )
    await servicer._process_guest_frame(rep)

    assert servicer.active_shares == {"s1": "MOUNTED"}
    fs_ctl.detach_share.assert_not_called()


async def test_incident_logs_at_error_level(
    servicer: FilesystemServiceServicer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    inc = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        incident=filesystem_pb2.ShareIncident(
            share_id="s1",
            kind=filesystem_pb2.ShareIncident.Kind.KIND_PATH_TRAVERSAL_BLOCKED,
            detail="symlink escape attempt",
        ),
    )
    with caplog.at_level(logging.ERROR):
        await servicer._process_guest_frame(inc)

    assert any(
        "Incident" in rec.message and rec.levelno == logging.ERROR
        for rec in caplog.records
    )


# ---------------------------------------------------------------------------
# Host-initiated mount
# ---------------------------------------------------------------------------


async def test_trigger_mount_attaches_libvirt_and_queues_request(
    servicer: FilesystemServiceServicer,
    fs_ctl: MagicMock,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    await servicer.trigger_mount(str(work_dir), "report.docx")

    # 1. libvirt was hot-plugged
    fs_ctl.attach_share.assert_called_once()
    args, _ = fs_ctl.attach_share.call_args
    share_id, host_path = args
    assert host_path == str(work_dir.resolve())
    assert servicer.active_shares[share_id] == "ATTACHED"

    # 2. A MountRequest frame was queued for the producer to send
    assert servicer.command_queue.qsize() == 1
    frame = servicer.command_queue.get_nowait()
    assert frame.WhichOneof("payload") == "mount"
    assert frame.mount.share_id == share_id

    # 3. The token on the wire is the one remembered for this share — that
    # binding is what later authorises the guest's frames about it.
    assert servicer.mount_tokens[share_id] == frame.mount.mount_token


async def test_trigger_mount_assigns_unique_share_ids(
    servicer: FilesystemServiceServicer,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """share_id must be unique per call to prevent collisions in active_shares."""
    monkeypatch.setenv("HOME", str(tmp_path))
    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"
    a_dir.mkdir()
    b_dir.mkdir()
    await servicer.trigger_mount(str(a_dir), "a.txt")
    await servicer.trigger_mount(str(b_dir), "b.txt")
    assert len(servicer.active_shares) == 2


async def test_trigger_mount_rejects_traversal(
    servicer: FilesystemServiceServicer, tmp_path
) -> None:
    """Phase 5 SPOF: any '..' escape MUST be rejected before libvirt is touched."""
    from crossdesk_host.jit_mount import MountPathError

    with pytest.raises(MountPathError):
        await servicer.trigger_mount("/etc/passwd", "shadow")


# NOTE: per-frame auth enforcement on ShareChannel is verified via the smoke
# test `test_filesystem_rejects_fingerprint_spoof` (real gRPC server). Driving
# ShareChannel from a unit test is awkward because its producer task polls
# `command_queue` on a 1s timeout and only exits when the gRPC context aborts —
# the smoke test exercises both paths through the wire instead.


# ---------------------------------------------------------------------------
# Wire-format invariant: mount_token must be exactly 32 bytes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_token", [b"", b"\x00" * 31, b"\x00" * 33, b"\x00" * 4096])
async def test_release_ack_rejected_when_mount_token_length_invalid(
    servicer: FilesystemServiceServicer, fs_ctl: MagicMock, bad_token: bytes
) -> None:
    """A malicious or buggy Guest could otherwise stamp every frame with a
    multi-MB token to balloon host memory; we drop the frame on length mismatch."""
    _mint(servicer, "s1")
    servicer.active_shares["s1"] = "MOUNTED"

    ack = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        release_ack=filesystem_pb2.ReleaseAck(share_id="s1", mount_token=bad_token),
    )
    await servicer._process_guest_frame(ack)

    fs_ctl.detach_share.assert_not_called()
    assert servicer.active_shares == {"s1": "MOUNTED"}
