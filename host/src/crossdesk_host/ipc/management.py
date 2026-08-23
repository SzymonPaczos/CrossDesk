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
import re
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
from crossdesk_host.display.rail_supervisor import RailSupervisor
from crossdesk_host.display.session_starter import (
    AuthHealthCheckFailed,
    spawn_rail_with_auth_check,
)
from crossdesk_host.display.window_icon import WindowIconStore
from crossdesk_host.doctor import has_failures, run_all
from crossdesk_host.doctor.checks import Status as DoctorStatus
from crossdesk_host.installer import credentials, settings
from crossdesk_host.ipc.verify_coordinator import NoActiveSession, VerifyCoordinator
from crossdesk_host.jit_mount.path_validation import (
    MountPathError,
    default_allowed_roots,
    parent_share_path,
    validate_mount_path,
)
from crossdesk_host.libvirt_ctl import libvirt_call
from crossdesk_host.lifecycle import LifecycleCoordinator
from crossdesk_host.observability import child_span_scope
from crossdesk_host.observability.log import get_logger
from crossdesk_host.observability.metrics import REGISTRY, MetricNames, Registry
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


# A drive-letter path (C:\…) or a UNC path (\\host\…) ending in .exe. Used to
# let `crossdesk launch <path>` run any installed program without a catalog
# entry. Anchored + .exe-terminated so a plain app_id ("notepad") never matches.
_WIN_EXE_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\).*\.exe$", re.IGNORECASE)


