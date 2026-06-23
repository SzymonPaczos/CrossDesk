"""MockTransport behaviours.

The real transport flows the same code path on TCP loopback today on Mac;
what we test here are the mock-only hooks (failure injection, server-create
counter) so callers can rely on them when scripting deterministic test
scenarios per DEC-0005.

PKI: tests mint an ephemeral CA + host leaf via ``cryptography`` so we
don't depend on ``infra/certs/pki/`` being populated (those leaves are
gitignored). Prior version of this file skipped most cases when the
real PKI wasn't on disk — coverage on transport/mock.py sat at 59%.
"""

from __future__ import annotations

import asyncio
import datetime
from pathlib import Path
from typing import Iterator, Tuple
from unittest.mock import MagicMock, patch

import grpc
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from crossdesk_host.abstractions.transport import Transport
from crossdesk_host.transport.mock import MockHooks, MockTransport

_REAL_PKI_DIR = Path(__file__).resolve().parent.parent.parent / "infra" / "certs" / "pki"


@pytest.fixture(autouse=True)
def _current_event_loop() -> Iterator[None]:
    """Give each sync test in this module its own current event loop.

    ``grpc.aio.server()`` calls ``asyncio.get_event_loop()`` internally; on
    Python 3.12 that raises ``RuntimeError: no current event loop`` when none
    is set — exactly the state pytest-asyncio leaves behind after any
    preceding async test (it closes its loop and unsets the current one). That
    made these create_server tests fail only when ordered after an async test
    (green in isolation, green on the 3.10 CI where get_event_loop still
    auto-creates). A fresh per-test loop makes them order-independent.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def _mint_self_signed(name: str) -> Tuple[bytes, bytes, bytes]:
    """Generate an in-memory CA + host leaf for transport tests.

    Returns ``(ca_pem, host_cert_pem, host_key_pem)``. The host cert is
    signed by the CA so the gRPC server's
    ``require_client_auth=True`` will accept clients whose certs
    chain to the same root.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, name)]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    # CA == host cert == self-signed root. That's fine for transport
    # bind tests — what we exercise is grpc.ssl_server_credentials
    # parsing the PEM, not a real chain.
    return cert_pem, cert_pem, key_pem


@pytest.fixture(scope="module")
def pki() -> Tuple[bytes, bytes, bytes]:
    """Ephemeral PKI material reused across all tests in this module."""
    return _mint_self_signed("crossdesk-test")


# ---------------------------------------------------------------------------
# Protocol satisfaction + dataclass smoke
# ---------------------------------------------------------------------------


def test_mock_transport_satisfies_protocol() -> None:
    transport = MockTransport()
    assert isinstance(transport, Transport)


def test_hooks_dataclass_defaults() -> None:
    """MockHooks initialises with disarmed failure injection and zero count."""
    hooks = MockHooks()
    assert hooks.fail_next_bind is False
    assert hooks.server_create_count == 0


def test_hooks_reset_per_instance() -> None:
    """Each MockTransport gets its own hooks object — no shared state."""
    t1 = MockTransport()
    t2 = MockTransport()
    t1.hooks.fail_next_bind = True
    assert t2.hooks.fail_next_bind is False


# ---------------------------------------------------------------------------
# Failure injection
# ---------------------------------------------------------------------------


def test_fail_next_bind_raises_then_clears(pki: Tuple[bytes, bytes, bytes]) -> None:
    ca, host_cert, host_key = pki
    transport = MockTransport()
    transport.hooks.fail_next_bind = True

    with pytest.raises(RuntimeError, match="mock-injected bind failure"):
        transport.create_server(ca, host_cert, host_key, port=0)

    assert transport.hooks.fail_next_bind is False, "hook clears after firing"
    assert transport.hooks.server_create_count == 0


def test_fail_next_bind_only_fires_once(pki: Tuple[bytes, bytes, bytes]) -> None:
    """After the failure hook fires, subsequent create_server calls succeed."""
    ca, host_cert, host_key = pki
    transport = MockTransport()
    transport.hooks.fail_next_bind = True

    with pytest.raises(RuntimeError):
        transport.create_server(ca, host_cert, host_key, port=0)

    # Second call should succeed since the hook auto-disarmed.
    server = transport.create_server(ca, host_cert, host_key, port=0)
    assert isinstance(server, grpc.aio.Server)
    assert transport.hooks.server_create_count == 1


