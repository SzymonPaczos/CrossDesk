#!/usr/bin/env bash
# Głębokość importów względnych — detektor niezależny od stosu.
#
# Po co, skoro linter to potrafi: bo linter trzeba mieć. W obu projektach, na
# których tę regułę wprowadzano, nie było ani lintera Pythona, ani reguły
# importów w ESLincie — reguła bez tego skryptu nie miałaby czym raportować.
# Ten skrypt czyta pliki śledzone przez git, więc działa w projekcie, który nie
# ma żadnej konfiguracji.
#
# Definicja głębokości = ile poziomów w górę sięga import:
#   JS/TS   ../x        → 1        ../../x      → 2
#   Python  from .x     → 0        from ..x     → 1     from ...x  → 2
# Próg domyślny: 2 (czyli „jedno `..` wolno, dwa i więcej nie" —
# `conventions/module-paths.md` §2).
#
# Języki pominięte świadomie: Go (język zabrania importów względnych w module),
# Rust, Java, C# (ścieżki względne nie istnieją). Brak zgłoszeń w tych stosach
# jest wynikiem, nie luką — i tak jest raportowany.
#
# Użycie:
#   import-depth.sh [--max N] [--baseline PLIK] [--format text|signals] [ŚCIEŻKA]
#
# Kody wyjścia: 0 = na progu lub poniżej, 1 = powyżej progu, 2 = błąd użycia.
set -uo pipefail

MAX=2
BASELINE=""
FORMAT=text
ROOT=.

while [ $# -gt 0 ]; do
    case "$1" in
        --max)      MAX="${2:-}"; shift 2 ;;
        --baseline) BASELINE="${2:-}"; shift 2 ;;
        --format)   FORMAT="${2:-}"; shift 2 ;;
        -h|--help)  sed -n '2,20p' "$0"; exit 0 ;;
        -*)         printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)          ROOT="$1"; shift ;;
    esac
done

command -v git >/dev/null || { printf 'brak git\n' >&2; exit 2; }
cd "$ROOT" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$ROOT" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$ROOT" >&2; exit 2; }

# Wynik jednego pliku: linie "głębokość<TAB>plik:linia<TAB>specyfikator".
skan_js() {
    # Specyfikator w cudzysłowie zaczynający się od ../ — łapie import, export,
    # require i import() jednym wzorcem, bo wszystkie niosą ścieżkę w cudzysłowie.
    grep -nEo "['\"]\\.\\./[^'\"]*['\"]" "$1" 2>/dev/null | while IFS= read -r trafienie; do
        local linia spec glebokosc
        linia="${trafienie%%:*}"
        spec="${trafienie#*:}"
        spec="${spec//\'/}"; spec="${spec//\"/}"
        glebokosc="$(printf '%s' "$spec" | grep -o '\.\./' | wc -l)"
        printf '%s\t%s:%s\t%s\n' "$glebokosc" "$1" "$linia" "$spec"
    done
}

