#!/usr/bin/env bash
# Dowód z testu — `conventions/test-evidence.md`, „Sygnały maszynowe".
#
# Trzy klasy, które konwencja wypisuje jako mechaniczne, i które do dziś
# rozstrzygało czytanie:
#   1. mutacja globalnego stanu interpretera przy KOLEKCJI (poza ciałem
#      funkcji i fixture'a) — psuje inny, nietknięty test na części jobów CI;
#   2. test bez ani jednej asercji — przechodzi zawsze, także bez naprawy;
#   3. asercja wyłącznie na kształcie wywołania (`assert_called_with`,
#      `toHaveBeenCalledWith`) bez asercji na obserwowalnym efekcie.
#
# Mianownik pochodzi z indeksu gita, nie z własnego spaceru po katalogach:
# najpierw lista plików testowych, potem ich otwieranie. Repozytorium
# z katalogiem testów i zerem plików testowych kończy się kodem 1.
#
# Sygnały maszynowe:
#   TESTS_FILES          ile plików testowych obejrzano  (mianownik)
#   TESTS_CASES          ile przypadków testowych w nich znaleziono
#   TESTS_IMPORT_SIDE_EFFECTS  mutacje stanu globalnego przy kolekcji — blokuje
#   TESTS_WITHOUT_ASSERT ile przypadków bez asercji — blokuje
#   TESTS_CALL_SHAPE_ONLY ile opiera się wyłącznie na kształcie wywołania — raport
#
# Użycie: test-evidence.sh [--format text|signals] [ŚCIEŻKA]
# Kody wyjścia: 0 = czysto, 1 = naruszenie blokujące, 2 = błąd użycia.
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

git ls-files 2>/dev/null \
    | grep -E '(^|/)(tests?|e2e|__tests__)/.*\.(py|ts|tsx|js|jsx)$|(^|/)test_[^/]*\.py$|[^/]*_test\.py$|\.(test|spec)\.[tj]sx?$' \
    | grep -vE '(^|/)(node_modules|dist|build|__pycache__)/|(^|/)fixtures/known-(good|bad)/' | sort -u > "$TMP/pliki"
PLIKOW="$(grep -c . "$TMP/pliki" || true)"

# Katalog testów bez plików testowych — pomiar, który się nie odbył.
KATALOGOW_TESTOWYCH="$(git ls-files 2>/dev/null \
    | grep -cE '(^|/)(tests?|e2e|__tests__)/' || true)"
if [ "$PLIKOW" -eq 0 ]; then
    if [ "$KATALOGOW_TESTOWYCH" -gt 0 ]; then
        printf 'TESTS_FILES: 0\n'
        printf '\n❌ Git zna %s plików w katalogach testowych, a bramka nie rozpoznała ani\n' "$KATALOGOW_TESTOWYCH" >&2
        printf '   jednego jako pliku testowego. Zero naruszeń przy zerowym mianowniku znaczy,\n' >&2
        printf '   że wzorzec nazw nie pasuje do tego projektu, a nie że testy są w porządku.\n' >&2
        exit 1
    fi
    printf 'TESTS_FILES: n/a — git nie zna w tym repozytorium plików testowych\n'
    printf 'TESTS_CASES: 0\n'
    exit 0
fi

command -v python3 >/dev/null 2>&1 || {
    printf 'TESTS_FILES: %s\n' "$PLIKOW"
    printf 'TESTS_CASES: n/a — brak python3, przypadków testowych nie da się rozebrać\n'
    printf 'Brak narzędzia to `n/a`, nigdy zero ustaleń (rules-as-gates.md §11).\n' >&2
    exit 2
}

python3 - "$TMP/pliki" "$TMP/wynik" <<'PYEOF'
import re, sys

