"""CrossDesk host daemon entry point.

Boots structured logging (must happen before any other ``crossdesk_host``
import that calls ``structlog.get_logger`` at module scope), wires the
mTLS-aware gRPC servicers, opens the libvirt control plane, and runs
the asyncio loop until SIGTERM. Configuration is loaded once from
``~/.config/crossdesk/config.toml`` via ``crossdesk_host.config``; the
daemon does not reload on SIGHUP — restart instead.
"""

import asyncio
import os
import signal
import threading
from typing import Optional

# Configure structured logging FIRST — before importing any module that
# captures `structlog.get_logger(...)` (or stdlib logging) at import
# time. Without this ordering every servicer's module-level logger
# binds to the default factory before configure_logging() rewires
# structlog's processors / contextvars / JSON renderer; the servicer
# never observes the configured stream and trace_id binding never
# reaches its log records. Discovered during the trace-propagation
# completion sweep — each ipc/* module that does
# ``logger = get_logger(__name__)`` at module scope was a victim.
from crossdesk_host.observability import configure_logging, get_logger

configure_logging()

import grpc  # noqa: E402

try:
    import systemd.daemon as systemd_daemon  # noqa: E402
except ImportError:
    systemd_daemon = None

from crossdesk_host.abstractions.libvirt import LibvirtController  # noqa: E402
from crossdesk_host.display.rail_manager import RailManager  # noqa: E402
from crossdesk_host.display.rail_supervisor import RailSupervisor  # noqa: E402
from crossdesk_host.display.window_icon import WindowIconStore  # noqa: E402
from crossdesk_host.filesystem_ctl.real import LibvirtFilesystemController  # noqa: E402
from crossdesk_host.freerdp.real import RealFreeRDPInvocation  # noqa: E402
from crossdesk_host.installer.steady_state import finalize_steady_state  # noqa: E402
from crossdesk_host.ipc.auth import AuthValidator  # noqa: E402
from crossdesk_host.ipc.control import ControlServiceServicer  # noqa: E402
from crossdesk_host.ipc.filesystem import FilesystemServiceServicer  # noqa: E402
from crossdesk_host.ipc.heartbeat import HeartbeatServiceServicer  # noqa: E402
from crossdesk_host.ipc.management import (  # noqa: E402
    ManagementServiceServicer,
    MgmtState,
    mgmt_socket_path,
)
from crossdesk_host.ipc.verify_coordinator import VerifyCoordinator  # noqa: E402
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock  # noqa: E402
from crossdesk_host.lifecycle.coordinator import LifecycleCoordinator  # noqa: E402
from crossdesk_host.lifecycle.dbus_listener import start_listener  # noqa: E402
from crossdesk_host.lifecycle.notifications import SubprocessNotifier  # noqa: E402
from crossdesk_host.observability.grpc_interceptor import TraceContextInterceptor  # noqa: E402
from crossdesk_host.observability.otlp import configure_from_env as configure_otlp_from_env  # noqa: E402
from crossdesk_host.proto.crossdesk.v1 import (  # noqa: E402
    control_pb2_grpc,
    filesystem_pb2_grpc,
    heartbeat_pb2_grpc,
    mgmt_pb2_grpc,
)
from crossdesk_host.transport.real import RealTransport  # noqa: E402

# OTLP span exporter wires here, after configure_logging() (which ran
# above before servicer imports — see the comment at the top of this
# module) so any warnings the SDK emits land in the JSON stream rather
# than the default stderr formatter. The function is a no-op when
# CROSSDESK_OTLP_ENDPOINT is unset, so production daemons that don't
# run their own collector pay nothing.
configure_otlp_from_env()

logger = get_logger("host.daemon")


def _assert_suspend_protection(
    libvirt_ctl: LibvirtController, listener_active: bool
) -> None:
    """Fail closed: the real libvirt controller must never run without the
    host-suspend listener wired.

    Without it, a host sleep strands the heartbeat FSMs ticking across the
    pause; missed pongs escalate to HARD_DESTROY, which on the real
    controller is ``virsh destroy`` — the VM and everything unsaved in it,
    gone. The mock controller has nothing to lose, so dev hosts without
    D-Bus are allowed through (the caller already logged the warning).
    """
    if listener_active or isinstance(libvirt_ctl, LibvirtControllerMock):
        return
    raise RuntimeError(
        "refusing to start: real libvirt controller without host-suspend "
        "protection. A host suspend could escalate the heartbeat FSM to "
        "virsh destroy and lose the VM. Install crossdesk-host[linux] so the "
        "PrepareForSleep listener can start."
    )


