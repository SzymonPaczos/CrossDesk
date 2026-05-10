#!/usr/bin/env bash
# Authenticode-sign agent.exe with the CrossDesk publisher leaf cert.
#
# Wraps osslsigncode (cross-platform, Linux/macOS) so the same script
# runs in CI and on a developer workstation. Adds a timestamp from a
# free RFC3161 server so the signature stays valid after the leaf cert
# expires (Authenticode timestamps freeze the trust chain at signing
# time).
#
# Inputs:
#   - PFX: ../code-signing/pki/publisher-signing.pfx (or override via
#     $CROSSDESK_SIGNING_PFX)
#   - target binary: $1 (path to agent.exe)
#
# Output:
#   - Overwrites $1 in place with the signed binary (after a verify
#     round-trip into a temp file). The original is restored if any
#     step fails.
#
# Threat-model recap (see docs/CODE_SIGNING.md):
# agent.exe is shipped only inside CrossDesk-orchestrated guest VMs
# whose Trusted Root Store has been seeded with publisher-root-ca.crt
# during autounattend. That makes Authenticode reputation a no-op
# *outside* a guest (Windows host running agent.exe directly would
# still see "Unknown publisher") but full Verified-Publisher inside
# every guest we ever ship. SmartScreen is not in the picture because
# the binary never crosses the Mark-of-the-Web boundary.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEFAULT_PFX="${SCRIPT_DIR}/pki/publisher-signing.pfx"
readonly PFX="${CROSSDESK_SIGNING_PFX:-${DEFAULT_PFX}}"
readonly TIMESTAMP_URL="${CROSSDESK_TIMESTAMP_URL:-http://timestamp.sectigo.com}"
readonly DESCRIPTION="CrossDesk Agent"
readonly URL="https://github.com/SzymonPaczos/CrossDesk"

usage() {
    cat <<'EOF' >&2
Usage: sign-agent.sh <path-to-agent.exe>

Environment overrides:
  CROSSDESK_SIGNING_PFX   path to PKCS#12 bundle (default: pki/publisher-signing.pfx)
  CROSSDESK_TIMESTAMP_URL RFC3161 timestamp endpoint (default: Sectigo)

Requires: osslsigncode on PATH. macOS: brew install osslsigncode.
          Debian/Ubuntu: apt install osslsigncode.
EOF
    exit 2
}

target="${1:-}"
[[ -n "${target}" ]] || usage
[[ -f "${target}" ]] || { echo "ERROR: ${target} not found" >&2; exit 1; }
[[ -f "${PFX}" ]] || {
    echo "ERROR: signing PFX not found at ${PFX}" >&2
    echo "  Run infra/code-signing/generate.sh first." >&2
    exit 1
}
command -v osslsigncode >/dev/null 2>&1 || {
    echo "ERROR: osslsigncode not on PATH." >&2
    echo "  macOS: brew install osslsigncode" >&2
    echo "  Debian/Ubuntu: apt install osslsigncode" >&2
    exit 1
}

tmp_signed="$(mktemp -t crossdesk-signed.XXXXXX)"
backup="${target}.unsigned.bak"
trap 'rm -f "${tmp_signed}"' EXIT

cp -p "${target}" "${backup}"

echo "==> Signing ${target}"
# -h sha256: SHA-256 digest, the modern default. Older signtool versions
#   default to SHA-1; Windows distrusts SHA-1 Authenticode signatures
#   from 2019 onward, so we never want it.
# -n / -i: friendly name + URL shown in Windows file properties.
# -ts: RFC3161 timestamp server. Without it, the signature stops being
#   trusted the day the leaf cert expires; with it, anything signed
#   today verifies forever.
osslsigncode sign \
    -pkcs12 "${PFX}" \
    -pass "" \
    -h sha256 \
    -n "${DESCRIPTION}" \
    -i "${URL}" \
    -ts "${TIMESTAMP_URL}" \
    -in "${target}" \
    -out "${tmp_signed}"

echo "==> Verifying signature"
osslsigncode verify "${tmp_signed}" \
    || { echo "ERROR: verification failed; original preserved at ${backup}" >&2;
         exit 1; }

mv "${tmp_signed}" "${target}"
chmod --reference "${backup}" "${target}" 2>/dev/null \
    || chmod 755 "${target}"   # macOS chmod has no --reference

echo
echo "Signed: ${target}"
echo "Backup of unsigned binary: ${backup}"
echo "  (delete after a successful release if you don't need it)"
