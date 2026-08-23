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
from crossdesk_host.display.rail_supervisor import RailSupervisor
from crossdesk_host.display.session_starter import AuthHealthCheckFailed
from crossdesk_host.freerdp.mock import MockFreeRDPInvocation
from crossdesk_host.installer.credentials import VerifyResult, VmCredentials
from crossdesk_host.ipc import management
from crossdesk_host.ipc.management import ManagementServiceServicer, MgmtState
from crossdesk_host.ipc.verify_coordinator import NoActiveSession, VerifyCoordinator
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.lifecycle.notifications import RecordingNotifier
from crossdesk_host.observability.metrics import MetricNames, Registry
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


async def test_launch_supervises_and_drops_session_on_exit(
    monkeypatch: pytest.MonkeyPatch, context: MagicMock
) -> None:
    _patch_app_and_creds(monkeypatch)
    mock_freerdp = MockFreeRDPInvocation()
    supervisor = RailSupervisor(mock_freerdp, notifier=RecordingNotifier())
    servicer = ManagementServiceServicer(
        MgmtState(fsm=HeartbeatFsm()),
        LibvirtControllerMock(),
        freerdp=mock_freerdp,
        verify_coordinator=VerifyCoordinator(),
        supervisor=supervisor,
    )
    session = RailSession(pid=77)

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0, log_label=""):  # type: ignore[no-untyped-def]
        # The app_id must reach spawn so the per-app capture log is named.
        assert log_label == "notepad"
        return session

    monkeypatch.setattr(management, "spawn_rail_with_auth_check", fake_spawn)

    resp = await servicer.Launch(mgmt_pb2.LaunchRequest(app_id="notepad"), context)
    assert resp.ok
    assert [s.pid for s in servicer._sessions] == [77]
    assert supervisor.active_count() == 1

    # When the FreeRDP process exits, the supervisor's on-exit callback
    # drops the dead session from the live list.
    task = supervisor._tasks[77]
    mock_freerdp.simulate_exit(session, returncode=0)
    await task
    assert servicer._sessions == []
    assert supervisor.active_count() == 0


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

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0, log_label=""):  # type: ignore[no-untyped-def]
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

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0, log_label=""):  # type: ignore[no-untyped-def]
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

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0, log_label=""):  # type: ignore[no-untyped-def]
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

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0, log_label=""):  # type: ignore[no-untyped-def]
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
            shared_folder_enabled=True,
            shared_folder_scope="custom",
            shared_folder_path=str(share_dir),
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
            shared_folder_scope="custom",
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
            shared_folder_scope="custom",
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
            shared_folder_scope="custom",
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
            shared_folder_scope="custom",
            shared_folder_path=str(tmp_path / "CrossDesk-Shared"),
        ),
    )
    seen: dict[str, object] = {}

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0, log_label=""):  # type: ignore[no-untyped-def]
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


# ---------------------------------------------------------------------------
# Launch latency (MVP criterion #2: native window <= 3 s p50)
# ---------------------------------------------------------------------------


def _metered_servicer(registry: Registry) -> ManagementServiceServicer:
    return ManagementServiceServicer(
        MgmtState(fsm=HeartbeatFsm()),
        LibvirtControllerMock(),
        freerdp=MockFreeRDPInvocation(),
        verify_coordinator=VerifyCoordinator(),
        metrics_registry=registry,
    )


async def test_successful_launch_records_its_duration(
    monkeypatch: pytest.MonkeyPatch, context: MagicMock
) -> None:
    """N1.1 is a p50, so the launch path has to feed a histogram.

    `launch_duration_seconds` existed in MetricNames with nothing writing to it,
    so the budget was unmeasurable through the product's own instrumentation --
    the same gap heartbeat RTT had.
    """
    _patch_app_and_creds(monkeypatch)
    registry = Registry()
    servicer = _metered_servicer(registry)

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0, log_label=""):  # type: ignore[no-untyped-def]
        return RailSession(pid=42)

    monkeypatch.setattr(management, "spawn_rail_with_auth_check", fake_spawn)

    resp = await servicer.Launch(mgmt_pb2.LaunchRequest(app_id="notepad"), context)
    assert resp.ok

    hist = registry.snapshot()["histograms"][MetricNames.LAUNCH_DURATION_SECONDS]
    assert hist["count"] == 1
    assert hist["p50"] >= 0.0


async def test_a_rejected_launch_is_not_a_slow_launch(
    monkeypatch: pytest.MonkeyPatch, context: MagicMock
) -> None:
    """A failure must not enter the histogram.

    An unknown app, a dead guest or bad credentials are errors, not latency.
    Folding them in would corrupt the p50 the budget is stated against.
    """
    _patch_app_and_creds(monkeypatch, app=None)
    registry = Registry()
    servicer = _metered_servicer(registry)

    resp = await servicer.Launch(mgmt_pb2.LaunchRequest(app_id="ghost"), context)
    assert not resp.ok

    assert MetricNames.LAUNCH_DURATION_SECONDS not in registry.snapshot()["histograms"]


# ---------------------------------------------------------------------------
# DEC-0019 JIT-lite: a launch carrying a host file path shares only that
# file's parent directory for the session, overriding the persistent scope.
# ---------------------------------------------------------------------------


