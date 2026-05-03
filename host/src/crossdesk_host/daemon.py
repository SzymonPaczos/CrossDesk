import logging
from pathlib import Path

try:
    import systemd.daemon as systemd_daemon
except ImportError:
    systemd_daemon = None

from crossdesk_host.ipc.server import create_vsock_server
from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.ipc.control import ControlServiceServicer
from crossdesk_host.ipc.heartbeat import HeartbeatServiceServicer
from crossdesk_host.ipc.filesystem import FilesystemServiceServicer
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.proto.crossdesk.v1 import control_pb2_grpc
from crossdesk_host.proto.crossdesk.v1 import heartbeat_pb2_grpc
from crossdesk_host.proto.crossdesk.v1 import filesystem_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    ca_cert = base_dir / "infra" / "certs" / "pki" / "ca.crt"
    host_cert = base_dir / "infra" / "certs" / "pki" / "host.crt"
    host_key = base_dir / "infra" / "certs" / "pki" / "host.key"

    auth_validator = AuthValidator()
    libvirt_ctl = LibvirtControllerMock()

    server = create_vsock_server(ca_cert, host_cert, host_key)

    control_pb2_grpc.add_ControlServiceServicer_to_server(
        ControlServiceServicer(auth_validator), server
    )
    heartbeat_pb2_grpc.add_HeartbeatServiceServicer_to_server(
        HeartbeatServiceServicer(auth_validator, libvirt_ctl), server
    )
    filesystem_pb2_grpc.add_FilesystemServiceServicer_to_server(
        FilesystemServiceServicer(auth_validator, libvirt_ctl), server
    )

    await server.start()

    if systemd_daemon is not None:
        systemd_daemon.notify("READY=1")

    logger.info("Server is running. Awaiting connections...")
    await server.wait_for_termination()
