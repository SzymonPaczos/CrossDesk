#!/usr/bin/env bash
# Generate the CrossDesk publisher PKI used to code-sign agent.exe.
#
# Output (under ./pki/):
#   - publisher-root-ca.crt   (PUBLIC; ships in the guest tools ISO and is
#                              imported into Cert:\LocalMachine\Root by the
#                              autounattend FirstLogonCommands so Windows
#                              treats agent.exe as Verified Publisher)
#   - publisher-root-ca.key   (PRIVATE; gitignored — must NEVER leave the
#                              signing host. Used only when re-issuing the
#                              leaf cert below.)
#   - publisher-signing.crt   (PUBLIC; the leaf code-signing certificate)
#   - publisher-signing.key   (PRIVATE; gitignored)
#   - publisher-signing.pfx   (PRIVATE; PKCS#12 bundle for osslsigncode/
#                              signtool — gitignored)
#
# Threat model boundary: agent.exe never leaves a CrossDesk-orchestrated
# guest VM (it is copied in via the install pipeline, not downloaded by
# the user). Trusting our own root CA *inside the guest* therefore does
# not affect any host-side trust store. The risk surface is "signing key
# leaks → attacker can sign binaries that look legit *to a CrossDesk
# guest*" — meaningful but bounded; mitigation is to keep the key on a
# signing host with restricted access (and rotate via this script).
#
# Re-running this script regenerates the leaf cert against the existing
# root CA when --rotate-leaf is passed. Without that flag, an existing
# CA is preserved (no overwrite); a missing CA triggers full generation.
#
# Usage:
#   ./generate.sh                 # generate CA + leaf if missing
#   ./generate.sh --rotate-leaf   # keep CA, re-issue leaf only
#   ./generate.sh --force         # regenerate everything (DANGEROUS)

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PKI_DIR="${SCRIPT_DIR}/pki"

readonly CA_DAYS=3650            # ~10 years; root never re-issued during MVP
readonly LEAF_DAYS=730           # ~2 years; rotate before expiry
readonly CA_BITS=4096
readonly LEAF_BITS=2048

readonly CA_SUBJECT="/C=PL/O=CrossDesk Project/CN=CrossDesk Publisher Root CA"
readonly LEAF_SUBJECT="/C=PL/O=CrossDesk Project/CN=CrossDesk Code Signing"

readonly CA_KEY="${PKI_DIR}/publisher-root-ca.key"
readonly CA_CRT="${PKI_DIR}/publisher-root-ca.crt"
readonly CA_SRL="${PKI_DIR}/publisher-root-ca.srl"
readonly LEAF_KEY="${PKI_DIR}/publisher-signing.key"
readonly LEAF_CSR="${PKI_DIR}/publisher-signing.csr"
readonly LEAF_CRT="${PKI_DIR}/publisher-signing.crt"
readonly LEAF_PFX="${PKI_DIR}/publisher-signing.pfx"

mode="${1:-}"

mkdir -p "${PKI_DIR}"
chmod 700 "${PKI_DIR}"

generate_ca() {
    echo "==> Generating root CA (${CA_BITS}-bit RSA, ${CA_DAYS} days)"
    openssl req -x509 -new -nodes \
        -newkey "rsa:${CA_BITS}" \
        -keyout "${CA_KEY}" \
        -out "${CA_CRT}" \
        -days "${CA_DAYS}" \
        -sha256 \
        -subj "${CA_SUBJECT}" \
        -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
        -addext "keyUsage=critical,keyCertSign,cRLSign"
    chmod 600 "${CA_KEY}"
    chmod 644 "${CA_CRT}"
}

generate_leaf() {
    # The leaf cert needs extendedKeyUsage=codeSigning so Windows accepts
    # it as a code-signing certificate. Without that EKU, signtool/
    # osslsigncode will produce a signature that Windows rejects with
    # "The certificate is not valid for the requested usage."
    local extfile
    extfile="$(mktemp)"
    cat > "${extfile}" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=critical,codeSigning
EOF

    echo "==> Generating leaf signing key + CSR (${LEAF_BITS}-bit RSA)"
    openssl req -new -nodes \
        -newkey "rsa:${LEAF_BITS}" \
        -keyout "${LEAF_KEY}" \
        -out "${LEAF_CSR}" \
        -sha256 \
        -subj "${LEAF_SUBJECT}"

    echo "==> Signing leaf with root CA (${LEAF_DAYS} days)"
    openssl x509 -req \
        -in "${LEAF_CSR}" \
        -CA "${CA_CRT}" \
        -CAkey "${CA_KEY}" \
        -CAcreateserial \
        -CAserial "${CA_SRL}" \
        -out "${LEAF_CRT}" \
        -days "${LEAF_DAYS}" \
        -sha256 \
        -extfile "${extfile}"

    rm -f "${extfile}" "${LEAF_CSR}"

    echo "==> Bundling PKCS#12 for osslsigncode/signtool"
    # Empty passphrase: the PFX is itself a private artifact (gitignored,
    # mode 600). Adding a passphrase would have to live somewhere else
    # secret too; one less thing to leak. Signing-side hardening (HSM /
    # YubiKey) is a separate uplift if the project ever ships beyond
    # solo dev.
    openssl pkcs12 -export \
        -out "${LEAF_PFX}" \
        -inkey "${LEAF_KEY}" \
        -in "${LEAF_CRT}" \
        -certfile "${CA_CRT}" \
        -passout pass:

    chmod 600 "${LEAF_KEY}" "${LEAF_PFX}"
    chmod 644 "${LEAF_CRT}"
}

case "${mode}" in
    --force)
        echo "==> --force: wiping existing PKI"
        rm -f "${CA_KEY}" "${CA_CRT}" "${CA_SRL}" \
              "${LEAF_KEY}" "${LEAF_CSR}" "${LEAF_CRT}" "${LEAF_PFX}"
        generate_ca
        generate_leaf
        ;;
    --rotate-leaf)
        if [[ ! -f "${CA_KEY}" ]] || [[ ! -f "${CA_CRT}" ]]; then
            echo "ERROR: --rotate-leaf requires existing CA at ${PKI_DIR}" >&2
            exit 1
        fi
        rm -f "${LEAF_KEY}" "${LEAF_CSR}" "${LEAF_CRT}" "${LEAF_PFX}"
        generate_leaf
        ;;
    "")
        if [[ ! -f "${CA_CRT}" ]]; then
            generate_ca
        else
            echo "==> root CA exists at ${CA_CRT}; preserved"
        fi
        if [[ ! -f "${LEAF_PFX}" ]]; then
            generate_leaf
        else
            echo "==> leaf PFX exists at ${LEAF_PFX}; preserved"
        fi
        ;;
    *)
        echo "Usage: $0 [--rotate-leaf|--force]" >&2
        exit 2
        ;;
esac

echo "==> Verifying chain"
openssl verify -CAfile "${CA_CRT}" "${LEAF_CRT}"

echo "==> Verifying leaf has codeSigning EKU"
openssl x509 -in "${LEAF_CRT}" -noout -ext extendedKeyUsage \
    | grep -qi "Code Signing" \
    || { echo "ERROR: leaf is missing codeSigning EKU" >&2; exit 1; }

echo
echo "PKI ready under ${PKI_DIR}/"
echo "  Public artifacts (committable):  publisher-root-ca.crt"
echo "  Private artifacts (gitignored):  publisher-root-ca.key, publisher-signing.{key,pfx}"
echo
echo "Next: ship publisher-root-ca.crt in the guest tools ISO so the"
echo "      autounattend FirstLogonCommands can certutil -addstore Root."
