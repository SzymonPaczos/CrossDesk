#!/usr/bin/env bash
# Higiena repozytorium — `conventions/repo-hygiene-gates.md`, „Sygnały maszynowe".
#
# Konwencja wypisuje osiem klas checków z gotowymi komendami i od miesiąca
# czeka na skrypt. Ten skrypt to jest ten skrypt.
#
# Mianownik: liczba plików ŚLEDZONYCH, bo to one jadą do cudzego systemu
# plików. Zero obejrzanych plików przy repozytorium z historią kończy się
# kodem 1 — pusty indeks przy istniejących commitach znaczy, że skrypt stoi
# nie w tym katalogu.
#
# Sygnały maszynowe:
#   HYGIENE_TRACKED        ile plików śledzonych obejrzano   (mianownik)
#   HYGIENE_JUNK           kopie .bak/BACKUP/_b64 — blokuje
#   HYGIENE_PII            nazwy sugerujące dane osobowe — blokuje
#   HYGIENE_HOSTILE        konfiguracja wykonująca kod przy otwarciu — blokuje
#   HYGIENE_FAKE_TOOLS     binaria podszywające się pod narzędzia — blokuje
#   HYGIENE_DEAD_LINKS     ścieżki z .claude/*.md wskazujące w pustkę — blokuje
#   HYGIENE_EXPIRED_CREDS  poświadczenia po dacie w .env* — blokuje
#   HYGIENE_UNPUSHED_DAYS  wiek najstarszego niewypchniętego commita — raport
#   HYGIENE_STASHES        wpisy w stash — raport
#
# Użycie: repo-hygiene.sh [--format text|signals] [--today RRRR-MM-DD] [ŚCIEŻKA]
# Kody wyjścia: 0 = czysto, 1 = naruszenie blokujące, 2 = błąd użycia.
set -uo pipefail

FORMAT=text
DZIS=""
CEL=.
while [ $# -gt 0 ]; do
    case "$1" in
        --format) FORMAT="${2:-}"; shift 2 ;;
        --today)  DZIS="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done
[ -n "$DZIS" ] || DZIS="$(date +%F)"
cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
# Materiał znany-zły zawiera z definicji śmieci i wrogą konfigurację — to jest
# jego zadanie. Wyklucza się go jawnie i liczy osobno, bo wykluczenie
# niepoliczone jest miejscem, w którym materiał znika bez śladu.
git ls-files > "$TMP/wszystkie"
grep -vE '(^|/)fixtures/known-(good|bad)/' "$TMP/wszystkie" > "$TMP/tracked" || true
SLEDZONYCH="$(grep -c . "$TMP/tracked" || true)"
FIXTUROWYCH="$(grep -cE '(^|/)fixtures/known-(good|bad)/' "$TMP/wszystkie" || true)"
MA_HISTORIE=0; git rev-parse HEAD >/dev/null 2>&1 && MA_HISTORIE=1

if [ "$SLEDZONYCH" -eq 0 ]; then
    printf 'HYGIENE_TRACKED: 0\n'
    if [ "$MA_HISTORIE" -eq 1 ]; then
        printf '\n❌ Repozytorium ma commity, a indeks jest pusty — bramka stoi nie w tym\n' >&2
        printf '   katalogu albo w podmodule. Czym to sprawdzić: `git ls-files | wc -l`\n' >&2
        exit 1
    fi
    printf 'HYGIENE_TRACKED: n/a — repozytorium bez ani jednego śledzonego pliku\n'
    exit 0
fi

licz() { grep -icE "$1" "$TMP/tracked" || true; }

JUNK="$(licz '\.bak$|\.orig$|(^|/)[^/]*BACKUP[^/]*|_b64(\.|$)|\.copy\.[a-z]+$')"
PII="$(licz 'legitymacja|dowod_|pesel|zaswiadczenie|paszport|umowa_[a-z]+_[a-z]+\.pdf')"
HOSTILE="$(licz '^\.claude/(settings|settings\.local)\.json$|^\.claude/hooks/|^\.vscode/tasks\.json$|^\.claude/.*\.(mjs|js|sh|py)$')"
FAKE="$(licz '(^|/)(git|npm|node|python|sh|bash)(\.exe|\.cmd|\.bat)$')"

# Integralność referencyjna: ścieżka wymieniona w trackowanym `.claude/*.md`
# ma istnieć. Martwy link do „jedynej kopii" jest tym samym co jej brak.
: > "$TMP/martwe"
while IFS= read -r md; do
    [ -f "$md" ] || continue
    # Tylko tokeny ze ZNAKIEM KATALOGU. Sama nazwa pliku w tekście („patrz
    # ci-cd.md") jest odsyłaczem do konwencji, nie ścieżką w tym repozytorium —
    # traktowanie jej jak ścieżki daje maszynę do fałszywych alarmów, a bramka
    # z fałszywymi alarmami zostaje wyłączona przy pierwszym pośpiechu.
    grep -oE '`[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)+`|\]\([A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)+\)' "$md" 2>/dev/null \
        | tr -d '`]()' | sort -u | while IFS= read -r sciezka; do
            case "$sciezka" in ""|http*|*@*) continue ;; esac
            [ -e "$sciezka" ] || [ -e "$(dirname "$md")/$sciezka" ] \
                || printf '%s\t%s\n' "$md" "$sciezka" >> "$TMP/martwe"
        done
