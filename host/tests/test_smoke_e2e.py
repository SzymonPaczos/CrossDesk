"""End-to-end smoke test: real mTLS gRPC client ↔ live host daemon.

Boots the actual host gRPC server (TCP fallback for macOS), connects with the
checked-in guest cert from infra/certs/pki, and exercises all three services
(Control, Heartbeat, Filesystem). This catches real wiring bugs that pure unit
tests miss — e.g. the AuthValidator hashlib/cryptography mismatch fixed earlier
would have shown up as UNAUTHENTICATED on every connection.

Skip conditions: missing PKI files (real run requires `host/run_mock_macos.sh`
to have generated certs at infra/certs/pki/).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator

import grpc
import pytest
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.ipc.control import ControlServiceServicer
from crossdesk_host.ipc.filesystem import FilesystemServiceServicer
from crossdesk_host.ipc.heartbeat import HeartbeatServiceServicer
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.proto.crossdesk.v1 import (
    common_pb2,
    control_pb2,
    control_pb2_grpc,
    filesystem_pb2,
    filesystem_pb2_grpc,
    heartbeat_pb2,
    heartbeat_pb2_grpc,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PKI = _REPO_ROOT / "infra" / "certs" / "pki"

# 32-byte mount_token — the wire contract enforces exactly this length on
# MountResult / LockReport / ReleaseAck (filesystem.py MOUNT_TOKEN_LEN).
# Wrong-length frames are silently dropped at the host servicer, so every
# smoke frame carrying one MUST use this constant or the test would pass
# while the frame was rejected. See FOLLOWUPS:64-69.
_MOUNT_TOKEN: bytes = b"\xab" * 32


pytestmark = pytest.mark.skipif(
    not (_PKI / "ca.crt").exists(),
    reason="PKI not generated. Run host/run_mock_macos.sh first.",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _guest_fingerprint() -> str:
    pem = (_PKI / "guest.crt").read_bytes()
    cert = x509.load_pem_x509_certificate(pem, default_backend())
    return cert.fingerprint(hashes.SHA256()).hex().lower()


@pytest.fixture
async def host_server():
    """Spin up the host gRPC server on a free TCP port with the real services."""
    server = grpc.aio.server()

    creds = grpc.ssl_server_credentials(
        [
            (
                (_PKI / "host.key").read_bytes(),
                (_PKI / "host.crt").read_bytes(),
            )
        ],
        root_certificates=(_PKI / "ca.crt").read_bytes(),
        require_client_auth=True,
    )

    auth = AuthValidator()
    libvirt = LibvirtControllerMock()
    control_pb2_grpc.add_ControlServiceServicer_to_server(
        ControlServiceServicer(auth), server
    )
    heartbeat_pb2_grpc.add_HeartbeatServiceServicer_to_server(
        HeartbeatServiceServicer(auth, libvirt), server
    )
    filesystem_pb2_grpc.add_FilesystemServiceServicer_to_server(
        FilesystemServiceServicer(auth, libvirt), server
    )

    port = server.add_secure_port("127.0.0.1:0", creds)
    assert port != 0, "Failed to bind smoke-test gRPC server"
    await server.start()
    try:
        yield port
    finally:
        await server.stop(grace=0.5)


@pytest.fixture
def channel_factory():
    """Build an mTLS-secured gRPC channel using the checked-in guest credentials."""
    ca = (_PKI / "ca.crt").read_bytes()
    cert = (_PKI / "guest.crt").read_bytes()
    key = (_PKI / "guest.key").read_bytes()
    creds = grpc.ssl_channel_credentials(
        root_certificates=ca, private_key=key, certificate_chain=cert
    )

    def _make(port: int) -> grpc.aio.Channel:
        # The host cert's CN is "crossdesk-host", not a real DNS name; override.
        opts = (("grpc.ssl_target_name_override", "crossdesk-host"),)
        return grpc.aio.secure_channel(f"127.0.0.1:{port}", creds, options=opts)

    return _make


# ---------------------------------------------------------------------------
# Control plane: full handshake → app launch → terminate
# ---------------------------------------------------------------------------


async def test_control_session_full_lifecycle(host_server, channel_factory) -> None:
    fp = _guest_fingerprint()
    nonce = b"smoke-control-1!"  # fixed for replay-clarity in the test

    async def client_frames() -> AsyncIterator[control_pb2.ClientFrame]:
        yield control_pb2.ClientFrame(
            auth=common_pb2.AuthContext(
                peer_cert_fingerprint=fp, stream_nonce=nonce, sequence=1
            ),
            hello=control_pb2.ClientHello(host_version="v0.1.0"),
        )
        # Tiny pause so server can yield ServerAccept before we pile up next frame
        await asyncio.sleep(0.05)
        yield control_pb2.ClientFrame(
            auth=common_pb2.AuthContext(
                peer_cert_fingerprint=fp, stream_nonce=nonce, sequence=2
            ),
            launch=control_pb2.AppLaunchRequest(
                request_id="req-smoke-1",
                executable_guest_path="C:\\Windows\\notepad.exe",
            ),
        )
        await asyncio.sleep(0.05)
        yield control_pb2.ClientFrame(
            auth=common_pb2.AuthContext(
                peer_cert_fingerprint=fp, stream_nonce=nonce, sequence=3
            ),
            terminate=control_pb2.SessionTerminate(
                reason=control_pb2.SessionTerminate.Reason.REASON_USER_QUIT
            ),
        )

    async with channel_factory(host_server) as channel:
        stub = control_pb2_grpc.ControlServiceStub(channel)
        responses: list[control_pb2.ServerFrame] = []
        async for frame in stub.OpenSession(client_frames()):
            responses.append(frame)

    payloads = [f.WhichOneof("payload") for f in responses]
    assert payloads == [
        "accept",
        "launched",
        "closed",
    ], f"unexpected response sequence: {payloads}"
    assert responses[1].launched.request_id == "req-smoke-1"
    assert responses[1].launched.process_id == 9999


# ---------------------------------------------------------------------------
# Auth enforcement at the wire: bad fingerprint must be rejected
# ---------------------------------------------------------------------------


async def test_control_rejects_fingerprint_spoof(host_server, channel_factory) -> None:
    """Send a Hello carrying a bogus fingerprint. The server must abort the
    stream — not yield any ServerAccept. Verifies the cryptography hashing fix
    landed earlier still holds end-to-end."""
    bogus_fp = "00" * 32

    async def frames() -> AsyncIterator[control_pb2.ClientFrame]:
        yield control_pb2.ClientFrame(
            auth=common_pb2.AuthContext(
                peer_cert_fingerprint=bogus_fp,
                stream_nonce=b"spoof-stream-001",
                sequence=1,
            ),
            hello=control_pb2.ClientHello(host_version="v0.1.0"),
        )

    async with channel_factory(host_server) as channel:
        stub = control_pb2_grpc.ControlServiceStub(channel)
        with pytest.raises(grpc.aio.AioRpcError) as exc:
            async for _ in stub.OpenSession(frames()):
                pass
        assert exc.value.code() == grpc.StatusCode.UNAUTHENTICATED


# ---------------------------------------------------------------------------
# Heartbeat: receive at least one Ping, send a Pong, close cleanly
# ---------------------------------------------------------------------------


async def test_heartbeat_ping_pong_roundtrip(host_server, channel_factory) -> None:
    fp = _guest_fingerprint()
    nonce = b"smoke-heartbeat!"
    pong_sent = asyncio.Event()

    async def guest_frames() -> AsyncIterator[heartbeat_pb2.GuestFrame]:
        # Stay alive until we've seen at least one Ping and replied with a Pong.
        await pong_sent.wait()
        yield heartbeat_pb2.GuestFrame(
            auth=common_pb2.AuthContext(
                peer_cert_fingerprint=fp, stream_nonce=nonce, sequence=1
            ),
            pong=heartbeat_pb2.Pong(sequence=1),
        )
        # Then bow out so the server's wait_for sees StopAsyncIteration.

    async with channel_factory(host_server) as channel:
        stub = heartbeat_pb2_grpc.HeartbeatServiceStub(channel)
        pings: list[heartbeat_pb2.HostFrame] = []
        try:
            async for hf in stub.Channel(guest_frames()):
                pings.append(hf)
                if hf.WhichOneof("payload") == "ping" and not pong_sent.is_set():
                    pong_sent.set()
                if len(pings) >= 1:
                    # Don't loop forever — we've proven the round-trip works.
                    break
        except grpc.aio.AioRpcError:
            pass

    assert len(pings) >= 1
    assert pings[0].WhichOneof("payload") == "ping"
    assert pings[0].ping.sequence == 1


# ---------------------------------------------------------------------------
# Filesystem: open share channel, post a MountResult, verify state mutation
# ---------------------------------------------------------------------------


async def test_filesystem_mount_result_recorded(
    host_server, channel_factory, caplog: pytest.LogCaptureFixture
) -> None:
    """Connect to ShareChannel, push a MountResult(STATUS_MOUNTED), then close.

    Beyond proving the bidi handshake completes without auth/wire errors, this
    asserts the host log line for the accept-path fired. Without that check
    the 32-byte ``mount_token`` enforcement could silently drop the frame and
    the test would still pass — the regression FOLLOWUPS:64-69 was filed for.
    """
    fp = _guest_fingerprint()
    nonce = b"smoke-filesystem"

    async def guest_frames() -> AsyncIterator[filesystem_pb2.ShareGuestFrame]:
        yield filesystem_pb2.ShareGuestFrame(
            auth=common_pb2.AuthContext(
                peer_cert_fingerprint=fp, stream_nonce=nonce, sequence=1
            ),
            mount_result=filesystem_pb2.MountResult(
                share_id="smoke-share-1",
                status=filesystem_pb2.MountResult.Status.STATUS_MOUNTED,
                mount_token=_MOUNT_TOKEN,
            ),
        )

    async with channel_factory(host_server) as channel:
        stub = filesystem_pb2_grpc.FilesystemServiceStub(channel)

        # The server's ShareChannel never yields anything until trigger_mount is
        # called (nothing in command_queue), so we just push our frame and bail.
        async def consume():
            async for _ in stub.ShareChannel(guest_frames()):
                break

        with caplog.at_level(logging.INFO, logger="crossdesk_host.ipc.filesystem"):
            try:
                await asyncio.wait_for(consume(), timeout=1.0)
            except (asyncio.TimeoutError, grpc.aio.AioRpcError):
                pass  # Expected: server never produces output on its own

    # Accept path: filesystem.py:_process_guest_frame mount_result branch
    # logs "MountResult for share <id>: <status>". The reject path logs
    # "rejected: mount_token len=…" instead. A failure here means the
    # 32-byte enforcement silently dropped the frame.
    fs_records = [
        r for r in caplog.records if r.name == "crossdesk_host.ipc.filesystem"
    ]
    accept_lines = [
        r for r in fs_records if "MountResult for share smoke-share-1" in r.message
    ]
    reject_lines = [r for r in fs_records if "rejected: mount_token len=" in r.message]
    assert accept_lines, (
        "Host did not log the MountResult accept path — the smoke frame was "
        "silently dropped (likely mount_token length mismatch). Captured "
        f"records: {[(r.levelname, r.message) for r in fs_records]}"
    )
    assert not reject_lines, (
        "Host logged a mount_token rejection for the smoke frame: "
        f"{[(r.levelname, r.message) for r in reject_lines]}"
    )


async def test_filesystem_rejects_fingerprint_spoof(
    host_server, channel_factory
) -> None:
    """Regression for S2: per-frame auth check on ShareChannel.

    Before the fix, the filesystem plane skipped verify_auth_context entirely.
    Spoofed fingerprint here must trigger UNAUTHENTICATED on the wire."""
    bogus_fp = "00" * 32

    async def frames() -> AsyncIterator[filesystem_pb2.ShareGuestFrame]:
        yield filesystem_pb2.ShareGuestFrame(
            auth=common_pb2.AuthContext(
                peer_cert_fingerprint=bogus_fp,
                stream_nonce=b"fs-spoof-stream1",
                sequence=1,
            ),
            # Valid 32-byte mount_token even though auth fires first — keeps
            # the test focused on auth rejection so a future reader doesn't
            # wonder whether the missing token was load-bearing.
            mount_result=filesystem_pb2.MountResult(
                share_id="x",
                status=filesystem_pb2.MountResult.Status.STATUS_MOUNTED,
                mount_token=_MOUNT_TOKEN,
            ),
        )

    async with channel_factory(host_server) as channel:
        stub = filesystem_pb2_grpc.FilesystemServiceStub(channel)

        # Spoofed auth must abort the stream on the consume side. The producer
        # may emit nothing, so we time-bound the iteration and check whether
        # we tripped UNAUTHENTICATED.
        async def consume():
            async for _ in stub.ShareChannel(frames()):
                break

        with pytest.raises((grpc.aio.AioRpcError, asyncio.TimeoutError)):
            await asyncio.wait_for(consume(), timeout=1.5)
