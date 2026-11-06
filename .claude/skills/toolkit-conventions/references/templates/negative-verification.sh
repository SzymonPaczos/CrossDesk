#!/usr/bin/env bash
# Rejestr weryfikacji negatywnej jako DANE — `conventions/negative-verification.md`.
#
# Zdanie „test był czerwony bez poprawki" napisane w mapie wdrożenia, w opisie
# commita albo w raporcie jest twierdzeniem, którego nikt nie może sprawdzić
# tydzień później. Liczba w rejestrze może pochodzić wyłącznie z przebiegu:
# skrypt sam uruchamia sprawdzian i zapisuje kod wyjścia, który zobaczył.
#
# Dwie rzeczy, które ten plik robi, a których nie robi zwykła notatka:
#
#   1. **Odmawia zapisu „czerwone" przy kodzie wyjścia 0.** Wiersz mówiący
#      „red" obok zera to rejestr kłamiący o jedynej rzeczy, którą zapisuje.
#      Bierze się to z mutacji, która nie zmieniła niczego, co test ogląda —
#      pola i tak pustego albo wołającego zamiast funkcji pod testem. W trzech
#      repozytoriach zdarzyło się to siedem razy.
#   2. **Czyści bytecode przed przebiegiem.** Mutacja zachowująca liczbę bajtów
#      zostawia ważny `.pyc`, więc interpreter serwuje STARY kod i strona „bez
#      poprawki" wychodzi na zielono. Kasowanie kosztuje milisekundy.
#
# W trybie bramki sprawdza spójność rejestru i listy długu:
#   * wiersz „czerwone" przy kodzie 0 (i odwrotnie) — blokuje;
#   * wiersz o innej liczbie kolumn niż nagłówek — blokuje;
#   * plik testowy w rejestrze I na liście długu jednocześnie — blokuje;
#   * lista długu ponad sufit zapisany w jej nagłówku — blokuje;
#   * plik testowy bez wiersza w rejestrze i bez wiersza na liście długu —
#     blokuje, gdy oba pliki istnieją (projekt zadeklarował ten rytuał).
#
# Sygnały maszynowe:
#   NEGVER_ROWS            wierszy rejestru                       (mianownik)
#   NEGVER_RED_ROWS        ile z nich zapisuje kod wyjścia != 0
#   NEGVER_LYING_ROWS      „czerwone" przy 0 lub „zielone" przy != 0 — blokuje
#   NEGVER_MALFORMED_ROWS  wiersze o złej liczbie kolumn — blokuje
#   NEGVER_IDS             różnych etykiet w rejestrze          (mianownik #2)
#   NEGVER_UNPAIRED        etykiet z czerwienią i bez zieleni — blokuje
#   NEGVER_UNPAIRED_CEILING sufit z .claude/negver-unpaired.baseline
#   NEGVER_GRANULARITY_MISMATCH ile z nich ma zieleń o poziom wyżej
#   NEGVER_DEBT_ROWS       pliki świadomie bez zapisu
#   NEGVER_DEBT_CEILING    sufit z nagłówka listy długu
#   NEGVER_TEST_FILES      pliki testowe znane gitowi
#   NEGVER_UNCOVERED       pliki testowe poza rejestrem i poza listą długu
#
# Użycie:
#   negative-verification.sh [--format text|signals] [ŚCIEŻKA]
#   negative-verification.sh --zapisz ETYKIETA NOTATKA -- KOMENDA [ARG...]
#
# Kody wyjścia: 0 = czysto, 1 = naruszenie blokujące, 2 = błąd użycia,
#               3 = odmowa zapisu (notatka mówi „czerwone", przebieg dał 0).
set -uo pipefail

FORMAT=text
TRYB=sprawdz
CEL=.
ARGS_ZAPISU=()

while [ $# -gt 0 ]; do
    case "$1" in
        --format) FORMAT="${2:-}"; shift 2 ;;
        --zapisz) TRYB=zapisz; shift; ARGS_ZAPISU=("$@"); break ;;
        -h|--help) sed -n '2,48p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done

cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }
# Korzeniem pomiaru jest katalog, na który bramkę wskazano, a NIE korzeń
# repozytorium. `git ls-files` woła się po `cd` i zwraca ścieżki względem
# katalogu bieżącego, więc sklejanie ich z korzeniem repozytorium daje ścieżkę,
# która nie istnieje — bramka czyta wtedy pusty plik i melduje pusty rejestr
# zamiast powiedzieć, że nie trafiła w plik. Przy wywołaniu bez argumentu obie
# wartości są tym samym katalogiem, więc zachowanie się nie zmienia.
KORZEN="$PWD"

