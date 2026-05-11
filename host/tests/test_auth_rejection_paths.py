"""Per-plane AuthContext rejection-path coverage.

The AuthValidator unit tests pin its own behaviour. This file pins
the behaviour of each gRPC servicer when the validator decides to
abort: every plane (Control, Heartbeat, Filesystem) must surface
the abort *before* it processes the offending payload, on each of
the three classes of bad frame:

- mismatched ``peer_cert_fingerprint`` → UNAUTHENTICATED
- empty ``stream_nonce`` → INVALID_ARGUMENT
- non-monotonic ``sequence`` (replay) → ABORTED

A regression on any of these would let a malicious peer past mTLS
into the FSM / virtiofs surface — explicit per-plane coverage
prevents the silent-bypass class of bug we hit before.
"""

from __future__ import annotations

from typing import AsyncIterator

import grpc
import pytest

from crossdesk_host.ipc.control import ControlServiceServicer
from crossdesk_host.ipc.filesystem import FilesystemServiceServicer
from crossdesk_host.ipc.heartbeat import HeartbeatServiceServicer
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.proto.crossdesk.v1 import (
    common_pb2,
    control_pb2,
    filesystem_pb2,
    heartbeat_pb2,
)
from tests.conftest import AbortError, context_with_cert


def _good_auth(
    fp: str, nonce: bytes = b"good", sequence: int = 1
) -> common_pb2.AuthContext:
    return common_pb2.AuthContext(
        peer_cert_fingerprint=fp, stream_nonce=nonce, sequence=sequence
    )


def _bad_fingerprint_auth() -> common_pb2.AuthContext:
    return common_pb2.AuthContext(
        peer_cert_fingerprint="00" * 32, stream_nonce=b"n", sequence=1
    )


def _missing_nonce_auth(fp: str) -> common_pb2.AuthContext:
    return common_pb2.AuthContext(
        peer_cert_fingerprint=fp, stream_nonce=b"", sequence=1
    )


# ---------------------------------------------------------------------------
# Control plane
# ---------------------------------------------------------------------------


async def _consume(stream: AsyncIterator) -> None:
    async for _ in stream:
        pass


async def test_control_rejects_fingerprint_mismatch(make_cert) -> None:
    pem, _ = make_cert()
    ctx = context_with_cert(pem)
    servicer = ControlServiceServicer(
        auth_validator=__import__(
            "crossdesk_host.ipc.auth", fromlist=["AuthValidator"]
        ).AuthValidator()
    )

    async def frames() -> AsyncIterator[control_pb2.ClientFrame]:
        yield control_pb2.ClientFrame(
            auth=_bad_fingerprint_auth(),
            hello=control_pb2.ClientHello(host_version="v0.1.0"),
        )

    with pytest.raises(AbortError) as exc:
        await _consume(servicer.OpenSession(frames(), ctx))
    assert exc.value.code == grpc.StatusCode.UNAUTHENTICATED


async def test_control_rejects_missing_nonce(make_cert) -> None:
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    servicer = ControlServiceServicer(
        auth_validator=__import__(
            "crossdesk_host.ipc.auth", fromlist=["AuthValidator"]
        ).AuthValidator()
    )

    async def frames() -> AsyncIterator[control_pb2.ClientFrame]:
        yield control_pb2.ClientFrame(
            auth=_missing_nonce_auth(fp),
            hello=control_pb2.ClientHello(host_version="v0.1.0"),
        )

    with pytest.raises(AbortError) as exc:
        await _consume(servicer.OpenSession(frames(), ctx))
    assert exc.value.code == grpc.StatusCode.INVALID_ARGUMENT


async def test_control_rejects_non_monotonic_sequence(make_cert) -> None:
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    from crossdesk_host.ipc.auth import AuthValidator

    servicer = ControlServiceServicer(auth_validator=AuthValidator())

    async def frames() -> AsyncIterator[control_pb2.ClientFrame]:
        # First frame primes the seq for nonce=b"r"
        yield control_pb2.ClientFrame(
            auth=_good_auth(fp, b"r", sequence=1),
            hello=control_pb2.ClientHello(host_version="v0.1.0"),
        )
        # Second frame replays sequence=1 — must abort.
        yield control_pb2.ClientFrame(
            auth=_good_auth(fp, b"r", sequence=1),
            launch=control_pb2.AppLaunchRequest(
                request_id="r", executable_guest_path=r"C:\notepad.exe"
            ),
        )

    with pytest.raises(AbortError) as exc:
        await _consume(servicer.OpenSession(frames(), ctx))
    assert exc.value.code == grpc.StatusCode.ABORTED


# ---------------------------------------------------------------------------
# Heartbeat plane
# ---------------------------------------------------------------------------


