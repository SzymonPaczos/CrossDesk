#!/usr/bin/env bash
# Kierunek zależności między warstwami backendu — `conventions/backend-layers.md`.
#
# Konwencja: „brak importu frameworka webowego, ORM, klienta HTTP, brokera ani
# konfiguracji środowiska w warstwie domeny". To jest test importów, czyli
# rzecz mechaniczna — a mimo to rozstrzygało go dotąd czytanie.
#
# Mianownik jest tu najważniejszy i pochodzi z DRUGIEJ ścieżki niż samo
# przejście: bramka najpierw pyta gita, ile plików leży w katalogach warstwy
# domenowej, i dopiero potem je otwiera. Zero modułów domeny przy repozytorium,
# które katalog domeny MA, kończy się kodem 1 — bo to znaczy, że bramka
# szukała nie tam, a nie że kierunek jest czysty.
#
# Sygnały maszynowe:
#   LAYER_DOMAIN_MODULES     ile modułów domeny obejrzano  (mianownik)
#   LAYER_DOMAIN_DIRS        katalogi rozpoznane jako domena
#   LAYER_VIOLATIONS         importy zakazane w domenie — blokuje
#   LAYER_ORM_IN_CONTRACTS   obiekty ORM w sygnaturach kontraktów — raport
#
# Użycie:
#   layer-direction.sh [--format text|signals] [--domain "domain core"] [ŚCIEŻKA]
#
# Kody wyjścia: 0 = kierunek zachowany, 1 = naruszenie, 2 = błąd użycia.
set -uo pipefail

FORMAT=text
KATALOGI_DOMENY="domain core entities model models"
CEL=.

while [ $# -gt 0 ]; do
    case "$1" in
        --format) FORMAT="${2:-}"; shift 2 ;;
        --domain) KATALOGI_DOMENY="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done

cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# ── Mianownik z gita ────────────────────────────────────────────────────────
: > "$TMP/domena"; : > "$TMP/kat"
for k in $KATALOGI_DOMENY; do
    git ls-files -- "*/$k/*.py" "$k/*.py" "*/$k/*.ts" "$k/*.ts" "*/$k/*.go" "$k/*.go" 2>/dev/null \
        | grep -vE '(^|/)(node_modules|dist|build|__pycache__)/|(^|/)fixtures/known-(good|bad)/' >> "$TMP/domena"
    git ls-files -- "*/$k/*" "$k/*" 2>/dev/null | grep -q . && printf '%s\n' "$k" >> "$TMP/kat"
done
sort -u "$TMP/domena" -o "$TMP/domena"
MODULOW="$(grep -c . "$TMP/domena" || true)"
KATALOGOW="$(sort -u "$TMP/kat" | grep -c . || true)"
NAZWY_KAT="$(sort -u "$TMP/kat" | tr '\n' ' ' | sed 's/ *$//')"

if [ "$KATALOGOW" -eq 0 ]; then
    printf 'LAYER_DOMAIN_MODULES: n/a — repozytorium nie ma katalogu warstwy domenowej (%s)\n' \
        "$(printf '%s' "$KATALOGI_DOMENY" | tr ' ' '/')"
    printf 'LAYER_DOMAIN_DIRS: 0\n'
    printf 'LAYER_VIOLATIONS: 0\n'
    exit 0
fi
if [ "$MODULOW" -eq 0 ]; then
    printf 'LAYER_DOMAIN_MODULES: 0\n'
    printf 'LAYER_DOMAIN_DIRS: %s (%s)\n' "$KATALOGOW" "$NAZWY_KAT"
    printf '\n❌ Katalog domeny istnieje, a bramka nie otworzyła w nim ani jednego modułu.\n' >&2
    printf '   Zero naruszeń przy zerowym mianowniku znaczy, że filtr rozszerzeń nie pasuje\n' >&2
    printf '   do tego repozytorium. Czym to sprawdzić: `git ls-files "*/%s/*"`\n' "${NAZWY_KAT%% *}" >&2
    exit 1
fi

# ── Importy zakazane w domenie ──────────────────────────────────────────────
# Lista jest wprost z konwencji: framework webowy, ORM, klient HTTP, broker,
# konfiguracja środowiska. Każdy wzorzec ma zdanie, bo raport czyta się tydzień
# później, bez legendy.
ZAKAZY='fastapi|flask|django|starlette|aiohttp\.web|express|nestjs:framework webowy w domenie — transport ma zostać w warstwie transportu
sqlalchemy|django\.db|tortoise|peewee|prisma|drizzle|typeorm|mongoose:ORM w domenie — reguła biznesowa zaczyna zależeć od kształtu tabeli
\brequests\b|httpx|aiohttp\.ClientSession|axios|node-fetch:klient HTTP w domenie — wywołanie sieciowe wchodzi pod transakcję
\bkafka\b|\bpika\b|celery|redis|boto3|aio_pika:broker albo usługa zewnętrzna w domenie — domena przestaje być testowalna bez infrastruktury
os\.environ|process\.env|dotenv:konfiguracja środowiska w domenie — ta sama reguła daje inny wynik na innej maszynie'

: > "$TMP/trafienia"
while IFS= read -r plik; do
    [ -f "$plik" ] || continue
    while IFS= read -r regula; do
        [ -n "$regula" ] || continue
        wzor="${regula%%:*}"; zdanie="${regula#*:}"
        grep -nE "^[[:space:]]*(import|from|const|let|var|require|use)[^\"']*(${wzor})" "$plik" 2>/dev/null \
            | while IFS= read -r t; do printf '%s:%s\t%s\n' "$plik" "$t" "$zdanie"; done >> "$TMP/trafienia"
    done <<EOF
$ZAKAZY
EOF
done < "$TMP/domena"
NARUSZEN="$(grep -c . "$TMP/trafienia" || true)"

# ── ORM w sygnaturach kontraktów (raport) ───────────────────────────────────
ORM_W_KONTRAKCIE="$(git grep -nE '(->|:)[[:space:]]*[A-Za-z_]*(Model|Entity|Row|ORM)\b' \
    -- '*/schemas/*.py' '*/contracts/*.py' '*/api/*.py' '*/contracts/*.ts' 2>/dev/null | grep -c . || true)"

if [ "$FORMAT" = text ] && [ "$NARUSZEN" -gt 0 ]; then
    printf 'Importy zakazane w warstwie domeny (%s modułów obejrzanych):\n\n' "$MODULOW"
    head -25 "$TMP/trafienia" | awk -F'\t' '{printf "  ❌ %s\n      %s\n", $1, $2}'
    printf '\n'
fi

printf 'LAYER_DOMAIN_MODULES: %s\n' "$MODULOW"
printf 'LAYER_DOMAIN_DIRS: %s (%s)\n' "$KATALOGOW" "$NAZWY_KAT"
printf 'LAYER_VIOLATIONS: %s\n' "$NARUSZEN"
printf 'LAYER_ORM_IN_CONTRACTS: %s\n' "$ORM_W_KONTRAKCIE"

[ "$NARUSZEN" -eq 0 ] || exit 1
exit 0
