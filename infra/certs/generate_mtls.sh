#!/usr/bin/env bash
# generate_mtls.sh — provision dev mTLS material for CrossDesk.
#
# Output goes to infra/certs/pki/ which is gitignored. NEVER commit anything
# under that directory. The committed history was scrubbed of earlier keys
# via `git filter-repo` (see CHANGELOG / commit log around the rotation);
# leaking them again puts the demo cluster trivially attackable.
#
# Production guidance:
#   - CA key belongs in an HSM or sealed vault (Vault / age / sops). On a bare
#     install, at minimum chmod 0400 + uid:host. This script creates an
#     unencrypted CA key for fast iteration ONLY.
#   - host.{crt,key} should be generated once per daemon install, on the
#     machine that will run crossdesk-host.
#   - guest.{crt,key} should be generated per VM and shipped inside tools.iso
#     to C:\CrossDesk\pki\ (the path agent-svc reads from).
#
# CN values must match what the peers expect:
#   - host CN  = "crossdesk-host"  (guest pins this via ClientTlsConfig.domain_name)
#   - guest CN = "crossdesk-guest"
set -euo pipefail

CERTS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKI_DIR="$CERTS_ROOT/pki"
mkdir -p "$PKI_DIR"
cd "$PKI_DIR"

DAYS_CA=3650
DAYS_LEAF=825   # browsers/tonic accept up to 825d for leaf certs

echo "=== Generating CrossDesk mTLS material into $PKI_DIR ==="

# 1. Root CA --------------------------------------------------------------
echo "[1/3] CA"
openssl req -x509 -newkey rsa:4096 -days "$DAYS_CA" -nodes \
    -keyout ca.key -out ca.crt \
    -subj "/C=PL/O=CrossDesk/CN=CrossDesk Dev CA" 2>/dev/null

# 2. Host leaf cert (CN must equal "crossdesk-host" — guest pins it) -------
echo "[2/3] host"
openssl req -newkey rsa:4096 -nodes \
    -keyout host.key -out host.csr \
    -subj "/C=PL/O=CrossDesk/CN=crossdesk-host" 2>/dev/null
openssl x509 -req -in host.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out host.crt -days "$DAYS_LEAF" \
    -extfile <(printf "subjectAltName=DNS:crossdesk-host,DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth,clientAuth\n") 2>/dev/null
rm host.csr

# 3. Guest leaf cert ------------------------------------------------------
echo "[3/3] guest"
openssl req -newkey rsa:4096 -nodes \
    -keyout guest.key -out guest.csr \
    -subj "/C=PL/O=CrossDesk/CN=crossdesk-guest" 2>/dev/null
openssl x509 -req -in guest.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out guest.crt -days "$DAYS_LEAF" \
    -extfile <(printf "subjectAltName=DNS:crossdesk-guest\nextendedKeyUsage=clientAuth\n") 2>/dev/null
rm guest.csr

chmod 600 ./*.key

echo
echo "Done. Files in $PKI_DIR:"
ls -1 ./*.crt ./*.key
echo
echo "Verify chain:"
echo "  openssl verify -CAfile ca.crt host.crt guest.crt"