NAGLOWEK='nodeid_or_label	commit	exit_code	date	note'

# Rejestr i lista długu znajdowane po NAZWIE w indeksie gita, nie po zaszytej
# ścieżce: katalog dokumentów różni się między projektami, a bramka wołana
# z inną ścieżką niż pozostałe jest drugą definicją tego, jak się ją uruchamia.
znajdz() { git ls-files 2>/dev/null | grep -E "(^|/)$1\$" | head -1; }
REJESTR="$(znajdz 'weryfikacja-negatywna\.tsv')"
DLUG="$(znajdz 'bez-weryfikacji-negatywnej\.tsv')"

# ── Tryb zapisu ─────────────────────────────────────────────────────────────
if [ "$TRYB" = zapisz ]; then
    [ "${#ARGS_ZAPISU[@]}" -ge 2 ] \
        || { printf 'użycie: %s --zapisz ETYKIETA NOTATKA -- KOMENDA [ARG...]\n' "$(basename "$0")" >&2; exit 2; }
    ETYKIETA="${ARGS_ZAPISU[0]}"
    NOTATKA="${ARGS_ZAPISU[1]}"
    KOMENDA=("${ARGS_ZAPISU[@]:2}")
    [ "${KOMENDA[0]:-}" = "--" ] && KOMENDA=("${KOMENDA[@]:1}")
    [ "${#KOMENDA[@]}" -gt 0 ] \
        || { printf 'brak komendy po `--`: nie ma czego uruchomić\n' >&2; exit 2; }

    case "$ETYKIETA$NOTATKA" in
        *"$(printf '\t')"*) printf 'tabulator jest separatorem kolumn i nie może wystąpić w polu\n' >&2; exit 2 ;;
    esac

    [ -n "$REJESTR" ] || REJESTR="docs/weryfikacja-negatywna.tsv"
    mkdir -p "$(dirname "$KORZEN/$REJESTR")"

    # Stary bytecode udaje działający kod (rules-as-gates.md §20). Mutacja
    # zachowująca liczbę bajtów nie unieważnia `.pyc`, więc przebieg mierzy
    # poprzednią wersję drzewa. Kasowanie należy do sprawdzianu, nie do
    # dyscypliny operatora — i dzieje się przed KAŻDĄ stroną, czyli przy
    # każdym wywołaniu tego trybu.
    find "$KORZEN" \
        -name node_modules -prune -o \
        -name .venv -prune -o \
        -name '__pycache__' -type d -print0 2>/dev/null | xargs -0 -r rm -rf
    rm -rf "$KORZEN/.pytest_cache" "$KORZEN/.mypy_cache" "$KORZEN/.ruff_cache"

    "${KOMENDA[@]}"
    KOD=$?

    # Notatka mówiąca „czerwone" obok kodu 0 to rejestr kłamiący o jedynej
    # rzeczy, którą zapisuje. Odmowa tutaj zamienia bezskuteczną mutację
    # w natychmiastowy błąd zamiast w wiarygodnie wyglądający wiersz.
    case "$NOTATKA" in
        *red:*|*czerwie*)
            [ "$KOD" -ne 0 ] || {
                printf 'ODMOWA ZAPISU: notatka mówi „czerwone", a przebieg zakończył się kodem 0.\n' >&2
                printf 'Mutacja nie zmieniła niczego, co ten sprawdzian ogląda. Wybierz pole,\n' >&2
                printf 'gałąź albo funkcję, którą sprawdzian naprawdę czyta, i uruchom ponownie.\n' >&2
                printf 'Czym to sprawdzić: co jeszcze zaczerwieniła ta mutacja? Jeśli nic — nie dotknęła kodu.\n' >&2
                exit 3
            } ;;
        *green:*|*zielon*)
            [ "$KOD" -eq 0 ] || {
                printf 'ODMOWA ZAPISU: notatka mówi „zielone", a przebieg zakończył się kodem %s.\n' "$KOD" >&2
                exit 3
            } ;;
    esac

    [ -f "$KORZEN/$REJESTR" ] || printf '%s\n' "$NAGLOWEK" > "$KORZEN/$REJESTR"
    printf '%s\t%s\t%s\t%s\t%s\n' \
        "$ETYKIETA" "$(git rev-parse HEAD)" "$KOD" "$(date -u +%Y-%m-%d)" "$NOTATKA" \
        >> "$KORZEN/$REJESTR"
    printf 'zapisano: exit_code=%s etykieta=%s\n' "$KOD" "$ETYKIETA"
    exit 0