done < <(grep -E '^\.claude/.*\.md$' "$TMP/tracked" || true)
MARTWYCH="$(grep -c . "$TMP/martwe" 2>/dev/null || true)"

# Poświadczenia z zapisaną datą wygaśnięcia w przeszłości.
WYGASLE=0
DZIS_S="$(date -d "$DZIS" +%s 2>/dev/null || date -j -f '%Y-%m-%d' "$DZIS" +%s 2>/dev/null || printf 0)"
while IFS= read -r env; do
    [ -f "$env" ] || continue
    while IFS= read -r data; do
        s="$(date -d "$data" +%s 2>/dev/null || date -j -f '%Y-%m-%d' "$data" +%s 2>/dev/null)" || continue
        [ "$s" -lt "$DZIS_S" ] && WYGASLE=$((WYGASLE + 1))
    done < <(grep -iE 'expires|expires_on|wygasa' "$env" 2>/dev/null \
             | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')
done < <(grep -E '^\.env' "$TMP/tracked" || true)

# Raport: ekspozycja na utratę pracy.
STASHY="$(git stash list 2>/dev/null | grep -c . || true)"
NIEWYPCHNIETE_DNI=0
if [ "$MA_HISTORIE" -eq 1 ]; then
    najstarszy="$(git log --format=%ct @{u}..HEAD 2>/dev/null | tail -1)"
    if [ -n "${najstarszy:-}" ]; then
        NIEWYPCHNIETE_DNI=$(( ( $(date +%s) - najstarszy ) / 86400 ))
    fi
fi

if [ "$FORMAT" = text ]; then
    for para in "JUNK:kopie i śmieci w indeksie:\\.bak\$|\\.orig\$|BACKUP|_b64" \
                "PII:nazwy sugerujące dane osobowe:legitymacja|dowod_|pesel|zaswiadczenie|paszport" \
                "HOSTILE:konfiguracja wykonująca kod przy otwarciu checkoutu:^\\.claude/(settings|settings\\.local)\\.json\$|^\\.claude/hooks/|^\\.vscode/tasks\\.json\$" \
                "FAKE:binaria o nazwach narzędzi systemowych:(^|/)(git|npm|node|python|sh|bash)(\\.exe|\\.cmd|\\.bat)\$"; do
        klucz="${para%%:*}"; reszta="${para#*:}"; opis="${reszta%%:*}"; wzor="${reszta#*:}"
        eval "n=\${$klucz}"
        [ "${n:-0}" -gt 0 ] || continue
        printf '%s:\n' "$opis"
        grep -iE "$wzor" "$TMP/tracked" | head -10 | sed 's/^/  ❌ /'
        printf '\n'
    done
    if [ "${MARTWYCH:-0}" -gt 0 ]; then
        printf 'Ścieżki z .claude/*.md wskazujące w pustkę:\n'
        head -10 "$TMP/martwe" | awk -F'\t' '{printf "  ❌ %s → %s\n", $1, $2}'
        printf '\n'
    fi
fi

printf 'HYGIENE_TRACKED: %s\n' "$SLEDZONYCH"
printf 'HYGIENE_FIXTURES_EXCLUDED: %s — pliki z fixtures/known-*/ — materiał bramek, nie kod projektu\n' "$FIXTUROWYCH"
printf 'HYGIENE_JUNK: %s\n' "$JUNK"
printf 'HYGIENE_PII: %s\n' "$PII"
printf 'HYGIENE_HOSTILE: %s\n' "$HOSTILE"
printf 'HYGIENE_FAKE_TOOLS: %s\n' "$FAKE"
printf 'HYGIENE_DEAD_LINKS: %s\n' "${MARTWYCH:-0}"
printf 'HYGIENE_EXPIRED_CREDS: %s\n' "$WYGASLE"
printf 'HYGIENE_UNPUSHED_DAYS: %s\n' "$NIEWYPCHNIETE_DNI"
printf 'HYGIENE_STASHES: %s\n' "$STASHY"

BLOKUJACE=$(( JUNK + PII + HOSTILE + FAKE + ${MARTWYCH:-0} + WYGASLE ))
if [ "$BLOKUJACE" -gt 0 ]; then
    printf '\n❌ %s wpisów, które jadą do każdego, kto sklonuje to repozytorium:\n' "$BLOKUJACE" >&2
    printf '   kopie robocze, dane osobowe, konfiguracja uruchamiająca kod przy otwarciu\n' >&2
    printf '   checkoutu, martwe odsyłacze do „jedynej kopii" i wygasłe poświadczenia.\n' >&2
    exit 1
fi
exit 0
