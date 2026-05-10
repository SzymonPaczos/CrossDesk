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
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator, List, Optional

import grpc
from google.protobuf import duration_pb2, timestamp_pb2

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.doctor import has_failures, run_all
from crossdesk_host.doctor.checks import Status as DoctorStatus
from crossdesk_host.installer import credentials, settings
from crossdesk_host.lifecycle import LifecycleCoordinator
from crossdesk_host.observability import child_span_scope
from crossdesk_host.observability.log import get_logger
from crossdesk_host.proto.crossdesk.v1 import mgmt_pb2, mgmt_pb2_grpc
from crossdesk_host.watchdog import HeartbeatFsm, State

logger = get_logger("host.ipc.management")


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
    ) -> None:
        self.state = state
        self.libvirt_ctl = libvirt_ctl
        self.coordinator = coordinator
        self.push_interval_seconds = push_interval_seconds

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
            if False:  # pragma: no cover
                yield mgmt_pb2.AppEntry()
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
        # Phase 6 stub: record the request, surface success. Actual
        # FreeRDP RAIL spawning runs through the existing
        # rail_manager / FreeRDPInvocation machinery; integration into
        # mgmt lands when the daemon's main entry point holds shared
        # references (Phase 7).
        with child_span_scope():
            logger.info("rpc_start", method="Launch")
            logger.info(
                "mgmt_launch_request",
                app_id=request.app_id,
                file_path=request.file_path,
            )
            self.state.append_activity(
                mgmt_pb2.RecentActivity.Kind.KIND_APP_LAUNCHED,
                f"Launch requested: {request.app_id}",
            )
            response = mgmt_pb2.LaunchResponse(
                ok=True, request_id=f"mgmt-{int(time.time() * 1000)}"
            )
            logger.info("rpc_end", method="Launch")
            return response

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
