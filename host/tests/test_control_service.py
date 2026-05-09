"""ControlService FSM and per-frame auth enforcement tests.

Phase 3 surface: validates the HANDSHAKE → READY → APP_RUNNING → DRAINING
transitions over the OpenSession bidi stream, plus the invariant that every
incoming frame goes through AuthValidator before payload dispatch.
"""

from __future__ import annotations

from typing import AsyncIterator, List
from unittest.mock import AsyncMock, MagicMock

import grpc
import pytest

from crossdesk_host.display.rail_manager import RailManager
from crossdesk_host.ipc.control import ControlServiceServicer
from crossdesk_host.proto.crossdesk.v1 import common_pb2, control_pb2

from tests.conftest import AbortError, FakeServicerContext


def _auth() -> common_pb2.AuthContext:
    return common_pb2.AuthContext(
        peer_cert_fingerprint="ff" * 32, stream_nonce=b"n", sequence=1
    )


def _hello() -> control_pb2.ClientFrame:
    return control_pb2.ClientFrame(
        auth=_auth(),
        hello=control_pb2.ClientHello(
            host_version="v0.1.0",
            supported_features=["rail.v1", "virtiofs.jit"],
        ),
    )


def _launch(
    req_id: str = "req-1", path: str = "C:\\Windows\\notepad.exe"
) -> control_pb2.ClientFrame:
    return control_pb2.ClientFrame(
        auth=_auth(),
        launch=control_pb2.AppLaunchRequest(
            request_id=req_id, executable_guest_path=path
        ),
    )


def _rail_create(hwnd: int = 0x100) -> control_pb2.ClientFrame:
    return control_pb2.ClientFrame(
        auth=_auth(),
        rail_event=control_pb2.RailWindowEvent(
            window_id=hwnd,
            kind=control_pb2.RailWindowEvent.Kind.KIND_CREATED,
            title="App",
        ),
    )


def _terminate() -> control_pb2.ClientFrame:
    return control_pb2.ClientFrame(
        auth=_auth(),
        terminate=control_pb2.SessionTerminate(
            reason=control_pb2.SessionTerminate.Reason.REASON_USER_QUIT
        ),
    )


async def _async_iter(
    frames: List[control_pb2.ClientFrame],
) -> AsyncIterator[control_pb2.ClientFrame]:
    for f in frames:
        yield f


async def _drive(
    frames: List[control_pb2.ClientFrame],
    *,
    rail_manager: RailManager | None = None,
    auth_raises: Exception | None = None,
):
    """Run OpenSession against a scripted client frame sequence and collect outputs."""
    auth_validator = MagicMock()
    auth_validator.verify_auth_context = AsyncMock()
    if auth_raises is not None:
        auth_validator.verify_auth_context.side_effect = auth_raises
    servicer = ControlServiceServicer(auth_validator, rail_manager=rail_manager)
    ctx = FakeServicerContext()
    out: List[control_pb2.ServerFrame] = []
    try:
        async for sf in servicer.OpenSession(_async_iter(frames), ctx):
            out.append(sf)
    except AbortError:
        # Abort terminates the stream; tests that expect it assert via ctx state.
        pass
    return out, ctx, auth_validator


# ---------------------------------------------------------------------------
# Handshake
# ---------------------------------------------------------------------------


async def test_hello_yields_server_accept() -> None:
    out, _, _ = await _drive([_hello()])
    assert len(out) == 1
    assert out[0].WhichOneof("payload") == "accept"
    assert out[0].accept.guest_version == "v0.1.0"
    assert "rail.v1" in list(out[0].accept.negotiated_features)


async def test_first_frame_other_than_hello_aborts_failed_precondition() -> None:
    out, ctx, _ = await _drive([_launch()])
    assert ctx.aborted
    assert ctx.abort_code == grpc.StatusCode.FAILED_PRECONDITION
    assert out == []


# ---------------------------------------------------------------------------
# READY state — launch & rail event
# ---------------------------------------------------------------------------


async def test_launch_in_ready_yields_app_launched_with_request_id() -> None:
    out, _, _ = await _drive([_hello(), _launch(req_id="abc-123")])
    payloads = [sf.WhichOneof("payload") for sf in out]
    assert payloads == ["accept", "launched"]
    assert out[1].launched.request_id == "abc-123"
    assert out[1].launched.process_id == 9999


async def test_rail_event_in_ready_is_forwarded_to_rail_manager() -> None:
    rm = RailManager()
    await _drive([_hello(), _rail_create(hwnd=0xCAFE)], rail_manager=rm)
    assert 0xCAFE in rm._windows
    assert rm._windows[0xCAFE]["title"] == "App"


async def test_terminate_yields_session_closed_and_stops_stream() -> None:
    out, _, _ = await _drive(
        [_hello(), _terminate(), _launch()]
    )  # launch never reached
    payloads = [sf.WhichOneof("payload") for sf in out]
    assert payloads == ["accept", "closed"]
    assert out[1].closed.reason == control_pb2.SessionTerminate.Reason.REASON_USER_QUIT


# ---------------------------------------------------------------------------
# Per-frame auth enforcement
# ---------------------------------------------------------------------------


async def test_auth_validator_called_for_every_frame() -> None:
    _, _, validator = await _drive([_hello(), _launch(), _rail_create()])
    assert validator.verify_auth_context.call_count == 3


async def test_auth_failure_on_any_frame_aborts_stream() -> None:
    abort = AbortError(grpc.StatusCode.UNAUTHENTICATED, "fingerprint mismatch")
    out, ctx, validator = await _drive(
        [_hello(), _launch()],
        auth_raises=abort,
    )
    # First frame's auth check raises → no payload processed → no ServerFrame yielded.
    assert validator.verify_auth_context.call_count == 1
    assert out == []