skan_py() {
    # `from ..x import y` oraz `from .. import y`. Liczba kropek minus jeden
    # to liczba poziomów w górę; jedna kropka to bieżący pakiet, czyli 0.
    grep -nE '^[[:space:]]*from[[:space:]]+\.+' "$1" 2>/dev/null | while IFS= read -r trafienie; do
        local linia reszta kropki glebokosc
        linia="${trafienie%%:*}"
        reszta="${trafienie#*:}"
        kropki="$(printf '%s' "$reszta" | sed -E 's/^[[:space:]]*from[[:space:]]+(\.+).*/\1/' | tr -d '\n')"
        glebokosc=$(( ${#kropki} - 1 ))
        [ "$glebokosc" -lt 0 ] && glebokosc=0
        printf '%s\t%s:%s\t%s\n' "$glebokosc" "$1" "$linia" "$(printf '%s' "$reszta" | sed 's/^[[:space:]]*//')"
    done
}

skan_css() {
    grep -nEo "(@import[[:space:]]+|url\\()['\"]?\\.\\./[^'\")]*" "$1" 2>/dev/null | while IFS= read -r trafienie; do
        local linia spec glebokosc
        linia="${trafienie%%:*}"
        spec="${trafienie#*:}"
        glebokosc="$(printf '%s' "$spec" | grep -o '\.\./' | wc -l)"
        printf '%s\t%s:%s\t%s\n' "$glebokosc" "$1" "$linia" "$spec"
    done
}

WYNIKI="$(mktemp)"; trap 'rm -f "$WYNIKI"' EXIT

# Mianownik: ile plików bramka faktycznie otworzyła i ile świadomie pominęła.
# Bez tych dwóch liczb „zero naruszeń" nie odróżnia się od „nie znalazłem
# żadnego pliku do obejrzenia" — a wykluczenia nieliczone są miejscem, w którym
# materiał znika po cichu.
SKANOWANYCH=0
POMINIETYCH=0

while IFS= read -r plik; do
    [ -f "$plik" ] || continue
    case "$plik" in
        */node_modules/*|node_modules/*|*/vendor/*|*/.venv/*|fixtures/known-good/*|*/fixtures/known-good/*|fixtures/known-bad/*|*/fixtures/known-bad/*)
            POMINIETYCH=$((POMINIETYCH + 1)); continue ;;
    esac
    case "$plik" in
        *.js|*.jsx|*.mjs|*.cjs|*.ts|*.tsx|*.mts|*.cts|*.astro|*.vue|*.svelte)
            SKANOWANYCH=$((SKANOWANYCH + 1)); skan_js "$plik" ;;
        *.py)   SKANOWANYCH=$((SKANOWANYCH + 1)); skan_py "$plik" ;;
        *.css|*.scss|*.sass|*.less)
            SKANOWANYCH=$((SKANOWANYCH + 1)); skan_css "$plik" ;;
    esac
done < <(git ls-files) >> "$WYNIKI"

NARUSZENIA="$(awk -F'\t' -v m="$MAX" '$1 >= m' "$WYNIKI" | wc -l | tr -d ' ')"
NAJGLEBSZY="$(awk -F'\t' 'BEGIN{n=0} $1>n{n=$1} END{print n+0}' "$WYNIKI")"
WSZYSTKICH="$(wc -l < "$WYNIKI" | tr -d ' ')"

# Stosy, w których ścieżek względnych nie ma z definicji języka — raportujemy
# je jawnie, żeby zero nie wyglądało na przeoczenie.
BEZ_WZGLEDNYCH=""
for wzorzec in '*.go:Go' '*.rs:Rust' '*.java:Java' '*.cs:C#'; do
    rozsz="${wzorzec%%:*}"; nazwa="${wzorzec##*:}"
    n="$(git ls-files "$rozsz" | wc -l | tr -d ' ')"
    [ "$n" -gt 0 ] && BEZ_WZGLEDNYCH="$BEZ_WZGLEDNYCH $nazwa($n)"
done

if [ "$FORMAT" = signals ]; then
    printf 'IMPORT_FILES_SCANNED: %s\n' "$SKANOWANYCH"
    printf 'IMPORT_FILES_SKIPPED: %s\n' "$POMINIETYCH"
    printf 'IMPORT_DEPTH_MAX: %s\n' "$NAJGLEBSZY"
    printf 'IMPORT_VIOLATIONS: %s\n' "$NARUSZENIA"
    printf 'IMPORT_RELATIVE_TOTAL: %s\n' "$WSZYSTKICH"
    printf 'IMPORT_NO_RELATIVE_LANGS:%s\n' "${BEZ_WZGLEDNYCH:- brak}"
else
    if [ "$NARUSZENIA" -gt 0 ]; then
        printf 'Importy sięgające %s poziomów w górę lub więcej:\n\n' "$MAX"
        awk -F'\t' -v m="$MAX" '$1 >= m {printf "  %s  (głębokość %s)\n      %s\n", $2, $1, $3}' \
            "$WYNIKI" | head -40
        [ "$NARUSZENIA" -gt 20 ] && printf '  … łącznie %s\n' "$NARUSZENIA"
        printf '\n'
    fi
    printf 'IMPORT_FILES_SCANNED: %s\n' "$SKANOWANYCH"
    printf 'IMPORT_FILES_SKIPPED: %s — node_modules, vendor, .venv\n' "$POMINIETYCH"
    printf 'IMPORT_DEPTH_MAX: %s\n' "$NAJGLEBSZY"
    printf 'IMPORT_VIOLATIONS: %s (próg głębokości: %s)\n' "$NARUSZENIA" "$MAX"
    printf 'IMPORT_RELATIVE_TOTAL: %s\n' "$WSZYSTKICH"
    printf 'IMPORT_NO_RELATIVE_LANGS:%s — brak zgłoszeń to wynik, nie luka\n' \
        "${BEZ_WZGLEDNYCH:- brak}"
fi

# Zapadka: liczba nigdy nie rośnie. Bez pliku baseline skrypt tylko raportuje
# przekroczenie progu; z plikiem porównuje z zapisanym stanem.
if [ -n "$BASELINE" ]; then
    if [ -f "$BASELINE" ]; then
        POPRZEDNIO="$(tr -cd '0-9' < "$BASELINE")"
        POPRZEDNIO="${POPRZEDNIO:-0}"
        if [ "$NARUSZENIA" -gt "$POPRZEDNIO" ]; then
            printf '\n❌ REGRESJA: %s > %s (baseline %s)\n' \
                "$NARUSZENIA" "$POPRZEDNIO" "$BASELINE" >&2
            exit 1
        fi
        if [ "$NARUSZENIA" -lt "$POPRZEDNIO" ]; then
            printf '\n✅ POSTĘP: %s < %s — zaktualizuj baseline w tym samym commicie\n' \
                "$NARUSZENIA" "$POPRZEDNIO"
        fi
        exit 0
    fi
    printf '%s\n' "$NARUSZENIA" > "$BASELINE"
    printf '\nZałożono baseline %s = %s\n' "$BASELINE" "$NARUSZENIA"
    exit 0
fi

[ "$NARUSZENIA" -eq 0 ] || exit 1
exit 0
