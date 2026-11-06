#!/usr/bin/env bash
# Bramka tekstów w interfejsie — `conventions/ui-copy.md`.
#
# Szuka w plikach widoku: słów z katalogu nowomowy (z wagą), wykrzykników,
# emoji, liczb-dowodów bez źródła i adresów spoza pul zarezerwowanych.
#
# Katalog i zwolnienia są PROJEKTOWE. Skrypt działa bez nich, na katalogu
# wbudowanym — ale projekt, który nie ma pliku zwolnień, prędzej czy później
# wyłączy bramkę przy pierwszym trafieniu w termin dziedzinowy. Realny
# przypadek: `seamless` w konfiguracji generowania obrazów to bezszwowe tło
# z rolki, nie marketing.
#
#   .claude/ui-copy-katalog.tsv     waga <TAB> słowo <TAB> zamiennik
#   .claude/ui-copy-zwolnienia.tsv  słowo <TAB> wzorzec-ścieżki <TAB> powód
#
# Użycie:
#   ui-copy-lint.sh [--format text|signals] [--ext "astro tsx jsx vue"] [ŚCIEŻKA]
#
# Kody wyjścia: 0 = bez trafień blokujących, 1 = trafienia blokujące, 2 = błąd.
set -uo pipefail

FORMAT=text
ROZSZERZENIA="astro tsx jsx vue svelte html ts js"
CEL=.

while [ $# -gt 0 ]; do
    case "$1" in
        --format) FORMAT="${2:-}"; shift 2 ;;
        --ext)    ROZSZERZENIA="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done

cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

KATALOG=.claude/ui-copy-katalog.tsv
ZWOLNIENIA=.claude/ui-copy-zwolnienia.tsv
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# Katalog wbudowany — rdzeń z conventions/ui-copy.md §2. Projekt nadpisuje go
# własnym plikiem; wbudowany jest punktem startu, nie kompletem.
if [ -f "$KATALOG" ]; then
    grep -v '^#' "$KATALOG" | grep -v '^[[:space:]]*$' > "$TMP/katalog"
else
    cat > "$TMP/katalog" <<'EOF'
3	seamless	bezszwowy (jeśli o teksturze) / [usuń]
3	robust	odporny na X / [usuń]
3	cutting-edge	[usuń, opisz co jest nowe]
3	game-changing	[usuń]
3	effortless	bez konfiguracji / [usuń]
3	enterprise-grade	[usuń, podaj konkret]
3	supercharge	przyspiesza o X
3	unleash	[usuń]
3	revolutionize	[usuń]
3	kluczowy	decydujący / najważniejszy / [usuń]
3	kompleksowy	pełny / obejmujący wszystko
3	holistyczny	uwzględniający całość
3	innowacyjny	[usuń, opisz co jest nowe]
3	rewolucyjny	[usuń]
3	potężne narzędzie	[nazwij funkcję]
3	intuicyjny	[usuń]
3	bezproblemowo	bez dodatkowej pracy / samo działa
3	na wyższy poziom	[usuń]
3	kompleksowe rozwiązanie	[nazwij co to jest]
3	odblokuj potencjał	[usuń]
3	wykorzystaj moc	[usuń]
2	solution	[nazwij co to jest]
2	powerful	[usuń, podaj konkret]
2	skuteczny	działa / przynosi X wyników
2	realnie	[usuń albo podaj liczbę]
2	znacząco	[podaj liczbę]
2	dynamicznie	[podaj liczbę]
1	platform	[sprawdź, czy to naprawdę platforma]
1	experience	[sprawdź, czy nie da się nazwać wprost]
EOF
fi

[ -f "$ZWOLNIENIA" ] && grep -v '^#' "$ZWOLNIENIA" | grep -v '^[[:space:]]*$' > "$TMP/zwolnienia" \
                     || : > "$TMP/zwolnienia"

