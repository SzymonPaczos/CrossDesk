"""Backwards-compat shim — the transport layer moved to
``crossdesk_host.transport`` per DEC-0005.

New callers should import from ``crossdesk_host.transport.real`` (or
``mock``) directly. This module is preserved so existing tests and any
external callers don't break in the same revision that introduces the
abstraction.
"""

from __future__ import annotations

from pathlib import Path

import grpc

from crossdesk_host.transport.real import RealTransport, _expected_endpoint

__all__ = ["create_vsock_server", "_expected_endpoint"]


def create_vsock_server(
    ca_cert_path: Path,
    host_cert_path: Path,
    host_key_path: Path,
    vsock_port: int = 50051,
) -> grpc.aio.Server:
    """Create an mTLS gRPC server bound to AF_VSOCK (Linux) or TCP (dev).

    Thin wrapper that reads the cert files and delegates to
    ``RealTransport.create_server``. Prefer ``RealTransport`` directly in
    new code so cert material can be tested in-memory.
    """
    return RealTransport().create_server(
        ca_cert_path.read_bytes(),
        host_cert_path.read_bytes(),
        host_key_path.read_bytes(),
        vsock_port,
    )
