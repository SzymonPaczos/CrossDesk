"""Tests for display.session_starter.spawn_rail_with_auth_check."""

from __future__ import annotations

import pytest

from crossdesk_host.abstractions.freerdp import RailSession
from crossdesk_host.display.session_starter import (
    AuthHealthCheckFailed,
    spawn_rail_with_auth_check,
)
from crossdesk_host.installer.credentials import VmCredentials
from crossdesk_host.proto.crossdesk.v1 import control_pb2

Status = control_pb2.VerifyCredentialsResult.Status


class _StubInvocation:
    def __init__(self) -> None:
        self.spawned: list[list[str]] = []

    def spawn_rail(self, argv: list[str]) -> RailSession:
        self.spawned.append(argv)
        return RailSession(pid=1234, argv=list(argv))

    def terminate(self, _session: RailSession) -> None:  # pragma: no cover
        pass


class _StubCoord:
    def __init__(self, status: int, detail: str = "") -> None:
        self._status = status
        self._detail = detail
        self.calls: list[tuple[str, str]] = []

    async def verify(
        self, username: str, password: str, domain: str = "", timeout: float = 5.0
    ) -> control_pb2.VerifyCredentialsResult:
        self.calls.append((username, password))
        return control_pb2.VerifyCredentialsResult(
            request_id="x",
            status=self._status,
            detail=self._detail,
            win32_error=0,
        )


@pytest.mark.asyncio
async def test_spawn_proceeds_when_verify_ok() -> None:
    inv = _StubInvocation()
    coord = _StubCoord(Status.STATUS_OK)
    session = await spawn_rail_with_auth_check(
        inv, coord, ["xfreerdp", "/v:vsock"], creds=VmCredentials("u", "p")
    )
    assert session.pid == 1234
    assert inv.spawned == [["xfreerdp", "/v:vsock"]]
    assert coord.calls == [("u", "p")]


@pytest.mark.asyncio
async def test_spawn_blocked_on_bad_credentials() -> None:
    inv = _StubInvocation()
    coord = _StubCoord(Status.STATUS_FAIL_BAD_CREDENTIALS, detail="logon failed")
    with pytest.raises(AuthHealthCheckFailed) as exc_info:
        await spawn_rail_with_auth_check(
            inv, coord, ["xfreerdp"], creds=VmCredentials("u", "p")
        )
    assert exc_info.value.result.status_label == "bad_credentials"
    assert "repair" in exc_info.value.result.repair_hint
    assert inv.spawned == []  # never reached


@pytest.mark.asyncio
async def test_spawn_blocked_surfaces_lockout_hint() -> None:
    inv = _StubInvocation()
    coord = _StubCoord(Status.STATUS_FAIL_ACCOUNT_LOCKED)
    with pytest.raises(AuthHealthCheckFailed) as exc_info:
        await spawn_rail_with_auth_check(
            inv, coord, ["xfreerdp"], creds=VmCredentials("u", "p")
        )
    assert "lock" in exc_info.value.result.repair_hint
    assert inv.spawned == []


@pytest.mark.asyncio
async def test_spawn_blocked_surfaces_expired_hint() -> None:
    inv = _StubInvocation()
    coord = _StubCoord(Status.STATUS_FAIL_PASSWORD_EXPIRED)
    with pytest.raises(AuthHealthCheckFailed) as exc_info:
        await spawn_rail_with_auth_check(
            inv, coord, ["xfreerdp"], creds=VmCredentials("u", "p")
        )
    assert "rotate" in exc_info.value.result.repair_hint
    assert inv.spawned == []


@pytest.mark.asyncio
async def test_spawn_blocked_surfaces_unavailable_hint() -> None:
    inv = _StubInvocation()
    coord = _StubCoord(Status.STATUS_UNAVAILABLE)
    with pytest.raises(AuthHealthCheckFailed) as exc_info:
        await spawn_rail_with_auth_check(
            inv, coord, ["xfreerdp"], creds=VmCredentials("u", "p")
        )
    assert "doctor" in exc_info.value.result.repair_hint
    assert inv.spawned == []
