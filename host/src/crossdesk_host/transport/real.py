"""Production transport. Linux binds AF_VSOCK; macOS/Windows bind TCP
loopback for dev — that's not a fallback, it's the explicit dev path
because those OSes have no AF_VSOCK kernel support.
"""

from __future__ import annotations

import logging
import sys

import grpc

from crossdesk_host.abstractions.transport import Transport

logger = logging.getLogger(__name__)


def _expected_endpoint(port: int) -> tuple[str, str]:
    """Pick the canonical bind endpoint for the current platform.

    Returns ``(endpoint, kind)`` where ``kind`` is either ``"vsock"`` or
    ``"tcp"``. macOS and stock Windows have no AF_VSOCK, so they
    intentionally target TCP — that is *not* a fallback, it is the
    production path on those platforms during development.
    """
    if sys.platform in ("darwin", "win32"):
        return f"127.0.0.1:{port}", "tcp"
    return f"vsock:-1:{port}", "vsock"


class RealTransport(Transport):
    """mTLS gRPC server bound to the platform-canonical address family.

    Stateless — multiple instances are fine. Cert material is supplied per
    ``create_server`` call so callers can drive multiple servers from the
    same transport object during tests.
    """

    def create_server(
        self,
        ca_cert_pem: bytes,
        host_cert_pem: bytes,
        host_key_pem: bytes,
        port: int,
    ) -> grpc.aio.Server:
        server = grpc.aio.server()

        server_credentials = grpc.ssl_server_credentials(
            [(host_key_pem, host_cert_pem)],
            root_certificates=ca_cert_pem,
            require_client_auth=True,
        )

        endpoint, kind = _expected_endpoint(port)

        bound_port = server.add_secure_port(endpoint, server_credentials)
        if bound_port == 0:
            raise RuntimeError(
                f"Failed to bind {kind} endpoint {endpoint!r}; "
                "on Linux ensure `modprobe vhost_vsock` succeeded, "
                "otherwise free the port."
            )

        logger.info("gRPC server listening securely on %s (%s)", endpoint, kind)
        return server