def test_bind_failure_when_add_secure_port_returns_zero(
    pki: Tuple[bytes, bytes, bytes],
) -> None:
    """If grpc returns 0 from add_secure_port (bind failure), the
    transport raises RuntimeError and does NOT bump the counter.

    Simulated by patching grpc.aio.server() to return a stub whose
    add_secure_port returns 0. Patching at the module-import level
    (``crossdesk_host.transport.mock.grpc``) so we don't have to
    monkey-patch a real Server class.
    """
    ca, host_cert, host_key = pki
    transport = MockTransport()

    fake_server = MagicMock(spec=grpc.aio.Server)
    fake_server.add_secure_port.return_value = 0

    with patch("crossdesk_host.transport.mock.grpc.aio.server", return_value=fake_server):
        with pytest.raises(RuntimeError, match="failed to bind"):
            transport.create_server(ca, host_cert, host_key, port=0)

    assert transport.hooks.server_create_count == 0


# ---------------------------------------------------------------------------
# Successful create_server path
# ---------------------------------------------------------------------------


def test_successful_create_increments_counter(
    pki: Tuple[bytes, bytes, bytes],
) -> None:
    ca, host_cert, host_key = pki
    transport = MockTransport()
    server = transport.create_server(ca, host_cert, host_key, port=0)

    assert transport.hooks.server_create_count == 1
    assert isinstance(server, grpc.aio.Server)


def test_multiple_creates_accumulate_counter(
    pki: Tuple[bytes, bytes, bytes],
) -> None:
    """Counter tracks lifetime creates, not just the most recent one."""
    ca, host_cert, host_key = pki
    transport = MockTransport()

    transport.create_server(ca, host_cert, host_key, port=0)
    transport.create_server(ca, host_cert, host_key, port=0)
    transport.create_server(ca, host_cert, host_key, port=0)

    assert transport.hooks.server_create_count == 3


def test_create_server_accepts_interceptors(
    pki: Tuple[bytes, bytes, bytes],
) -> None:
    """Interceptors parameter threads through to grpc.aio.server()."""
    ca, host_cert, host_key = pki
    transport = MockTransport()

    class _DummyInterceptor(grpc.aio.ServerInterceptor):  # type: ignore[misc]
        async def intercept_service(self, continuation, handler_call_details):  # type: ignore[no-untyped-def]
            return await continuation(handler_call_details)

    server = transport.create_server(
        ca, host_cert, host_key, port=0, interceptors=[_DummyInterceptor()]
    )
    assert isinstance(server, grpc.aio.Server)


def test_create_server_none_interceptors(
    pki: Tuple[bytes, bytes, bytes],
) -> None:
    """interceptors=None is the default and means no chain."""
    ca, host_cert, host_key = pki
    transport = MockTransport()
    server = transport.create_server(
        ca, host_cert, host_key, port=0, interceptors=None
    )
    assert isinstance(server, grpc.aio.Server)


# ---------------------------------------------------------------------------
# Real-PKI parity (skipped when leaves aren't generated)
# ---------------------------------------------------------------------------


def test_real_pki_still_works_when_present() -> None:
    """If infra/certs/pki/ has been generated locally, the transport
    accepts those materials too — guards against the ephemeral cert
    fixture masking a real divergence."""
    ca = _REAL_PKI_DIR / "ca.crt"
    host_cert = _REAL_PKI_DIR / "host.crt"
    host_key = _REAL_PKI_DIR / "host.key"
    if not (ca.exists() and host_cert.exists() and host_key.exists()):
        pytest.skip("Real PKI material not present at infra/certs/pki/")

    transport = MockTransport()
    server = transport.create_server(
        ca.read_bytes(),
        host_cert.read_bytes(),
        host_key.read_bytes(),
        port=0,
    )
    assert isinstance(server, grpc.aio.Server)
    assert transport.hooks.server_create_count == 1