def test_jitlite_flags_shares_parent_of_opened_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    # validate_mount_path requires the path under $HOME → point $HOME at tmp.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    doc_dir = tmp_path / "notes"
    doc_dir.mkdir()
    opened = doc_dir / "todo.txt"
    opened.write_text("x")
    _patch_peripherals(monkeypatch, PeripheralsConfig())  # persistent share OFF

    result = _backend_servicer()._jitlite_flags(str(opened))
    assert result is not None
    flags, workdir = result
    # Only the parent dir is shared — not the whole $HOME, not the file itself.
    assert flags == [f"/drive:CrossDesk,{doc_dir}"]
    assert workdir == "Z:\\"


def test_jitlite_flags_skip_for_empty_guest_or_outside_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    _patch_peripherals(monkeypatch, PeripheralsConfig())
    servicer = _backend_servicer()
    # Empty (no file arg), a guest C:\ path, a missing file, and a path
    # outside $HOME all fall through to the persistent share (None).
    assert servicer._jitlite_flags("") is None
    assert servicer._jitlite_flags("C:\\Users\\me\\todo.txt") is None
    assert servicer._jitlite_flags(str(tmp_path / "ghost.txt")) is None
    assert servicer._jitlite_flags("/etc/passwd") is None


def test_jitlite_refuses_to_share_home_itself(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """A file directly in $HOME must NOT silently share the whole $HOME.

    Its parent *is* $HOME, so the naive "share the parent" produces
    ``/drive:CrossDesk,/home/<user>`` — R/W over ~/.ssh and
    ~/.config/crossdesk (host mTLS key + VM password) — with no warning and
    with the persistent share disabled. DEC-0019 makes that scope an explicit,
    warned opt-in; this path bypassed it.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    loose = tmp_path / "notes.txt"
    loose.write_text("x")
    _patch_peripherals(monkeypatch, PeripheralsConfig())  # persistent share OFF

    assert _backend_servicer()._jitlite_flags(str(loose)) is None


async def test_launch_with_home_root_file_shares_nothing(
    monkeypatch: pytest.MonkeyPatch, context: MagicMock, tmp_path
) -> None:
    """End-to-end: launching with ~/x.txt while sharing is off must produce
    no /drive: flag at all — not a whole-$HOME one."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    loose = tmp_path / "instalator.exe"
    loose.write_text("x")
    _patch_app_and_creds(monkeypatch)
    _patch_peripherals(monkeypatch, PeripheralsConfig())
    seen: dict[str, object] = {}

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0, log_label=""):  # type: ignore[no-untyped-def]
        seen["argv"] = argv
        return RailSession(pid=56, argv=list(argv))

    monkeypatch.setattr(management, "spawn_rail_with_auth_check", fake_spawn)

    resp = await _backend_servicer().Launch(
        mgmt_pb2.LaunchRequest(app_id="notepad", file_path=str(loose)), context
    )
    assert resp.ok
    argv = seen["argv"]
    assert isinstance(argv, list)
    assert [a for a in argv if a.startswith("/drive:")] == []


def test_jitlite_still_shares_a_subdirectory(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The guard must not break the feature: a file one level down still
    shares exactly its parent."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    docs = tmp_path / "Documents"
    docs.mkdir()
    opened = docs / "spec.docx"
    opened.write_text("x")
    _patch_peripherals(monkeypatch, PeripheralsConfig())

    result = _backend_servicer()._jitlite_flags(str(opened))
    assert result == ([f"/drive:CrossDesk,{docs}"], "Z:\\")


async def test_launch_with_file_path_uses_jitlite_over_persistent_share(
    monkeypatch: pytest.MonkeyPatch, context: MagicMock, tmp_path
) -> None:
    # Persistent share is enabled at documents scope, but a launch carrying a
    # host file path must share ONLY that file's parent dir (JIT-lite wins).
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    doc_dir = tmp_path / "work"
    doc_dir.mkdir()
    opened = doc_dir / "spec.txt"
    opened.write_text("x")
    _patch_app_and_creds(monkeypatch)
    _patch_peripherals(
        monkeypatch,
        PeripheralsConfig(shared_folder_enabled=True, clipboard_mode="text-only"),
    )
    seen: dict[str, object] = {}

    async def fake_spawn(inv, coord, argv, *, creds=None, verify_timeout=5.0, log_label=""):  # type: ignore[no-untyped-def]
        seen["argv"] = argv
        return RailSession(pid=55, argv=list(argv))

    monkeypatch.setattr(management, "spawn_rail_with_auth_check", fake_spawn)

    resp = await _backend_servicer().Launch(
        mgmt_pb2.LaunchRequest(app_id="notepad", file_path=str(opened)), context
    )
    assert resp.ok
    argv = seen["argv"]
    assert isinstance(argv, list)
    drives = [a for a in argv if a.startswith("/drive:")]
    # Exactly one drive, pointing at the opened file's parent — not ~/Documents.
    assert drives == [f"/drive:CrossDesk,{doc_dir}"]
    # Non-share peripheral flags still apply.
    assert "+clipboard" in argv
