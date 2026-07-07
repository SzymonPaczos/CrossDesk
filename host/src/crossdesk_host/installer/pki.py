"""Per-install mTLS PKI generation.

Each CrossDesk install mints its OWN CA + host leaf + guest leaf instead of
sharing one static dev keypair across every install. A ``guest.key`` leaked
from one machine then cannot impersonate the guest on any *other* install:
the CAs differ, so the forged cert chains to nothing the other host trusts.
This is the strongest single security win available without touching the
wire protocol — today ``infra/certs/generate_mtls.sh`` ships one shared
"CrossDesk Dev CA" identity that every install would reuse.

The Common Names stay fixed (``crossdesk-host`` / ``crossdesk-guest``)
because the peers pin them: the guest verifies the host against
``ClientTlsConfig.domain_name`` and the host's ``AuthValidator`` pins the
guest CN. Only the key material and the issuing CA are unique per install.
A SubjectAlternativeName matching each CN is added so modern TLS stacks
(which ignore CN for hostname verification) still accept the pinned name.

Pure host-side; uses ``cryptography`` (already a dependency). Private keys
are written ``0600``, certificates ``0644``.
"""

from __future__ import annotations

import datetime
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

HOST_CN = "crossdesk-host"
GUEST_CN = "crossdesk-guest"
CA_CN = "CrossDesk Install CA"

_CA_DAYS = 3650
_LEAF_DAYS = 825  # tonic / browsers cap leaf validity at 825 days


@dataclass(frozen=True)
class InstallPki:
    """Filesystem locations of a generated per-install PKI set."""

    ca_cert: Path
    host_cert: Path
    host_key: Path
    guest_cert: Path
    guest_key: Path

    def _all(self) -> tuple[Path, ...]:
        return (self.ca_cert, self.host_cert, self.host_key, self.guest_cert, self.guest_key)

    def complete(self) -> bool:
        return all(p.is_file() for p in self._all())


def _paths(out_dir: Path) -> InstallPki:
    return InstallPki(
        ca_cert=out_dir / "ca.crt",
        host_cert=out_dir / "host.crt",
        host_key=out_dir / "host.key",
        guest_cert=out_dir / "guest.crt",
        guest_key=out_dir / "guest.key",
    )


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _rsa() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=4096)


def _write_key(path: Path, key: rsa.RSAPrivateKey) -> None:
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    # Born 0600 — no write-then-chmod window where the private key is
    # world-readable. fchmod repairs a looser pre-existing file.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        os.fchmod(fd, 0o600)
        fh.write(pem)


def _write_cert(path: Path, cert: x509.Certificate) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    path.chmod(0o644)


def _leaf(
    cn: str,
    ca_cert: x509.Certificate,
    ca_key: rsa.RSAPrivateKey,
    key: rsa.RSAPrivateKey,
) -> x509.Certificate:
    return (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_now() - datetime.timedelta(minutes=1))
        .not_valid_after(_now() + datetime.timedelta(days=_LEAF_DAYS))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(cn)]), critical=False)
        .add_extension(
            x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]
            ),
            critical=False,
        )
        .sign(private_key=ca_key, algorithm=hashes.SHA256())
    )


def generate_install_pki(out_dir: Path) -> InstallPki:
    """Mint a fresh CA + host + guest set into *out_dir*, overwriting any
    existing files. Use :func:`ensure_install_pki` to generate-once."""
    out_dir.mkdir(parents=True, exist_ok=True)

    ca_key = _rsa()
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, CA_CN)]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, CA_CN)]))
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_now() - datetime.timedelta(minutes=1))
        .not_valid_after(_now() + datetime.timedelta(days=_CA_DAYS))
        # path_length=0: this CA signs leaves only, never an intermediate CA.
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(private_key=ca_key, algorithm=hashes.SHA256())
    )

    host_key = _rsa()
    guest_key = _rsa()
    host_cert = _leaf(HOST_CN, ca_cert, ca_key, host_key)
    guest_cert = _leaf(GUEST_CN, ca_cert, ca_key, guest_key)

    paths = _paths(out_dir)
    _write_cert(paths.ca_cert, ca_cert)
    _write_cert(paths.host_cert, host_cert)
    _write_key(paths.host_key, host_key)
    _write_cert(paths.guest_cert, guest_cert)
    _write_key(paths.guest_key, guest_key)
    return paths


def ensure_install_pki(out_dir: Path) -> InstallPki:
    """Return *out_dir*'s PKI, generating it once if any file is missing.

    Idempotent: a complete existing set is reused untouched — regenerating
    would invalidate the guest cert already shipped into the VM's
    ``C:\\CrossDesk\\pki\\``.
    """
    paths = _paths(out_dir)
    if paths.complete():
        return paths
    return generate_install_pki(out_dir)
