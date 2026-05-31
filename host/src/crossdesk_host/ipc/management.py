"""ManagementService gRPC servicer (Phase 6 / Week 25).

Local-IPC surface for the GUI / tray / KCM. Bound to a Unix socket
under ``$XDG_RUNTIME_DIR/crossdesk-host.sock``; Unix permissions
(0600 socket file owned by the daemon's UID) provide authentication.

Wires existing host machinery — heartbeat FSM state, libvirt
controller, lifecycle coordinator, doctor checks, settings module —
into the proto surface defined in ``proto/crossdesk/v1/mgmt.proto``.

Streaming RPCs (Status / ListMounts) push on every state change with
a coalesce window so plain HEALTHY ticks don't flood the wire. The
GUI subscribes once and renders updates as they arrive.

This servicer is independent of the guest-facing servicers (control,
heartbeat, filesystem) — separate proto, separate binding, no shared
auth state. Lets us iterate on management surface without touching
the wire format guests already speak.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, List, Optional

import grpc
from google.protobuf import duration_pb2, timestamp_pb2

from crossdesk_host.abstractions.freerdp import FreeRDPInvocation, RailSession
from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.catalog.loader import find_app
from crossdesk_host.display.rail_command import (
    AppLaunchSpec,
    FreeRDPConnectionSpec,
    build_rail_argv,
)
from crossdesk_host.display.session_starter import (
    AuthHealthCheckFailed,
    spawn_rail_with_auth_check,
)
from crossdesk_host.doctor import has_failures, run_all
from crossdesk_host.doctor.checks import Status as DoctorStatus
from crossdesk_host.installer import credentials, settings
from crossdesk_host.ipc.verify_coordinator import NoActiveSession, VerifyCoordinator
from crossdesk_host.lifecycle import LifecycleCoordinator
from crossdesk_host.observability import child_span_scope
from crossdesk_host.observability.log import get_logger
from crossdesk_host.observability.metrics import REGISTRY, Registry
from crossdesk_host.proto.crossdesk.v1 import mgmt_pb2, mgmt_pb2_grpc
from crossdesk_host.watchdog import HeartbeatFsm, State

logger = get_logger("host.ipc.management")

# Shared between daemon (which binds the socket) and the CLI (which
# connects to it). Keeping the function on the servicer module — and
# not the daemon — is what lets ``crossdesk metrics`` import it
# without dragging the whole daemon entry point along.
_SOCK_NAME = "crossdesk-host.sock"


def mgmt_socket_path() -> Path:
    """Resolve the Unix socket path the management plane binds to.

    Honours ``XDG_RUNTIME_DIR`` per the freedesktop spec; falls back
    to ``~/.local/run`` for environments that don't set it (Mac dev,
    minimal containers). The fallback directory is created on demand
    so callers don't have to."""

    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / _SOCK_NAME
    fallback = Path.home() / ".local" / "run"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / _SOCK_NAME


def _ts(when: Optional[datetime] = None) -> timestamp_pb2.Timestamp:
    when = when or datetime.now(timezone.utc)
    out = timestamp_pb2.Timestamp()
    out.FromDatetime(when)
    return out


def _dur_seconds(value: float) -> duration_pb2.Duration:
    seconds = int(value)
    nanos = int((value - seconds) * 1_000_000_000)
    return duration_pb2.Duration(seconds=seconds, nanos=nanos)


def _dur_ns(ns: Optional[int]) -> duration_pb2.Duration:
    if ns is None or ns < 0:
        return duration_pb2.Duration()
    seconds, n = divmod(int(ns), 1_000_000_000)
    return duration_pb2.Duration(seconds=seconds, nanos=n)


