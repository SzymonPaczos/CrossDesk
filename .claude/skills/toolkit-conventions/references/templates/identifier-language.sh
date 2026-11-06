#!/usr/bin/env bash
# Język identyfikatorów — `conventions/naming-conventions.md` §2.
#
# Szuka deklaracji, których nazwa nie jest angielska: znaki diakrytyczne albo
# rdzeń z listy polskich słów. Terminy dziedzinowe bez angielskiego
# odpowiednika zwalnia się przez leksykon projektu — i tylko przez niego, bo
# inaczej „termin dziedzinowy" staje się furtką na wszystko.
#
#   .claude/leksykon-terminow.txt   jeden termin w linii, po # powód
#   .claude/identyfikatory.baseline liczba progowa (zapadka: nigdy w górę)
#
# Użycie:
#   identifier-language.sh [--format text|signals] [--baseline] [ŚCIEŻKA]
#
# `--baseline` zapisuje bieżącą liczbę jako próg zamiast ją sprawdzać.
#
# Kody wyjścia: 0 = na progu lub poniżej, 1 = powyżej progu, 2 = błąd użycia.
set -uo pipefail

FORMAT=text
USTAW_BASELINE=0
CEL=.

while [ $# -gt 0 ]; do
    case "$1" in
        --format)   FORMAT="${2:-}"; shift 2 ;;
        --baseline) USTAW_BASELINE=1; shift ;;
        -h|--help)  sed -n '2,18p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done

cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

LEKSYKON=.claude/leksykon-terminow.txt
BASELINE=.claude/identyfikatory.baseline
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# Rdzenie polskie spotykane w nazwach. Lista jest z natury niepełna — łapie
# częste przypadki, a nie wszystkie. Uzupełnia ją wykrywanie diakrytyków.
RDZENIE='utworz|utwórz|zlecen|produkt|artykul|artykuł|rozmow|watek|wątek|wynik|dane|uzytkownik|użytkownik|zadani|regul|reguł|kanon|etap|krok|blad|błąd|nazwa|opis|tresc|treść|wartosc|wartość|liczba|pole|widok|szukan|dodaj|usun|usuń|zapisz|pobierz|buduj|licz|sprawdz|sprawdź|pytani|odpowiedz|odpowiedź|zgod|bramk|przebieg|proba|próba|plik|katalog|sciez|ścież|czat|obraz|zdjec|zdjęc|galeri|koszt|budzet|budżet|stan|nowy|stary|pusty|calosc|całość|czesc|część|kolejk|wiersz|kolumn|naglow|nagłów|stopk|przycisk|formularz|zakladk|zakładk|ustawien|wybor|wybór|zmien|zmień|otworz|otwórz|zamknij|wlacz|włącz|wylacz|wyłącz'

if [ -f "$LEKSYKON" ]; then
    grep -v '^#' "$LEKSYKON" 2>/dev/null | sed 's/#.*//' | tr -d ' \t' | grep -v '^$' | sort -u > "$TMP/leksykon"
else
    : > "$TMP/leksykon"
fi

# Deklaracje: Python `def`/`class`, TypeScript `function|const|let|interface|type|class`.
{
    git grep -nE '^[[:space:]]*(def|class)[[:space:]]+[a-zA-Z_ąćęłńóśźż][a-zA-Z0-9_ąćęłńóśźż]*' \
        -- '*.py' 2>/dev/null \
        | sed -E 's/^([^:]+:[0-9]+):[[:space:]]*(def|class)[[:space:]]+([a-zA-Z0-9_ąćęłńóśźż]+).*/\1\t\3/'
    git grep -nE '\b(function|const|let|interface|type|class)[[:space:]]+[a-zA-Z_ąćęłńóśźż][a-zA-Z0-9_ąćęłńóśźż]*' \
        -- '*.ts' '*.tsx' '*.js' '*.jsx' 2>/dev/null \
        | sed -E 's/^([^:]+:[0-9]+):.*\b(function|const|let|interface|type|class)[[:space:]]+([a-zA-Z0-9_ąćęłńóśźż]+).*/\1\t\3/'
} | grep -vE '(^|/)(node_modules|dist|build|\.next|vendor|generated)/|(^|/)fixtures/known-(good|bad)/' \
  | grep "$(printf '\t')" | sort -u > "$TMP/deklaracje"

WSZYSTKICH="$(grep -c . "$TMP/deklaracje" || true)"

: > "$TMP/trafienia"; : > "$TMP/zwolnione"

# Dopasowanie w jednym przebiegu awk. Pętla powłoki po kilku tysiącach
# deklaracji trwała ponad dwie minuty, a bramka, która tyle trwa, zostaje
# pominięta przy pierwszym pośpiechu.
awk -F'\t' -v rdzenie="$RDZENIE" -v lekplik="$TMP/leksykon" \
    -v wyjT="$TMP/trafienia" -v wyjZ="$TMP/zwolnione" '
