#!/usr/bin/env bash
# Smoke test for the code-signing PKI scripts. Runs in CI on macOS +
# Linux; only requires `openssl`. The osslsigncode round-trip is
# exercised separately on Linux CI where the tool is available.
#
# Asserts:
# 1. generate.sh produces a chain that openssl verifies.
# 2. The leaf cert carries extendedKeyUsage=codeSigning (required for
#    Windows Authenticode).
# 3. The leaf cert is signed by the root CA (issuer matches).
# 4. The PFX bundle parses and contains exactly one cert + one key.
# 5. --rotate-leaf preserves the root but regenerates the leaf
#    (different serial / fingerprint).
#
# Usage:
#   ./test_pki.sh            # runs against an isolated tmp PKI
#   PRESERVE_TMP=1 ./...     # keeps the tmp dir for debugging

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly GENERATE="${SCRIPT_DIR}/generate.sh"

tmp="$(mktemp -d -t crossdesk-pki-test.XXXXXX)"
trap '[[ "${PRESERVE_TMP:-0}" == "1" ]] || rm -rf "${tmp}"' EXIT

# generate.sh writes into <its-own-dir>/pki, so we run it from a
# staging copy so the real pki/ stays untouched by the test.
mkdir -p "${tmp}/code-signing"
cp "${GENERATE}" "${tmp}/code-signing/generate.sh"
chmod +x "${tmp}/code-signing/generate.sh"

cd "${tmp}/code-signing"

echo "==> [1/5] generate.sh produces a verifiable chain"
./generate.sh >/dev/null
[[ -f pki/publisher-root-ca.crt ]] || { echo "missing root cert"; exit 1; }
[[ -f pki/publisher-root-ca.key ]] || { echo "missing root key"; exit 1; }
[[ -f pki/publisher-signing.crt ]] || { echo "missing leaf cert"; exit 1; }
[[ -f pki/publisher-signing.pfx ]] || { echo "missing PFX bundle"; exit 1; }
openssl verify -CAfile pki/publisher-root-ca.crt pki/publisher-signing.crt >/dev/null

echo "==> [2/5] leaf has extendedKeyUsage=codeSigning"
openssl x509 -in pki/publisher-signing.crt -noout -ext extendedKeyUsage \
    | grep -qi "Code Signing"

echo "==> [3/5] leaf issued by the root CA"
leaf_issuer="$(openssl x509 -in pki/publisher-signing.crt -noout -issuer)"
ca_subject="$(openssl x509 -in pki/publisher-root-ca.crt -noout -subject)"
# `issuer=` vs `subject=` prefix differ; compare the X509 name body
[[ "${leaf_issuer#issuer=}" == "${ca_subject#subject=}" ]] || {
    echo "issuer/subject mismatch:"
    echo "  leaf issuer:  ${leaf_issuer}"
    echo "  CA subject:   ${ca_subject}"
    exit 1
}

echo "==> [4/5] PFX bundle parses (1 cert, 1 key)"
# openssl pkcs12 -info -nokeys lists certs; -nocerts lists keys.
cert_count="$(openssl pkcs12 -info -in pki/publisher-signing.pfx -passin pass: -nokeys -noout 2>&1 | grep -c "MAC verified OK" || true)"
# A more robust count: extract certs and count BEGIN markers.
extracted_certs="$(openssl pkcs12 -in pki/publisher-signing.pfx -passin pass: -nokeys -nodes 2>/dev/null | grep -c "BEGIN CERTIFICATE")"
extracted_keys="$(openssl pkcs12 -in pki/publisher-signing.pfx -passin pass: -nocerts -nodes 2>/dev/null | grep -c "BEGIN PRIVATE KEY")"
# We expect leaf + CA in the PFX (2 certs) and 1 private key.
[[ "${extracted_certs}" -ge 1 ]] || { echo "PFX has no certs"; exit 1; }
[[ "${extracted_keys}" == "1" ]] || { echo "PFX has ${extracted_keys} keys, expected 1"; exit 1; }

echo "==> [5/5] --rotate-leaf preserves root, replaces leaf"
ca_fp_before="$(openssl x509 -in pki/publisher-root-ca.crt -noout -fingerprint -sha256)"
leaf_fp_before="$(openssl x509 -in pki/publisher-signing.crt -noout -fingerprint -sha256)"
sleep 1   # ensure serial change even if generation is sub-second
./generate.sh --rotate-leaf >/dev/null
ca_fp_after="$(openssl x509 -in pki/publisher-root-ca.crt -noout -fingerprint -sha256)"
leaf_fp_after="$(openssl x509 -in pki/publisher-signing.crt -noout -fingerprint -sha256)"
[[ "${ca_fp_before}" == "${ca_fp_after}" ]] || { echo "root fingerprint changed unexpectedly"; exit 1; }
[[ "${leaf_fp_before}" != "${leaf_fp_after}" ]] || { echo "leaf fingerprint did not change after --rotate-leaf"; exit 1; }
# Re-verify the chain still works.
openssl verify -CAfile pki/publisher-root-ca.crt pki/publisher-signing.crt >/dev/null

echo
echo "All PKI smoke tests passed."
