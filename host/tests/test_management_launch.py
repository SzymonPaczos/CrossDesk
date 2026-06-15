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
from crossdesk_host.config.peripherals import PeripheralsConfig
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


@pytest.fixture(autouse=True)
def _isolate_peripherals(monkeypatch: pytest.MonkeyPatch) -> None:
    # The Launch path loads peripherals.toml fresh per launch. Default every
    # test in this module to an all-off config so the suite never depends on
    # the developer's real ~/.config/crossdesk/peripherals.toml (which on a
    # dev box may enable the shared folder and change the produced argv).
    # Tests that exercise the shared folder re-patch via _patch_peripherals.
    monkeypatch.setattr(
        "crossdesk_host.config.peripherals.load_peripherals_config",
        lambda path=None: PeripheralsConfig(),
    )


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


# ---------------------------------------------------------------------------
# Shared folder → RemoteApp working directory (Save/Open dialog default)
# ---------------------------------------------------------------------------


def _patch_peripherals(monkeypatch: pytest.MonkeyPatch, cfg: PeripheralsConfig) -> None:
    # _peripheral_flags imports load_peripherals_config at call time from the
    # source module, so patch it there.
    monkeypatch.setattr(
        "crossdesk_host.config.peripherals.load_peripherals_config",
        lambda path=None: cfg,
    )


def test_peripheral_flags_workdir_when_shared_folder_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    share_dir = tmp_path / "CrossDesk-Shared"
    _patch_peripherals(
        monkeypatch,
        PeripheralsConfig(
            shared_folder_enabled=True, shared_folder_path=str(share_dir)
        ),
    )
    flags, workdir = _backend_servicer()._peripheral_flags()
    assert any(f.startswith("/drive:CrossDesk,") for f in flags)
    # Drive letter, not the UNC: Windows ignores a UNC working directory and
    # falls back to System32, so the launcher points the app at Z:\ (mapped to
    # the share by the guest logon step).
    assert workdir == "Z:\\"
    # Folder is created on demand so the redirect has something to mount.
    assert share_dir.is_dir()


def test_peripheral_flags_workdir_honours_custom_drive_letter(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    share_dir = tmp_path / "CrossDesk-Shared"
    _patch_peripherals(
        monkeypatch,
        PeripheralsConfig(
            shared_folder_enabled=True,
            shared_folder_path=str(share_dir),
            shared_folder_drive_letter="m",  # lower-case normalised to M
        ),
    )
    _flags, workdir = _backend_servicer()._peripheral_flags()
    assert workdir == "M:\\"


def test_peripheral_flags_no_workdir_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_peripherals(monkeypatch, PeripheralsConfig())  # shared folder off
    flags, workdir = _backend_servicer()._peripheral_flags()
    assert not any(f.startswith("/drive:") for f in flags)
    assert workdir == ""


def test_peripheral_flags_drops_drive_and_workdir_when_uncreatable(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    # Point the share at a path whose parent is a regular file → mkdir raises
    # OSError (NotADirectoryError). The drive redirect AND the workdir must be
    # dropped so the launch doesn't point the app at a share that won't mount.
    blocker = tmp_path / "afile"
    blocker.write_text("not a dir")
    _patch_peripherals(
        monkeypatch,
        PeripheralsConfig(
            shared_folder_enabled=True,
            shared_folder_path=str(blocker / "nope"),
            # A non-share flag survives so we can prove only the drive dropped.
            clipboard_mode="text-only",
        ),
    )
    flags, workdir = _backend_servicer()._peripheral_flags()
    assert not any(f.startswith("/drive:") for f in flags)
    assert "+clipboard" in flags
    assert workdir == ""


def test_peripheral_flags_drops_drive_and_workdir_for_relative_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A non-absolute path bypasses the OSError mkdir gate (Path("rel").mkdir
    # succeeds against the CWD), so the launcher rejects it up front: drop the
    # /drive: redirect AND the workdir, keep the other peripheral flags. No
    # directory is created (the guard returns before mkdir).
    _patch_peripherals(
        monkeypatch,
        PeripheralsConfig(
            shared_folder_enabled=True,
            shared_folder_path="relative/share",
            clipboard_mode="text-only",
        ),
    )
    flags, workdir = _backend_servicer()._peripheral_flags()
    assert not any(f.startswith("/drive:") for f in flags)
    assert "+clipboard" in flags
    assert workdir == ""


def test_peripheral_flags_invalid_config_degrades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(path=None):  # type: ignore[no-untyped-def]
        raise ValueError("bad toml")

    monkeypatch.setattr(
        "crossdesk_host.config.peripherals.load_peripherals_config", _boom
    )
    flags, workdir = _backend_servicer()._peripheral_flags()
    assert flags == []
    assert workdir == ""


async def test_launch_threads_workdir_into_argv(
    monkeypatch: pytest.MonkeyPatch, context: MagicMock, tmp_path
) -> None:
    _patch_app_and_creds(monkeypatch)
    _patch_peripherals(
        monkeypatch,
        PeripheralsConfig(
            shared_folder_enabled=True,
            shared_folder_path=str(tmp_path / "CrossDesk-Shared"),
        ),
    )
    seen: dict[str, object] = {}

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0):  # type: ignore[no-untyped-def]
        seen["argv"] = argv
        return RailSession(pid=99, argv=list(argv))

    monkeypatch.setattr(management, "spawn_rail_with_auth_check", fake_spawn)

    resp = await _backend_servicer().Launch(
        mgmt_pb2.LaunchRequest(app_id="notepad"), context
    )
    assert resp.ok
    argv = seen["argv"]
    assert isinstance(argv, list)
    program = next(a for a in argv if a.startswith("/app:"))
    assert "workdir:Z:\\" in program
