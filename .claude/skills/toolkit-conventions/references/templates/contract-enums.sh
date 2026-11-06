#!/usr/bin/env bash
# Słownik zamknięty przechodzi przez granicę języka — `conventions/contract-canon.md` §3.
#
# Pole zadeklarowane jako `str` serializuje te same wartości co enum i wygląda
# w przeglądzie tak samo. Różnica pojawia się dopiero w wygenerowanym typie:
# `status: string` znaczy, że kompilator drugiej strony nie odróżni „pending"
# od „pendign", więc rozjazd wychodzi jako karta, której operator nigdy nie
# zobaczy, zamiast jako błąd budowy.
#
# Reprodukcja z pola: sześć pól po stronie Pythona jechało przez kontrakt jako
# `str`. Po zamianie na enum i regeneracji klienta kompilator TypeScriptu
# zaczerwienił **trzy zmyślone wartości w fiksturach** — `postgres`,
# `capture_screenshot` i trzecią, której nie wskazał żaden audyt. Nikt ich nie
# zgłaszał, bo nic nie mogło ich zauważyć.
#
# Bramka czyta **wyeksportowany kontrakt**, nie modele źródłowe. Modele są
# o krok wyżej niż awaria: kontrakt jest tym, co konsumuje generator, więc to
# w nim widać, co naprawdę dostaje druga strona.
#
# Dwa naruszenia blokujące:
#   1. pole o nazwie ze słownika (`status`, `state`, `action`, `provenance`…)
#      zadeklarowane jako otwarty `string` — bez `enum`, `const` ani `$ref`;
#   2. wygenerowany artefakt kontraktu, którego git nie śledzi — `git diff`
#      milczy o plikach nieśledzonych, więc strażnik regeneracji melduje
#      zgodność, której nigdy nie sprawdził.
#
# Furtka jest wąska i ma powód: `.claude/otwarte-slowniki.txt`, wiersze
# `Model.pole<TAB>powód`. Pole bez powodu nie jest zwolnione.
#
# Sygnały maszynowe:
#   CONTRACT_VOCABULARY_FIELDS  ile pól słownikowych obejrzano  (mianownik)
#   CONTRACT_SCHEMAS            ile schematów niesie kontrakt
#   CONTRACT_OPEN_STRINGS       pola słownikowe jako otwarty string — blokuje
#   CONTRACT_UNTRACKED_GENERATED  generaty poza indeksem gita — blokuje
#   CONTRACT_EXEMPTIONS         ile pól zwolniono z powodem
#
# Użycie: contract-enums.sh [--format text|signals] [ŚCIEŻKA]
# Kody wyjścia: 0 = czysto, 1 = naruszenie blokujące, 2 = błąd użycia.
set -uo pipefail

FORMAT=text
CEL=.
while [ $# -gt 0 ]; do
    case "$1" in
        --format) FORMAT="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done
cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

KONTRAKT="$(git ls-files 2>/dev/null | grep -E '(^|/)openapi[^/]*\.json$' | grep -v snapshot | head -1)"
if [ -z "$KONTRAKT" ]; then
    printf 'CONTRACT_VOCABULARY_FIELDS: n/a — git nie zna w tym repozytorium pliku openapi*.json\n'
    exit 0
fi
command -v python3 >/dev/null 2>&1 || {
    printf 'CONTRACT_VOCABULARY_FIELDS: n/a — brak python3, kontraktu nie da się rozebrać\n'
    printf 'Brak narzędzia to `n/a`, nigdy zero ustaleń (rules-as-gates.md §11).\n' >&2
    exit 2
}

ZWOLNIENIA=".claude/otwarte-slowniki.txt"
[ -f "$ZWOLNIENIA" ] || ZWOLNIENIA=/dev/null

python3 - "$KONTRAKT" "$ZWOLNIENIA" "$TMP/wynik" <<'PYEOF'
import json, sys

kontrakt, zwolnienia_plik, wynik = sys.argv[1], sys.argv[2], sys.argv[3]

# Nazwy, które w każdej dziedzinie niosą zamknięty zbiór wartości. Lista jest
# krótka celowo: ma łapać klasę, nie każde pole tekstowe.
SLOWNIK = {"status", "state", "kind", "action", "decision", "origin", "role",
           "category", "surface", "provenance", "phase", "outcome", "reason_code"}

zwolnione = {}
try:
    for linia in open(zwolnienia_plik, encoding="utf-8"):
        if not linia.strip() or linia.startswith("#"):
            continue
        czesci = linia.rstrip("\n").split("\t")
        # Powód jest warunkiem zwolnienia. Wiersz bez powodu nie zwalnia:
        # to jest ta furtka, przez którą „to nie jest tak naprawdę enum"
        # wraca do korpusu bez rozmowy.
        if len(czesci) >= 2 and czesci[1].strip():
            zwolnione[czesci[0].strip()] = czesci[1].strip()
except OSError:
    pass

dokument = json.load(open(kontrakt, encoding="utf-8"))
schematy = dokument.get("components", {}).get("schemas", {}) or dokument.get("definitions", {}) or {}

