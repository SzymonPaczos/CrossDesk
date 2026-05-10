"""Unit tests for VerifyCoordinator request/response correlation."""

from __future__ import annotations

import asyncio
from typing import Optional

import pytest

from crossdesk_host.ipc.verify_coordinator import (
    NoActiveSession,
    VerifyCoordinator,
)
from crossdesk_host.proto.crossdesk.v1 import control_pb2


def _ok_result(request_id: str) -> control_pb2.VerifyCredentialsResult:
    return control_pb2.VerifyCredentialsResult(
        request_id=request_id,
        status=control_pb2.VerifyCredentialsResult.Status.STATUS_OK,
        detail="ok",
        win32_error=0,
    )


@pytest.mark.asyncio
async def test_verify_without_session_raises_no_active_session() -> None:
    coord = VerifyCoordinator()
    with pytest.raises(NoActiveSession):
        await coord.verify("user", "pass")


@pytest.mark.asyncio
async def test_verify_happy_path_resolves_with_delivered_result() -> None:
    coord = VerifyCoordinator()
    outbound: asyncio.Queue[Optional[control_pb2.ServerFrame]] = asyncio.Queue()
    coord.register_session(outbound)

    verify_task = asyncio.create_task(coord.verify("crossdesk", "test123"))
    # Pull the request off the wire-side queue, then deliver matching reply.
    frame = await asyncio.wait_for(outbound.get(), timeout=1.0)
    assert frame is not None
    assert frame.WhichOneof("payload") == "verify_credentials"
    assert frame.verify_credentials.username == "crossdesk"
    assert frame.verify_credentials.password == "test123"
    request_id = frame.verify_credentials.request_id

    coord.deliver(_ok_result(request_id))
    result = await asyncio.wait_for(verify_task, timeout=1.0)
    assert result.status == control_pb2.VerifyCredentialsResult.Status.STATUS_OK
    assert result.request_id == request_id


@pytest.mark.asyncio
async def test_request_id_correlation_with_concurrent_verifies() -> None:
    coord = VerifyCoordinator()
    outbound: asyncio.Queue[Optional[control_pb2.ServerFrame]] = asyncio.Queue()
    coord.register_session(outbound)

    task_a = asyncio.create_task(coord.verify("user_a", "pass_a"))
    task_b = asyncio.create_task(coord.verify("user_b", "pass_b"))

    frame_a = await asyncio.wait_for(outbound.get(), timeout=1.0)
    frame_b = await asyncio.wait_for(outbound.get(), timeout=1.0)
    assert frame_a is not None and frame_b is not None
    rid_a = frame_a.verify_credentials.request_id
    rid_b = frame_b.verify_credentials.request_id
    assert rid_a != rid_b

    # Deliver in REVERSE order — proves correlation isn't FIFO-based.
    bad = control_pb2.VerifyCredentialsResult(
        request_id=rid_b,
        status=control_pb2.VerifyCredentialsResult.Status.STATUS_FAIL_BAD_CREDENTIALS,
        detail="bad",
        win32_error=1326,
    )
    coord.deliver(bad)
    coord.deliver(_ok_result(rid_a))

    res_a = await asyncio.wait_for(task_a, timeout=1.0)
    res_b = await asyncio.wait_for(task_b, timeout=1.0)
    assert res_a.status == control_pb2.VerifyCredentialsResult.Status.STATUS_OK
    assert res_b.status == control_pb2.VerifyCredentialsResult.Status.STATUS_FAIL_BAD_CREDENTIALS


@pytest.mark.asyncio
async def test_verify_timeout_raises() -> None:
    coord = VerifyCoordinator()
    outbound: asyncio.Queue[Optional[control_pb2.ServerFrame]] = asyncio.Queue()
    coord.register_session(outbound)
    with pytest.raises(asyncio.TimeoutError):
        await coord.verify("user", "pass", timeout=0.05)
    # After timeout, internal pending map cleaned up; subsequent verify
    # with a slow reply must not double-resolve the timed-out future.
    # Drain and discard the lingering frame from the first verify.
    _ = await outbound.get()


@pytest.mark.asyncio
async def test_session_unregister_cancels_pending_with_no_active_session() -> None:
    coord = VerifyCoordinator()
    outbound: asyncio.Queue[Optional[control_pb2.ServerFrame]] = asyncio.Queue()
    coord.register_session(outbound)

    task = asyncio.create_task(coord.verify("user", "pass", timeout=10.0))
    _ = await asyncio.wait_for(outbound.get(), timeout=1.0)  # consume request

    coord.unregister_session(outbound)

    with pytest.raises(NoActiveSession):
        await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_deliver_unknown_request_id_is_noop(caplog: pytest.LogCaptureFixture) -> None:
    coord = VerifyCoordinator()
    # No raise, no crash — just a warning log.
    coord.deliver(_ok_result("ghost-request"))
    assert any("unknown request_id" in r.getMessage() for r in caplog.records)
