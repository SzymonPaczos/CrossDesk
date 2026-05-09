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
def libvirt() -> MagicMock:
    return MagicMock()


@pytest.fixture
def servicer(libvirt: MagicMock) -> FilesystemServiceServicer:
    return FilesystemServiceServicer(MagicMock(), libvirt)


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


def test_mount_result_status_mounted_marks_share_active(
    servicer: FilesystemServiceServicer,
) -> None:
    frame = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        mount_result=filesystem_pb2.MountResult(
            share_id="share-1",
            status=filesystem_pb2.MountResult.Status.STATUS_MOUNTED,
            mount_token=_TOKEN,
        ),
    )
    servicer._process_guest_frame(frame)
    assert servicer.active_shares["share-1"] == "MOUNTED"


def test_mount_result_failure_does_not_register_share(
    servicer: FilesystemServiceServicer,
) -> None:
    """A failed mount (drive letter taken, permission denied, etc.) must NOT
    leave a phantom entry in active_shares — that would later block a retry."""
    for failed_status in (
        filesystem_pb2.MountResult.Status.STATUS_DRIVE_LETTER_TAKEN,
        filesystem_pb2.MountResult.Status.STATUS_PERMISSION_DENIED,
        filesystem_pb2.MountResult.Status.STATUS_DEVICE_NOT_PRESENT,
    ):
        frame = filesystem_pb2.ShareGuestFrame(
            auth=_auth(),
            mount_result=filesystem_pb2.MountResult(
                share_id=f"share-{failed_status}",
                status=failed_status,
                mount_token=_TOKEN,
            ),
        )
        servicer._process_guest_frame(frame)
        assert f"share-{failed_status}" not in servicer.active_shares


# ---------------------------------------------------------------------------
# ReleaseAck — the critical security-relevant path
# ---------------------------------------------------------------------------


def test_release_ack_triggers_detach_and_removes_share(
    servicer: FilesystemServiceServicer, libvirt: MagicMock
) -> None:
    """ROADMAP Phase 5 happy path: ReleaseAck → libvirt detach + state cleanup."""
    servicer.active_shares["s1"] = "MOUNTED"

    ack = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        release_ack=filesystem_pb2.ReleaseAck(share_id="s1", mount_token=_TOKEN),
    )
    servicer._process_guest_frame(ack)

    libvirt.detach_virtiofs.assert_called_once_with("s1")
    assert "s1" not in servicer.active_shares


def test_release_ack_for_unknown_share_still_detaches(
    servicer: FilesystemServiceServicer, libvirt: MagicMock
) -> None:
    """Defense-in-depth: if Guest reports release for a share we don't track,
    still call detach (libvirt is idempotent for missing devices) — the
    alternative is a stuck virtiofs device on the host."""
    ack = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        release_ack=filesystem_pb2.ReleaseAck(share_id="ghost", mount_token=_TOKEN),
    )
    servicer._process_guest_frame(ack)

    libvirt.detach_virtiofs.assert_called_once_with("ghost")


# ---------------------------------------------------------------------------
# LockReport / Incident — observe-only paths
# ---------------------------------------------------------------------------


def test_lock_report_does_not_mutate_state(
    servicer: FilesystemServiceServicer, libvirt: MagicMock
) -> None:
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
    servicer._process_guest_frame(rep)

    assert servicer.active_shares == {"s1": "MOUNTED"}
    libvirt.detach_virtiofs.assert_not_called()


def test_incident_logs_at_error_level(
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
        servicer._process_guest_frame(inc)

    assert any(
        "Incident" in rec.message and rec.levelno == logging.ERROR
        for rec in caplog.records
    )


# ---------------------------------------------------------------------------
# Host-initiated mount
# ---------------------------------------------------------------------------


async def test_trigger_mount_attaches_libvirt_and_queues_request(
    servicer: FilesystemServiceServicer,
    libvirt: MagicMock,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    await servicer.trigger_mount(str(work_dir), "report.docx")

    # 1. libvirt was hot-plugged
    libvirt.attach_virtiofs.assert_called_once()
    args, _ = libvirt.attach_virtiofs.call_args
    share_id, host_path = args
    assert host_path == str(work_dir.resolve())
    assert servicer.active_shares[share_id] == "ATTACHED"

    # 2. A MountRequest frame was queued for the producer to send
    assert servicer.command_queue.qsize() == 1
    frame = servicer.command_queue.get_nowait()
    assert frame.WhichOneof("payload") == "mount"
    assert frame.mount.share_id == share_id


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
def test_release_ack_rejected_when_mount_token_length_invalid(
    servicer: FilesystemServiceServicer, libvirt: MagicMock, bad_token: bytes
) -> None:
    """A malicious or buggy Guest could otherwise stamp every frame with a
    multi-MB token to balloon host memory; we drop the frame on length mismatch."""
    servicer.active_shares["s1"] = "MOUNTED"

    ack = filesystem_pb2.ShareGuestFrame(
        auth=_auth(),
        release_ack=filesystem_pb2.ReleaseAck(share_id="s1", mount_token=bad_token),
    )
    servicer._process_guest_frame(ack)

    libvirt.detach_virtiofs.assert_not_called()
    assert servicer.active_shares == {"s1": "MOUNTED"}
