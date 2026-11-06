#!/usr/bin/env bash
# Bramka kontraktu backlogu — `conventions/backlog-contract.md`.
#
# Działa bez konfiguracji projektu, tak samo jak `import-depth.sh`
# i `dependency-currency.sh`: czyta plik, wypisuje sygnały maszynowe, wraca
# kodem wyjścia. Nie zmienia niczego.
#
# Użycie:
#   backlog-lint.sh [--format text|signals] [--today RRRR-MM-DD] [ŚCIEŻKA]
#
# ŚCIEŻKA to katalog projektu (domyślnie `.`) albo wprost plik backlogu.
# `--today` służy testom; domyślnie bierze datę systemową.
#
# Kody wyjścia: 0 = kontrakt spełniony, 1 = naruszenia, 2 = błąd użycia.
set -uo pipefail

FORMAT=text
CEL=.
DZIS=""

while [ $# -gt 0 ]; do
    case "$1" in
        --format) [ $# -ge 2 ] || { printf 'brak wartości --format\n' >&2; exit 2; }; FORMAT="$2"; shift 2 ;;
        --today)  [ $# -ge 2 ] || { printf 'brak wartości --today\n' >&2; exit 2; }; DZIS="$2"; shift 2 ;;
        -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done
case "$FORMAT" in text|signals) ;; *) printf 'nieznany format: %s\n' "$FORMAT" >&2; exit 2 ;; esac

[ -n "$DZIS" ] || DZIS="$(date +%F)"

if [ -d "$CEL" ]; then
    PLIK="$CEL/.claude/backlog.md"
else
    PLIK="$CEL"
fi
[ -f "$PLIK" ] || { printf 'brak pliku backlogu: %s\n' "$PLIK" >&2; exit 2; }

KLUCZE="WPLYW STATUS ZRODLO DOWOD BRAMKA_ZAMYKAJACA PRZEGLAD BRIEF"
WZOR_ID='^[A-Z][A-Z0-9]*-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2,}$'

BLEDY="$(mktemp)"; OSTRZEZENIA="$(mktemp)"; POZYCJE="$(mktemp)"; TRESC_PLIKU="$(mktemp)"
trap 'rm -f "$BLEDY" "$OSTRZEZENIA" "$POZYCJE" "$TRESC_PLIKU"' EXIT

# Komentarz ze wzorem i przykład w kodzie nie są pozycjami backlogu.
if ! awk '
  function uncomment(line, clean, pos) {
    while (length(line)) {
      if (comment) {
        pos=index(line,"-->"); if (!pos) return clean
        line=substr(line,pos+3); comment=0
      } else {
        pos=index(line,"<!--"); if (!pos) return clean line
        clean=clean substr(line,1,pos-1); line=substr(line,pos+4); comment=1
      }
    }
    return clean
  }
  {
    line=$0
    if (!fence) line=uncomment(line)
    marker=line; sub(/^[[:space:]]*/, "", marker)
    if (marker ~ /^(```|~~~)/) {
    match(marker, /^`+|^~+/); size=RLENGTH
    if (!fence) { fence=substr(marker,1,1); width=size; next }
    if (substr(marker,1,1)==fence && size>=width && substr(marker,size+1) ~ /^[[:space:]]*$/) fence=""
    next
    }
    if (!fence) print line
  }
  END { if (comment || fence) exit 2 }
' "$PLIK" > "$TRESC_PLIKU"; then
    printf 'niedomknięty komentarz albo blok kodu w backlogu\n' >&2
    exit 2
fi

blad()      { printf '%s\n' "$*" >> "$BLEDY"; }
ostrzezenie() { printf '%s\n' "$*" >> "$OSTRZEZENIA"; }

# Data w formacie RRRR-MM-DD na liczbę dni od epoki; puste gdy nie parsuje.
# GNU `date -d` albo BSD `date -j -f` (macOS): szablon jedzie do każdego
# projektu, więc przenośność jest częścią poprawności (toolkit-sync.md).
na_dni() {
    printf '%s' "$1" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' || return 1
    local s
    s="$(date -d "$1" +%s 2>/dev/null)" \
        || s="$(date -j -f '%Y-%m-%d' "$1" +%s 2>/dev/null)" \
        || return 1
    printf '%s' "$s" | awk '{print int($1/86400)}'
}
DZIS_DNI="$(na_dni "$DZIS")" || { printf 'zła data --today: %s\n' "$DZIS" >&2; exit 2; }

