#!/usr/bin/env bash
# Granica serwer–klient — `conventions/runtime-boundaries.md`, „Egzekwowanie".
#
# Konwencja: „Importy `db`, `node:*`, modułów sekretów i SDK administracyjnych
# do klienta MUSZĄ blokować merge". Do dziś nie było czym.
#
# Mianownik pochodzi z gita, nie z własnego przejścia: najpierw lista plików
# klienckich z indeksu, potem ich otwieranie. Repozytorium z dyrektywą
# kliencką i zerem plików klienckich kończy się kodem 1, bo to znaczy, że
# bramka szukała nie tam.
#
# Za kod klienta uznajemy: plik z dyrektywą `"use client"`, plik w katalogu
# `client/`, `components/`, `app/` bez `server-only`, oraz każdy `.tsx`/`.vue`/
# `.svelte`/`.astro` bez `import "server-only"`.
#
# Sygnały maszynowe:
#   CLIENT_MODULES        ile modułów klienckich obejrzano   (mianownik)
#   CLIENT_MODULES_TOTAL  ile plików widoku zna git
#   CLIENT_SERVER_ONLY    ile z nich jawnie oznaczono jako serwerowe
#   CLIENT_LEAKS          importy serwerowe w kliencie — blokuje
#   CLIENT_SECRET_ENVS    odczyt sekretu przez `process.env` w kliencie — blokuje
#
# Użycie: runtime-boundaries.sh [--format text|signals] [ŚCIEŻKA]
# Kody wyjścia: 0 = granica zachowana, 1 = wyciek, 2 = błąd użycia.
set -uo pipefail

FORMAT=text
CEL=.
while [ $# -gt 0 ]; do
    case "$1" in
        --format) FORMAT="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done
cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

git ls-files -- '*.tsx' '*.jsx' '*.vue' '*.svelte' '*.astro' '*.ts' '*.js' 2>/dev/null \
    | grep -vE '(^|/)(node_modules|dist|build|out|coverage|\.next)/|(^|/)fixtures/known-(good|bad)/' \
    | grep -vE '\.(min|bundle|d)\.[a-z]+$' | sort -u > "$TMP/widok"
WIDOKU="$(grep -c . "$TMP/widok" || true)"

if [ "$WIDOKU" -eq 0 ]; then
    printf 'CLIENT_MODULES: n/a — git nie zna w tym repozytorium plików widoku\n'
    printf 'CLIENT_MODULES_TOTAL: 0\n'
    printf 'CLIENT_LEAKS: 0\n'
    exit 0
fi

: > "$TMP/klient"; SERVER_ONLY=0
while IFS= read -r plik; do
    if grep -qE '^[[:space:]]*(import[[:space:]]+)?["'"'"']server-only["'"'"']' "$plik" 2>/dev/null; then
        SERVER_ONLY=$((SERVER_ONLY + 1)); continue
    fi
    case "$plik" in
        */server/*|server/*|*/api/*|*.server.ts|*.server.js) SERVER_ONLY=$((SERVER_ONLY + 1)); continue ;;
    esac
    printf '%s\n' "$plik" >> "$TMP/klient"
done < "$TMP/widok"
KLIENTA="$(grep -c . "$TMP/klient" || true)"

if [ "$KLIENTA" -eq 0 ]; then
    printf 'CLIENT_MODULES: 0\n'
    printf 'CLIENT_MODULES_TOTAL: %s\n' "$WIDOKU"
    printf 'CLIENT_SERVER_ONLY: %s\n' "$SERVER_ONLY"
    printf '\n❌ Git zna %s plików widoku, a żaden nie został uznany za kod klienta.\n' "$WIDOKU" >&2
    printf '   Zero wycieków przy zerowym mianowniku to brak pomiaru, nie czysta granica.\n' >&2
    exit 1
fi

# Wzorzec:zdanie — komunikat mówi, co się stanie, nie jak bardzo boli.
ZAKAZY='node:[a-z_]+|from[[:space:]]+["'"'"'](fs|path|crypto|child_process|net|dns|os)["'"'"']:moduł Node w kodzie klienta — w przeglądarce nie istnieje, a w bundlu zdradza kształt serwera
(server/db|@/server|/db["'"'"'\)]|drizzle-orm|@prisma/client|mongoose|pg["'"'"'\)]):sterownik bazy w kodzie klienta — poświadczenia i schemat lecą do przeglądarki
(firebase-admin|@aws-sdk/client-secrets|googleapis|stripe["'"'"'\)]):SDK administracyjne w kodzie klienta — klucz usługowy trafia do bundla'

: > "$TMP/wycieki"
while IFS= read -r plik; do
    while IFS= read -r regula; do
        [ -n "$regula" ] || continue
        wzor="${regula%%:*}"; zdanie="${regula#*:}"
        grep -nE "^[[:space:]]*(import|export|const|let|var).*(${wzor})|require\((${wzor})" "$plik" 2>/dev/null \
            | while IFS= read -r t; do printf '%s:%s\t%s\n' "$plik" "$t" "$zdanie"; done >> "$TMP/wycieki"
    done <<EOF
$ZAKAZY
EOF
done < "$TMP/klient"
WYCIEKOW="$(grep -c . "$TMP/wycieki" || true)"

# Sekret czytany po stronie klienta. Zmienne z prefiksem publicznym są jawnie
# przeznaczone do bundla i nie są tu naruszeniem.
SEKRETOW=0
if [ "$KLIENTA" -gt 0 ]; then
    SEKRETOW="$(xargs -r grep -nE 'process\.env\.[A-Za-z_]*(SECRET|TOKEN|KEY|PASSWORD|CREDENTIAL)' < "$TMP/klient" 2>/dev/null \
        | grep -vE 'process\.env\.(NEXT_PUBLIC|PUBLIC|VITE|REACT_APP)_' | grep -c . || true)"
fi

if [ "$FORMAT" = text ] && [ "$WYCIEKOW" -gt 0 ]; then
    printf 'Moduły serwerowe w kodzie klienta (%s modułów klienckich obejrzanych):\n\n' "$KLIENTA"
    head -25 "$TMP/wycieki" | awk -F'\t' '{printf "  ❌ %s\n      %s\n", $1, $2}'
    printf '\n'
fi

printf 'CLIENT_MODULES: %s\n' "$KLIENTA"
printf 'CLIENT_MODULES_TOTAL: %s\n' "$WIDOKU"
printf 'CLIENT_SERVER_ONLY: %s\n' "$SERVER_ONLY"
printf 'CLIENT_LEAKS: %s\n' "$WYCIEKOW"
printf 'CLIENT_SECRET_ENVS: %s\n' "$SEKRETOW"

if [ "$((WYCIEKOW + SEKRETOW))" -gt 0 ]; then
    printf '\n❌ %s importów serwerowych i %s odczytów sekretu w kodzie, który jedzie do\n' \
        "$WYCIEKOW" "$SEKRETOW" >&2
    printf '   przeglądarki. Dostęp do bazy i tokeny usługowe zostają na serwerze.\n' >&2
    exit 1
fi
exit 0