def _spec_from_exe_path(raw: str) -> Optional[AppLaunchSpec]:
    """Build an :class:`AppLaunchSpec` from a raw Windows executable path, or
    ``None`` when *raw* is not such a path. The ``app_id`` (which drives the
    RAIL window's WM_CLASS / grouping) and the display name are derived from
    the executable's base name, e.g. ``C:\\Games\\RobinHood\\RobinHood.exe`` →
    app_id ``robinhood`` / name ``RobinHood``."""
    candidate = raw.strip()
    if not _WIN_EXE_RE.match(candidate):
        return None
    base = re.split(r"[\\/]", candidate)[-1]  # RobinHood.exe
    stem = base[:-4] if base.lower().endswith(".exe") else base
    app_id = re.sub(r"[^A-Za-z0-9_-]", "-", stem).strip("-").lower() or "app"
    return AppLaunchSpec(
        app_id=app_id, executable_guest_path=candidate, display_name=stem
    )


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
        icon_store: Optional[WindowIconStore] = None,
        supervisor: Optional["RailSupervisor"] = None,
    ) -> None:
        self.state = state
        self.libvirt_ctl = libvirt_ctl
        self.coordinator = coordinator
        self.push_interval_seconds = push_interval_seconds
        # Shared with the RailManager: a launch registers its app_id here so
        # the next window icon the agent reports gets applied to that app's
        # .desktop / icon theme (display/window_icon.py). None ⇒ skip.
        self._icon_store = icon_store
        # Launch backend: the FreeRDP spawner + the credential-verify
        # coordinator (shared with the control servicer, which registers
        # the live guest session). Both None ⇒ Launch reports the backend
        # is unavailable rather than pretending success.
        self._freerdp = freerdp
        self._verify_coordinator = verify_coordinator
        # Watches each spawned FreeRDP process: reaps it on exit, logs the
        # reason, and surfaces a notification on an unexpected drop. None ⇒
        # sessions are still spawned but not monitored (e.g. unit tests that
        # don't exercise the supervisor).
        self._supervisor = supervisor
        # RAIL sessions spawned via Launch, kept so they aren't lost. The
        # supervisor's on-exit callback removes a session here once its
        # FreeRDP process dies, so the list reflects live sessions.
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
            started_ns = time.monotonic_ns()
            try:
                response = await self._launch(request)
            finally:
                logger.info("rpc_end", method="Launch")
            if response.ok:
                # Successful launches only. A rejected launch (unknown app, dead
                # guest, bad credentials) is an error, not a slow launch, and
                # folding its latency in would corrupt the p50 this is read against.
                #
                # NOTE what this does and does not measure. It is the HOST-SIDE
                # cost: resolve the app, gate on the credential check, spawn
                # FreeRDP. Measured live it is ~7.5 ms p50 — roughly 0.3% of what
                # the user actually waits for. The window appears ~2.7 s later,
                # and that time is FreeRDP negotiating RDP + RAIL with the guest,
                # entirely after this RPC has returned. So this metric tells you
                # whether the *daemon* is slow; it is NOT criterion #2, which is
                # end-to-end to a window on screen. Measuring that in-product means
                # correlating the launch with the agent's RailWindowEvent CREATED
                # — a follow-up, tracked in the backlog.
                elapsed_s = (time.monotonic_ns() - started_ns) / 1e9
                self.metrics_registry.histogram(
                    MetricNames.LAUNCH_DURATION_SECONDS
                ).observe(elapsed_s)
                logger.info(
                    "launch_duration", app_id=request.app_id, seconds=round(elapsed_s, 3)
                )
            return response

    async def _launch(self, request: mgmt_pb2.LaunchRequest) -> mgmt_pb2.LaunchResponse:
        """Resolve the app, gate on the guest credential check, and spawn
        a FreeRDP RAIL session. Every failure mode maps to
        ``LaunchResponse(ok=False, error=...)`` so the CLI/GUI can print an
        actionable message instead of an opaque RPC error.

        A launch that carries a host ``file_path`` ("Open with Notepad") uses
        DEC-0019 JIT-lite: only that file's parent directory is shared for this
        session (see :meth:`_jitlite_flags`). Stage C JIT-per-file mount/detach
        with ``ReleaseAck`` remains a post-1.0 follow-up."""
        app_id = request.app_id
        if self._freerdp is None or self._verify_coordinator is None:
            return mgmt_pb2.LaunchResponse(
                ok=False, error="launch backend not available in this daemon"
            )
        app = find_app(app_id)
        if app is not None:
            spec = AppLaunchSpec(
                app_id=app.app_id,
                executable_guest_path=app.win_executable,
                display_name=app.name,
            )
        else:
            # Not in the catalog: accept a raw Windows executable path so any
            # installed program (an Office app at a non-standard path, a game,
            # anything the user dropped in via the shared folder + installed)
            # can be launched without first being catalogued. App discovery
            # (registry-scan → catalog) is the scalable follow-up; this is the
            # "just run this .exe" escape hatch.
            by_path = _spec_from_exe_path(app_id)
            if by_path is None:
                return mgmt_pb2.LaunchResponse(
                    ok=False,
                    error=(
                        f"unknown app_id: {app_id!r} (not in the catalog; to "
                        "launch by path pass a Windows .exe path like "
                        r"'C:\\Program Files\\App\\app.exe')"
                    ),
                )
            spec = by_path
        creds = credentials.load()
        if creds is None:
            return mgmt_pb2.LaunchResponse(
                ok=False, error="no VM credentials — run `crossdesk install`"
            )

        conn = FreeRDPConnectionSpec(username=creds.username, password=creds.password)
        # Apply peripheral redirection (audio / clipboard / printer / USB /
        # the scoped shared folder) to the launch. Loaded fresh per launch so
        # an edit to peripherals.toml takes effect on the next app without a
        # daemon restart. Best-effort: a malformed config must not block the
        # launch, so fall back to no extra flags.
        extra_flags, workdir = self._peripheral_flags()
        # DEC-0019 JIT-lite: a launch that carries a host file path shares only
        # that file's parent directory for this session, overriding the
        # persistent scoped share (but keeping the other peripheral flags).
        jit = self._jitlite_flags(request.file_path)
        if jit is not None:
            jit_flags, jit_workdir = jit
            extra_flags = [
                f for f in extra_flags if not f.startswith("/drive:")
            ] + jit_flags
            workdir = jit_workdir
        argv = build_rail_argv(spec, conn, extra_flags=extra_flags, workdir=workdir)

        # Register the icon expectation before the window appears: the agent's
        # CREATED-with-icon for the launched window then applies the real .exe
        # icon to this app's .desktop (display/window_icon.py).
        if self._icon_store is not None:
            self._icon_store.expect(spec.app_id, spec.display_name)

        try:
            session = await spawn_rail_with_auth_check(
                self._freerdp,
                self._verify_coordinator,
                argv,
                creds=creds,
                log_label=app_id,
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
        if self._supervisor is not None:
            # Watch the process: reap on exit, log the reason, notify on an
            # unexpected drop, and drop our handle when it dies.
            self._supervisor.supervise(
                session,
                app_id=spec.app_id,
                display_name=spec.display_name,
                on_exit=self._on_session_exit,
            )
        self.state.append_activity(
            mgmt_pb2.RecentActivity.Kind.KIND_APP_LAUNCHED,
            # spec.display_name covers both the catalog and launch-by-path
            # cases (app may be None when launched by raw .exe path).
            f"Launched {spec.display_name} (pid {session.pid})",
        )
        return mgmt_pb2.LaunchResponse(ok=True, request_id=f"rail-{session.pid}")

    def _peripheral_flags(self) -> tuple[list[str], str]:
        """Resolve the FreeRDP redirection flags **and** the RemoteApp working
        directory for this launch from ``peripherals.toml`` (loaded fresh each
        launch), creating the shared folder on demand.

        Returns ``(flags, workdir)``. *workdir* is the guest-side root of the
        mapped drive (``Z:\\``) when the shared folder is enabled and its host
        directory exists — so a launched app's Save/Open dialog defaults to the
        Linux-visible folder instead of ``C:\\``. A drive letter, not the UNC
        (``\\\\tsclient\\<name>``): Windows ignores a UNC working directory and
        falls back to System32 (verified live 2026-06-09); the guest logon step
        maps the letter to the share. It is empty when the shared folder is off,
        or when its host directory could not be created: in that case the drive
        redirect is dropped too, and a workdir pointing at a share that won't
        mount would only fail the RemoteApp launch.

        Best-effort: any config/IO error degrades to no extra flags and no
        workdir rather than blocking the launch."""
        from crossdesk_host.config.peripherals import load_peripherals_config

        try:
            cfg = load_peripherals_config()
        except Exception:
            logger.warning("peripherals config invalid; launching with no redirections")
            return [], ""
        # DEC-0019: the whole-$HOME ``home`` scope is a security-relevant opt-in.
        # Surface the loud warning at every launch so it is never silent.
        home_warning = cfg.home_scope_warning()
        if home_warning is not None:
            logger.warning("shared_folder_home_scope", warning=home_warning)
        flags = cfg.to_freerdp_flags()
        if not cfg.shared_folder_enabled:
            return flags, ""
        # The drive redirect (and the workdir that points the app at it) only
        # make sense for a real, absolute host directory we can create. Drop
        # both — keeping the other peripheral flags — for any path we can't
        # honour, so the launch never points the app at a share that won't
        # mount. Cases: empty/relative path (Path("").mkdir would silently
        # succeed against the CWD, bypassing the OSError gate) and uncreatable
        # path (parent is a file, permissions, etc.).
        no_share = [f for f in flags if not f.startswith("/drive:")]
        share = cfg.shared_folder_host_path()
        if not share or not os.path.isabs(share):
            logger.warning("shared folder path %r is not absolute; skipping redirect", share)
            return no_share, ""
        try:
            Path(share).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("shared folder %s not creatable: %s", share, exc)
            return no_share, ""
        return flags, cfg.shared_folder_drive_path()

    def _jitlite_flags(self, file_path: str) -> Optional[tuple[List[str], str]]:
        """DEC-0019 JIT-lite: when a launch carries a host file path
        ("Open with Notepad"), share only that file's **parent directory** for
        this RAIL session — a per-launch rdpdr ``/drive:`` that dies with the
        FreeRDP process — instead of any persistent scoped share.

        Returns ``(flags, workdir)`` for the ephemeral drive, or ``None`` when
        the path is not a shareable host file (empty, a guest ``C:\\`` path,
        non-absolute, missing, denylisted, or outside ``$HOME``), in which case
        the caller falls back to the persistent scoped share. Validation reuses
        the JIT-mount choke point (:func:`validate_mount_path`): existence +
        symlink-resolved, under ``$HOME``, not a system root.

        SECURITY: a file sitting *directly* in ``$HOME`` (``~/notes.txt``) has
        ``$HOME`` itself as its parent, so sharing "just the parent" would hand
        the guest the whole home R/W — the exact exposure DEC-0019 made an
        explicit, warned opt-in (``scope = home``), reachable here silently and
        regardless of :attr:`shared_folder_enabled`. Such a parent is refused,
        not shared."""
        if not file_path:
            return None
        try:
            validated = validate_mount_path(file_path)
        except MountPathError as exc:
            # Not JIT-lite-eligible (e.g. a guest path, or outside $HOME) —
            # fall back to the persistent scoped share.
            logger.info("jitlite_skip", file_path=file_path, reason=str(exc))
            return None
        from crossdesk_host.config.peripherals import (
            PeripheralsConfig,
            load_peripherals_config,
        )

        try:
            cfg = load_peripherals_config()
        except Exception:
            # Defaults are fine for the share name / drive letter.
            cfg = PeripheralsConfig()
        # parent_share_path's contract is "caller still must run
        # validate_mount_path on the result" — the parent is a different path
        # from the file, so it gets the same denylist / allowed-root / symlink
        # treatment rather than inheriting the child's verdict.
        parent = parent_share_path(validated.canonical)
        try:
            validated_parent = validate_mount_path(str(parent))
        except MountPathError as exc:
            logger.info("jitlite_skip", file_path=file_path, reason=str(exc))
            return None
        roots = [root.resolve() for root in default_allowed_roots()]
        if validated_parent.canonical in roots:
            # Refuse rather than fall through to a warning: the persistent
            # scoped share (or no share at all, when sharing is off) is the
            # safe default, and a per-launch whole-$HOME share is precisely
            # what DEC-0019 removed from the defaults.
            logger.warning(
                "jitlite_root_scope_refused",
                file_path=file_path,
                host_dir=str(validated_parent.canonical),
                reason=(
                    "sharing this file's parent would expose an entire allowed "
                    "root (e.g. $HOME) to the guest; falling back to the "
                    "configured share (DEC-0019)"
                ),
            )
            return None
        parent = validated_parent.canonical
        flags = [f"/drive:{cfg.shared_folder_name},{parent}"]
        workdir = f"{cfg.shared_folder_drive_letter}:\\"
        logger.info("jitlite_share", host_dir=str(parent))
        return flags, workdir

    def _on_session_exit(self, session: RailSession, returncode: int) -> None:
        """Supervisor callback: drop the dead session from the live list."""
        self._sessions = [s for s in self._sessions if s.pid != session.pid]

    async def Suspend(  # noqa: N802
        self, request: mgmt_pb2.Empty, context: grpc.aio.ServicerContext
    ) -> mgmt_pb2.ActionAck:
        with child_span_scope():
            logger.info("rpc_start", method="Suspend")
            try:
                if self.coordinator is not None:
                    await self.coordinator.on_prepare_for_sleep()
                else:
                    await libvirt_call(self.libvirt_ctl.suspend)
                self.state.append_activity(
                    mgmt_pb2.RecentActivity.Kind.KIND_SUSPEND, "Manual suspend"
                )
                logger.info("rpc_end", method="Suspend")
                return mgmt_pb2.ActionAck(ok=True)
            except asyncio.TimeoutError:
                logger.info("rpc_end_early", method="Suspend", reason="libvirt_timeout")
                return mgmt_pb2.ActionAck(
                    ok=False, detail="libvirt call timed out after 30s"
                )
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
                    await self.coordinator.on_resumed()
                else:
                    await libvirt_call(self.libvirt_ctl.resume)
                self.state.append_activity(
                    mgmt_pb2.RecentActivity.Kind.KIND_RESUME, "Manual resume"
                )
                logger.info("rpc_end", method="Resume")
                return mgmt_pb2.ActionAck(ok=True)
            except asyncio.TimeoutError:
                logger.info("rpc_end_early", method="Resume", reason="libvirt_timeout")
                return mgmt_pb2.ActionAck(
                    ok=False, detail="libvirt call timed out after 30s"
                )
            except Exception as exc:
                logger.info("rpc_end_early", method="Resume", reason="libvirt_error")
                return mgmt_pb2.ActionAck(ok=False, detail=str(exc))

    async def HardDestroy(  # noqa: N802
        self, request: mgmt_pb2.Empty, context: grpc.aio.ServicerContext
    ) -> mgmt_pb2.ActionAck:
        with child_span_scope():
            logger.info("rpc_start", method="HardDestroy")
            try:
                await libvirt_call(self.libvirt_ctl.hard_destroy)
                self.state.last_hard_destroy = datetime.now(timezone.utc)
                self.state.append_activity(
                    mgmt_pb2.RecentActivity.Kind.KIND_HARD_DESTROY,
                    "Manual HARD_DESTROY",
                )
                logger.info("rpc_end", method="HardDestroy")
                return mgmt_pb2.ActionAck(ok=True)
            except asyncio.TimeoutError:
                logger.info(
                    "rpc_end_early",
                    method="HardDestroy",
                    reason="libvirt_timeout",
                )
                return mgmt_pb2.ActionAck(
                    ok=False, detail="libvirt call timed out after 30s"
                )
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
