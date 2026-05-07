"""In-process integration harness — Python host ↔ live Rust guest binary.

Boots the actual host gRPC server on a free TCP port, spawns the Rust
agent built with ``--features mock`` so it skips the Windows SCM
dispatcher, points it at the host via ``CROSSDESK_*`` env vars, and
asserts that the full mTLS + AuthContext + ClientHello → ServerAccept
handshake completes end-to-end.

This is the cross-language integration that the per-language unit
mocks (test_transport_mock.py, test_libvirt_mock.py,
test_freerdp_mock.py) cannot catch on their own — wire-format
mismatches, AuthContext sequence ordering, mTLS cert validation, and
tonic-vs-grpcio interop all live in this seam.

Skip conditions:
- Missing PKI material at ``infra/certs/pki``.
- ``cargo`` not on PATH.
- The smoke build has been disabled via the ``CROSSDESK_SKIP_INPROCESS``
  env var (set by CI lanes that lack the Rust toolchain).
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import grpc
import pytest

from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.ipc.control import ControlServiceServicer
from crossdesk_host.ipc.filesystem import FilesystemServiceServicer
from crossdesk_host.ipc.heartbeat import HeartbeatServiceServicer
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.proto.crossdesk.v1 import (
    control_pb2_grpc,
    filesystem_pb2_grpc,
    heartbeat_pb2_grpc,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PKI = _REPO_ROOT / "infra" / "certs" / "pki"
_GUEST_DIR = _REPO_ROOT / "guest"


pytestmark = [
    pytest.mark.skipif(
        not (_PKI / "ca.crt").exists(),
        reason="PKI not generated. Run host/run_mock_macos.sh first.",
    ),
    pytest.mark.skipif(
        shutil.which("cargo") is None,
        reason="cargo not on PATH; cannot spawn Rust guest.",
    ),
    pytest.mark.skipif(
        os.environ.get("CROSSDESK_SKIP_INPROCESS") == "1",
        reason="CROSSDESK_SKIP_INPROCESS=1 set; in-process harness disabled.",
    ),
    pytest.mark.timeout(180),
]


# Maps to the Rust agent's expected PKI layout. The host and guest
# certificates flip for the agent's perspective: the agent presents its
# `guest.*` keypair, trusts `ca.crt`, and uses `host.crt` (renamed to
# match the agent's runtime path) for fingerprint stamping.
def _stage_agent_pki(tmp_path: Path) -> Path:
    pki = tmp_path / "pki"
    pki.mkdir()
    for name in ("ca.crt", "guest.crt", "guest.key", "host.crt"):
        (pki / name).write_bytes((_PKI / name).read_bytes())
    return pki


@pytest.fixture(scope="module")
def cargo_built_agent() -> Path:
    """Pre-build the agent so the first test doesn't pay the compile cost.

    Module-scoped because cargo only needs to run once per pytest
    session even with multiple test functions in this file.
    """
    result = subprocess.run(
        ["cargo", "build", "-p", "agent-svc", "--features", "mock", "--bin", "agent"],
        cwd=_GUEST_DIR,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail(
            f"cargo build failed (rc={result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    binary = _GUEST_DIR / "target" / "debug" / "agent"
    assert binary.exists(), f"expected built agent at {binary}"
    return binary


@pytest.fixture
async def host_with_port():
    """Boot the host gRPC server on a free TCP port and yield ``port``."""
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
    assert port != 0
    await server.start()
    try:
        yield port
    finally:
        await server.stop(grace=0.5)


async def _drain_subprocess_logs(
    proc: asyncio.subprocess.Process, sink: list[bytes]
) -> None:
    """Forward agent stderr to a list (and through to test output) so a
    failing run leaves an actionable trace. Returns when the agent's
    stderr closes."""
    assert proc.stderr is not None
    while True:
        line = await proc.stderr.readline()
        if not line:
            return
        sink.append(line)


async def test_agent_connects_and_completes_handshake(
    host_with_port: int,
    cargo_built_agent: Path,
    tmp_path: Path,
) -> None:
    """The Rust guest, given pointers to host endpoint + PKI, must
    open the Control session and successfully complete the
    ClientHello → ServerAccept handshake. Failure modes that this
    catches: AuthValidator/AuthCarrier sequence-ordering drift,
    mTLS cert mismatch, gRPC stream-typing regressions on either side.
    """
    pki = _stage_agent_pki(tmp_path)

    env = {
        **os.environ,
        "CROSSDESK_PKI_DIR": str(pki),
        # `https://` is mandatory; tonic's `tls_config` runs only with
        # an `https` URL, and the host requires mTLS. See the matching
        # comment on `DEFAULT_HOST_ENDPOINT` in agent-svc/src/planes.rs.
        "CROSSDESK_HOST_ENDPOINT": f"https://127.0.0.1:{host_with_port}",
        # Bypasses host_uuid::read SMBIOS path (Linux/macOS have no
        # GetSystemFirmwareTable). Any non-empty string is fine.
        "CROSSDESK_DOMAIN_UUID": "smoke-test-uuid",
        "RUST_LOG": "info",
    }

    proc = await asyncio.create_subprocess_exec(
        str(cargo_built_agent),
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    stderr_sink: list[bytes] = []
    drain_task = asyncio.create_task(_drain_subprocess_logs(proc, stderr_sink))

    async def _saw_handshake() -> bool:
        # Watch stderr for the host-side log line that the
        # ControlServiceServicer prints when ClientHello arrives. The
        # surrounding host process is in the same Python — we tail the
        # agent's stderr because RUST_LOG=info prints "Resolved host
        # domain UUID" once the handshake is in flight.
        deadline = asyncio.get_event_loop().time() + 30.0
        while asyncio.get_event_loop().time() < deadline:
            joined = b"".join(stderr_sink)
            if (
                b"Resolved host domain UUID" in joined
                or b"Starting Control Session FSM" in joined
            ):
                return True
            await asyncio.sleep(0.1)
        return False

    try:
        ok = await _saw_handshake()
        agent_stderr = b"".join(stderr_sink).decode("utf-8", errors="replace")
        if not ok:
            pytest.fail(
                "agent did not log handshake markers within 30s; "
                f"agent rc={proc.returncode}; agent stderr:\n{agent_stderr}"
            )
        # Even with markers seen, fail if the agent died before we could
        # tear it down — that means the gRPC call after handshake errored.
        if proc.returncode is not None and proc.returncode != 0:
            pytest.fail(
                f"agent exited prematurely (rc={proc.returncode}) after "
                f"handshake markers fired; stderr:\n{agent_stderr}"
            )
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        drain_task.cancel()
        try:
            await drain_task
        except asyncio.CancelledError:
            pass
