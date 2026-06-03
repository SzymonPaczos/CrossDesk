"""CrossDesk host daemon entry point.

Boots structured logging (must happen before any other ``crossdesk_host``
import that calls ``structlog.get_logger`` at module scope), wires the
mTLS-aware gRPC servicers, opens the libvirt control plane, and runs
the asyncio loop until SIGTERM. Configuration is loaded once from
``~/.config/crossdesk/config.toml`` via ``crossdesk_host.config``; the
daemon does not reload on SIGHUP — restart instead.
"""

import os

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

from crossdesk_host.display.rail_manager import RailManager  # noqa: E402
from crossdesk_host.display.window_icon import WindowIconStore  # noqa: E402
from crossdesk_host.filesystem_ctl.real import LibvirtFilesystemController  # noqa: E402
from crossdesk_host.freerdp.real import RealFreeRDPInvocation  # noqa: E402
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

    ca_cert = cfg.paths.ca_cert.read_bytes()
    host_cert = cfg.paths.host_cert.read_bytes()
    host_key = cfg.paths.host_key.read_bytes()

    auth_validator = AuthValidator()
    libvirt_ctl = LibvirtControllerMock()
    mgmt_state = MgmtState()

    # Shared RAIL launch backend. The control servicer registers the live
    # guest session with the verify_coordinator and routes RailWindowEvents
    # to the rail_manager; the management servicer's Launch RPC uses the
    # same freerdp + coordinator to spawn sessions. One instance each so
    # both planes agree on session/credential state.
    freerdp = RealFreeRDPInvocation()
    verify_coordinator = VerifyCoordinator()
    # Shared icon store: the management Launch RPC registers each launch's
    # app_id; the rail_manager applies the agent's extracted .exe icon to that
    # app's .desktop / icon theme so it shows in the dock (display/window_icon).
    icon_store = WindowIconStore()
    rail_manager = RailManager(freerdp_inv=freerdp, icon_store=icon_store)

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

    control_pb2_grpc.add_ControlServiceServicer_to_server(
        ControlServiceServicer(
            auth_validator,
            rail_manager=rail_manager,
            verify_coordinator=verify_coordinator,
            on_agent_version=_store_agent_version,
        ),
        server,
    )
    heartbeat_pb2_grpc.add_HeartbeatServiceServicer_to_server(
        HeartbeatServiceServicer(auth_validator, libvirt_ctl), server
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

    if systemd_daemon is not None:
        systemd_daemon.notify("READY=1")

    logger.info(
        "Server is running. Awaiting connections.",
        mgmt_socket=str(sock_path),
    )
    await server.wait_for_termination()
