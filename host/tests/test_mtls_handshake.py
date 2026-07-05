"""Negative mTLS-handshake coverage.

The production server (``transport/real.py``) binds with
``grpc.ssl_server_credentials(require_client_auth=True, root_certificates=CA)``.
Every other test that touches this config only exercises the happy path
(a valid guest leaf chaining to the trusted CA); ``docs`` /
``.claude/rules/audit.md`` §4 names the mTLS handshake a MUST-cover critical
path, so this module drives a *real* gRPC handshake over loopback and asserts
that clients are **rejected at the TLS layer** (never reach RPC dispatch) when
they present:

- no client certificate (``require_client_auth`` violation),
- a certificate signed by a different / untrusted CA,
- an expired certificate,

and that the client itself rejects a server whose cert doesn't match the
requested hostname (SAN / ``ssl_target_name_override`` mismatch).

Technique: the server registers **no** service, so a client whose handshake
*succeeds* gets ``UNIMPLEMENTED`` (TLS ok, method missing) while a client whose
handshake *fails* gets ``UNAVAILABLE`` (never dispatched). That contrast is the
security signal — a rejected client must never reach a servicer.
"""

from __future__ import annotations

import datetime
from typing import AsyncIterator, Tuple

import grpc
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

_SERVER_SAN = "crossdesk-host"


def _make_ca(cn: str) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    return cert, key


def _make_leaf(
    ca_cert: x509.Certificate,
    ca_key: rsa.RSAPrivateKey,
    cn: str,
    *,
    expired: bool = False,
) -> Tuple[bytes, bytes]:
    """Mint a leaf signed by *ca_cert* with SAN == *cn*. ``expired`` backdates
    the validity window so the cert is already outside it."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.datetime.now(datetime.timezone.utc)
    if expired:
        not_before = now - datetime.timedelta(days=3)
        not_after = now - datetime.timedelta(days=1)
    else:
        not_before = now - datetime.timedelta(minutes=1)
        not_after = now + datetime.timedelta(hours=1)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(cn)]), critical=False)
        .sign(private_key=ca_key, algorithm=hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def _pem(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


@pytest.fixture
async def server_env() -> AsyncIterator[Tuple[int, x509.Certificate, rsa.RSAPrivateKey]]:
    """A running mTLS gRPC server (no services registered) pinned to a fresh
    CA. Yields ``(port, ca_cert, ca_key)`` so each test mints its own client
    material against the same trusted CA."""
    ca_cert, ca_key = _make_ca("crossdesk-test-ca")
    server_cert_pem, server_key_pem = _make_leaf(ca_cert, ca_key, _SERVER_SAN)
    # Mirror transport/real.py's server-credential config exactly.
    creds = grpc.ssl_server_credentials(
        [(server_key_pem, server_cert_pem)],
        root_certificates=_pem(ca_cert),
        require_client_auth=True,
    )
    server = grpc.aio.server()
    port = server.add_secure_port("127.0.0.1:0", creds)
    assert port != 0, "failed to bind ephemeral secure port"
    await server.start()
    try:
        yield port, ca_cert, ca_key
    finally:
        await server.stop(grace=None)


async def _call(
    port: int,
    channel_creds: grpc.ChannelCredentials,
    *,
    target_override: str = _SERVER_SAN,
) -> grpc.StatusCode:
    """Attempt one unary RPC to a non-existent method and return the resulting
    status code (raises nothing on RPC error — the code is the signal)."""
    options = (("grpc.ssl_target_name_override", target_override),)
    async with grpc.aio.secure_channel(
        f"127.0.0.1:{port}", channel_creds, options=options
    ) as channel:
        rpc = channel.unary_unary("/crossdesk.test.v1.Probe/Ping")
        try:
            await rpc(b"", timeout=8)
        except grpc.aio.AioRpcError as exc:
            return exc.code()
    raise AssertionError("RPC unexpectedly succeeded against a service-less server")


async def test_valid_client_completes_handshake(
    server_env: Tuple[int, x509.Certificate, rsa.RSAPrivateKey],
) -> None:
    """A guest leaf chaining to the trusted CA passes mTLS — the handshake
    reaches dispatch (UNIMPLEMENTED = TLS ok, method missing)."""
    port, ca_cert, ca_key = server_env
    client_cert, client_key = _make_leaf(ca_cert, ca_key, "crossdesk-guest")
    creds = grpc.ssl_channel_credentials(
        root_certificates=_pem(ca_cert),
        private_key=client_key,
        certificate_chain=client_cert,
    )
    assert await _call(port, creds) == grpc.StatusCode.UNIMPLEMENTED


async def test_no_client_cert_is_rejected(
    server_env: Tuple[int, x509.Certificate, rsa.RSAPrivateKey],
) -> None:
    """require_client_auth=True must reject a client that presents no cert —
    rejected at TLS, never dispatched (so never UNIMPLEMENTED)."""
    port, ca_cert, _ = server_env
    creds = grpc.ssl_channel_credentials(root_certificates=_pem(ca_cert))
    code = await _call(port, creds)
    assert code == grpc.StatusCode.UNAVAILABLE
    assert code != grpc.StatusCode.UNIMPLEMENTED


async def test_wrong_ca_client_cert_is_rejected(
    server_env: Tuple[int, x509.Certificate, rsa.RSAPrivateKey],
) -> None:
    """A leaf signed by a DIFFERENT CA doesn't chain to the pinned root — the
    server rejects it at the handshake."""
    port, ca_cert, _ = server_env
    rogue_ca_cert, rogue_ca_key = _make_ca("rogue-ca")
    rogue_cert, rogue_key = _make_leaf(rogue_ca_cert, rogue_ca_key, "crossdesk-guest")
    creds = grpc.ssl_channel_credentials(
        root_certificates=_pem(ca_cert),  # client still trusts the real server
        private_key=rogue_key,
        certificate_chain=rogue_cert,  # ...but presents an untrusted client leaf
    )
    code = await _call(port, creds)
    assert code == grpc.StatusCode.UNAVAILABLE
    assert code != grpc.StatusCode.UNIMPLEMENTED


async def test_expired_client_cert_is_rejected(
    server_env: Tuple[int, x509.Certificate, rsa.RSAPrivateKey],
) -> None:
    """An expired leaf (correct CA, past not_valid_after) is rejected."""
    port, ca_cert, ca_key = server_env
    expired_cert, expired_key = _make_leaf(
        ca_cert, ca_key, "crossdesk-guest", expired=True
    )
    creds = grpc.ssl_channel_credentials(
        root_certificates=_pem(ca_cert),
        private_key=expired_key,
        certificate_chain=expired_cert,
    )
    code = await _call(port, creds)
    assert code == grpc.StatusCode.UNAVAILABLE
    assert code != grpc.StatusCode.UNIMPLEMENTED


async def test_hostname_mismatch_client_rejects_server(
    server_env: Tuple[int, x509.Certificate, rsa.RSAPrivateKey],
) -> None:
    """Client-side name check: a target override outside the server cert's SAN
    fails validation, so the client aborts the connection even though its own
    (valid) client cert would satisfy the server."""
    port, ca_cert, ca_key = server_env
    client_cert, client_key = _make_leaf(ca_cert, ca_key, "crossdesk-guest")
    creds = grpc.ssl_channel_credentials(
        root_certificates=_pem(ca_cert),
        private_key=client_key,
        certificate_chain=client_cert,
    )
    code = await _call(port, creds, target_override="not-the-server.example.com")
    assert code == grpc.StatusCode.UNAVAILABLE
    assert code != grpc.StatusCode.UNIMPLEMENTED