# Pliki widoku, tylko śledzone przez git. Kandydaci przed filtrem i po filtrze
# liczeni osobno: różnica to wykluczenia, a wykluczenie niepoliczone jest
# miejscem, w którym materiał znika bez śladu w wyniku bramki.
: > "$TMP/kandydaci"
for e in $ROZSZERZENIA; do git ls-files "*.$e" 2>/dev/null; done | sort -u > "$TMP/kandydaci"
KANDYDATOW="$(grep -c . "$TMP/kandydaci" || true)"
grep -vE '(^|/)(node_modules|dist|build|out|coverage|\.next|\.astro|vendor|docs|storybook-static)/|(^|/)fixtures/known-(good|bad)/' "$TMP/kandydaci" \
    | grep -vE '\.(min|generated|bundle)\.[a-z]+$' | sort -u > "$TMP/pliki" || true
LICZBA_PLIKOW="$(grep -c . "$TMP/pliki" || true)"
WYKLUCZONYCH=$(( KANDYDATOW - LICZBA_PLIKOW ))

# Zero plików do obejrzenia przy repozytorium, które pliki widoku MA, to nie
# jest czysty interfejs — to filtr, który zjadł cały materiał.
if [ "$LICZBA_PLIKOW" -eq 0 ] && [ "$KANDYDATOW" -gt 0 ]; then
    printf 'UI_COPY_FILES: 0\n'
    printf 'UI_COPY_FILES_CANDIDATES: %s\n' "$KANDYDATOW"
    printf 'UI_COPY_FILES_EXCLUDED: %s\n' "$WYKLUCZONYCH"
    printf '\n❌ Bramka nie obejrzała ani jednego pliku, choć git zna %s plików widoku.\n' "$KANDYDATOW" >&2
    printf '   Wszystkie wpadły w filtr katalogów wygenerowanych. Czym to sprawdzić:\n' >&2
    printf '   `git ls-files %s`\n' "$(for e in $ROZSZERZENIA; do printf "'*.%s' " "$e"; done)" >&2
    exit 1
fi

zwolniony() {
    local slowo="$1" plik="$2" s w
    while IFS=$'\t' read -r s w _; do
        [ "$s" = "$slowo" ] || continue
        case "$plik" in $w) return 0 ;; esac
    done < "$TMP/zwolnienia"
    return 1
}

: > "$TMP/blok"; : > "$TMP/review"; : > "$TMP/exempt"

while IFS=$'\t' read -r waga slowo zamiennik; do
    [ -n "${slowo:-}" ] || continue
    while IFS= read -r trafienie; do
        [ -n "$trafienie" ] || continue
        plik="${trafienie%%:*}"
        if zwolniony "$slowo" "$plik"; then
            printf '%s\t%s\n' "$slowo" "$plik" >> "$TMP/exempt"
            continue
        fi
        if [ "$waga" = "3" ]; then
            printf '%s\t%s\t%s\n' "$trafienie" "$slowo" "$zamiennik" >> "$TMP/blok"
        else
            printf '%s\t%s\t%s\t%s\n' "$trafienie" "$slowo" "$zamiennik" "$waga" >> "$TMP/review"
        fi
    done < <(grep -rniF -- "$slowo" $(cat "$TMP/pliki") 2>/dev/null | sort -u -t: -k1,2 | head -40)
done < "$TMP/katalog"

# Wykrzyknik i emoji w napisie widocznym dla użytkownika.
: > "$TMP/interpunkcja"
if [ "$LICZBA_PLIKOW" -gt 0 ]; then
    grep -rnoE '"[^"]{5,80}!"' $(cat "$TMP/pliki") 2>/dev/null | head -20 >> "$TMP/interpunkcja"
    grep -rnP '[\x{1F300}-\x{1FAFF}\x{2700}-\x{27BF}]' $(cat "$TMP/pliki") 2>/dev/null \
        | cut -c1-120 | sort -u -t: -k1,2 | head -20 >> "$TMP/interpunkcja"
fi

# Liczby-dowody: procenty z miejscem po przecinku, „ponad N", „N+ klientów".
: > "$TMP/liczby"
if [ "$LICZBA_PLIKOW" -gt 0 ]; then
    grep -rnoiE '(9[0-9][.,][0-9] ?% ?(uptime|dostępnoś|sla)|(ponad|over|\+) ?[0-9]{1,3}[  ]?[0-9]{3}\+? ?(klient|użytkownik|firm|users|customers|opinii|reviews)|[0-9][.,][0-9] ?/ ?5|zaufało nam)' \
        $(cat "$TMP/pliki") 2>/dev/null | sort -u -t: -k1,2 | head -20 > "$TMP/liczby"
