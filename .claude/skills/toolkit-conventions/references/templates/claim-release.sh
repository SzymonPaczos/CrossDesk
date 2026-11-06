#!/usr/bin/env bash
# Praca wykonana albo zasób zwolniony — `conventions/background-work.md` §3 i §9.
#
# Między zajęciem zasobu a końcem funkcji rejestr idempotencji twierdzi, że
# ktoś tę pracę wykonuje. Każde wyjście, które zostawia zajęcie bez odpowiedzi,
# jest wtedy zniknięciem zadania: ponowienie trafia na `claim -> False`, wraca
# bez pracy i zostaje potwierdzone jako cichy sukces. Nic nie rzuca, nic nie
# czerwienieje, a zlecenie stoi w stanie „zatwierdzone" na zawsze.
#
# Test zachowaniowy dowodzi tego dla ścieżek, które ktoś przewidział. Ta bramka
# jest regułą, której te ścieżki są przypadkami: czyta strukturę funkcji
# i czerwienieje na wyjściu, którego jeszcze nikt nie pokrył. Reprodukcja
# z pola: audyt wskazał JEDNĄ taką ścieżkę, a bramka przy pierwszym
# uruchomieniu pokazała TRZY — nieznalezione zlecenie oraz dwa zapisy
# wprowadzające je w stan uruchomiony.
#
# Dwie klasy naruszeń, obie blokujące:
#   1. funkcja zajmuje zasób i w całym ciele nie ma ani jednego zwolnienia;
#   2. po zajęciu zasobu stoi `return` albo `raise` poza `try` i poza `with` —
#      czyli wyjście bez obsługi, przez które zajęcie przeżywa funkcję.
#
# Sygnały maszynowe:
#   CLAIM_SITES              ile miejsc zajęcia zasobu obejrzano  (mianownik)
#   CLAIM_FUNCTIONS          w ilu funkcjach one leżą
#   CLAIM_NEVER_RELEASED     funkcje bez ani jednego zwolnienia — blokuje
#   CLAIM_EXIT_OUTSIDE_TRY   wyjścia po zajęciu poza try/with — blokuje
#
# Nazwy rozpoznawane jako zajęcie i jako zwolnienie da się poszerzyć zmiennymi
# CLAIM_NAMES i RELEASE_NAMES (lista rozdzielona przecinkami).
#
# Użycie: claim-release.sh [--format text|signals] [ŚCIEŻKA]
# Kody wyjścia: 0 = czysto, 1 = naruszenie blokujące, 2 = błąd użycia.
set -uo pipefail

FORMAT=text
CEL=.
while [ $# -gt 0 ]; do
    case "$1" in
        --format) FORMAT="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done
cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# Mianownik z indeksu gita; kontrola z przejścia po systemie plików stoi
# w `fixtures/rejestr-bramek.tsv` i jest uruchamiana osobno.
git ls-files -- '*.py' 2>/dev/null \
    | grep -vE '(^|/)(node_modules|dist|build|__pycache__|\.venv)/' | sort -u > "$TMP/pliki"
PLIKOW="$(grep -c . "$TMP/pliki" || true)"

if [ "$PLIKOW" -eq 0 ]; then
    printf 'CLAIM_SITES: n/a — git nie zna w tym repozytorium plików .py\n'
    exit 0
fi

command -v python3 >/dev/null 2>&1 || {
    printf 'CLAIM_SITES: n/a — brak python3, struktury funkcji nie da się rozebrać\n'
    printf 'Brak narzędzia to `n/a`, nigdy zero ustaleń (rules-as-gates.md §11).\n' >&2
    exit 2
}

CLAIM_NAMES="${CLAIM_NAMES:-claim,acquire,lease,reserve,checkout,take_lease}"
RELEASE_NAMES="${RELEASE_NAMES:-release,rollback,unlock,give_back,abandon,_fail,fail_run}"

python3 - "$TMP/pliki" "$TMP/wynik" "$CLAIM_NAMES" "$RELEASE_NAMES" <<'PYEOF'
import ast, sys