fi

# ── Tryb bramki ─────────────────────────────────────────────────────────────
PLIKI_TESTOWE="$(git ls-files 2>/dev/null \
    | grep -E '(^|/)(tests?|e2e|__tests__)/.*\.(py|ts|tsx|js|jsx|mjs)$|(^|/)test_[^/]*\.py$|[^/]*_test\.py$|\.(test|spec)\.[tj]sx?$' \
    | grep -vE '(^|/)(node_modules|dist|build|__pycache__)/|(^|/)fixtures/known-(good|bad)/' | sort -u)"
N_TESTOWYCH="$(printf '%s' "$PLIKI_TESTOWE" | grep -c . || true)"

if [ -z "$REJESTR" ]; then
    if [ "$N_TESTOWYCH" -eq 0 ]; then
        printf 'NEGVER_ROWS: n/a — repozytorium nie ma ani plików testowych, ani rejestru\n'
        exit 0
    fi
    printf 'NEGVER_ROWS: n/a — %s plików testowych i brak rejestru weryfikacji negatywnej\n' "$N_TESTOWYCH"
    printf 'NEGVER_TEST_FILES: %s\n' "$N_TESTOWYCH"
    printf 'Rejestru nie ma, więc nie wiadomo, czy którykolwiek z tych testów potrafi zawieść.\n' >&2
    printf 'Zacznij od: `negative-verification.sh --zapisz <etykieta> "red: <powód>" -- <komenda>`.\n' >&2
    exit 0
fi

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# Rozbiór rejestru. `awk -F'\t'`, nigdy gołe `read`: tabulator należy do
# domyślnego IFS-a, więc `read` skleja sąsiadujące tabulatory i pusta kolumna
# znika, przesuwając wszystkie następne (ten sam plik czytany dwoma
# narzędziami dawał dwie różne prawdy).
#
# Mianownik NEGVER_ROWS liczy WYŁĄCZNIE wiersze o pełnej liczbie kolumn — te,
# które bramka w ogóle umie przeczytać. Drugim źródłem jest licznik linii
# (grep), więc wiersz z brakującym tabulatorem daje rozjazd między liczbami
# zamiast po cichu wypaść z pomiaru.
awk -F'\t' -v OFS='\t' '
    /^[[:space:]]*(#|$)/ { next }
    $1 == "nodeid_or_label" { next }
    { print NF, $1, $3, $5 }
' "$KORZEN/$REJESTR" > "$TMP/wszystkie"

WIERSZY="$(awk -F'\t' '$1 == 5' "$TMP/wszystkie" | grep -c . || true)"
ZLE_KOLUMNY="$(awk -F'\t' '$1 != 5' "$TMP/wszystkie" | grep -c . || true)"
CZERWONYCH="$(awk -F'\t' '$1 == 5 && $3 ~ /^[0-9]+$/ && $3 != 0' "$TMP/wszystkie" | grep -c . || true)"

# Wiersz kłamiący: notatka i kod wyjścia mówią co innego. Cudzysłowy w treści
# komunikatu są typograficzne, bo cały program awk stoi w apostrofach.
awk -F'\t' '
    $1 != 5 { next }
    {
        nota = tolower($4); kod = $3
        czerwona = (nota ~ /red:/ || nota ~ /czerwie/)
        zielona  = (nota ~ /green:/ || nota ~ /zielon/)
        if (czerwona && kod == "0")      print $2 "\tnotatka mówi CZERWONE, kod wyjścia 0"
        else if (zielona && kod != "0")  print $2 "\tnotatka mówi ZIELONE, kod wyjścia " kod
    }
' "$TMP/wszystkie" > "$TMP/klamstwa"
KLAMSTW="$(grep -c . "$TMP/klamstwa" || true)"

# ── Pary czerwień/zieleń ────────────────────────────────────────────────────
# Wiersz negatywny bez wiersza pozytywnego PRZY TEJ SAMEJ ETYKIECIE nie domyka
# rytuału: ktoś widział sprawdzian na czerwono i nikt nie zapisał, że po
# poprawce zrobił się zielony.
#
# Najczęstsza postać tej luki nie jest brakiem przebiegu, tylko ROZJAZDEM
# GRANULACJI: czerwień zapisana per test (`plik::test`), zieleń per plik
# (`plik`). Oba kody wyjścia są prawdziwe, obie notatki zgodne z kodem, więc
# kontrola kłamstw przepuszcza taki rejestr — a pary nie ma, bo nic
# maszynowego nie zestawi `plik::test` z `plik`. W jednym repozytorium
# trzynaście wierszy negatywnych stało tak bez partnera, w tym dwa, których
# zieleni nikt nigdy nie widział, bo przypadek był `skipped` przy zgaszonej
# infrastrukturze — a `skipped` to nie jest zieleń.
awk -F'\t' '$1 == 5 && $3 == "0"                        {print $2}' "$TMP/wszystkie" | sort -u > "$TMP/zielone-id"
awk -F'\t' '$1 == 5 && $3 ~ /^[0-9]+$/ && $3 != "0"     {print $2}' "$TMP/wszystkie" | sort -u > "$TMP/czerwone-id"
sort -u "$TMP/zielone-id" "$TMP/czerwone-id" > "$TMP/wszystkie-id"
IDENTYFIKATOROW="$(grep -c . "$TMP/wszystkie-id" || true)"
comm -23 "$TMP/czerwone-id" "$TMP/zielone-id" > "$TMP/bez-pary" || true
BEZ_PARY="$(grep -c . "$TMP/bez-pary" || true)"

# Rozpoznanie dla wiersza bez pary: czy zieleń leży o poziom wyżej. Ta liczba
# jest osobna, bo mówi co innego niż brak przebiegu — przebieg był, zapisano
# go pod etykietą, która nie domyka niczego. Poprawka jest inna w obu razach.
: > "$TMP/rozjazd-granulacji"
while IFS= read -r id; do
    [ -n "$id" ] || continue
    case "$id" in
        *::*) grep -qxF "${id%%::*}" "$TMP/zielone-id" \
                  && printf '%s\n' "$id" >> "$TMP/rozjazd-granulacji" ;;
    esac