fi

# Adresy spoza pul zarezerwowanych (RFC 2606).
: > "$TMP/adresy"
if [ "$LICZBA_PLIKOW" -gt 0 ]; then
    grep -rnoE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' $(cat "$TMP/pliki") 2>/dev/null \
        | grep -vE '@(example\.(com|org|net)|[^ ]*\.(invalid|test|localhost))' \
        | sort -u -t: -k1,2 | head -20 > "$TMP/adresy"
fi

N_BLOK="$(grep -c . "$TMP/blok" || true)"
N_REVIEW="$(grep -c . "$TMP/review" || true)"
N_EXEMPT="$(grep -c . "$TMP/exempt" || true)"
N_INTERP="$(grep -c . "$TMP/interpunkcja" || true)"
N_LICZBY="$(grep -c . "$TMP/liczby" || true)"
N_ADRESY="$(grep -c . "$TMP/adresy" || true)"

if [ "$FORMAT" = text ]; then
    printf 'Pliki widoku: %s\n\n' "$LICZBA_PLIKOW"
    if [ "$N_BLOK" -gt 0 ]; then
        printf 'Waga 3 — do usunięcia:\n'
        awk -F'\t' '{printf "  ❌ %s\n      „%s\" → %s\n", $1, $2, $3}' "$TMP/blok" | head -30
        printf '\n'
    fi
    if [ "$N_REVIEW" -gt 0 ]; then
        printf 'Waga 2 i 1 — do przeczytania:\n'
        awk -F'\t' '{printf "  · [%s] %s  („%s\")\n", $4, $1, $2}' "$TMP/review" | head -20
        printf '\n'
    fi
    [ "$N_LICZBY" -gt 0 ] && { printf 'Liczby bez źródła:\n'; sed 's/^/  ❌ /' "$TMP/liczby" | head -10; printf '\n'; }
    [ "$N_ADRESY" -gt 0 ] && { printf 'Adresy spoza pul zarezerwowanych:\n'; sed 's/^/  · /' "$TMP/adresy" | head -10; printf '\n'; }
    [ "$N_INTERP" -gt 0 ] && { printf 'Wykrzykniki i emoji:\n'; sed 's/^/  · /' "$TMP/interpunkcja" | head -10; printf '\n'; }
    if [ "$N_EXEMPT" -gt 0 ]; then
        printf 'Zwolnione dziedzinowo: %s trafień (%s)\n\n' "$N_EXEMPT" \
            "$(cut -f1 "$TMP/exempt" | sort -u | tr '\n' ' ')"
    fi
fi

printf 'UI_COPY_FILES: %s\n' "$LICZBA_PLIKOW"
printf 'UI_COPY_FILES_CANDIDATES: %s\n' "$KANDYDATOW"
printf 'UI_COPY_FILES_EXCLUDED: %s — katalogi wygenerowane i pliki .min/.bundle\n' "$WYKLUCZONYCH"
printf 'UI_COPY_BLOCKING: %s\n' "$N_BLOK"
printf 'UI_COPY_REVIEW: %s\n' "$N_REVIEW"
printf 'UI_COPY_EXEMPT: %s\n' "$N_EXEMPT"
printf 'UI_COPY_NUMBERS: %s\n' "$N_LICZBY"
printf 'UI_COPY_ADDRESSES: %s\n' "$N_ADRESY"
printf 'UI_COPY_PUNCT: %s\n' "$N_INTERP"
[ -f "$KATALOG" ] || printf 'UI_COPY_CATALOG: wbudowany (projekt nie ma %s)\n' "$KATALOG"
[ -f "$ZWOLNIENIA" ] || printf 'UI_COPY_EXEMPTIONS: brak pliku %s — pierwsze trafienie dziedzinowe wyłączy tę bramkę\n' "$ZWOLNIENIA"

[ "$((N_BLOK + N_LICZBY))" -eq 0 ] || exit 1
exit 0
