#!/usr/bin/env bash
# Liczby w dokumentach są cytowane, nie przepisywane —
# `conventions/tool-adoption-and-measurement.md` §Pomiar w dokumencie.
#
# Sześć wielkości miało w jednym dokumencie po kilka różnych wartości naraz:
# zebrane testy 397 obok 393 i 399, przeanalizowane pliki 60 obok 58, rewizje
# migracji 6 obok 5, tabele 20 obok 19 i 14. Żadna nie była napisana
# niedbale — każda była poprawna w dniu, w którym ktoś ją wpisał.
#
# **Liczba, której nikt nie umie odtworzyć, nie może być błędna w konkretnej
# chwili — jest po prostu stara i nie widać po niej, jak bardzo.** Dlatego
# liczby produkuje jeden skrypt do jednego śledzonego artefaktu, dokument ten
# artefakt **cytuje** w oznaczonym bloku, a bramka porównuje cytat z plikiem.
#
# Cztery naruszenia blokujące:
#   1. blok w dokumencie różni się od artefaktu — cytat przestał być cytatem;
#   2. artefakt bez wiersza `COMMIT:` — zbiór liczb, który nie nazywa drzewa;
#   3. pomiar o wartości `0` — liczba, której nie dało się wziąć, nigdy nie jest
#      zerem: dokument z dziurą zaprasza, żeby wypełnić ją z pamięci;
#   4. artefakt, którego żaden dokument nie cytuje — plik generowany raz
#      w zeszłym kwartale.
#
# Czego ta bramka NIE robi: nie zakazuje cyfr w prozie. Zakazuje cyfry, która
# udaje pomiar rzeczy mierzonej przez skrypt.
#
# Sygnały maszynowe:
#   DOCNUM_MEASUREMENTS   ile pomiarów niesie artefakt        (mianownik)
#   DOCNUM_DOCUMENTS      ile dokumentów cytuje artefakt
#   DOCNUM_STALE_BLOCKS   cytaty rozjechane z artefaktem — blokuje
#   DOCNUM_ZERO_VALUES    pomiary równe zeru — blokuje
#   DOCNUM_PROVENANCE     czy artefakt nazywa commit (1/0) — 0 blokuje
#
# Użycie:
#   document-numbers.sh [--format text|signals] [ŚCIEŻKA]
#   document-numbers.sh --wstaw DOKUMENT [ŚCIEŻKA]   # odśwież blok w dokumencie
#
# Kody wyjścia: 0 = czysto, 1 = naruszenie blokujące, 2 = błąd użycia.
set -uo pipefail

FORMAT=text
CEL=.
WSTAW=""
while [ $# -gt 0 ]; do
    case "$1" in
        --format) FORMAT="${2:-}"; shift 2 ;;
        --wstaw)  WSTAW="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done
cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

OTWARCIE='<!-- ostatni-przebieg:start -->'
ZAMKNIECIE='<!-- ostatni-przebieg:end -->'

ARTEFAKT="$(git ls-files 2>/dev/null | grep -E '(^|/)ostatni-przebieg\.txt$' | head -1)"
if [ -z "$ARTEFAKT" ]; then
    printf 'DOCNUM_MEASUREMENTS: n/a — git nie zna w tym repozytorium pliku ostatni-przebieg.txt\n'
    exit 0
