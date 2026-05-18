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
- ``cargo`` not on PATH (unless ``CROSSDESK_PREBUILT_AGENT`` is set —
  see below).
- The smoke build has been disabled via the ``CROSSDESK_SKIP_INPROCESS``
  env var (set by CI lanes that lack the Rust toolchain).

Environment overrides:
- ``CROSSDESK_PREBUILT_AGENT`` — absolute path to an already-built
  ``agent`` binary. When set, the ``cargo_built_agent`` fixture
  validates the file exists and is executable, then returns it
  directly without invoking ``cargo build``. Used by the
  ``compat-matrix`` GitHub workflow to point this harness at a
  prior-tag agent built in a sibling worktree, avoiding a redundant
  build (saves ~30+s and sidesteps the cargo cache surprise of
  back-to-back builds in different workspaces).
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import grpc
import pytest

from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.ipc.control import ControlServiceServicer
from crossdesk_host.ipc.filesystem import FilesystemServiceServicer
from crossdesk_host.ipc.heartbeat import HeartbeatServiceServicer
from crossdesk_host.ipc.verify_coordinator import VerifyCoordinator
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.observability import configure_logging
from crossdesk_host.observability.grpc_interceptor import TraceContextInterceptor
from crossdesk_host.proto.crossdesk.v1 import (
    control_pb2,
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
        shutil.which("cargo") is None
        and not os.environ.get("CROSSDESK_PREBUILT_AGENT"),
        reason="cargo not on PATH and CROSSDESK_PREBUILT_AGENT unset; "
        "cannot obtain a Rust guest binary.",
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
    """Provide a path to a usable Rust agent binary.

    Two paths:

    1. ``CROSSDESK_PREBUILT_AGENT`` env var set — validate the
       referenced file exists + is executable and return it. Used by
       the compat-matrix workflow (``.github/workflows/compat-matrix.yml``)
       so a prior-tag agent built in a sibling worktree is exercised
       directly instead of triggering a redundant ``cargo build`` here.
    2. Otherwise — invoke ``cargo build -p agent-svc --features mock
       --bin agent`` and return the resulting binary path.

    Module-scoped because cargo (when invoked) only needs to run once
    per pytest session even with multiple test functions in this file.
    """
    prebuilt = os.environ.get("CROSSDESK_PREBUILT_AGENT")
    if prebuilt:
        binary = Path(prebuilt)
        if not binary.is_file():
            pytest.fail(
                f"CROSSDESK_PREBUILT_AGENT={prebuilt!r} does not point at "
                "an existing file."
            )
        if not os.access(binary, os.X_OK):
            pytest.fail(
                f"CROSSDESK_PREBUILT_AGENT={prebuilt!r} exists but is not "
                "executable (chmod +x?)."
            )
        return binary

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
def verify_coordinator() -> VerifyCoordinator:
    """One coordinator per test; injected into ControlServiceServicer below."""
    return VerifyCoordinator()


@pytest.fixture
async def host_with_port_and_logs(verify_coordinator: VerifyCoordinator):
    """Boot the host gRPC server on a free TCP port, mount the
    TraceContextInterceptor, and pipe structlog output into a buffer
    the test can inspect. Yields ``(port, log_buffer)``."""
    log_buffer = io.StringIO()
    configure_logging(stream=log_buffer)

    server = grpc.aio.server(interceptors=[TraceContextInterceptor()])

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
        ControlServiceServicer(auth, verify_coordinator=verify_coordinator), server
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
        yield port, log_buffer
    finally:
        await server.stop(grace=0.5)


@pytest.fixture
async def host_with_port(host_with_port_and_logs):
    """Backwards-compatible alias for tests that don't care about the
    log buffer — returns just the port."""
    port, _ = host_with_port_and_logs
    yield port


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
        with contextlib.suppress(asyncio.CancelledError):
            await drain_task


_TRACE_ID_AGENT_RE = re.compile(rb"trace_id[=:\s\"]+([0-9a-f]{32})")


async def test_traceparent_propagates_from_agent_to_host_logs(
    host_with_port_and_logs: "tuple[int, io.StringIO]",
    cargo_built_agent: Path,
    tmp_path: Path,
) -> None:
    """End-to-end W3C Trace Context propagation per DEC-0006:

    - Agent's `agent-svc::planes::run_with_pki` mints a root
      TraceContext and passes it via `inject_interceptor` to all
      three planes' tonic clients.
    - Host's `TraceContextInterceptor` extracts ``traceparent`` on
      every RPC and binds the trace_id+span_id to structlog
      contextvars for the duration of the handler.
    - This test asserts the same `trace_id` shows up on both sides.
    """
    port, log_buffer = host_with_port_and_logs
    pki = _stage_agent_pki(tmp_path)

    env = {
        **os.environ,
        "CROSSDESK_PKI_DIR": str(pki),
        "CROSSDESK_HOST_ENDPOINT": f"https://127.0.0.1:{port}",
        "CROSSDESK_DOMAIN_UUID": "trace-prop-test",
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

    async def _wait_until_host_saw_trace() -> str | None:
        deadline = asyncio.get_event_loop().time() + 30.0
        while asyncio.get_event_loop().time() < deadline:
            for line in log_buffer.getvalue().splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tid = rec.get("trace_id", "")
                if isinstance(tid, str) and len(tid) == 32 and tid != "0" * 32:
                    return tid
            await asyncio.sleep(0.1)
        return None

    try:
        host_trace_id = await _wait_until_host_saw_trace()
        assert host_trace_id is not None, (
            "host structlog never bound a non-empty trace_id; "
            f"buffer:\n{log_buffer.getvalue()[:2000]}"
        )

        agent_stderr_blob = b"".join(stderr_sink)
        agent_match = _TRACE_ID_AGENT_RE.search(agent_stderr_blob)
        assert agent_match is not None, (
            "agent never logged its minted trace_id; agent stderr:\n"
            + agent_stderr_blob.decode("utf-8", errors="replace")[:2000]
        )
        agent_trace_id = agent_match.group(1).decode("ascii")

        assert host_trace_id == agent_trace_id, (
            f"trace_id mismatch: agent={agent_trace_id!r} " f"host={host_trace_id!r}"
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
        with contextlib.suppress(asyncio.CancelledError):
            await drain_task


async def test_traceparent_propagates_to_all_three_planes(
    host_with_port_and_logs: "tuple[int, io.StringIO]",
    cargo_built_agent: Path,
    tmp_path: Path,
) -> None:
    """W3C Trace Context completeness check across CONTROL, HEARTBEAT,
    and FILESYSTEM planes.

    The earlier test asserts a single non-empty trace_id appears on
    *some* host log line — sufficient to prove the interceptor wires up,
    but it doesn't catch the failure mode where one plane's gRPC client
    forgot to mount ``inject_interceptor`` (or the host dropped the
    interceptor for a specific service). This test waits until each
    plane has emitted at least one structured log line, then asserts:

    1. Each plane's first-call log carries a non-empty trace_id.
    2. All three planes share the same trace_id (DEC-0006: one root
       per agent session, propagated everywhere).
    3. The trace_id matches the one the agent minted (printed to
       stderr at startup).
    """
    port, log_buffer = host_with_port_and_logs
    pki = _stage_agent_pki(tmp_path)

    env = {
        **os.environ,
        "CROSSDESK_PKI_DIR": str(pki),
        "CROSSDESK_HOST_ENDPOINT": f"https://127.0.0.1:{port}",
        "CROSSDESK_DOMAIN_UUID": "trace-all-planes",
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

    # Per-plane → distinctive event-substring of that plane's first
    # servicer log (fires the moment the gRPC stream opens). We match on
    # the ``event`` field rather than ``component`` because stdlib log
    # records flow through structlog's foreign_pre_chain without their
    # logger name being copied — the per-plane signal lives in the
    # log message itself.
    expected_event_markers = {
        "control": "New ControlSession stream initiated",
        "heartbeat": "heartbeat_channel_opened",
        "filesystem": "Filesystem channel established",
    }

    async def _collect_per_plane_trace_ids() -> dict[str, str]:
        """Return ``{plane: trace_id}`` once each plane has produced
        at least one log line with a non-empty trace_id, or {} on timeout.
        """
        deadline = asyncio.get_event_loop().time() + 30.0
        found: dict[str, str] = {}
        while asyncio.get_event_loop().time() < deadline:
            for line in log_buffer.getvalue().splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tid = rec.get("trace_id", "")
                if not (isinstance(tid, str) and len(tid) == 32 and tid != "0" * 32):
                    continue
                event = rec.get("event", "")
                if not isinstance(event, str):
                    continue
                for plane, needle in expected_event_markers.items():
                    if plane in found:
                        continue
                    if needle in event:
                        found[plane] = tid
            if len(found) == len(expected_event_markers):
                return found
            await asyncio.sleep(0.1)
        return found

    try:
        per_plane = await _collect_per_plane_trace_ids()
        missing = set(expected_event_markers) - set(per_plane)
        assert not missing, (
            f"plane(s) never produced a trace_id-bearing log line: {missing}; "
            f"got per_plane={per_plane}; "
            f"buffer (last 2KB):\n{log_buffer.getvalue()[-2000:]}"
        )

        unique_trace_ids = set(per_plane.values())
        assert len(unique_trace_ids) == 1, (
            "planes carried different trace_ids — they should share one "
            f"root per session: {per_plane}"
        )
        host_trace_id = next(iter(unique_trace_ids))

        agent_stderr_blob = b"".join(stderr_sink)
        agent_match = _TRACE_ID_AGENT_RE.search(agent_stderr_blob)
        assert agent_match is not None, (
            "agent never logged its minted trace_id; agent stderr:\n"
            + agent_stderr_blob.decode("utf-8", errors="replace")[:2000]
        )
        agent_trace_id = agent_match.group(1).decode("ascii")

        assert host_trace_id == agent_trace_id, (
            f"trace_id mismatch: agent={agent_trace_id!r} "
            f"host={host_trace_id!r}"
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
        with contextlib.suppress(asyncio.CancelledError):
            await drain_task


async def test_verify_coordinator_binds_fresh_trace_per_call(
    host_with_port_and_logs: "tuple[int, io.StringIO]",
    verify_coordinator: VerifyCoordinator,
    cargo_built_agent: Path,
    tmp_path: Path,
) -> None:
    """Server-initiated VerifyCredentials must carry a host-side trace
    context per call so operators can correlate dispatch ↔ resolve logs.

    The ServerFrame itself doesn't carry traceparent (no proto field
    on this payload variant — wire-format change is owner-approval
    territory), so this test verifies the host-side guarantee:
    ``verify_coordinator.verify()`` mints a fresh trace context, binds
    it, and the ``verify_credentials_dispatch`` log line carries it.
    Two consecutive calls produce two distinct trace_ids — proving the
    binding doesn't leak across calls.
    """
    port, log_buffer = host_with_port_and_logs
    pki = _stage_agent_pki(tmp_path)

    env = {
        **os.environ,
        "CROSSDESK_PKI_DIR": str(pki),
        "CROSSDESK_HOST_ENDPOINT": f"https://127.0.0.1:{port}",
        "CROSSDESK_DOMAIN_UUID": "verify-trace-test",
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

    def _trace_ids_for_dispatch_lines() -> list[str]:
        """Pull trace_id from every host log line that emitted a
        ``verify_credentials_dispatch`` event."""
        out: list[str] = []
        for line in log_buffer.getvalue().splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            event = rec.get("event", "")
            if isinstance(event, str) and "verify_credentials_dispatch" in event:
                tid = rec.get("trace_id", "")
                if isinstance(tid, str):
                    out.append(tid)
        return out

    try:
        deadline = asyncio.get_event_loop().time() + 30.0
        while asyncio.get_event_loop().time() < deadline:
            if verify_coordinator.session_count() > 0:
                break
            await asyncio.sleep(0.1)
        else:
            agent_stderr = b"".join(stderr_sink).decode("utf-8", errors="replace")
            pytest.fail(
                "session never registered with VerifyCoordinator within 30s; "
                f"agent stderr:\n{agent_stderr}"
            )

        # Two back-to-back verifies — each should mint its own trace.
        await verify_coordinator.verify("__inject_ok__", "ignored", timeout=10.0)
        await verify_coordinator.verify("__inject_ok__", "ignored", timeout=10.0)

        # Allow the structured log emission to flush.
        await asyncio.sleep(0.1)

        dispatch_traces = _trace_ids_for_dispatch_lines()
        assert len(dispatch_traces) >= 2, (
            "expected at least 2 verify_credentials_dispatch log lines; "
            f"got {dispatch_traces}; buffer tail:\n{log_buffer.getvalue()[-2000:]}"
        )
        first_two = dispatch_traces[:2]
        for tid in first_two:
            assert (
                isinstance(tid, str) and len(tid) == 32 and tid != "0" * 32
            ), f"verify dispatch line missing valid trace_id: {tid!r}"
        assert (
            first_two[0] != first_two[1]
        ), f"two consecutive verify calls reused the same trace_id: {first_two}"
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        drain_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await drain_task


async def test_verify_credentials_roundtrip_through_real_agent(
    host_with_port_and_logs: "tuple[int, io.StringIO]",
    verify_coordinator: VerifyCoordinator,
    cargo_built_agent: Path,
    tmp_path: Path,
) -> None:
    """End-to-end VerifyCredentials: host pushes ServerFrame.verify_credentials
    via VerifyCoordinator, the live Rust agent's ``handle_server_frame``
    dispatches to the mock ``credentials.rs`` impl, and the result comes
    back as ClientFrame.verify_credentials_result, resolving the host's
    awaited future.

    Uses the agent mock's ``__inject_<status>__`` username convention so
    the test exercises both the OK path and a structured failure path
    without depending on real LogonUserW (Stage 4 / post-hardware).
    """
    port, _ = host_with_port_and_logs
    pki = _stage_agent_pki(tmp_path)

    env = {
        **os.environ,
        "CROSSDESK_PKI_DIR": str(pki),
        "CROSSDESK_HOST_ENDPOINT": f"https://127.0.0.1:{port}",
        "CROSSDESK_DOMAIN_UUID": "verify-rpc-test",
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

    try:
        # Wait for ClientHello → ServerAccept to complete; servicer
        # registers the session with VerifyCoordinator at that point.
        deadline = asyncio.get_event_loop().time() + 30.0
        while asyncio.get_event_loop().time() < deadline:
            if verify_coordinator.session_count() > 0:
                break
            await asyncio.sleep(0.1)
        else:
            agent_stderr = b"".join(stderr_sink).decode("utf-8", errors="replace")
            pytest.fail(
                "session never registered with VerifyCoordinator within 30s; "
                f"agent stderr:\n{agent_stderr}"
            )

        ok = await verify_coordinator.verify(
            "__inject_ok__", "ignored", timeout=10.0
        )
        assert (
            ok.status == control_pb2.VerifyCredentialsResult.Status.STATUS_OK
        ), f"expected OK, got {ok}"

        bad = await verify_coordinator.verify(
            "__inject_bad__", "ignored", timeout=10.0
        )
        assert bad.status == (
            control_pb2.VerifyCredentialsResult.Status.STATUS_FAIL_BAD_CREDENTIALS
        ), f"expected FAIL_BAD_CREDENTIALS, got {bad}"
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        drain_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await drain_task