done < "$TMP/bez-pary"
ROZJAZDOW="$(grep -c . "$TMP/rozjazd-granulacji" || true)"

# Zapadka, tym samym kształtem co sufit listy długu i baseline ruffa: liczba
# wierszy bez pary może maleć, nigdy rosnąć, a podniesienie wymaga zapisu
# w repozytorium — czyli decyzji, którą widać w historii, a nie ustępstwa
# zrobionego w przebiegu CI.
SUFIT_BEZ_PARY=0
# Sufit szukany po NAZWIE w indeksie gita, tak samo jak rejestr i lista długu.
# Ścieżka zaszyta w `.claude/` wygląda naturalnie i jest pułapką: ten katalog
# bywa w `.gitignore`, więc plik z zatwierdzeniem nie wchodzi do repozytorium
# — a sufit, którego nie widać w historii, nie jest zatwierdzeniem, tylko
# ustawieniem na czyimś laptopie. Fallback zostaje dla projektów, które ten
# katalog śledzą.
PLIK_SUFITU="$(znajdz 'negver-unpaired\.baseline')"
[ -n "$PLIK_SUFITU" ] && PLIK_SUFITU="$KORZEN/$PLIK_SUFITU"
[ -n "$PLIK_SUFITU" ] || PLIK_SUFITU="$KORZEN/.claude/negver-unpaired.baseline"
if [ -f "$PLIK_SUFITU" ]; then
    # Pierwsza linia będąca samą liczbą. Zdzieranie wszystkiego poza cyframi
    # z CAŁEGO pliku skleiłoby liczby z komentarza w jedną — a sufit bez
    # uzasadnienia obok jest wpisem, którego przy przeglądzie nikt nie obroni,
    # więc komentarz ma tu prawo stać.
    SUFIT_BEZ_PARY="$(grep -m1 -E '^[[:space:]]*[0-9]+[[:space:]]*$' "$PLIK_SUFITU" | tr -cd '0-9')"
    SUFIT_BEZ_PARY="${SUFIT_BEZ_PARY:-0}"
fi

