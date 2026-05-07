"""Transport Protocol — host-side abstraction for the gRPC bind step.

The Linux production path binds an mTLS gRPC server on AF_VSOCK; the
macOS/Windows dev path binds the same server on TCP loopback. Tests
substitute a mock that always uses TCP and exposes failure-injection
hooks.

Real implementation: ``crossdesk_host.transport.real.RealTransport``.
Mock implementation: ``crossdesk_host.transport.mock.MockTransport``.

Both must enforce identical mTLS validation rules — the only allowed
divergences are:
- the address family (AF_VSOCK vs TCP loopback)
- the failure-injection hooks the mock exposes for tests
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

import grpc


@runtime_checkable
class Transport(Protocol):
    """Server-side transport factory.

    Implementations build a fully-configured ``grpc.aio.Server`` bound to
    the appropriate endpoint with mTLS credentials wired in. Callers register
    servicers and start the server themselves — the transport is responsible
    only for the address family / port / TLS material decision.
    """

    def create_server(
        self,
        ca_cert_pem: bytes,
        host_cert_pem: bytes,
        host_key_pem: bytes,
        port: int,
        interceptors: Sequence[grpc.aio.ServerInterceptor] | None = None,
    ) -> grpc.aio.Server:
        """Build a secure gRPC server bound to a transport-specific endpoint.

        ``interceptors`` are wired into the gRPC server before any
        servicer is registered — used for cross-cutting concerns
        (W3C Trace Context extraction, redaction enforcement,
        metrics) per DEC-0006.

        Raises ``RuntimeError`` if the bind fails — production paths must
        not silently fall back to a less-isolated transport (Linux refusing
        to bind AF_VSOCK should not transparently land on TCP).
        """
        ...