@dataclass
class MgmtState:
    """Mutable state the daemon updates from the heartbeat plane,
    lifecycle coordinator, and rail manager. The servicer reads from
    this when emitting StatusFrames."""

    fsm: Optional[HeartbeatFsm] = None
    libvirt_state: str = "RUNNING"  # mirrors VmStatus.State string name
    boot_time: float = field(default_factory=time.time)
    last_hard_destroy: Optional[datetime] = None
    auth_rejections: int = 0
    running_apps: List[mgmt_pb2.RailAppRunning] = field(default_factory=list)
    recent_activity: List[mgmt_pb2.RecentActivity] = field(default_factory=list)
    active_mounts: List[mgmt_pb2.MountEntry] = field(default_factory=list)
    # Set by ControlServiceServicer.on_agent_version after each successful
    # handshake. Empty string means no session has completed yet.
    agent_version: str = ""

    def append_activity(
        self,
        kind: "mgmt_pb2.RecentActivity.Kind.ValueType",
        detail: str,
    ) -> None:
        entry = mgmt_pb2.RecentActivity(
            kind=kind,
            detail=detail,
            timestamp=_ts(),
        )
        self.recent_activity.insert(0, entry)
        if len(self.recent_activity) > 30:
            self.recent_activity.pop()


class ManagementServiceServicer(mgmt_pb2_grpc.ManagementServiceServicer):
    def __init__(
        self,
        state: MgmtState,
        libvirt_ctl: LibvirtController,
        coordinator: Optional[LifecycleCoordinator] = None,
        push_interval_seconds: float = 1.0,
        metrics_registry: Optional[Registry] = None,
        freerdp: Optional[FreeRDPInvocation] = None,
        verify_coordinator: Optional[VerifyCoordinator] = None,
    ) -> None:
        self.state = state
        self.libvirt_ctl = libvirt_ctl
        self.coordinator = coordinator
        self.push_interval_seconds = push_interval_seconds
        # Launch backend: the FreeRDP spawner + the credential-verify
        # coordinator (shared with the control servicer, which registers
        # the live guest session). Both None ⇒ Launch reports the backend
        # is unavailable rather than pretending success.
        self._freerdp = freerdp
        self._verify_coordinator = verify_coordinator
        # RAIL sessions spawned via Launch, kept so they aren't lost
        # (terminate-on-window-close adoption by RailManager is a Phase-4
        # follow-up; for now this keeps the handle reachable).
        self._sessions: List[RailSession] = []
        # Tests inject a fresh Registry to avoid cross-test pollution;
        # production wires the module-level singleton so every metric
        # instrumented anywhere in the host shows up here.
        self.metrics_registry = metrics_registry or REGISTRY

    # ------------------------------------------------------------------
    # Status stream
    # ------------------------------------------------------------------

    async def Status(  # noqa: N802 — gRPC requires CamelCase
        self,
        request: mgmt_pb2.Empty,
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[mgmt_pb2.StatusFrame]:
        with child_span_scope():
            logger.info("rpc_start", method="Status")
            logger.info("mgmt_status_stream_opened")
            try:
                while not context.cancelled():
                    yield self._build_status_frame()
                    await asyncio.sleep(self.push_interval_seconds)
            except asyncio.CancelledError:
                pass
            finally:
                logger.info("mgmt_status_stream_closed")
                logger.info("rpc_end", method="Status")

    def _build_status_frame(self) -> mgmt_pb2.StatusFrame:
        uptime_seconds = max(0.0, time.time() - self.state.boot_time)
        vm_state_value = getattr(
            mgmt_pb2.VmStatus.State,
            f"STATE_{self.state.libvirt_state}",
            mgmt_pb2.VmStatus.State.STATE_UNSPECIFIED,
        )
        vm = mgmt_pb2.VmStatus(
            state=vm_state_value,
            uptime=_dur_seconds(uptime_seconds),
            last_hard_destroy=(
                _ts(self.state.last_hard_destroy)
                if self.state.last_hard_destroy
                else timestamp_pb2.Timestamp()
            ),
        )
        if self.state.fsm is not None:
            fsm_state_label = self.state.fsm.state.value
        else:
            fsm_state_label = State.HEALTHY.value
        hb = mgmt_pb2.HeartbeatStatus(
            fsm_state=fsm_state_label,
            ewma_rtt=duration_pb2.Duration(),
            consecutive_miss_count=0,
            soft_attempts=0,
            auth_context_rejections=self.state.auth_rejections,
        )
        return mgmt_pb2.StatusFrame(
            vm=vm,
            heartbeat=hb,
            resources=mgmt_pb2.ResourceUsage(),
            running_apps=list(self.state.running_apps),
            recent_activity=list(self.state.recent_activity[:10]),
            emitted_at=_ts(),
            agent_version=self.state.agent_version,
        )

    # ------------------------------------------------------------------
    # App catalog
    # ------------------------------------------------------------------

    async def ListApps(  # noqa: N802
        self,
        request: mgmt_pb2.Empty,
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[mgmt_pb2.AppEntry]:
        with child_span_scope():
            logger.info("rpc_start", method="ListApps")
            for entry in self._curated_apps():
                yield entry
            logger.info("rpc_end", method="ListApps")

    async def ListDiscoveredApps(  # noqa: N802
        self,
        request: mgmt_pb2.Empty,
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[mgmt_pb2.AppEntry]:
        # Phase 8 Week 34 wires this to the guest's RegistryScannerService.
        # For now the daemon returns nothing; GUI shows "no discoveries
        # yet" message.
        with child_span_scope():
            logger.info("rpc_start", method="ListDiscoveredApps")
            # The `for _ in ()` keeps this a real async generator (the
            # function signature is AsyncIterator[...]) while emitting
            # zero items. Replaces an older `if False: yield` which
            # vulture flagged as an unsatisfiable branch.
            for _ in ():
                yield mgmt_pb2.AppEntry()  # pragma: no cover
            logger.info("rpc_end", method="ListDiscoveredApps")

    def _curated_apps(self) -> List[mgmt_pb2.AppEntry]:
        # Curated tier loader lands in Phase 8 Week 33; wire the four
        # built-in Windows apps as a starter set so the GUI's Apps pane
        # has data to render against today.
        starter = [
            ("notepad", "Notepad", "C:\\Windows\\notepad.exe", "Built-in", 5),
            ("calc", "Calculator", "C:\\Windows\\System32\\calc.exe", "Built-in", 5),
            ("cmd", "Command Prompt", "C:\\Windows\\System32\\cmd.exe", "Built-in", 5),
            ("paint", "Paint", "C:\\Windows\\System32\\mspaint.exe", "Built-in", 5),
        ]
        return [
            mgmt_pb2.AppEntry(
                app_id=app_id,
                display_name=name,
                executable_guest_path=path,
                category=cat,
                compatibility_stars=stars,
                tier=mgmt_pb2.AppEntry.Tier.TIER_CURATED,
            )
            for app_id, name, path, cat, stars in starter
        ]

    # ------------------------------------------------------------------
    # Mounts
    # ------------------------------------------------------------------

    async def ListMounts(  # noqa: N802
        self,
        request: mgmt_pb2.Empty,
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[mgmt_pb2.MountEntry]:
        with child_span_scope():
            logger.info("rpc_start", method="ListMounts")
            try:
                while not context.cancelled():
                    for entry in self.state.active_mounts:
                        yield entry
                    await asyncio.sleep(self.push_interval_seconds)
                    # Re-yield on every tick so a freshly-attached mount
                    # appears at the next interval. Phase 8 will replace
                    # this with an event-driven push.
                    if not self.state.active_mounts:
                        # Empty stream — keep the connection alive but don't
                        # yield empties; the GUI handles "no mounts" via the
                        # absence of frames during a window.
                        pass
            except asyncio.CancelledError:
                pass
            finally:
                logger.info("rpc_end", method="ListMounts")

    # ------------------------------------------------------------------
    # Imperative actions
    # ------------------------------------------------------------------

    async def Launch(  # noqa: N802
        self,
        request: mgmt_pb2.LaunchRequest,
        context: grpc.aio.ServicerContext,
    ) -> mgmt_pb2.LaunchResponse:
        with child_span_scope():
            logger.info("rpc_start", method="Launch")
            logger.info(
                "mgmt_launch_request",
                app_id=request.app_id,
                file_path=request.file_path,
            )
            try:
                return await self._launch(request)
            finally:
                logger.info("rpc_end", method="Launch")

    async def _launch(self, request: mgmt_pb2.LaunchRequest) -> mgmt_pb2.LaunchResponse:
        """Resolve the app, gate on the guest credential check, and spawn
        a FreeRDP RAIL session. Every failure mode maps to
        ``LaunchResponse(ok=False, error=...)`` so the CLI/GUI can print an
        actionable message instead of an opaque RPC error. (file_path-driven
        JIT mount is a Phase-5 follow-up — not wired here.)"""
        app_id = request.app_id
        if self._freerdp is None or self._verify_coordinator is None:
            return mgmt_pb2.LaunchResponse(
                ok=False, error="launch backend not available in this daemon"
            )
        app = find_app(app_id)
        if app is None:
            return mgmt_pb2.LaunchResponse(
                ok=False, error=f"unknown app_id: {app_id!r}"
            )
        creds = credentials.load()
        if creds is None:
            return mgmt_pb2.LaunchResponse(
                ok=False, error="no VM credentials — run `crossdesk install`"
            )

        spec = AppLaunchSpec(
            app_id=app.app_id,
            executable_guest_path=app.win_executable,
            display_name=app.name,
        )
        conn = FreeRDPConnectionSpec(username=creds.username, password=creds.password)
        argv = build_rail_argv(spec, conn)

        try:
            session = await spawn_rail_with_auth_check(
                self._freerdp, self._verify_coordinator, argv, creds=creds
            )
        except AuthHealthCheckFailed as exc:
            hint = exc.result.repair_hint or exc.result.detail
            logger.warning("launch_auth_failed", app_id=app_id, detail=hint)
            return mgmt_pb2.LaunchResponse(ok=False, error=hint)
        except NoActiveSession:
            return mgmt_pb2.LaunchResponse(
                ok=False, error="no guest session connected — is the VM running?"
            )
        except asyncio.TimeoutError:
            return mgmt_pb2.LaunchResponse(
                ok=False, error="guest did not respond to the credential check"
            )
        except FileNotFoundError as exc:
            return mgmt_pb2.LaunchResponse(ok=False, error=str(exc))
        except Exception as exc:  # boundary: convert to RPC error, never crash the daemon
            logger.exception("launch_failed", app_id=app_id)
            return mgmt_pb2.LaunchResponse(ok=False, error=f"launch failed: {exc}")

        self._sessions.append(session)
        self.state.append_activity(
            mgmt_pb2.RecentActivity.Kind.KIND_APP_LAUNCHED,
            f"Launched {app.name} (pid {session.pid})",
        )
        return mgmt_pb2.LaunchResponse(ok=True, request_id=f"rail-{session.pid}")

    async def Suspend(  # noqa: N802
        self, request: mgmt_pb2.Empty, context: grpc.aio.ServicerContext
    ) -> mgmt_pb2.ActionAck:
        with child_span_scope():
            logger.info("rpc_start", method="Suspend")
            try:
                if self.coordinator is not None:
                    self.coordinator.on_prepare_for_sleep()
                else:
                    self.libvirt_ctl.suspend()
                self.state.append_activity(
                    mgmt_pb2.RecentActivity.Kind.KIND_SUSPEND, "Manual suspend"
                )
                logger.info("rpc_end", method="Suspend")
                return mgmt_pb2.ActionAck(ok=True)
            except Exception as exc:
                logger.info("rpc_end_early", method="Suspend", reason="libvirt_error")
                return mgmt_pb2.ActionAck(ok=False, detail=str(exc))

    async def Resume(  # noqa: N802
        self, request: mgmt_pb2.Empty, context: grpc.aio.ServicerContext
    ) -> mgmt_pb2.ActionAck:
        with child_span_scope():
            logger.info("rpc_start", method="Resume")
            try:
                if self.coordinator is not None:
                    self.coordinator.on_resumed()
                else:
                    self.libvirt_ctl.resume()
                self.state.append_activity(
                    mgmt_pb2.RecentActivity.Kind.KIND_RESUME, "Manual resume"
                )
                logger.info("rpc_end", method="Resume")
                return mgmt_pb2.ActionAck(ok=True)
            except Exception as exc:
                logger.info("rpc_end_early", method="Resume", reason="libvirt_error")
                return mgmt_pb2.ActionAck(ok=False, detail=str(exc))

    async def HardDestroy(  # noqa: N802
        self, request: mgmt_pb2.Empty, context: grpc.aio.ServicerContext
    ) -> mgmt_pb2.ActionAck:
        with child_span_scope():
            logger.info("rpc_start", method="HardDestroy")
            try:
                self.libvirt_ctl.hard_destroy()
                self.state.last_hard_destroy = datetime.now(timezone.utc)
                self.state.append_activity(
                    mgmt_pb2.RecentActivity.Kind.KIND_HARD_DESTROY,
                    "Manual HARD_DESTROY",
                )
                logger.info("rpc_end", method="HardDestroy")
                return mgmt_pb2.ActionAck(ok=True)
            except Exception as exc:
                logger.info(
                    "rpc_end_early",
                    method="HardDestroy",
                    reason="libvirt_error",
                )
                return mgmt_pb2.ActionAck(ok=False, detail=str(exc))

    async def RotateCredentials(  # noqa: N802
        self, request: mgmt_pb2.Empty, context: grpc.aio.ServicerContext
    ) -> mgmt_pb2.CredentialsResponse:
        with child_span_scope():
            logger.info("rpc_start", method="RotateCredentials")
            existing = credentials.load()
            username = existing.username if existing else "crossdesk"
            new_creds = credentials.generate(username)
            credentials.save(new_creds)
            logger.info("rpc_end", method="RotateCredentials")
            return mgmt_pb2.CredentialsResponse(
                username=new_creds.username,
                keyring_key="crossdesk/vm/password",
                last_rotated=_ts(),
            )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    async def RunDiagnostics(  # noqa: N802
        self, request: mgmt_pb2.Empty, context: grpc.aio.ServicerContext
    ) -> mgmt_pb2.DiagnosticsReport:
        with child_span_scope():
            logger.info("rpc_start", method="RunDiagnostics")
            results = run_all()
            proto_status = {
                DoctorStatus.OK: mgmt_pb2.DiagnosticsCheck.Status.STATUS_OK,
                DoctorStatus.WARN: mgmt_pb2.DiagnosticsCheck.Status.STATUS_WARN,
                DoctorStatus.FAIL: mgmt_pb2.DiagnosticsCheck.Status.STATUS_FAIL,
            }
            report = mgmt_pb2.DiagnosticsReport(
                checks=[
                    mgmt_pb2.DiagnosticsCheck(
                        name=r.name,
                        status=proto_status[r.status],
                        message=r.message,
                    )
                    for r in results
                ],
                any_failed=has_failures(results),
            )
            logger.info("rpc_end", method="RunDiagnostics")
            return report

    async def ExportDiagnosticBundle(  # noqa: N802
        self, request: mgmt_pb2.Empty, context: grpc.aio.ServicerContext
    ) -> mgmt_pb2.DiagnosticBundle:
        # Phase 9 Week 37 wires the actual zip generation. For now
        # return an empty bundle so callers can verify the round-trip.
        with child_span_scope():
            logger.info("rpc_start", method="ExportDiagnosticBundle")
            bundle = mgmt_pb2.DiagnosticBundle(
                zip_payload=b"",
                filename=f"crossdesk-diag-{int(time.time())}.zip",
                generated_at=_ts(),
            )
            logger.info("rpc_end", method="ExportDiagnosticBundle")
            return bundle

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    async def UpdateSettings(  # noqa: N802
        self,
        request: mgmt_pb2.SettingsRequest,
        context: grpc.aio.ServicerContext,
    ) -> mgmt_pb2.SettingsResponse:
        with child_span_scope():
            logger.info("rpc_start", method="UpdateSettings")
            s = _settings_from_proto(request.desired)
            s = settings.clamp(s)
            settings.save(s)
            logger.info("rpc_end", method="UpdateSettings")
            return mgmt_pb2.SettingsResponse(current=_settings_to_proto(s))

    async def ReadSettings(  # noqa: N802
        self, request: mgmt_pb2.Empty, context: grpc.aio.ServicerContext
    ) -> mgmt_pb2.SettingsResponse:
        with child_span_scope():
            logger.info("rpc_start", method="ReadSettings")
            response = mgmt_pb2.SettingsResponse(
                current=_settings_to_proto(settings.load())
            )
            logger.info("rpc_end", method="ReadSettings")
            return response

    # ------------------------------------------------------------------
    # Metrics snapshot
    # ------------------------------------------------------------------

    async def GetMetrics(  # noqa: N802
        self,
        request: mgmt_pb2.GetMetricsRequest,
        context: grpc.aio.ServicerContext,
    ) -> mgmt_pb2.GetMetricsResponse:
        prefixes = tuple(request.name_prefix)
        return mgmt_pb2.GetMetricsResponse(
            metrics=_serialise_registry(self.metrics_registry, prefixes),
        )


def _serialise_registry(
    registry: Registry, prefixes: tuple[str, ...]
) -> List[mgmt_pb2.Metric]:
    out: List[mgmt_pb2.Metric] = []
    for name, counter in registry.counters.items():
        if not _name_matches(name, prefixes):
            continue
        out.append(
            mgmt_pb2.Metric(
                name=name,
                type=mgmt_pb2.Metric.Type.COUNTER,
                scalar=float(counter.value()),
            )
        )
    for name, gauge in registry.gauges.items():
        if not _name_matches(name, prefixes):
            continue
        out.append(
            mgmt_pb2.Metric(
                name=name,
                type=mgmt_pb2.Metric.Type.GAUGE,
                scalar=float(gauge.value()),
            )
        )
    for name, histogram in registry.histograms.items():
        if not _name_matches(name, prefixes):
            continue
        snap = histogram.snapshot()
        out.append(
            mgmt_pb2.Metric(
                name=name,
                type=mgmt_pb2.Metric.Type.HISTOGRAM,
                histogram=mgmt_pb2.HistogramSnapshot(
                    p50=snap["p50"],
                    p95=snap["p95"],
                    p99=snap["p99"],
                    min=snap["min"],
                    max=snap["max"],
                    count=snap["count"],
                ),
            )
        )
    return out


def _name_matches(name: str, prefixes: tuple[str, ...]) -> bool:
    if not prefixes:
        return True
    return any(name.startswith(p) for p in prefixes)


def _settings_from_proto(p: mgmt_pb2.Settings) -> settings.Settings:
    return settings.Settings(
        language=p.language or "auto",
        theme=p.theme or "system",
        telemetry_enabled=p.telemetry_enabled,
        keyring_enabled=p.keyring_enabled,
        lean_mode=p.lean_mode,
        network_mode=p.network_mode or "nat",
        hidpi_scale=p.hidpi_scale,
        multi_monitor_placement=p.multi_monitor_placement,
        auto_suspend_on_idle=p.auto_suspend_on_idle,
        auto_suspend_after_seconds=int(
            p.auto_suspend_after.seconds + p.auto_suspend_after.nanos / 1e9
        ),
        auto_suspend_on_lid=p.auto_suspend_on_lid,
        auto_resume_on_launch=p.auto_resume_on_launch,
        miss_threshold=p.miss_threshold or 3,
        recovery_ticks=p.recovery_ticks or 3,
        backoff_initial_seconds=(
            p.backoff_initial.seconds + p.backoff_initial.nanos / 1e9
        )
        or 5.0,
        max_soft_attempts=p.max_soft_attempts or 3,
    )


def _settings_to_proto(s: settings.Settings) -> mgmt_pb2.Settings:
    return mgmt_pb2.Settings(
        language=s.language,
        theme=s.theme,
        telemetry_enabled=s.telemetry_enabled,
        keyring_enabled=s.keyring_enabled,
        lean_mode=s.lean_mode,
        network_mode=s.network_mode,
        hidpi_scale=s.hidpi_scale,
        multi_monitor_placement=s.multi_monitor_placement,
        auto_suspend_on_idle=s.auto_suspend_on_idle,
        auto_suspend_after=_dur_seconds(s.auto_suspend_after_seconds),
        auto_suspend_on_lid=s.auto_suspend_on_lid,
        auto_resume_on_launch=s.auto_resume_on_launch,
        miss_threshold=s.miss_threshold,
        recovery_ticks=s.recovery_ticks,
        backoff_initial=_dur_seconds(s.backoff_initial_seconds),
        max_soft_attempts=s.max_soft_attempts,
    )