# ── Rozbiór pliku ───────────────────────────────────────────────────────────
# Pozycje: `### <ID> — <tytuł>` w kolejności wykonania pod `## Do wykonania`.
# Pola trzymane w zmiennych Z_<KLUCZ>, nie w tablicy asocjacyjnej: `declare -A`
# wymaga basha 4, a /bin/bash na macOS to 3.2.
SEKCJA=""
ID=""
NIEODCZYTANE=0
zebrane_reset() { local k; for k in $KLUCZE; do eval "Z_$k=''"; done; }
zebrane_get()   { eval "printf '%s' \"\${Z_$1-}\""; }
zebrane_set()   { eval "Z_$1=\"\$2\""; }
zebrane_reset

zamknij_pozycje() {
    [ -n "$ID" ] || return 0
    local k brak="" wartosc
    for k in $KLUCZE; do
        wartosc="$(zebrane_get "$k")"
        if [ -z "$wartosc" ]; then
            brak="$brak $k"
        elif printf '%s' "$wartosc" | grep -q 'TODO:'; then
            blad "$ID: pole $k ma nieuzupełniony marker TODO: po migracji"
        fi
    done
    [ -n "$brak" ] && blad "$ID: brak pól:$brak"

    printf '%s\t%s\t%s\t%s\t%s\n' "$ID" "$(zebrane_get WPLYW)" \
        "$(zebrane_get STATUS)" "$(zebrane_get BRAMKA_ZAMYKAJACA)" \
        "$(zebrane_get PRZEGLAD)" >> "$POZYCJE"

    printf '%s' "$ID" | grep -qE "$WZOR_ID" \
        || blad "$ID: identyfikator niezgodny ze wzorcem <ZRODLO>-<RRRR-MM-DD>-<nn>"

    case "$(zebrane_get WPLYW)" in
        critical|high|medium|low|—|-|'') ;;
        *) blad "$ID: WPLYW '$(zebrane_get WPLYW)' spoza critical/high/medium/low/—" ;;
    esac
    case "$(zebrane_get STATUS)" in
        otwarte|'w trakcie'|zaparkowane|'') ;;
        zamkniete|zamknięte)
            blad "$ID: STATUS 'zamkniete' nie istnieje — pozycja domknięta znika z backlogu (reguła done ≠ open)" ;;
        *) blad "$ID: STATUS '$(zebrane_get STATUS)' spoza otwarte/w trakcie/zaparkowane" ;;
    esac

    # PRZEGLAD jest obowiązkowa dla zaparkowanych i dla odstępstw, bo to
    # jedyne, co odróżnia świadome odłożenie od zapomnienia.
    local wymaga_przegladu=0
    [ "$(zebrane_get STATUS)" = "zaparkowane" ] && wymaga_przegladu=1
    case "$(zebrane_get BRAMKA_ZAMYKAJACA)" in odstepstwo:*) wymaga_przegladu=1 ;; esac

    local p p_dni
    p="$(zebrane_get PRZEGLAD)"
    if [ "$wymaga_przegladu" -eq 1 ]; then
        if [ -z "$p" ] || [ "$p" = "—" ] || [ "$p" = "-" ]; then
            blad "$ID: zaparkowane albo odstępstwo bez PRZEGLAD"
        elif ! p_dni="$(na_dni "$p")"; then
            blad "$ID: PRZEGLAD '$p' nie jest datą RRRR-MM-DD"
        elif [ "$p_dni" -lt "$DZIS_DNI" ]; then
            blad "$ID: PRZEGLAD $p minęła — odstępstwo po terminie wraca jako otwarte"
        elif [ $((p_dni - DZIS_DNI)) -le 7 ]; then
            ostrzezenie "$ID: PRZEGLAD za $((p_dni - DZIS_DNI)) dni ($p)"
        fi
    fi

    local b
    b="$(zebrane_get BRIEF)"
    if [ -n "$b" ] && [ "$b" != "—" ] && [ "$b" != "-" ]; then
        [ -f "$(dirname "$PLIK")/$b" ] \
            || blad "$ID: BRIEF wskazuje nieistniejący plik: $b"
    fi

    ID=""; zebrane_reset
}

while IFS= read -r linia; do
    case "$linia" in
        '## '*) zamknij_pozycje; SEKCJA="$linia"; continue ;;
        '### '*)
            zamknij_pozycje
            ID="$(printf '%s' "$linia" | sed -E 's/^### +//; s/ +[—-].*$//; s/[[:space:]]+$//')"
            continue ;;
    esac
    # Mieszany format nie może przejść tylko dlatego, że istnieje jeden
    # poprawny rekord. Wewnątrz pozycji listy mogą być zwykłą prozą;
    # ich znaczenia parser nie rozstrzyga, ocenia je review.
    if [ -z "$ID" ] && printf '%s\n' "$linia" | grep -qE '^[[:space:]]*[-*] (\[[ xX]\] |\*\*[^*]+\*\*)'; then
        NIEODCZYTANE=$((NIEODCZYTANE + 1))
        blad "wpis listy poza kontraktem: $linia"
    fi
    if [ -n "$ID" ]; then
        case "$linia" in
            [A-Z_]*:*)
                klucz="${linia%%:*}"
                wartosc="${linia#*:}"
                wartosc="${wartosc# }"
                case " $KLUCZE " in *" $klucz "*) zebrane_set "$klucz" "$wartosc" ;; esac ;;
        esac
    fi
