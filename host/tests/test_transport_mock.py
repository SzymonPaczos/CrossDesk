"""MockTransport behaviours.

The real transport flows the same code path on TCP loopback today on Mac;
what we test here are the mock-only hooks (failure injection, server-create
counter) so callers can rely on them when scripting deterministic test
scenarios per DEC-0005.
"""
from __future__ import annotations

from pathlib import Path

import grpc
import pytest

from crossdesk_host.abstractions.transport import Transport
from crossdesk_host.transport.mock import MockTransport


PKI_DIR = Path(__file__).resolve().parent.parent.parent / "infra" / "certs" / "pki"


def _load_pki() -> tuple[bytes, bytes, bytes] | None:
    ca = PKI_DIR / "ca.crt"
    host_cert = PKI_DIR / "host.crt"
    host_key = PKI_DIR / "host.key"
    if not (ca.exists() and host_cert.exists() and host_key.exists()):
        return None
    return ca.read_bytes(), host_cert.read_bytes(), host_key.read_bytes()


def test_mock_transport_satisfies_protocol() -> None:
    transport = MockTransport()
    assert isinstance(transport, Transport)


def test_fail_next_bind_raises_then_clears() -> None:
    pki = _load_pki()
    if pki is None:
        pytest.skip("PKI material not present at infra/certs/pki/")
    ca, host_cert, host_key = pki

    transport = MockTransport()
    transport.hooks.fail_next_bind = True

    with pytest.raises(RuntimeError, match="mock-injected bind failure"):
        transport.create_server(ca, host_cert, host_key, port=0)

    assert transport.hooks.fail_next_bind is False, "hook clears after firing"
    assert transport.hooks.server_create_count == 0


def test_successful_create_increments_counter() -> None:
    pki = _load_pki()
    if pki is None:
        pytest.skip("PKI material not present at infra/certs/pki/")
    ca, host_cert, host_key = pki

    transport = MockTransport()
    server = transport.create_server(ca, host_cert, host_key, port=0)

    assert transport.hooks.server_create_count == 1
    assert isinstance(server, grpc.aio.Server)
