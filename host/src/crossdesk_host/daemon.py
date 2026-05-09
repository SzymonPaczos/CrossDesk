import os
from pathlib import Path

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
from crossdesk_host.observability import configure_logging, get_logger
from crossdesk_host.observability.grpc_interceptor import TraceContextInterceptor
from crossdesk_host.proto.crossdesk.v1 import (
    control_pb2_grpc,
    filesystem_pb2_grpc,
    heartbeat_pb2_grpc,
    mgmt_pb2_grpc,
)
from crossdesk_host.transport.real import RealTransport

configure_logging()
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
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    ca_cert = (base_dir / "infra" / "certs" / "pki" / "ca.crt").read_bytes()
    host_cert = (base_dir / "infra" / "certs" / "pki" / "host.crt").read_bytes()
    host_key = (base_dir / "infra" / "certs" / "pki" / "host.key").read_bytes()

    auth_validator = AuthValidator()
    libvirt_ctl = LibvirtControllerMock()
    mgmt_state = MgmtState()

    transport = RealTransport()
    server = transport.create_server(
        ca_cert,
        host_cert,
        host_key,
        port=50051,
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
