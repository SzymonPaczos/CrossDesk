#!/bin/bash
set -euo pipefail

# Konfiguracja ścieżek
CERTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CERTS_DIR"

echo "=== Generowanie certyfikatów mTLS dla CrossDesk ==="

# 1. Generowanie CA (Certificate Authority)
echo "[1/3] Generowanie CA..."
openssl req -x509 -newkey rsa:4096 -days 3650 -nodes -keyout ca.key -out ca.crt -subj "/C=PL/O=CrossDesk/CN=CrossDesk Root CA" 2>/dev/null

# 2. Generowanie certyfikatu dla Hosta (Python)
echo "[2/3] Generowanie certyfikatu Hosta..."
openssl req -newkey rsa:4096 -nodes -keyout host.key -out host.csr -subj "/C=PL/O=CrossDesk/CN=CrossDesk Host" 2>/dev/null
openssl x509 -req -in host.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out host.crt -days 3650 2>/dev/null
rm host.csr

# 3. Generowanie certyfikatu dla Guesta (Rust)
echo "[3/3] Generowanie certyfikatu Guesta..."
openssl req -newkey rsa:4096 -nodes -keyout guest.key -out guest.csr -subj "/C=PL/O=CrossDesk/CN=CrossDesk Guest" 2>/dev/null
openssl x509 -req -in guest.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out guest.crt -days 3650 2>/dev/null
rm guest.csr

# Ustawienie uprawnień (prywatne klucze tylko dla właściciela)
chmod 600 *.key

echo "✅ Gotowe! Certyfikaty zapisane w: $CERTS_DIR"
echo "---"
echo "  ca.crt    - Certyfikat CA (wymagany po obu stronach)"
echo "  host.crt  - Certyfikat Hosta"
echo "  host.key  - Klucz Hosta"
echo "  guest.crt - Certyfikat Guesta"
echo "  guest.key - Klucz Guesta"