def zamkniete(pole):
    """Zamknięty słownik: `enum`, `const`, `$ref` albo unia samych zamkniętych."""
    if not isinstance(pole, dict):
        return True
    if "enum" in pole or "const" in pole or "$ref" in pole:
        return True
    # `X | None` przychodzi jako anyOf — zamknięte, gdy każda gałąź niepusta
    # jest zamknięta. Bez tej gałęzi pole opcjonalne wyglądałoby na otwarte.
    galezie = pole.get("anyOf") or pole.get("oneOf") or pole.get("allOf")
    if galezie:
        realne = [g for g in galezie if isinstance(g, dict) and g.get("type") != "null"]
        return bool(realne) and all(zamkniete(g) for g in realne)
    return pole.get("type") != "string"

pol = 0
otwarte = []
uzyte_zwolnienia = 0
for nazwa_modelu, schemat in sorted(schematy.items()):
    if not isinstance(schemat, dict):
        continue
    for nazwa_pola, pole in sorted((schemat.get("properties") or {}).items()):
        if nazwa_pola not in SLOWNIK:
            continue
        pol += 1
        klucz = "%s.%s" % (nazwa_modelu, nazwa_pola)
        if zamkniete(pole):
            continue
        if klucz in zwolnione:
            uzyte_zwolnienia += 1
            continue
        otwarte.append("%s\totwarty string; enum po stronie kanonu nie dojechał do kontraktu" % klucz)

with open(wynik, "w", encoding="utf-8") as f:
    f.write("SCHEMAS %d\nFIELDS %d\nOPEN %d\nEXEMPT %d\n"
            % (len(schematy), pol, len(otwarte), uzyte_zwolnienia))
    for l in otwarte:
        f.write("OPEN\t%s\n" % l)
PYEOF

odczyt() { awk -v k="$1" '$1==k {print $2}' "$TMP/wynik" | head -1; }
SCHEMATOW="$(odczyt SCHEMAS)"; POL="$(odczyt FIELDS)"
OTWARTYCH="$(odczyt OPEN)"; ZWOLNIONYCH="$(odczyt EXEMPT)"

# Generat, którego git nie śledzi, jest bramką, która nie ma czego porównać.
# `git diff` o plikach nieśledzonych milczy, więc strażnik regeneracji
# meldowałby zgodność, której nigdy nie sprawdził.
NIESLEDZONE=0
: > "$TMP/niesledzone"
while IFS= read -r kandydat; do
    [ -n "$kandydat" ] || continue
    [ -e "$kandydat" ] || continue
    git ls-files --error-unmatch -- "$kandydat" >/dev/null 2>&1 || {
        printf '%s\n' "$kandydat" >> "$TMP/niesledzone"
        NIESLEDZONE=$((NIESLEDZONE + 1))
    }
done < <(find . -path ./.git -prune -o -path '*/node_modules' -prune -o \
            -type f \( -name 'api-types.d.ts' -o -name 'openapi.generated.ts' -o -name '*.generated.ts' \) -print 2>/dev/null | sed 's|^\./||')

if [ "$FORMAT" = text ]; then
    printf 'Kontrakt: %s\n\n' "$KONTRAKT"
    if [ "${OTWARTYCH:-0}" -gt 0 ]; then
        printf 'Pola słownikowe, które wychodzą przez kontrakt jako otwarty string:\n\n'
        awk -F'\t' '$1=="OPEN" && NF>1 {printf "  ❌ %-40s %s\n", $2, $3}' "$TMP/wynik" | head -15
        printf '\n'
    fi
    if [ "$NIESLEDZONE" -gt 0 ]; then
        printf 'Wygenerowane artefakty kontraktu poza indeksem gita:\n\n'
        sed 's/^/  ❌ /' "$TMP/niesledzone" | head -10
        printf '\n'
    fi
fi

printf 'CONTRACT_VOCABULARY_FIELDS: %s\n' "$POL"
printf 'CONTRACT_SCHEMAS: %s\n' "$SCHEMATOW"
printf 'CONTRACT_OPEN_STRINGS: %s\n' "$OTWARTYCH"
printf 'CONTRACT_UNTRACKED_GENERATED: %s\n' "$NIESLEDZONE"
printf 'CONTRACT_EXEMPTIONS: %s\n' "$ZWOLNIONYCH"

if [ "${POL:-0}" -eq 0 ]; then
    printf '\n❌ Kontrakt niesie %s schematów i ani jednego pola słownikowego. Zero pól\n' "${SCHEMATOW:-0}" >&2
    printf '   przy zielonym wyniku znaczy, że rozbiór nie trafił w kształt tego pliku,\n' >&2
    printf '   a nie że wszystkie słowniki są zamknięte.\n' >&2
    exit 1
fi
if [ "$(( ${OTWARTYCH:-0} + NIESLEDZONE ))" -gt 0 ]; then
    printf '\n❌ %s pól słownikowych jedzie przez kontrakt jako otwarty string, %s generatów\n' \
        "${OTWARTYCH:-0}" "$NIESLEDZONE" >&2
    printf '   jest poza indeksem gita. Pierwsze znaczy, że kompilator drugiej strony nie\n' >&2
    printf '   odróżni wartości poprawnej od literówki; drugie, że strażnik regeneracji\n' >&2
    printf '   porównuje plik, o którym git milczy.\n' >&2
    printf '   Czym to sprawdzić: `templates/contract-enums.sh --format text`\n' >&2
    exit 1
fi
exit 0
