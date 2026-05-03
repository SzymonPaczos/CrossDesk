import logging
import sys
from pathlib import Path

import grpc

logger = logging.getLogger(__name__)


def _expected_endpoint(vsock_port: int) -> tuple[str, str]:
    """
    Pick the canonical bind endpoint for the current platform.

    Returns a `(endpoint, kind)` pair where `kind` is either ``"vsock"`` or
    ``"tcp"``. macOS and stock Windows have no AF_VSOCK, so they intentionally
    target TCP — that is *not* a fallback, it is the production path on those
    platforms during development.
    """
    if sys.platform in ("darwin", "win32"):
        return f"127.0.0.1:{vsock_port}", "tcp"
    return f"vsock:-1:{vsock_port}", "vsock"


def create_vsock_server(
    ca_cert_path: Path,
    host_cert_path: Path,
    host_key_path: Path,
    vsock_port: int = 50051,
) -> grpc.aio.Server:
    """Create an mTLS-secured async gRPC server bound to AF_VSOCK (Linux) or TCP loopback (dev)."""
    server = grpc.aio.server()

    ca_cert = ca_cert_path.read_bytes()
    host_cert = host_cert_path.read_bytes()
    host_key = host_key_path.read_bytes()

    server_credentials = grpc.ssl_server_credentials(
        [(host_key, host_cert)],
        root_certificates=ca_cert,
        require_client_auth=True,
    )

    endpoint, kind = _expected_endpoint(vsock_port)

    port = server.add_secure_port(endpoint, server_credentials)
    if port == 0:
        # On Linux, failure to bind a vsock endpoint means vhost_vsock is not
        # loaded — falling back to TCP would silently bypass the entire
        # transport-isolation model. On macOS/Windows we are already on TCP, so
        # a bind failure means the port is taken.
        raise RuntimeError(
            f"Failed to bind {kind} endpoint {endpoint!r}; "
            "on Linux ensure `modprobe vhost_vsock` succeeded, "
            "otherwise free the port."
        )

    logger.info("gRPC server listening securely on %s (%s)", endpoint, kind)
    return server