done < "$TRESC_PLIKU"
zamknij_pozycje

# ── Plik, którego w ogóle nie da się przeczytać ─────────────────────────────
# Najgorszy tryb awarii bramki: zero rozpoznanych pozycji zgłoszone jako zero
# naruszeń. Backlog sprzed migracji nie ma nagłówków `### <ID>`, więc pętla
# wyżej nie zbiera nic — i bez tego sprawdzenia wyglądałby na zgodny.
TRESC="$(grep -cE '^[[:space:]]*([-*|]|###? )' "$TRESC_PLIKU" || true)"
if [ ! -s "$POZYCJE" ] && [ "$TRESC" -gt 3 ]; then
    blad "plik ma treść ($TRESC linii pozycjopodobnych), ale zero pozycji w formacie \`### <ID> — <tytuł>\` — backlog nie jest w kontrakcie, uruchom migrację"
fi

# ── Duplikaty identyfikatorów ───────────────────────────────────────────────
while IFS= read -r dup; do
    [ -n "$dup" ] || continue
    blad "identyfikator powtórzony: $dup"
done < <(cut -f1 "$POZYCJE" | sort | uniq -d)

# ── Briefy osierocone ───────────────────────────────────────────────────────
KAT_BRIEF="$(dirname "$PLIK")/task-briefs"
OSIEROCONE=0
if [ -d "$KAT_BRIEF" ]; then
    while IFS= read -r bf; do
        grep -qF "task-briefs/$(basename "$bf")" "$TRESC_PLIKU" \
            || { OSIEROCONE=$((OSIEROCONE + 1)); ostrzezenie "brief bez linku z backlogu: $(basename "$bf")"; }
    done < <(find "$KAT_BRIEF" -maxdepth 1 -name '*.md' -type f | sort)
fi

# ── Sygnały ─────────────────────────────────────────────────────────────────
ITEMS="$(wc -l < "$POZYCJE" | tr -d ' ')"
MALFORMED="$(sort -u "$BLEDY" 2>/dev/null | grep -c . || true)"
OVERDUE="$(grep -c 'PRZEGLAD .* minęła' "$BLEDY" 2>/dev/null || true)"
NO_GATE="$(awk -F'\t' '$4 ~ /^odstepstwo:/ || $4 == ""' "$POZYCJE" | wc -l | tr -d ' ')"

NAJSTARSZY_HIGH=0
while IFS=$'\t' read -r i p _ _ _; do
    [ "$p" = "high" ] || continue
    d="$(printf '%s' "$i" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)"
    [ -n "$d" ] || continue
    dd="$(na_dni "$d")" || continue
    wiek=$((DZIS_DNI - dd))
    [ "$wiek" -gt "$NAJSTARSZY_HIGH" ] && NAJSTARSZY_HIGH="$wiek"
done < "$POZYCJE"

if [ "$FORMAT" = text ]; then
    if [ -s "$BLEDY" ]; then
        printf 'Naruszenia kontraktu backlogu (%s):\n\n' "$PLIK"
        sort -u "$BLEDY" | sed 's/^/  ❌ /'
        printf '\n'
    fi
    if [ -s "$OSTRZEZENIA" ]; then
        sort -u "$OSTRZEZENIA" | sed 's/^/  ⚠️  /'
        printf '\n'
    fi
fi

printf 'BACKLOG_ITEMS: %s\n' "$ITEMS"
printf 'BACKLOG_UNPARSED: %s\n' "$NIEODCZYTANE"
printf 'BACKLOG_MALFORMED: %s\n' "$MALFORMED"
printf 'BACKLOG_OVERDUE_REVIEWS: %s\n' "$OVERDUE"
printf 'BACKLOG_OLDEST_HIGH_DAYS: %s\n' "$NAJSTARSZY_HIGH"
printf 'BACKLOG_ORPHAN_BRIEFS: %s\n' "$OSIEROCONE"
printf 'BACKLOG_NO_GATE: %s\n' "$NO_GATE"

[ "$MALFORMED" -eq 0 ] || exit 1
exit 0
