import os
from pathlib import Path

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

import grpc

try:
    import systemd.daemon as systemd_daemon
except ImportError:
    systemd_daemon = None

from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.ipc.control import ControlServiceServicer
from crossdesk_host.ipc.filesystem import FilesystemServiceServicer
from crossdesk_host.ipc.heartbeat import HeartbeatServiceServicer
from crossdesk_host.ipc.management import ManagementServiceServicer, MgmtState
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.observability.grpc_interceptor import TraceContextInterceptor
from crossdesk_host.observability.otlp import configure_from_env as configure_otlp_from_env
from crossdesk_host.proto.crossdesk.v1 import (
    control_pb2_grpc,
    filesystem_pb2_grpc,
    heartbeat_pb2_grpc,
    mgmt_pb2_grpc,
)
from crossdesk_host.transport.real import RealTransport

# OTLP span exporter wires here, after configure_logging() (which ran
# above before servicer imports — see the comment at the top of this
# module) so any warnings the SDK emits land in the JSON stream rather
# than the default stderr formatter. The function is a no-op when
# CROSSDESK_OTLP_ENDPOINT is unset, so production daemons that don't
# run their own collector pay nothing.
configure_otlp_from_env()

logger = get_logger("host.daemon")


def _mgmt_socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "crossdesk-host.sock"
    # Fallback for environments without XDG_RUNTIME_DIR (Mac dev,
    # minimal containers): drop the socket under ~/.local/run.
    fallback = Path.home() / ".local" / "run"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / "crossdesk-host.sock"


async def main() -> None:
    # Single typed entry point for every operator-facing knob (paths,
    # ports, mTLS material, peripherals). Defaults match the historical
    # hardcoded values in this file so a missing config.toml keeps
    # behaviour identical; an operator that wants to override anything
    # drops a ``~/.config/crossdesk/config.toml`` and restarts.
    from crossdesk_host.config import load_from_toml

    cfg = load_from_toml()

    ca_cert = cfg.paths.ca_cert.read_bytes()
    host_cert = cfg.paths.host_cert.read_bytes()
    host_key = cfg.paths.host_key.read_bytes()

    auth_validator = AuthValidator()
    libvirt_ctl = LibvirtControllerMock()
    mgmt_state = MgmtState()

    transport = RealTransport()
    server = transport.create_server(
        ca_cert,
        host_cert,
        host_key,
        port=cfg.transport.vsock_port,
        interceptors=[TraceContextInterceptor()],
    )

    control_pb2_grpc.add_ControlServiceServicer_to_server(
        ControlServiceServicer(auth_validator), server
    )
    heartbeat_pb2_grpc.add_HeartbeatServiceServicer_to_server(
        HeartbeatServiceServicer(auth_validator, libvirt_ctl), server
    )
    filesystem_pb2_grpc.add_FilesystemServiceServicer_to_server(
        FilesystemServiceServicer(auth_validator, libvirt_ctl), server
    )

    # Local management socket for the GUI / tray / KCM. Separate gRPC
    # server, no mTLS — Unix permissions on the socket file gate access.
    mgmt_server = grpc.aio.server()
    mgmt_pb2_grpc.add_ManagementServiceServicer_to_server(
        ManagementServiceServicer(mgmt_state, libvirt_ctl), mgmt_server
    )
    sock_path = _mgmt_socket_path()
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
