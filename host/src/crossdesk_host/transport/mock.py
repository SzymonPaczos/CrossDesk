"""Test-side transport. Always TCP loopback, never vsock — but enforces
the same mTLS bind semantics as the real transport (require_client_auth,
root_certificates, etc.). Exposes failure-injection hooks so tests can
script bind failures, port-already-taken, and similar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Sequence

import grpc

from crossdesk_host.abstractions.transport import Transport

logger = logging.getLogger(__name__)


@dataclass
class MockHooks:
    """Knobs flipped by tests to drive deterministic failure scenarios.

    Each hook fires at most once per ``create_server`` call so a "fail on
    the third bind" pattern is built by toggling the hook between calls.
    """

    fail_next_bind: bool = False
    """If ``True``, the next ``create_server`` raises ``RuntimeError``
    instead of binding. Cleared after firing."""

    server_create_count: int = field(default=0)
    """Total number of servers successfully created. Tests inspect this
    to confirm the transport was actually exercised."""


class MockTransport(Transport):
    """TCP-only mTLS transport for unit tests.

    Honours the same ``require_client_auth`` and certificate material
    contract as ``RealTransport`` so tests catch real validation
    regressions, but always binds 127.0.0.1 regardless of platform.
    """

    def __init__(self) -> None:
        self.hooks = MockHooks()

    def create_server(
        self,
        ca_cert_pem: bytes,
        host_cert_pem: bytes,
        host_key_pem: bytes,
        port: int,
        interceptors: Sequence[grpc.aio.ServerInterceptor] | None = None,
    ) -> grpc.aio.Server:
        if self.hooks.fail_next_bind:
            self.hooks.fail_next_bind = False
            raise RuntimeError("mock-injected bind failure")

        server = grpc.aio.server(
            interceptors=tuple(interceptors) if interceptors else None
        )
        server_credentials = grpc.ssl_server_credentials(
            [(host_key_pem, host_cert_pem)],
            root_certificates=ca_cert_pem,
            require_client_auth=True,
        )

        endpoint = f"127.0.0.1:{port}"
        bound_port = server.add_secure_port(endpoint, server_credentials)
        if bound_port == 0:
            raise RuntimeError(f"MockTransport: failed to bind {endpoint!r}")

        self.hooks.server_create_count += 1
        logger.debug("mock gRPC server listening on %s", endpoint)
        return server