# ── Lista długu ─────────────────────────────────────────────────────────────
DLUG_WIERSZY=0
SUFIT=""
if [ -n "$DLUG" ]; then
    awk -F'\t' 'NR>0 && !/^[[:space:]]*#/ && NF>=2 && $1 != "test_file" {print $1}' \
        "$KORZEN/$DLUG" | sort -u > "$TMP/dlug"
    DLUG_WIERSZY="$(grep -c . "$TMP/dlug" || true)"
    SUFIT="$(grep -m1 -iE '^#[[:space:]]*(sufit|ceiling)[[:space:]]*:' "$KORZEN/$DLUG" \
        | grep -oE '[0-9]+' | head -1)"
else
    : > "$TMP/dlug"
fi

# Plik testowy jest pokryty, gdy jego ścieżka jest przedrostkiem którejkolwiek
# etykiety w rejestrze (nodeid `plik::test` albo sama etykieta).
awk -F'\t' '$1 == 5 {print $2}' "$TMP/wszystkie" | sed 's/::.*//' | sort -u > "$TMP/pokryte"
printf '%s\n' "$PLIKI_TESTOWE" | grep . > "$TMP/testowe" || : > "$TMP/testowe"
comm -23 <(sort -u "$TMP/testowe") <(sort -u "$TMP/pokryte") > "$TMP/nie-w-rejestrze" || true
comm -23 <(sort "$TMP/nie-w-rejestrze") <(sort -u "$TMP/dlug") > "$TMP/niepokryte" || true
NIEPOKRYTYCH="$(grep -c . "$TMP/niepokryte" || true)"

# Plik nie może być jednocześnie pokryty i zadeklarowany jako dług — wtedy
# jedna z dwóch deklaracji jest nieaktualna i nie wiadomo która.
comm -12 <(sort -u "$TMP/pokryte") <(sort -u "$TMP/dlug") > "$TMP/podwojne" || true
PODWOJNYCH="$(grep -c . "$TMP/podwojne" || true)"

if [ "$FORMAT" = text ]; then
    printf 'Rejestr weryfikacji negatywnej: %s\n' "$REJESTR"
    [ -n "$DLUG" ] && printf 'Lista długu: %s (sufit %s)\n' "$DLUG" "${SUFIT:-brak}"
    printf '\n'
    if [ "${KLAMSTW:-0}" -gt 0 ]; then
        printf 'Wiersze, w których notatka i kod wyjścia mówią co innego:\n\n'
        awk -F'\t' '{printf "  ❌ %-58s %s\n", $1, $2}' "$TMP/klamstwa" | head -15
        printf '\n'
    fi
    if [ "${BEZ_PARY:-0}" -gt "$SUFIT_BEZ_PARY" ]; then
        printf 'Etykiety z zapisaną czerwienią i bez zieleni:\n\n'
        while IFS= read -r id; do
            [ -n "$id" ] || continue
            if grep -qxF "$id" "$TMP/rozjazd-granulacji" 2>/dev/null; then
                printf '  ❌ %-58s zieleń zapisana per plik, czerwień per test\n' "$id"
            else
                printf '  ❌ %-58s zieleni nikt nie zapisał\n' "$id"
            fi
        done < "$TMP/bez-pary" | head -15
        printf '\n'
    fi
    if [ "${PODWOJNYCH:-0}" -gt 0 ]; then
        printf 'Pliki jednocześnie w rejestrze i na liście długu:\n\n'
        sed 's/^/  ❌ /' "$TMP/podwojne" | head -15
        printf '\n'
    fi
    if [ -n "$DLUG" ] && [ "${NIEPOKRYTYCH:-0}" -gt 0 ]; then
        printf 'Pliki testowe bez wiersza w rejestrze i bez wiersza na liście długu:\n\n'
        sed 's/^/  ❌ /' "$TMP/niepokryte" | head -15
        printf '\n'
    fi
fi

printf 'NEGVER_ROWS: %s\n' "$WIERSZY"
printf 'NEGVER_RED_ROWS: %s\n' "$CZERWONYCH"
printf 'NEGVER_LYING_ROWS: %s\n' "$KLAMSTW"
printf 'NEGVER_MALFORMED_ROWS: %s\n' "$ZLE_KOLUMNY"
printf 'NEGVER_IDS: %s\n' "$IDENTYFIKATOROW"
printf 'NEGVER_UNPAIRED: %s\n' "$BEZ_PARY"
printf 'NEGVER_UNPAIRED_CEILING: %s\n' "$SUFIT_BEZ_PARY"
printf 'NEGVER_GRANULARITY_MISMATCH: %s\n' "$ROZJAZDOW"
printf 'NEGVER_DEBT_ROWS: %s\n' "$DLUG_WIERSZY"
printf 'NEGVER_DEBT_CEILING: %s\n' "${SUFIT:-n/a}"
printf 'NEGVER_TEST_FILES: %s\n' "$N_TESTOWYCH"
printf 'NEGVER_UNCOVERED: %s\n' "$NIEPOKRYTYCH"