pliki = [l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
CLAIM = {n.strip() for n in sys.argv[3].split(",") if n.strip()}
RELEASE = {n.strip() for n in sys.argv[4].split(",") if n.strip()}

# Zajęcie i zwolnienie rozpoznajemy po nazwie wołanej metody albo funkcji.
# Nazwa, nie typ: bramka czyta źródło, nie uruchamia aplikacji — uruchomienie
# jej po to, żeby ją zmierzyć, zainstalowałoby mierzoną zależność w procesie
# pomiaru.
def wolania(wezel, nazwy):
    trafienia = []
    for dziecko in ast.walk(wezel):
        if not isinstance(dziecko, ast.Call):
            continue
        f = dziecko.func
        nazwa = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
        if nazwa in nazwy:
            trafienia.append(dziecko)
    return trafienia

miejsc = 0
funkcji = 0
bez_zwolnienia = []
wyjscia = []

for sciezka in pliki:
    try:
        drzewo = ast.parse(open(sciezka, encoding="utf-8", errors="replace").read(), filename=sciezka)
    except (OSError, SyntaxError):
        continue
    for wezel in ast.walk(drzewo):
        if not isinstance(wezel, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        zajecia = wolania(wezel, CLAIM)
        if not zajecia:
            continue
        miejsc += len(zajecia)
        funkcji += 1

        if not wolania(wezel, RELEASE):
            bez_zwolnienia.append("%s:%d\t%s" % (sciezka, wezel.lineno, wezel.name))
            continue

        # Indeks pierwszej instrukcji NAJWYŻSZEGO poziomu funkcji, w której
        # leży zajęcie. Wszystko po niej biegnie z zajętym zasobem.
        pierwsza = None
        for i, instrukcja in enumerate(wezel.body):
            if wolania(instrukcja, CLAIM):
                pierwsza = i
                break
        if pierwsza is None:
            continue

        for instrukcja in wezel.body[pierwsza + 1:]:
            if isinstance(instrukcja, (ast.Try, ast.With, ast.AsyncWith)):
                continue
            # `return` i `raise` na najwyższym poziomie, poza obsługą, to
            # wyjście, na którym zajęcie przeżywa funkcję. Zagnieżdżone w `if`
            # też: warunek nie jest obsługą.
            for dziecko in ast.walk(instrukcja):
                if isinstance(dziecko, (ast.Return, ast.Raise)):
                    wyjscia.append("%s:%d\t%s -> %s" % (
                        sciezka, getattr(dziecko, "lineno", instrukcja.lineno),
                        wezel.name, type(dziecko).__name__.lower()))
                    break

with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write("SITES %d\nFUNCS %d\nNORELEASE %d\nOUTSIDE %d\n"
            % (miejsc, funkcji, len(bez_zwolnienia), len(wyjscia)))
    for l in bez_zwolnienia:
        f.write("NORELEASE\t%s\n" % l)
    for l in wyjscia:
        f.write("OUTSIDE\t%s\n" % l)
PYEOF

odczyt() { awk -v k="$1" '$1==k {print $2}' "$TMP/wynik" | head -1; }
MIEJSC="$(odczyt SITES)"; FUNKCJI="$(odczyt FUNCS)"
BEZ="$(odczyt NORELEASE)"; POZA="$(odczyt OUTSIDE)"

if [ "${MIEJSC:-0}" -eq 0 ]; then
    printf 'CLAIM_SITES: n/a — %s plików .py i ani jednego zajęcia zasobu (%s)\n' "$PLIKOW" "$CLAIM_NAMES"
    printf 'CLAIM_FUNCTIONS: 0\n'
    exit 0
fi

if [ "$FORMAT" = text ]; then
    if [ "${BEZ:-0}" -gt 0 ]; then
        printf 'Funkcje zajmujące zasób i nigdy go niezwalniające:\n\n'
        awk -F'\t' '$1=="NORELEASE" && NF>1 {printf "  ❌ %-44s %s\n", $2, $3}' "$TMP/wynik" | head -15
        printf '\n'
    fi
    if [ "${POZA:-0}" -gt 0 ]; then
        printf 'Wyjścia po zajęciu zasobu, poza try i poza with:\n\n'
        awk -F'\t' '$1=="OUTSIDE" && NF>1 {printf "  ❌ %-44s %s\n", $2, $3}' "$TMP/wynik" | head -15
        printf '\n'
    fi
fi

printf 'CLAIM_SITES: %s\n' "$MIEJSC"
printf 'CLAIM_FUNCTIONS: %s\n' "$FUNKCJI"
printf 'CLAIM_NEVER_RELEASED: %s\n' "$BEZ"
printf 'CLAIM_EXIT_OUTSIDE_TRY: %s\n' "$POZA"

if [ "$(( ${BEZ:-0} + ${POZA:-0} ))" -gt 0 ]; then
    printf '\n❌ %s funkcji zajmuje zasób bez zwolnienia, %s wyjść biegnie po zajęciu poza\n' \
        "${BEZ:-0}" "${POZA:-0}" >&2
    printf '   obsługą. Ponowienie trafi wtedy na „już zajęte", wróci bez pracy i zostanie\n' >&2
    printf '   potwierdzone jako sukces — zlecenie znika bez zapisu i bez wykonania.\n' >&2
    printf '   Czym to sprawdzić: `templates/claim-release.sh --format text`\n' >&2
    exit 1
fi
exit 0