pliki = [l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
MUTACJE = re.compile(r"(sys\.modules\[|sys\.modules\.pop|sys\.path\.(insert|append)|"
                     r"os\.environ\[|os\.environ\.setdefault|importlib\.reload)")
DEF_PY = re.compile(r"^(\s*)def\s+(test_[A-Za-z0-9_]*)\s*\(")
DEF_JS = re.compile(r"""^\s*(?:it|test)\s*(?:\.\w+)?\s*\(\s*['"`]""")
ASERCJA = re.compile(r"\bassert\b|\bexpect\s*\(|\.should\b|self\.assert|pytest\.raises|"
                     r"assertRaises|toBe|toEqual|toThrow|toMatch")
KSZTALT = re.compile(r"assert_called|assert_has_calls|called_once|toHaveBeenCalled")

skutki, przypadki, bez_asercji, tylko_ksztalt = [], 0, [], 0
for p in pliki:
    try:
        linie = open(p, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        continue

    # Mutacja globalnego stanu na poziomie modułu: wcięcie zero i poza `def`.
    poziom_modulu = True
    for i, l in enumerate(linie):
        goly = l.strip()
        if not goly or goly.startswith("#"):
            continue
        wciecie = len(l) - len(l.lstrip())
        if wciecie == 0:
            poziom_modulu = not re.match(r"^(def|class|@|async\s+def)", goly)
        if poziom_modulu and wciecie == 0 and MUTACJE.search(l):
            skutki.append("%s:%d\t%s" % (p, i + 1, goly[:90]))

    if p.endswith(".py"):
        i = 0
        while i < len(linie):
            m = DEF_PY.match(linie[i])
            if not m:
                i += 1
                continue
            przypadki += 1
            wciecie = len(m.group(1))
            j = i + 1
            cialo = []
            while j < len(linie):
                l = linie[j]
                if l.strip() and (len(l) - len(l.lstrip())) <= wciecie and not l.strip().startswith(")"):
                    break
                cialo.append(l)
                j += 1
            tekst = "\n".join(cialo)
            if not ASERCJA.search(tekst):
                bez_asercji.append("%s:%d\t%s" % (p, i + 1, m.group(2)))
            elif KSZTALT.search(tekst) and not re.search(
                    r"\bassert\s+(?!.*(assert_called|called_once))", tekst):
                tylko_ksztalt += 1
            i = j
    else:
        blok, otwarty, start = [], False, 0
        for i, l in enumerate(linie):
            if DEF_JS.match(l):
                if otwarty:
                    tekst = "\n".join(blok)
                    if not ASERCJA.search(tekst):
                        bez_asercji.append("%s:%d\t%s" % (p, start + 1, linie[start].strip()[:70]))
                    elif KSZTALT.search(tekst) and not re.search(r"expect\((?!.*HaveBeenCalled)", tekst):
                        tylko_ksztalt += 1
                przypadki += 1
                otwarty, blok, start = True, [l], i
            elif otwarty:
                blok.append(l)
        if otwarty:
            tekst = "\n".join(blok)
            if not ASERCJA.search(tekst):
                bez_asercji.append("%s:%d\t%s" % (p, start + 1, linie[start].strip()[:70]))
            elif KSZTALT.search(tekst) and not re.search(r"expect\((?!.*HaveBeenCalled)", tekst):
                tylko_ksztalt += 1

with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write("CASES %d\nSIDE %d\nNOASSERT %d\nSHAPE %d\n"
            % (przypadki, len(skutki), len(bez_asercji), tylko_ksztalt))
    for l in skutki:
        f.write("SIDE\t%s\n" % l)
    for l in bez_asercji:
        f.write("NOASSERT\t%s\n" % l)
PYEOF

odczyt() { awk -v k="$1" '$1==k {print $2}' "$TMP/wynik" | head -1; }
PRZYPADKOW="$(odczyt CASES)"; SKUTKOW="$(odczyt SIDE)"
BEZ_ASERCJI="$(odczyt NOASSERT)"; KSZTALT="$(odczyt SHAPE)"

if [ "$FORMAT" = text ]; then
    if [ "${SKUTKOW:-0}" -gt 0 ]; then
        printf 'Mutacja stanu globalnego przy kolekcji (wykonuje się w każdej sesji):\n\n'
        awk -F'\t' '$1=="SIDE" && NF>1 {printf "  ❌ %s\n      %s\n", $2, $3}' "$TMP/wynik" | head -15
        printf '\n'
    fi
    if [ "${BEZ_ASERCJI:-0}" -gt 0 ]; then
        printf 'Przypadki testowe bez ani jednej asercji — przechodzą także bez naprawy:\n\n'
        awk -F'\t' '$1=="NOASSERT" && NF>1 {printf "  ❌ %-44s %s\n", $2, $3}' "$TMP/wynik" | head -15
        printf '\n'
    fi
fi

printf 'TESTS_FILES: %s\n' "$PLIKOW"
printf 'TESTS_CASES: %s\n' "$PRZYPADKOW"
printf 'TESTS_IMPORT_SIDE_EFFECTS: %s\n' "$SKUTKOW"
printf 'TESTS_WITHOUT_ASSERT: %s\n' "$BEZ_ASERCJI"
printf 'TESTS_CALL_SHAPE_ONLY: %s\n' "$KSZTALT"

if [ "${PRZYPADKOW:-0}" -eq 0 ]; then
    printf '\n❌ %s plików testowych i zero przypadków testowych w środku. To nie jest\n' "$PLIKOW" >&2
    printf '   suite bez błędów, tylko parser, który nic nie zebrał — ta sama awaria,\n' >&2
    printf '   co „collected: 0 tests" z kodem wyjścia zero.\n' >&2
    exit 1
fi
if [ "$(( ${SKUTKOW:-0} + ${BEZ_ASERCJI:-0} ))" -gt 0 ]; then
    printf '\n❌ %s mutacji stanu globalnego przy kolekcji i %s testów bez asercji.\n' \
        "${SKUTKOW:-0}" "${BEZ_ASERCJI:-0}" >&2
    printf '   Pierwsze psują inny, nietknięty test na części jobów CI; drugie przechodzą\n' >&2
    printf '   zarówno z naprawą, jak i bez niej, czyli nie dowodzą niczego.\n' >&2
    exit 1
fi
exit 0