BEGIN {
    n = split(rdzenie, r, "|")
    while ((getline l < lekplik) > 0) leks[tolower(l)] = 1
}
{
    miejsce = $1; nazwa = $2
    if (nazwa == "") next

    podejrzana = (nazwa ~ /[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]/)
    if (!podejrzana) {
        # rozbij po podkreśleniu i po wielkiej literze
        rozbita = nazwa
        # POSIX awk nie ma odwołań wstecznych w gsub — `\1` nic nie podstawia.
        # Wielką literę poprzedzamy podkreśleniem przez `&` (całe dopasowanie).
        gsub(/[A-ZĄĆĘŁŃÓŚŹŻ]/, "_&", rozbita)
        m = split(tolower(rozbita), slowa, "_")
        for (i = 1; i <= m && !podejrzana; i++)
            for (j = 1; j <= n; j++)
                if (index(slowa[i], tolower(r[j])) == 1) { podejrzana = 1; break }
    }
    if (!podejrzana) next

    if (tolower(nazwa) in leks) print nazwa "\t" miejsce >> wyjZ
    else print miejsce "\t" nazwa >> wyjT
}
' "$TMP/deklaracje"

TRAFIEN="$(grep -c . "$TMP/trafienia" || true)"
ZWOLNIONYCH="$(grep -c . "$TMP/zwolnione" || true)"
UNIKALNYCH="$(cut -f2 "$TMP/trafienia" 2>/dev/null | sort -u | grep -c . || true)"
PROCENT=0
[ "$WSZYSTKICH" -gt 0 ] && PROCENT=$(( TRAFIEN * 100 / WSZYSTKICH ))

if [ "$USTAW_BASELINE" -eq 1 ]; then
    mkdir -p .claude
    printf '%s\n' "$TRAFIEN" > "$BASELINE"
    printf 'Założono baseline %s = %s (na %s deklaracji, %s%%)\n' \
        "$BASELINE" "$TRAFIEN" "$WSZYSTKICH" "$PROCENT"
    exit 0
fi

if [ "$FORMAT" = text ] && [ "$TRAFIEN" -gt 0 ]; then
    printf 'Deklaracje z nazwą nieangielską (%s unikalnych nazw):\n\n' "$UNIKALNYCH"
    cut -f2 "$TMP/trafienia" | sort | uniq -c | sort -rn | head -20 \
        | awk '{printf "  %4s× %s\n", $1, $2}'
    [ "$UNIKALNYCH" -gt 20 ] && printf '  … i %s dalszych nazw\n' "$((UNIKALNYCH - 20))"
    printf '\n'
    [ "$ZWOLNIONYCH" -gt 0 ] && printf 'Zwolnione leksykonem: %s (%s)\n\n' "$ZWOLNIONYCH" \
        "$(cut -f1 "$TMP/zwolnione" | sort -u | tr '\n' ' ')"
fi

printf 'IDENT_TOTAL: %s\n' "$WSZYSTKICH"
printf 'IDENT_NON_ENGLISH: %s\n' "$TRAFIEN"
printf 'IDENT_NON_ENGLISH_UNIQUE: %s\n' "$UNIKALNYCH"
printf 'IDENT_NON_ENGLISH_PCT: %s\n' "$PROCENT"
printf 'IDENT_LEXICON_EXEMPT: %s\n' "$ZWOLNIONYCH"
[ -f "$LEKSYKON" ] || printf 'IDENT_LEXICON: brak %s — termin dziedzinowy nie ma jak zostać zwolniony\n' "$LEKSYKON"

# Zapadka: liczba nigdy nie rośnie. Bez pliku baseline bramka tylko raportuje —
# projekt sprzed decyzji nie powinien nagle stanąć na czerwonym.
if [ -f "$BASELINE" ]; then
    PROG="$(tr -cd '0-9' < "$BASELINE")"; PROG="${PROG:-0}"
    printf 'IDENT_BASELINE: %s\n' "$PROG"
    if [ "$TRAFIEN" -gt "$PROG" ]; then
        printf '\n❌ REGRESJA: %s > %s. Nowy kod ma mieć nazwy angielskie (naming-conventions.md §2).\n' \
            "$TRAFIEN" "$PROG" >&2
        exit 1
    fi
    [ "$TRAFIEN" -lt "$PROG" ] && printf '\n✅ POSTĘP: %s < %s — zaktualizuj baseline w tym samym commicie\n' "$TRAFIEN" "$PROG"
    exit 0
fi
printf 'IDENT_BASELINE: brak (tryb raportowy)\n'
exit 0
