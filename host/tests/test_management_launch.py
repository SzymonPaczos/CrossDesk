"""ManagementService.Launch RPC — RAIL spawn wiring.

The spawn boundary (``spawn_rail_with_auth_check``) and app/credential
lookups are monkeypatched so every Launch branch — backend-missing,
unknown app, no credentials, auth-failure, no-guest, success — is
exercised deterministically without a guest, libvirt, or FreeRDP binary.
"""

from __future__ import annotations

from typing import Optional
from unittest.mock import MagicMock

import pytest

from crossdesk_host.abstractions.freerdp import RailSession
from crossdesk_host.catalog.schema import AppEntry
from crossdesk_host.display.session_starter import AuthHealthCheckFailed
from crossdesk_host.freerdp.mock import MockFreeRDPInvocation
from crossdesk_host.installer.credentials import VerifyResult, VmCredentials
from crossdesk_host.ipc import management
from crossdesk_host.ipc.management import ManagementServiceServicer, MgmtState
from crossdesk_host.ipc.verify_coordinator import NoActiveSession, VerifyCoordinator
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.proto.crossdesk.v1 import mgmt_pb2
from crossdesk_host.watchdog import HeartbeatFsm

_APP = AppEntry(app_id="notepad", name="Notepad", win_executable="C:\\Windows\\notepad.exe")
_CREDS = VmCredentials(username="Admin", password="hunter2")


@pytest.fixture
def context() -> MagicMock:
    ctx = MagicMock()
    ctx.cancelled.return_value = False
    return ctx


def _backend_servicer() -> ManagementServiceServicer:
    return ManagementServiceServicer(
        MgmtState(fsm=HeartbeatFsm()),
        LibvirtControllerMock(),
        freerdp=MockFreeRDPInvocation(),
        verify_coordinator=VerifyCoordinator(),
    )


def _patch_app_and_creds(
    monkeypatch: pytest.MonkeyPatch,
    *,
    app: Optional[AppEntry] = _APP,
    creds: Optional[VmCredentials] = _CREDS,
) -> None:
    monkeypatch.setattr(management, "find_app", lambda app_id, path=None: app)
    monkeypatch.setattr(management.credentials, "load", lambda path=None: creds)


async def test_launch_unknown_app(monkeypatch: pytest.MonkeyPatch, context: MagicMock) -> None:
    _patch_app_and_creds(monkeypatch, app=None)
    resp = await _backend_servicer().Launch(mgmt_pb2.LaunchRequest(app_id="ghost"), context)
    assert not resp.ok
    assert "unknown app_id" in resp.error


async def test_launch_no_credentials(monkeypatch: pytest.MonkeyPatch, context: MagicMock) -> None:
    _patch_app_and_creds(monkeypatch, creds=None)
    resp = await _backend_servicer().Launch(mgmt_pb2.LaunchRequest(app_id="notepad"), context)
    assert not resp.ok
    assert "credentials" in resp.error


async def test_launch_success_spawns_and_tracks(
    monkeypatch: pytest.MonkeyPatch, context: MagicMock
) -> None:
    _patch_app_and_creds(monkeypatch)
    seen: dict[str, object] = {}

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0):  # type: ignore[no-untyped-def]
        seen["argv"] = argv
        return RailSession(pid=42, argv=list(argv))

    monkeypatch.setattr(management, "spawn_rail_with_auth_check", fake_spawn)

    servicer = _backend_servicer()
    resp = await servicer.Launch(mgmt_pb2.LaunchRequest(app_id="notepad"), context)

    assert resp.ok
    assert resp.request_id == "rail-42"
    # argv carries the RAIL program clause built from the resolved app.
    argv = seen["argv"]
    assert isinstance(argv, list)
    assert any("notepad.exe" in part for part in argv)
    assert any(part == "/wm-class:crossdesk-notepad" for part in argv)
    # Session tracked + activity recorded.
    assert [s.pid for s in servicer._sessions] == [42]
    kinds = [a.kind for a in servicer.state.recent_activity]
    assert mgmt_pb2.RecentActivity.Kind.KIND_APP_LAUNCHED in kinds


async def test_launch_auth_failure_surfaces_repair_hint(
    monkeypatch: pytest.MonkeyPatch, context: MagicMock
) -> None:
    _patch_app_and_creds(monkeypatch)
    hint = "run `crossdesk vm credentials repair`"

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0):  # type: ignore[no-untyped-def]
        raise AuthHealthCheckFailed(
            VerifyResult(
                ok=False,
                status_label="bad-password",
                detail="logon denied",
                repair_hint=hint,
                win32_error=1326,
            )
        )

    monkeypatch.setattr(management, "spawn_rail_with_auth_check", fake_spawn)

    resp = await _backend_servicer().Launch(mgmt_pb2.LaunchRequest(app_id="notepad"), context)
    assert not resp.ok
    assert resp.error == hint


async def test_launch_no_active_session(monkeypatch: pytest.MonkeyPatch, context: MagicMock) -> None:
    _patch_app_and_creds(monkeypatch)

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0):  # type: ignore[no-untyped-def]
        raise NoActiveSession("no active guest session for verify")

    monkeypatch.setattr(management, "spawn_rail_with_auth_check", fake_spawn)

    resp = await _backend_servicer().Launch(mgmt_pb2.LaunchRequest(app_id="notepad"), context)
    assert not resp.ok
    assert "no guest session" in resp.error


# ---------------------------------------------------------------------------
# Launch by raw Windows .exe path (any installed program, no catalog entry)
# ---------------------------------------------------------------------------


def test_spec_from_exe_path_drive_letter() -> None:
    spec = management._spec_from_exe_path("C:\\Games\\RobinHood\\RobinHood.exe")
    assert spec is not None
    assert spec.executable_guest_path == "C:\\Games\\RobinHood\\RobinHood.exe"
    assert spec.app_id == "robinhood"  # drives WM_CLASS / grouping
    assert spec.display_name == "RobinHood"


def test_spec_from_exe_path_unc() -> None:
    spec = management._spec_from_exe_path("\\\\server\\share\\setup.exe")
    assert spec is not None
    assert spec.app_id == "setup"


def test_spec_from_exe_path_rejects_plain_id_and_non_exe() -> None:
    assert management._spec_from_exe_path("notepad") is None
    assert management._spec_from_exe_path("ghost") is None
    assert management._spec_from_exe_path("C:\\Windows\\System32") is None  # no .exe
    assert management._spec_from_exe_path("/usr/bin/foo") is None  # not a Windows path


async def test_launch_by_exe_path_spawns(
    monkeypatch: pytest.MonkeyPatch, context: MagicMock
) -> None:
    # Not in the catalog, but a real Windows .exe path → launches directly.
    _patch_app_and_creds(monkeypatch, app=None)
    seen: dict[str, object] = {}

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0):  # type: ignore[no-untyped-def]
        seen["argv"] = argv
        return RailSession(pid=77, argv=list(argv))

    monkeypatch.setattr(management, "spawn_rail_with_auth_check", fake_spawn)

    resp = await _backend_servicer().Launch(
        mgmt_pb2.LaunchRequest(app_id="C:\\Program Files\\Game\\game.exe"), context
    )
    assert resp.ok
    argv = seen["argv"]
    assert isinstance(argv, list)
    assert any("game.exe" in part for part in argv)
    assert any(part == "/wm-class:crossdesk-game" for part in argv)
