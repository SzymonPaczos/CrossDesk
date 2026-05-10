"""ManagementServiceServicer unit tests (Phase 6 / Week 25)."""

from __future__ import annotations

import importlib
import io
import json
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock

import pytest
import structlog

from crossdesk_host.ipc.management import (
    ManagementServiceServicer,
    MgmtState,
)
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.lifecycle import LifecycleCoordinator
from crossdesk_host.observability import (
    TraceContext,
    bind_to_log_context,
    configure_logging,
)
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


# ---------------------------------------------------------------------------
# Span coverage (per docs/SPAN_COVERAGE.md)
# ---------------------------------------------------------------------------


@pytest.fixture
def captured_log() -> Iterator[io.StringIO]:
    """Pipe the JSON Lines log stream into an in-memory buffer so the
    span-coverage test can inspect the structured records emitted by
    each RPC handler.

    The management module is reloaded after `configure_logging` so its
    module-level `logger = get_logger(...)` snapshot picks up the new
    JSON renderer + buffer stream. Without the reload we'd see the
    pre-configure default console renderer write to stderr instead.
    """
    buf = io.StringIO()
    configure_logging(stream=buf)
    import crossdesk_host.ipc.management as management_module

    importlib.reload(management_module)
    structlog.contextvars.clear_contextvars()
    try:
        yield buf
    finally:
        structlog.contextvars.clear_contextvars()


def _records(buf: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]


def _reloaded_servicer() -> ManagementServiceServicer:
    # After importlib.reload, the symbols in this module's import scope
    # still point at the pre-reload class — re-fetch from the live
    # module so the servicer instance carries the freshly-bound logger.
    import crossdesk_host.ipc.management as management_module

    libvirt = LibvirtControllerMock()
    state = management_module.MgmtState(fsm=HeartbeatFsm())
    return management_module.ManagementServiceServicer(state, libvirt)


async def test_rpc_handler_emits_rpc_start_with_span_id(
    captured_log: io.StringIO,
    context: MagicMock,
) -> None:
    """Every Management handler must mint a per-call span_id while
    inheriting the upstream trace_id (when one is bound). ReadSettings
    is the simplest probe — pure read path, no I/O surprises.
    """
    parent = TraceContext(trace_id="a" * 32, span_id="b" * 16)
    bind_to_log_context(parent)

    servicer = _reloaded_servicer()
    await servicer.ReadSettings(mgmt_pb2.Empty(), context)

    records = _records(captured_log)
    starts = [r for r in records if r.get("event") == "rpc_start"]
    assert starts, f"no rpc_start record emitted: {records}"
    start = starts[0]
    assert start["method"] == "ReadSettings"
    span_id = start.get("span_id")
    assert isinstance(span_id, str) and span_id, "span_id must be non-empty"
    # Inherits the bound parent's trace_id, mints a fresh span_id.
    assert start["trace_id"] == parent.trace_id
    assert span_id != parent.span_id


async def test_rpc_handler_mints_root_when_no_parent(
    captured_log: io.StringIO,
    context: MagicMock,
) -> None:
    """No upstream trace bound → handler still gets a non-empty
    span_id (and trace_id) from the freshly-minted root span.
    """
    servicer = _reloaded_servicer()
    await servicer.ReadSettings(mgmt_pb2.Empty(), context)

    starts = [r for r in _records(captured_log) if r.get("event") == "rpc_start"]
    assert starts, "no rpc_start record emitted"
    start = starts[0]
    assert isinstance(start.get("span_id"), str) and start["span_id"]
    assert isinstance(start.get("trace_id"), str) and start["trace_id"]


async def test_rpc_end_early_fires_on_validation_failure(
    captured_log: io.StringIO,
    context: MagicMock,
) -> None:
    """Error paths must emit a terminal `rpc_end_early` so trace
    backends see a span-close event even when the happy-path
    `rpc_end` is skipped.
    """
    import crossdesk_host.ipc.management as management_module

    libvirt = LibvirtControllerMock()
    libvirt.hooks.fail_next_hard_destroy = True
    servicer = management_module.ManagementServiceServicer(
        management_module.MgmtState(fsm=HeartbeatFsm()), libvirt
    )

    response = await servicer.HardDestroy(mgmt_pb2.Empty(), context)
    assert not response.ok

    records = _records(captured_log)
    early = [r for r in records if r.get("event") == "rpc_end_early"]
    assert early, f"expected rpc_end_early, got: {records}"
    assert early[0]["method"] == "HardDestroy"
    # And no successful terminal event for the same call.
    ends = [r for r in records if r.get("event") == "rpc_end"]
    assert not ends, f"rpc_end should not fire on failure path: {ends}"
