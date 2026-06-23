"""``_resolve_mtls_pki`` prefers a pre-provisioned dir, else mints a unique
per-install PKI under ``CROSSDESK_PKI_DIR``."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography import x509
from cryptography.x509.oid import NameOID

from crossdesk_host.cli.install_cmd import _resolve_mtls_pki
from crossdesk_host.installer.pki import CA_CN, GUEST_CN


def _cn(cert: x509.Certificate) -> str:
    return str(cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value)


def test_mints_per_install_when_unprovisioned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CROSSDESK_MTLS_PKI_DIR", str(tmp_path / "empty"))
    monkeypatch.setenv("CROSSDESK_PKI_DIR", str(tmp_path / "install-pki"))

    ca, cert, key = _resolve_mtls_pki()

    assert ca.is_file() and cert.is_file() and key.is_file()
    assert ca.parent == tmp_path / "install-pki"
    ca_cert = x509.load_pem_x509_certificate(ca.read_bytes())
    guest = x509.load_pem_x509_certificate(cert.read_bytes())
    assert _cn(ca_cert) == CA_CN
    assert _cn(guest) == GUEST_CN
    assert guest.issuer == ca_cert.subject
    assert "per-install mTLS PKI" in capsys.readouterr().out


def test_prefers_provisioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prov = tmp_path / "prov"
    prov.mkdir()
    for name in ("ca.crt", "guest.crt", "guest.key"):
        (prov / name).write_text("stub")
    monkeypatch.setenv("CROSSDESK_MTLS_PKI_DIR", str(prov))
    monkeypatch.setenv("CROSSDESK_PKI_DIR", str(tmp_path / "unused"))

    ca, cert, key = _resolve_mtls_pki()

    assert ca == prov / "ca.crt"
    # Provisioned set present → no per-install minting happened.
    assert not (tmp_path / "unused").exists()