async def test_heartbeat_rejects_fingerprint_mismatch(make_cert) -> None:
    pem, _ = make_cert()
    ctx = context_with_cert(pem)
    from crossdesk_host.ipc.auth import AuthValidator

    servicer = HeartbeatServiceServicer(AuthValidator(), LibvirtControllerMock())

    async def frames() -> AsyncIterator[heartbeat_pb2.GuestFrame]:
        yield heartbeat_pb2.GuestFrame(
            auth=_bad_fingerprint_auth(),
            pong=heartbeat_pb2.Pong(sequence=1),
        )

    with pytest.raises(AbortError) as exc:
        await _consume(servicer.Channel(frames(), ctx))
    assert exc.value.code == grpc.StatusCode.UNAUTHENTICATED


async def test_heartbeat_rejects_missing_nonce(make_cert) -> None:
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    from crossdesk_host.ipc.auth import AuthValidator

    servicer = HeartbeatServiceServicer(AuthValidator(), LibvirtControllerMock())

    async def frames() -> AsyncIterator[heartbeat_pb2.GuestFrame]:
        yield heartbeat_pb2.GuestFrame(
            auth=_missing_nonce_auth(fp),
            pong=heartbeat_pb2.Pong(sequence=1),
        )

    with pytest.raises(AbortError) as exc:
        await _consume(servicer.Channel(frames(), ctx))
    assert exc.value.code == grpc.StatusCode.INVALID_ARGUMENT


async def test_heartbeat_rejects_non_monotonic_sequence(make_cert) -> None:
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    from crossdesk_host.ipc.auth import AuthValidator

    servicer = HeartbeatServiceServicer(AuthValidator(), LibvirtControllerMock())

    async def frames() -> AsyncIterator[heartbeat_pb2.GuestFrame]:
        yield heartbeat_pb2.GuestFrame(
            auth=_good_auth(fp, b"hb", sequence=1),
            pong=heartbeat_pb2.Pong(sequence=1),
        )
        yield heartbeat_pb2.GuestFrame(
            auth=_good_auth(fp, b"hb", sequence=1),  # replay
            pong=heartbeat_pb2.Pong(sequence=2),
        )

    with pytest.raises(AbortError) as exc:
        await _consume(servicer.Channel(frames(), ctx))
    assert exc.value.code == grpc.StatusCode.ABORTED


# ---------------------------------------------------------------------------
# Filesystem plane
# ---------------------------------------------------------------------------


async def test_filesystem_rejects_fingerprint_mismatch(make_cert) -> None:
    pem, _ = make_cert()
    ctx = context_with_cert(pem)
    from crossdesk_host.ipc.auth import AuthValidator

    servicer = FilesystemServiceServicer(AuthValidator(), LibvirtControllerMock())

    async def frames() -> AsyncIterator[filesystem_pb2.ShareGuestFrame]:
        yield filesystem_pb2.ShareGuestFrame(
            auth=_bad_fingerprint_auth(),
            mount_result=filesystem_pb2.MountResult(
                share_id="x",
                status=filesystem_pb2.MountResult.Status.STATUS_MOUNTED,
                mount_token=b"\x00" * 32,
            ),
        )

    with pytest.raises(AbortError) as exc:
        await _consume(servicer.ShareChannel(frames(), ctx))
    assert exc.value.code == grpc.StatusCode.UNAUTHENTICATED


async def test_filesystem_rejects_missing_nonce(make_cert) -> None:
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    from crossdesk_host.ipc.auth import AuthValidator

    servicer = FilesystemServiceServicer(AuthValidator(), LibvirtControllerMock())

    async def frames() -> AsyncIterator[filesystem_pb2.ShareGuestFrame]:
        yield filesystem_pb2.ShareGuestFrame(
            auth=_missing_nonce_auth(fp),
            mount_result=filesystem_pb2.MountResult(
                share_id="x",
                status=filesystem_pb2.MountResult.Status.STATUS_MOUNTED,
                mount_token=b"\x00" * 32,
            ),
        )

    with pytest.raises(AbortError) as exc:
        await _consume(servicer.ShareChannel(frames(), ctx))
    assert exc.value.code == grpc.StatusCode.INVALID_ARGUMENT


async def test_filesystem_rejects_non_monotonic_sequence(make_cert) -> None:
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    from crossdesk_host.ipc.auth import AuthValidator

    servicer = FilesystemServiceServicer(AuthValidator(), LibvirtControllerMock())

    async def frames() -> AsyncIterator[filesystem_pb2.ShareGuestFrame]:
        yield filesystem_pb2.ShareGuestFrame(
            auth=_good_auth(fp, b"fs", sequence=1),
            mount_result=filesystem_pb2.MountResult(
                share_id="x1",
                status=filesystem_pb2.MountResult.Status.STATUS_MOUNTED,
                mount_token=b"\x00" * 32,
            ),
        )
        yield filesystem_pb2.ShareGuestFrame(
            auth=_good_auth(fp, b"fs", sequence=1),  # replay
            mount_result=filesystem_pb2.MountResult(
                share_id="x2",
                status=filesystem_pb2.MountResult.Status.STATUS_MOUNTED,
                mount_token=b"\x00" * 32,
            ),
        )

    with pytest.raises(AbortError) as exc:
        await _consume(servicer.ShareChannel(frames(), ctx))
    assert exc.value.code == grpc.StatusCode.ABORTED
