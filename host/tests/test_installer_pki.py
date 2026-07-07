"""Per-install mTLS PKI: unique CA per install, pinned CNs, real chaining,
0600 private keys, idempotent ensure."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509.oid import NameOID

from crossdesk_host.installer.pki import (
    CA_CN,
    GUEST_CN,
    HOST_CN,
    ensure_install_pki,
    generate_install_pki,
)


def _cn(cert: x509.Certificate) -> str:
    return str(cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value)


def _load(path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificate(path.read_bytes())


def test_generates_full_set(tmp_path: Path) -> None:
    pki = generate_install_pki(tmp_path)
    assert pki.complete()


def test_private_keys_are_0600(tmp_path: Path) -> None:
    pki = generate_install_pki(tmp_path)
    for key in (pki.host_key, pki.guest_key):
        assert stat.S_IMODE(key.stat().st_mode) == 0o600, key


def test_keys_owner_only_regardless_of_umask(tmp_path: Path) -> None:
    # os.open forces 0600 at creation — a permissive umask must not widen the
    # private keys. Certs stay 0644 (public material, explicit chmod).
    old = os.umask(0o000)
    try:
        pki = ensure_install_pki(tmp_path)
    finally:
        os.umask(old)
    for key in (pki.host_key, pki.guest_key):
        assert stat.S_IMODE(key.stat().st_mode) == 0o600, key
    for cert in (pki.ca_cert, pki.host_cert, pki.guest_cert):
        assert stat.S_IMODE(cert.stat().st_mode) == 0o644, cert


def test_common_names_are_pinned(tmp_path: Path) -> None:
    pki = generate_install_pki(tmp_path)
    assert _cn(_load(pki.ca_cert)) == CA_CN
    assert _cn(_load(pki.host_cert)) == HOST_CN
    assert _cn(_load(pki.guest_cert)) == GUEST_CN


def test_leaves_chain_to_the_generated_ca(tmp_path: Path) -> None:
    pki = generate_install_pki(tmp_path)
    ca = _load(pki.ca_cert)
    for leaf_path in (pki.host_cert, pki.guest_cert):
        leaf = _load(leaf_path)
        assert leaf.issuer == ca.subject
        # Raises InvalidSignature if the CA key did not sign this leaf.
        ca.public_key().verify(  # type: ignore[union-attr]
            leaf.signature,
            leaf.tbs_certificate_bytes,
            padding.PKCS1v15(),
            leaf.signature_hash_algorithm,  # type: ignore[arg-type]
        )


def test_san_matches_cn(tmp_path: Path) -> None:
    pki = generate_install_pki(tmp_path)
    san = (
        _load(pki.host_cert)
        .extensions.get_extension_for_class(x509.SubjectAlternativeName)
        .value
    )
    assert san.get_values_for_type(x509.DNSName) == [HOST_CN]


def test_each_install_gets_a_distinct_ca(tmp_path: Path) -> None:
    # Core security property: a guest.key leaked from one install can't
    # impersonate the guest on another — the CAs (trust roots) differ.
    a = generate_install_pki(tmp_path / "a")
    b = generate_install_pki(tmp_path / "b")
    assert a.ca_cert.read_bytes() != b.ca_cert.read_bytes()
    assert a.guest_key.read_bytes() != b.guest_key.read_bytes()


def test_ensure_is_idempotent(tmp_path: Path) -> None:
    first = ensure_install_pki(tmp_path)
    ca_before = first.ca_cert.read_bytes()
    guest_key_before = first.guest_key.read_bytes()
    second = ensure_install_pki(tmp_path)
    # Reused untouched — regenerating would invalidate the guest cert already
    # shipped into the VM.
    assert second.ca_cert.read_bytes() == ca_before
    assert second.guest_key.read_bytes() == guest_key_before