STATUS=0
if [ "$WIERSZY" -eq 0 ]; then
    printf '\n❌ Rejestr istnieje i ma zero wierszy. Pusty rejestr wygląda w raporcie tak\n' >&2
    printf '   samo jak rejestr pełny zieleni: żaden test nie ma zapisanego czerwonego\n' >&2
    printf '   przebiegu. Czym to sprawdzić: `negative-verification.sh --zapisz …`.\n' >&2
    STATUS=1
fi
if [ "${ZLE_KOLUMNY:-0}" -gt 0 ]; then
    printf '\n❌ %s wierszy rejestru ma inną liczbę kolumn niż nagłówek. Rejestr czytany\n' "$ZLE_KOLUMNY" >&2
    printf '   dwoma narzędziami daje wtedy dwie różne prawdy o tym samym pliku.\n' >&2
    STATUS=1
fi
if [ "${KLAMSTW:-0}" -gt 0 ]; then
    printf '\n❌ %s wierszy, w których notatka i kod wyjścia mówią co innego. Wiersz „czerwone"\n' "$KLAMSTW" >&2
    printf '   obok kodu 0 znaczy, że mutacja nie zmieniła niczego, co sprawdzian ogląda —\n' >&2
    printf '   czyli że nikt nie widział tego testu na czerwono, choć rejestr tak twierdzi.\n' >&2
    STATUS=1
fi
if [ "${PODWOJNYCH:-0}" -gt 0 ]; then
    printf '\n❌ %s plików jest naraz w rejestrze i na liście długu. Jedna z tych dwóch\n' "$PODWOJNYCH" >&2
    printf '   deklaracji jest nieaktualna i z pliku nie wynika która.\n' >&2
    STATUS=1
fi
if [ "${BEZ_PARY:-0}" -gt "$SUFIT_BEZ_PARY" ]; then
    printf '\n❌ Etykiet z zapisaną czerwienią i bez zieleni przy tej samej etykiecie: %s (sufit %s).\n' \
        "$BEZ_PARY" "$SUFIT_BEZ_PARY" >&2
    printf '   Rytuał weryfikacji negatywnej ma dwie strony, a rejestr zapisuje tu jedną:\n' >&2
    printf '   wiadomo, że sprawdzian potrafi upaść, nie wiadomo, czy poprawka go podniosła.\n' >&2
    if [ "${ROZJAZDOW:-0}" -gt 0 ]; then
        printf '   Z tego rozjazdem granulacji jest: %s — zieleń leży pod samą nazwą pliku, czerwień\n' "$ROZJAZDOW" >&2
        printf '   pod `plik::test`. Wiersz na poziomie pliku nie domyka wiersza na poziomie\n' >&2
        printf '   testu; zapisz zieleń ponownie, tą samą etykietą co czerwień.\n' >&2
    fi
    printf '   Uwaga: przebieg `skipped` nie jest zielenią. Jeśli sprawdzian potrzebuje bazy\n' >&2
    printf '   albo kolejki, podnieś je przed zapisem, inaczej zapisujesz czerwień bez partnera.\n' >&2
    STATUS=1
fi
if [ -n "$SUFIT" ] && [ "${DLUG_WIERSZY:-0}" -gt "$SUFIT" ]; then
    printf '\n❌ Lista długu ma %s wierszy przy sufcie %s. Sufit jest zapadką: może maleć,\n' "$DLUG_WIERSZY" "$SUFIT" >&2
    printf '   nigdy rosnąć. Zamknij wiersz przebiegiem albo uzasadnij podniesienie w commicie.\n' >&2
    STATUS=1
fi
if [ -n "$DLUG" ] && [ "${NIEPOKRYTYCH:-0}" -gt 0 ]; then
    printf '\n❌ %s plików testowych nie ma ani wiersza w rejestrze, ani wiersza na liście długu.\n' "$NIEPOKRYTYCH" >&2
    printf '   Nikt nie widział ich na czerwono i nikt nie napisał, dlaczego nie — więc\n' >&2
    printf '   o tych testach nie wiadomo nic poza tym, że dziś przechodzą.\n' >&2
    STATUS=1
fi
exit "$STATUS"
