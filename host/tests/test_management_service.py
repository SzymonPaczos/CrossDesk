"""ManagementServiceServicer unit tests (Phase 6 / Week 25)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crossdesk_host.ipc.management import (
    ManagementServiceServicer,
    MgmtState,
)
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.lifecycle import LifecycleCoordinator
from crossdesk_host.proto.crossdesk.v1 import mgmt_pb2
from crossdesk_host.watchdog import HeartbeatFsm


def _servicer(
    coordinator: LifecycleCoordinator | None = None,
) -> ManagementServiceServicer:
    libvirt = LibvirtControllerMock()
    state = MgmtState(fsm=HeartbeatFsm())
    return ManagementServiceServicer(state, libvirt, coordinator)


@pytest.fixture
def context() -> MagicMock:
    ctx = MagicMock()
    ctx.cancelled.return_value = False
    return ctx


# ---------------------------------------------------------------------------
# Status stream
# ---------------------------------------------------------------------------


async def test_status_first_frame_carries_fsm_state(context: MagicMock) -> None:
    servicer = _servicer()
    servicer.push_interval_seconds = 0
    stream = servicer.Status(mgmt_pb2.Empty(), context)
    frame = await stream.__anext__()
    assert frame.heartbeat.fsm_state == "HEALTHY"
    assert frame.vm.state == mgmt_pb2.VmStatus.State.STATE_RUNNING


async def test_status_emits_running_apps(context: MagicMock) -> None:
    servicer = _servicer()
    servicer.push_interval_seconds = 0
    servicer.state.running_apps.append(
        mgmt_pb2.RailAppRunning(app_id="notepad", display_name="Notepad", hwnd=0x123)
    )
    stream = servicer.Status(mgmt_pb2.Empty(), context)
    frame = await stream.__anext__()
    assert len(frame.running_apps) == 1
    assert frame.running_apps[0].app_id == "notepad"


# ---------------------------------------------------------------------------
# App catalog
# ---------------------------------------------------------------------------


async def test_list_apps_returns_built_in_starter(context: MagicMock) -> None:
    servicer = _servicer()
    apps = []
    async for entry in servicer.ListApps(mgmt_pb2.Empty(), context):
        apps.append(entry)
    ids = [a.app_id for a in apps]
    assert "notepad" in ids
    assert "calc" in ids
    assert all(a.tier == mgmt_pb2.AppEntry.Tier.TIER_CURATED for a in apps)


async def test_list_discovered_apps_starts_empty(context: MagicMock) -> None:
    """Phase 6 only ships curated; discovered tier lights up Phase 8."""
    servicer = _servicer()
    apps = [a async for a in servicer.ListDiscoveredApps(mgmt_pb2.Empty(), context)]
    assert apps == []


# ---------------------------------------------------------------------------
# Imperative actions
# ---------------------------------------------------------------------------


async def test_launch_records_activity(context: MagicMock) -> None:
    servicer = _servicer()
    response = await servicer.Launch(mgmt_pb2.LaunchRequest(app_id="notepad"), context)
    assert response.ok
    kinds = [a.kind for a in servicer.state.recent_activity]
    assert mgmt_pb2.RecentActivity.Kind.KIND_APP_LAUNCHED in kinds


async def test_suspend_uses_coordinator_when_present(context: MagicMock) -> None:
    libvirt = LibvirtControllerMock()
    coordinator = LifecycleCoordinator(libvirt)
    servicer = ManagementServiceServicer(
        MgmtState(fsm=HeartbeatFsm()), libvirt, coordinator
    )
    response = await servicer.Suspend(mgmt_pb2.Empty(), context)
    assert response.ok
    assert libvirt.hooks.suspend_count == 1


async def test_suspend_falls_back_to_libvirt_directly(context: MagicMock) -> None:
    libvirt = LibvirtControllerMock()
    servicer = ManagementServiceServicer(
        MgmtState(fsm=HeartbeatFsm()), libvirt, coordinator=None
    )
    response = await servicer.Suspend(mgmt_pb2.Empty(), context)
    assert response.ok
    assert libvirt.hooks.suspend_count == 1


async def test_hard_destroy_records_timestamp(context: MagicMock) -> None:
    servicer = _servicer()
    response = await servicer.HardDestroy(mgmt_pb2.Empty(), context)
    assert response.ok
    assert servicer.state.last_hard_destroy is not None


async def test_hard_destroy_failure_returns_detail(context: MagicMock) -> None:
    libvirt = LibvirtControllerMock()
    libvirt.hooks.fail_next_hard_destroy = True
    servicer = ManagementServiceServicer(MgmtState(fsm=HeartbeatFsm()), libvirt)
    response = await servicer.HardDestroy(mgmt_pb2.Empty(), context)
    assert not response.ok
    assert "hard_destroy" in response.detail


async def test_rotate_credentials_writes_new_password(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    context: MagicMock,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    servicer = _servicer()
    # Seed with existing credentials so rotation knows the username.
    from crossdesk_host.installer import credentials

    credentials.save(credentials.VmCredentials("alice", "old"))
    old_loaded = credentials.load()
    assert old_loaded is not None
    await servicer.RotateCredentials(mgmt_pb2.Empty(), context)
    new_loaded = credentials.load()
    assert new_loaded is not None
    assert new_loaded.username == "alice"
    assert new_loaded.password != old_loaded.password


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


async def test_run_diagnostics_returns_check_results(context: MagicMock) -> None:
    servicer = _servicer()
    report = await servicer.RunDiagnostics(mgmt_pb2.Empty(), context)
    names = [c.name for c in report.checks]
    # 4 checks come from doctor.DEFAULT_CHECKS; freerdp / kvm / libvirt / disk_space
    assert "freerdp" in names
    assert "disk_space" in names


async def test_export_diagnostic_bundle_returns_filename(
    context: MagicMock,
) -> None:
    servicer = _servicer()
    bundle = await servicer.ExportDiagnosticBundle(mgmt_pb2.Empty(), context)
    assert bundle.filename.startswith("crossdesk-diag-")
    assert bundle.filename.endswith(".zip")


# ---------------------------------------------------------------------------
# Settings round-trip
# ---------------------------------------------------------------------------


async def test_settings_round_trip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    context: MagicMock,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    servicer = _servicer()

    desired = mgmt_pb2.Settings(
        language="pl",
        theme="dark",
        hidpi_scale=140,
        miss_threshold=5,
    )
    response = await servicer.UpdateSettings(
        mgmt_pb2.SettingsRequest(desired=desired), context
    )
    assert response.current.language == "pl"
    assert response.current.theme == "dark"
    assert response.current.hidpi_scale == 140
    assert response.current.miss_threshold == 5

    read = await servicer.ReadSettings(mgmt_pb2.Empty(), context)
    assert read.current.theme == "dark"


async def test_update_settings_clamps_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    context: MagicMock,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    servicer = _servicer()
    desired = mgmt_pb2.Settings(theme="bogus", hidpi_scale=125)
    response = await servicer.UpdateSettings(
        mgmt_pb2.SettingsRequest(desired=desired), context
    )
    assert response.current.theme == "system"
    assert response.current.hidpi_scale == 0
