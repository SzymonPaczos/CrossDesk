"""Shared fixtures and grpc test doubles for the host test suite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import grpc
import pytest


class AbortError(Exception):
    """Raised by FakeServicerContext.abort to mimic gRPC's stream-killing behavior.

    Real grpc.aio.ServicerContext.abort raises AbortError internally; tests use
    pytest.raises(AbortError) to assert the rejection path was taken.
    """

    def __init__(self, code: grpc.StatusCode, detail: str) -> None:
        super().__init__(f"{code.name}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class FakeAuthContext:
    """Mimics the dict-like return from grpc context.auth_context()."""

    properties: Dict[str, List[bytes]] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.properties.get(key, default)

    def __bool__(self) -> bool:
        return bool(self.properties)


@dataclass
class FakeServicerContext:
    """Stand-in for grpc.aio.ServicerContext used by every Servicer test.

    Captures `abort()` calls as exceptions and stores the peer auth context so
    AuthValidator can extract a fingerprint from the leaf x509 PEM.
    """

    auth_props: Optional[Dict[str, List[bytes]]] = None
    aborted: bool = False
    abort_code: Optional[grpc.StatusCode] = None
    abort_detail: Optional[str] = None

    def auth_context(self) -> FakeAuthContext:
        return FakeAuthContext(properties=self.auth_props or {})

    async def abort(self, code: grpc.StatusCode, detail: str) -> None:
        # grpc.aio.ServicerContext.abort is a coroutine in real gRPC, so
        # production code awaits it. Keep the same shape here so tests catch
        # missing-await regressions (the bug pattern that let spoofed auth
        # frames pass silently before).
        self.aborted = True
        self.abort_code = code
        self.abort_detail = detail
        raise AbortError(code, detail)

    def peer(self) -> str:
        return "ipv4:127.0.0.1:0"

    def cancelled(self) -> bool:
        # Public grpc-python API equivalent to the older private
        # `core_context.aborted()`. FilesystemService's producer
        # loop polls this to learn whether the stream was killed
        # by a downstream abort.
        return self.aborted

    def invocation_metadata(self) -> tuple[tuple[str, str], ...]:
        # Empty metadata is fine for the rejection-path tests; the
        # TraceContextInterceptor only reads `traceparent`, which
        # these tests don't set. Returning an empty tuple keeps
        # `extract_from_metadata` happy.
        return ()

    @property
    def core_context(self) -> "_CoreContextShim":
        # Real grpc.aio.ServicerContext exposes a `core_context` with an
        # `aborted()` method; the FilesystemService producer task polls it.
        return _CoreContextShim(self)


@dataclass
class _CoreContextShim:
    parent: "FakeServicerContext"

    def aborted(self) -> bool:
        return self.parent.aborted


@pytest.fixture
def fake_context() -> FakeServicerContext:
    return FakeServicerContext()


def _self_signed_cert_pem(common_name: str = "test-peer") -> bytes:
    """Generate a throwaway self-signed cert PEM for tests that need a real x509."""
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2020, 1, 1))
        .not_valid_after(datetime.datetime(2099, 1, 1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


def context_with_cert(cert_pem: bytes) -> FakeServicerContext:
    """Build a FakeServicerContext that exposes a leaf cert via auth_context()."""
    return FakeServicerContext(auth_props={"x509_pem_cert": [cert_pem]})


@pytest.fixture
def make_cert():
    """Factory: returns (pem_bytes, sha256_hex_lower) for a fresh self-signed cert."""
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes

    def _make(common_name: str = "test-peer") -> tuple[bytes, str]:
        pem = _self_signed_cert_pem(common_name)
        cert = x509.load_pem_x509_certificate(pem, default_backend())
        fp = cert.fingerprint(hashes.SHA256()).hex().lower()
        return pem, fp

    return _make
