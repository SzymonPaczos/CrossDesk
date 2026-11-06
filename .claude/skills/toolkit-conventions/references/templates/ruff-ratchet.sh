#!/usr/bin/env bash
# Zapadka lintera Pythona — `conventions/quality-gates-and-dod.md`.
#
# Projekt z tysiącem naruszeń nie może nagle stanąć na czerwonym, bo bramka,
# której nikt nie widział zielonej, zostaje wyłączona przy pierwszym pośpiechu.
# Dlatego liczba naruszeń jest progiem, który **może tylko maleć**.
#
#   .claude/ruff.baseline   liczba progowa
#
# Użycie: ruff-ratchet.sh [--baseline] [ŚCIEŻKA]
#
# `--baseline` zapisuje bieżącą liczbę jako próg zamiast ją sprawdzać.
#
# Kody wyjścia: 0 = na progu lub poniżej, 1 = powyżej progu, 2 = błąd użycia.
set -uo pipefail

USTAW_BASELINE=0
CEL=.
while [ $# -gt 0 ]; do
    case "$1" in
        --baseline) USTAW_BASELINE=1; shift ;;
        -h|--help)  sed -n '2,14p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done

cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }

# Ruff z projektu ma pierwszeństwo przed tym z PATH: wersja narzędzia zmienia
# domyślny zestaw reguł, więc próg policzony inną wersją nic nie znaczy.
if [ -x .venv/bin/ruff ]; then RUFF=.venv/bin/ruff
elif command -v ruff >/dev/null 2>&1; then RUFF=ruff
else
    printf 'RUFF: n/a — nie ma ruffa ani w .venv, ani w PATH\n'
    exit 0
fi

BASELINE=.claude/ruff.baseline
# Ruff kończy się 1, gdy COŚ ZNALAZŁ, i 2, gdy nie zrozumiał konfiguracji.
# Zrównanie tych dwóch przypadków daje bramkę, która melduje zero naruszeń,
# bo narzędzie w ogóle nie wystartowało — najgorszy możliwy wynik.
BLEDY="$(mktemp)"; trap 'rm -f "$BLEDY"' EXIT
WYNIK="$("$RUFF" check --no-cache --quiet --output-format=concise . 2>"$BLEDY")"; KOD=$?
if [ "$KOD" -ge 2 ]; then
    printf 'RUFF_VIOLATIONS: n/a — ruff nie wystartował (kod %s)\n' "$KOD"
    sed -n '1,6p' "$BLEDY" >&2
    printf '\n❌ Bramka nie ma wyniku. Zero naruszeń przy zepsutej konfiguracji\n' >&2
    printf '   to nie jest czysty kod, tylko brak pomiaru.\n' >&2
    exit 1
fi
NARUSZEN="$(printf '%s' "$WYNIK" | grep -c . || true)"

# Mianownik z DRUGIEJ ścieżki niż własne przejście lintera: ile plików ruff
# zamierza obejrzeć (`--show-files`) zestawione z tym, ile plików .py zna git.
# Różnica to wykluczenia z konfiguracji — i ta różnica ma być wypisana, bo
# `exclude = [...]` jest najwygodniejszym miejscem, w którym materiał znika
# bez śladu w wyniku.
PLIKOW="$("$RUFF" check --no-cache --show-files . 2>/dev/null | grep -cE '\.pyi?$' || true)"
SLEDZONYCH="$(git ls-files '*.py' '*.pyi' 2>/dev/null | grep -c . || true)"
WYKLUCZONYCH=$(( SLEDZONYCH - PLIKOW ))
[ "$WYKLUCZONYCH" -lt 0 ] && WYKLUCZONYCH=0

# Konfiguracja i wersja narzędzia w wyniku, bo bramka wołana inaczej niż w CI
# daje inny wynik przy IDENTYCZNYM mianowniku — tak powstało 252 błędy w CI
# przy zielonym przebiegu lokalnym. Rozjazd ma być widoczny w raporcie, a nie
# odkrywany po pushu.
KONFIG=""
for k in .ruff.toml ruff.toml pyproject.toml; do
    [ -f "$k" ] && { KONFIG="$k"; break; }
done
if [ -n "$KONFIG" ] && command -v sha256sum >/dev/null 2>&1; then
    KONFIG_SHA="$(sha256sum "$KONFIG" | cut -c1-16)"
else
    KONFIG_SHA="brak"
fi
printf 'RUFF_VERSION: %s\n' "$("$RUFF" --version 2>/dev/null)"
printf 'RUFF_BINARY: %s\n' "$RUFF"
printf 'RUFF_CONFIG: %s\n' "${KONFIG:-brak (ruff bierze wartości domyślne)}"
printf 'RUFF_CONFIG_SHA: %s\n' "$KONFIG_SHA"
if [ "$SLEDZONYCH" -eq 0 ] && [ "$PLIKOW" -eq 0 ]; then
    printf 'RUFF_FILES: n/a — git nie zna w tym repozytorium żadnego pliku .py\n'
else
    printf 'RUFF_FILES: %s\n' "$PLIKOW"
fi
printf 'RUFF_FILES_TRACKED: %s\n' "$SLEDZONYCH"
printf 'RUFF_FILES_EXCLUDED: %s — pliki .py znane gitowi, których ruff nie bierze (exclude w konfiguracji)\n' "$WYKLUCZONYCH"
printf 'RUFF_VIOLATIONS: %s\n' "$NARUSZEN"

# Zero obejrzanych plików przy repozytorium, które pliki .py MA, to nie jest
# czysty kod — to wykluczenie zjadło cały materiał.
if [ "$PLIKOW" -eq 0 ] && [ "$SLEDZONYCH" -gt 0 ]; then
    printf '\n❌ Ruff nie obejrzał ani jednego pliku, choć git zna %s plików .py.\n' "$SLEDZONYCH" >&2
    printf '   Zero naruszeń przy zerowym mianowniku znaczy, że wykluczenia w konfiguracji\n' >&2
    printf '   zabrały cały materiał. Czym to sprawdzić: `ruff check --show-files .`\n' >&2
    exit 1
fi
printf 'RUFF_TOP_RULES: %s\n' \
    "$(printf '%s' "$WYNIK" | grep -oE '[A-Z]+[0-9]+' | sort | uniq -c | sort -rn | head -5 \
       | awk '{printf "%s×%s ", $1, $2}')"

if [ "$USTAW_BASELINE" -eq 1 ]; then
    mkdir -p .claude
    printf '%s\n' "$NARUSZEN" > "$BASELINE"
    printf 'Założono baseline %s = %s\n' "$BASELINE" "$NARUSZEN"
    exit 0
fi

if [ -f "$BASELINE" ]; then
    PROG="$(tr -cd '0-9' < "$BASELINE")"; PROG="${PROG:-0}"
    printf 'RUFF_BASELINE: %s\n' "$PROG"
    if [ "$NARUSZEN" -gt "$PROG" ]; then
        printf '\n❌ REGRESJA: %s > %s. Nowy kod ma przechodzić lintera.\n' "$NARUSZEN" "$PROG" >&2
        printf '   Naruszenia, które doszły, pokaże `ruff check --output-format=concise`.\n' >&2
        exit 1
    fi
    [ "$NARUSZEN" -lt "$PROG" ] && \
        printf '\n✅ POSTĘP: %s < %s — zaktualizuj baseline w tym samym commicie\n' "$NARUSZEN" "$PROG"
    exit 0
fi
printf 'RUFF_BASELINE: brak (tryb raportowy)\n'
exit 0