async def main() -> None:
    """Run the daemon until the asyncio loop is cancelled.

    Loads typed configuration from ``~/.config/crossdesk/config.toml``
    (defaults preserved if the file is absent), wires mTLS material from
    the configured PKI paths, instantiates the libvirt controller +
    servicers, and starts the gRPC server. Returns when the server is
    asked to stop; does not catch SIGTERM itself — that is the caller's
    job (``__main__.py`` uses ``asyncio.run``).
    """
    from crossdesk_host.config import load_from_toml

    cfg = load_from_toml()

    # Re-configure logging now that we know the state dir, adding a bounded
    # rotating file alongside stderr so `crossdesk logs` works for users not
    # running under journald and we can ask a beta tester to attach it.
    # Done here (not at import) so merely importing the daemon never writes
    # a file. Idempotent — rebinds the processor chain.
    configure_logging(log_file=cfg.paths.state_dir / "logs" / "crossdesk-host.jsonl")

    ca_cert = cfg.paths.ca_cert.read_bytes()
    host_cert = cfg.paths.host_cert.read_bytes()
    host_key = cfg.paths.host_key.read_bytes()

    auth_validator = AuthValidator()
    # Backend is config-selectable (default mock, unchanged dev behaviour). Set
    # libvirt.backend = "real" (or CROSSDESK_CONFIG__LIBVIRT__BACKEND=real) on a
    # Linux+KVM host to drive the real qemu:///session domain — that also
    # activates the steady-state finalize + real heartbeat recovery below.
    # RealLibvirtController is imported lazily so a dev host without
    # libvirt-python still imports the daemon module.
    libvirt_ctl: LibvirtController
    if cfg.libvirt.backend == "real":
        from crossdesk_host.libvirt_ctl.real import RealLibvirtController

        libvirt_ctl = RealLibvirtController(domain_name=cfg.libvirt.domain_name)
    else:
        libvirt_ctl = LibvirtControllerMock()
    mgmt_state = MgmtState()

    # Shared RAIL launch backend. The control servicer registers the live
    # guest session with the verify_coordinator and routes RailWindowEvents
    # to the rail_manager; the management servicer's Launch RPC uses the
    # same freerdp + coordinator to spawn sessions. One instance each so
    # both planes agree on session/credential state.
    freerdp = RealFreeRDPInvocation()
    verify_coordinator = VerifyCoordinator()
    # One notifier surfaces watchdog / RAIL-drop errors to the desktop
    # (notify-send; a silent no-op on headless boxes). Previously the
    # servicers were constructed without one, so every notify_* helper
    # was dead code in production — wire it once here.
    notifier = SubprocessNotifier()
    # Shared icon store: the management Launch RPC registers each launch's
    # app_id; the rail_manager applies the agent's extracted .exe icon to that
    # app's .desktop / icon theme so it shows in the dock (display/window_icon).
    icon_store = WindowIconStore()
    rail_manager = RailManager(
        freerdp_inv=freerdp, icon_store=icon_store, notifier=notifier
    )
    # Supervises each spawned FreeRDP process: reaps it on exit (no more
    # zombie xfreerdp), logs why it ended, and notifies on an unexpected
    # drop instead of leaving a dead window with no message.
    rail_supervisor = RailSupervisor(freerdp, notifier=notifier)

    transport = RealTransport()
    server = transport.create_server(
        ca_cert,
        host_cert,
        host_key,
        port=cfg.transport.vsock_port,
        interceptors=[TraceContextInterceptor()],
        bind_kind=cfg.transport.bind_kind,
    )

    def _store_agent_version(version: str) -> None:
        mgmt_state.agent_version = version

    # Post-install steady-state finalize: on the first agent Hello, redefine
    # the persistent domain so a later hard_destroy can't reboot the install
    # ISO and reinstall over the disk (installer.steady_state). It rewrites the
    # REAL domain via defineXML — running it against the mock would mark the
    # step done without redefining anything, masking the data-loss path once
    # the real controller lands. So only wire it when the controller is real.
    # on_session_ready now runs in a thread (control offloads it via
    # libvirt_call), so two concurrent Hellos could enter finalize at once.
    # A non-blocking lock makes it single-flight; finalize is idempotent, so a
    # skipped concurrent run just retries on the next Hello.
    _finalize_once = threading.Lock()

    def _finalize_steady_state() -> None:
        if not _finalize_once.acquire(blocking=False):
            return
        try:
            finalize_steady_state(libvirt_ctl)
        finally:
            _finalize_once.release()

    on_session_ready = (
        None if isinstance(libvirt_ctl, LibvirtControllerMock) else _finalize_steady_state
    )

    control_pb2_grpc.add_ControlServiceServicer_to_server(
        ControlServiceServicer(
            auth_validator,
            rail_manager=rail_manager,
            verify_coordinator=verify_coordinator,
            on_agent_version=_store_agent_version,
            on_session_ready=on_session_ready,
        ),
        server,
    )
    heartbeat_servicer = HeartbeatServiceServicer(
        auth_validator, libvirt_ctl, notifier=notifier
    )
    heartbeat_pb2_grpc.add_HeartbeatServiceServicer_to_server(
        heartbeat_servicer, server
    )
    # Host suspend/resume protection. On a host sleep the coordinator moves
    # the heartbeat FSMs into SUSPENDED before the VM pauses (and back after),
    # so missed pongs across the sleep can't escalate to a false-positive
    # HARD_DESTROY. fsm_group = the heartbeat servicer: it already owns every
    # live channel and inherits SUSPENDED onto channels that attach mid-sleep.
    lifecycle_coordinator = LifecycleCoordinator(
        libvirt_ctl, notifier=notifier, fsm_group=heartbeat_servicer
    )
    filesystem_pb2_grpc.add_FilesystemServiceServicer_to_server(
        FilesystemServiceServicer(
            auth_validator, LibvirtFilesystemController(libvirt_ctl)
        ),
        server,
    )

    # Local management socket for the GUI / tray / KCM. Separate gRPC
    # server, no mTLS — Unix permissions on the socket file gate access.
    mgmt_server = grpc.aio.server()
    mgmt_pb2_grpc.add_ManagementServiceServicer_to_server(
        ManagementServiceServicer(
            mgmt_state,
            libvirt_ctl,
            freerdp=freerdp,
            verify_coordinator=verify_coordinator,
            icon_store=icon_store,
            supervisor=rail_supervisor,
        ),
        mgmt_server,
    )
    sock_path = mgmt_socket_path()
    if sock_path.exists():
        sock_path.unlink()
    mgmt_server.add_insecure_port(f"unix://{sock_path}")

    await server.start()
    await mgmt_server.start()

    # 0600 on the socket file so other local users can't connect.
    if sock_path.exists():
        os.chmod(sock_path, 0o600)

    # Drive the coordinator from the host's D-Bus PrepareForSleep signal.
    # Linux-only (needs dbus-next); on a dev host start_listener raises and we
    # run without protection — _assert_suspend_protection then refuses to
    # continue if that's paired with the real controller (fail-closed).
    lifecycle_listener: Optional[asyncio.Task[None]] = None
    try:
        lifecycle_listener = await start_listener(lifecycle_coordinator)
    except RuntimeError as exc:
        logger.warning("lifecycle_listener_unavailable", error=str(exc))
    _assert_suspend_protection(libvirt_ctl, lifecycle_listener is not None)

    if systemd_daemon is not None:
        systemd_daemon.notify("READY=1")

    # Graceful shutdown on SIGTERM (systemd stop) / SIGINT (Ctrl-C): the
    # default SIGTERM action kills the process before the gRPC servers and
    # FreeRDP children get a chance to stop cleanly, leaking sockets and
    # leaving orphaned xfreerdp. Trip a stop event instead and unwind below.
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError):
            # add_signal_handler isn't available on every platform/loop
            # (e.g. a non-main thread). Fall back to the default disposition.
            pass

    logger.info(
        "Server is running. Awaiting connections.",
        mgmt_socket=str(sock_path),
    )
    try:
        await stop_event.wait()
    finally:
        logger.info("daemon_shutting_down")
        if lifecycle_listener is not None:
            lifecycle_listener.cancel()
        # Stop FreeRDP children first so the supervisor's monitor tasks see
        # an expected exit, then the gRPC servers.
        await rail_supervisor.shutdown_all()
        await server.stop(grace=2.0)
        await mgmt_server.stop(grace=2.0)