fi

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# blok <plik> — treść między znacznikami, bez ogrodzenia kodu.
blok() {
    awk -v o="$OTWARCIE" -v z="$ZAMKNIECIE" '
        index($0, o) { w = 1; next }
        index($0, z) { w = 0 }
        w && $0 !~ /^```/ && $0 != "" { print }
    ' "$1"
}

if [ -n "$WSTAW" ]; then
    [ -f "$WSTAW" ] || { printf 'nie ma pliku: %s\n' "$WSTAW" >&2; exit 2; }
    grep -qF "$OTWARCIE" "$WSTAW" && grep -qF "$ZAMKNIECIE" "$WSTAW" \
        || { printf 'w %s nie ma bloku %s … %s\n' "$WSTAW" "$OTWARCIE" "$ZAMKNIECIE" >&2; exit 2; }
    awk -v o="$OTWARCIE" -v z="$ZAMKNIECIE" -v plik="$ARTEFAKT" '
        index($0, o) { print; print ""; print "```"; while ((getline l < plik) > 0) print l; print "```"; print ""; w = 1; next }
        index($0, z) { w = 0 }
        !w { print }
    ' "$WSTAW" > "$TMP/nowy" && mv "$TMP/nowy" "$WSTAW"
    printf 'odswiezono blok w %s z %s\n' "$WSTAW" "$ARTEFAKT"
    exit 0
fi

grep -E '^[A-Z][A-Z0-9_]*: ' "$ARTEFAKT" > "$TMP/pomiary" || : > "$TMP/pomiary"
POMIAROW="$(grep -c . "$TMP/pomiary" || true)"

PROWENIENCJA=0
grep -qE '^COMMIT: [0-9a-f]{7,}' "$ARTEFAKT" && PROWENIENCJA=1

ZERA="$(awk -F': ' '$2 == "0" || $2 == "" {print $1}' "$TMP/pomiary" | grep -c . || true)"

DOKUMENTOW=0
ROZJAZDOW=0
: > "$TMP/rozjazdy"
while IFS= read -r dokument; do
    [ -n "$dokument" ] || continue
    grep -qF "$OTWARCIE" "$dokument" || continue
    DOKUMENTOW=$((DOKUMENTOW + 1))
    blok "$dokument" > "$TMP/cytat"
    if ! diff -q <(grep -v '^$' "$ARTEFAKT") "$TMP/cytat" >/dev/null 2>&1; then
        ROZJAZDOW=$((ROZJAZDOW + 1))
        printf '%s\t%s\n' "$dokument" \
            "$(diff <(grep -v '^$' "$ARTEFAKT") "$TMP/cytat" | grep -cE '^[<>]' || true) linii różnicy" \
            >> "$TMP/rozjazdy"
    fi
done < <(git ls-files -- '*.md' 2>/dev/null)

if [ "$FORMAT" = text ]; then
    printf 'Artefakt przebiegu: %s (%s pomiarów)\n\n' "$ARTEFAKT" "$POMIAROW"
    if [ "$ROZJAZDOW" -gt 0 ]; then
        printf 'Dokumenty, w których cytat rozjechał się z artefaktem:\n\n'
        awk -F'\t' '{printf "  ❌ %-40s %s\n", $1, $2}' "$TMP/rozjazdy" | head -10
        printf '\n'
    fi
    if [ "${ZERA:-0}" -gt 0 ]; then
        printf 'Pomiary równe zeru (liczba, której nie dało się wziąć, nie jest zerem):\n\n'
        awk -F': ' '$2 == "0" || $2 == "" {printf "  ❌ %s\n", $1}' "$TMP/pomiary" | head -10
        printf '\n'
    fi
fi

printf 'DOCNUM_MEASUREMENTS: %s\n' "$POMIAROW"
printf 'DOCNUM_DOCUMENTS: %s\n' "$DOKUMENTOW"
printf 'DOCNUM_STALE_BLOCKS: %s\n' "$ROZJAZDOW"
printf 'DOCNUM_ZERO_VALUES: %s\n' "$ZERA"
printf 'DOCNUM_PROVENANCE: %s\n' "$PROWENIENCJA"

STATUS=0
if [ "$POMIAROW" -eq 0 ]; then
    printf '\n❌ Artefakt przebiegu istnieje i nie niesie ani jednego wiersza `NAZWA: wartość`.\n' >&2
    printf '   Pusty artefakt „zgadza się" z pustym cytatem, więc porównanie niżej byłoby\n' >&2
    printf '   spełnione, nic nie zmierzywszy.\n' >&2
    STATUS=1
fi
if [ "$PROWENIENCJA" -eq 0 ]; then
    printf '\n❌ Artefakt nie ma wiersza `COMMIT: <hash>`. Zbiór liczb, który nie nazywa\n' >&2
    printf '   drzewa, nie da się z niczym porównać — nie wiadomo, o czym mówi.\n' >&2
    STATUS=1
fi
if [ "${ZERA:-0}" -gt 0 ]; then
    printf '\n❌ %s pomiarów ma wartość zero albo pustą. Pomiar, którego nie dało się wziąć,\n' "$ZERA" >&2
    printf '   jest porażką, nie zerem: dokument z dziurą zaprasza, żeby wypełnić ją z pamięci.\n' >&2
    STATUS=1
fi
if [ "$DOKUMENTOW" -eq 0 ]; then
    printf '\n❌ Żaden dokument nie cytuje %s. Artefakt bez konsumenta to plik generowany raz\n' "$ARTEFAKT" >&2
    printf '   w zeszłym kwartale — a liczby dalej są w dokumentach przepisywane ręcznie.\n' >&2
    STATUS=1
fi
if [ "$ROZJAZDOW" -gt 0 ]; then
    printf '\n❌ %s dokumentów cytuje artefakt niedosłownie. Cytat i artefakt mówiące co innego\n' "$ROZJAZDOW" >&2
    printf '   to dokładnie ta awaria, którą cytowanie miało usunąć.\n' >&2
    printf '   Czym to naprawić: `templates/document-numbers.sh --wstaw <dokument>`\n' >&2
    STATUS=1
fi
exit "$STATUS"
