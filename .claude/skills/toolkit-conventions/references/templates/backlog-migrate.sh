#!/usr/bin/env bash
# Migracja backlogu do kontraktu maszynowego (`conventions/backlog-contract.md`).
#
# Skrypt NIE ZGADUJE. Pole, którego nie potrafi wyprowadzić ze źródła, dostaje
# marker `TODO: <czego brakuje>` — nigdy wartości wymyślonej. Bramka kontraktu
# (`backlog-lint.sh`) traktuje pozostawiony `TODO:` jako naruszenie, więc
# migracja niedokończona nie przejdzie za zieloną.
#
# Rozpoznawane kształty wejścia:
#   kontrakt  — już zgodny, nic do roboty
#   tabela    — `| ID | P | Pozycja | Dowód | Bramka | Źródło | Data |`
#   lista     — `- [ ] **ID Tytuł.** proza…` pod nagłówkami `## P0/P1/P2`
#   narracja  — bloki `### Tytuł`, kolejka numerowana, pozycje przekreślone
#
# Użycie:
#   backlog-migrate.sh [--apply] [--today RRRR-MM-DD] [ŚCIEŻKA]
#
# Bez `--apply` zapisuje obok, jako `<backlog>.migrated`, i nic nie podmienia.
# Z `--apply` kopiuje oryginał do `.claude/history/backlog-przed-migracja-<data>.md`,
# potem podmienia plik.
#
# Kody wyjścia: 0 = gotowe, 1 = niezmiennik bezstratności naruszony (nic nie
# zapisano), 2 = błąd użycia.
set -uo pipefail

APPLY=0
DZIS=""
CEL=.

while [ $# -gt 0 ]; do
    case "$1" in
        --apply) APPLY=1; shift ;;
        --today) DZIS="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done
[ -n "$DZIS" ] || DZIS="$(date +%F)"

if [ -d "$CEL" ]; then PLIK="$CEL/.claude/backlog.md"; else PLIK="$CEL"; fi
[ -f "$PLIK" ] || { printf 'brak pliku backlogu: %s\n' "$PLIK" >&2; exit 2; }

REKORDY="$(mktemp -d)"; HISTORIA="$(mktemp)"; KOLEJKA="$(mktemp)"
trap 'rm -rf "$REKORDY" "$HISTORIA" "$KOLEJKA"' EXIT
LICZNIK=0

# ── Rozpoznanie kształtu ────────────────────────────────────────────────────
# Punktacja, nie kolejność testów. Plik narracyjny potrafi zawierać kilka
# wierszy tabeli i przy testowaniu po kolei zostałby uznany za tabelę.
wykryj_ksztalt() {
    grep -qE '^### [A-Z][A-Z0-9]*-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]+' "$PLIK" \
        && grep -q '^BRAMKA_ZAMYKAJACA:' "$PLIK" && { printf 'kontrakt\n'; return; }

    local n_tab n_lista n_narr
    n_tab="$(grep -cE '^\|[[:space:]]*[A-Za-z]+-?[0-9]+[[:space:]]*\|.*\|.*\|' "$PLIK" || true)"
    n_lista="$(grep -cE '^- \[[ x]\] ' "$PLIK" || true)"
    n_narr="$(grep -cE '^### ' "$PLIK" || true)"

    if [ "$n_tab" -ge "$n_lista" ] && [ "$n_tab" -ge "$n_narr" ] && [ "$n_tab" -gt 0 ]; then
        printf 'tabela\n'; return
    fi
    if [ "$n_lista" -ge "$n_narr" ] && [ "$n_lista" -gt 0 ]; then printf 'lista\n'; return; fi
    [ "$n_narr" -gt 0 ] && { printf 'narracja\n'; return; }
    printf 'nieznany\n'
}

# ── Liczenie pozycji w źródle, niezależne od parsera ────────────────────────
# Niezależne celowo: gdyby liczył ten sam kod, co parsuje, niezmiennik
# potwierdzałby sam siebie i nie wykryłby zgubionej pozycji.
policz_wejscie() {
    case "$1" in
        tabela)   grep -cE '^\|[[:space:]]*[A-Za-z]+-?[0-9]+[[:space:]]*\|' "$PLIK" ;;
        lista)    grep -cE '^- \[[ x]\] ' "$PLIK" ;;
        narracja) grep -cE '^### ' "$PLIK" ;;
        *)        printf '0\n' ;;
    esac
}

# Pierwszy argument to identyfikator ze źródła (może być pusty albo w cudzym
# formacie), drugi to data ze źródła. Numer kolejny bierze się z LICZNIKA, więc
# generowanie MUSI dziać się tutaj: `nowe_id` wołane przez `$(…)` liczyłoby
# w podpowłoce i każda pozycja dostałaby ten sam numer.
zapisz_rekord() {
    local id_zrodlowy="$1" data_zrodlowa="$2" prio="$3" status="$4" zrodlo="$5"
    local dowod="$6" bramka="$7" przeglad="$8" tytul="$9" proza="${10}"
    LICZNIK=$((LICZNIK + 1))
    local id
    if printf '%s' "$id_zrodlowy" | grep -qE '^[A-Z][A-Z0-9]*-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]+$'; then
        id="$id_zrodlowy"
    else
        local d="$DZIS"
        printf '%s' "$data_zrodlowa" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' && d="$data_zrodlowa"
        id="$(printf 'MIG-%s-%02d' "$d" "$LICZNIK")"
    fi
    {
        printf '### %s — %s\n\n' "$id" "$tytul"
        printf 'WPLYW: %s\n' "$(wplyw_dla "$prio")"
        printf 'STATUS: %s\n' "$status"
        printf 'ZRODLO: %s\n' "$zrodlo"
        printf 'DOWOD: %s\n' "$dowod"
        printf 'BRAMKA_ZAMYKAJACA: %s\n' "$bramka"
        printf 'PRZEGLAD: %s\n' "$przeglad"
        printf 'BRIEF: —\n\n'
        [ -n "$proza" ] && printf '%s\n\n' "$proza"
    } > "$REKORDY/$(printf '%04d' "$LICZNIK")-$(sekcja_dla "$prio")"
}

# Dawna etykieta priorytetu (format wejściowy) staje się polem WPLYW pozycji;
# sekcje według priorytetu nie istnieją od wersji 2026.09.07 toolkitu.
wplyw_dla() {
    case "${1:-}" in
        P0) printf 'critical' ;;
        P1) printf 'high' ;;
        P2) printf 'medium' ;;
        Inbox|'') printf '—' ;;
        *) printf '%s' "$1" ;;
    esac
}

# Sekcja docelowa. Pozycja z rozpoznaną etykietą idzie do `Do wykonania`
# w kolejności źródła; wszystko, czego nie rozpoznajemy — łącznie z markerem
# TODO — ląduje w Inboxie.
sekcja_dla() {
    case "${1:-}" in
        P0|P1|P2) printf 'Do-wykonania' ;;
        *) printf 'Inbox' ;;
    esac
}

# Pusta wartość → marker TODO z nazwą brakującego pola.
lub_todo() { [ -n "${1:-}" ] && printf '%s' "$1" || printf 'TODO: %s' "$2"; }

# ── Parser: tabela ──────────────────────────────────────────────────────────
parsuj_tabele() {
    local naglowek kol_id=0 kol_p=0 kol_poz=0 kol_dow=0 kol_bram=0 kol_zr=0 kol_dat=0
    naglowek="$(grep -m1 -nE '^\|.*\|.*\|' "$PLIK" | cut -d: -f2-)"
    local i=0 nazwa
    while IFS= read -r nazwa; do
        i=$((i + 1))
        nazwa="$(printf '%s' "$nazwa" \
            | sed 'y/ŹŻÓŁĄĆĘŃŚźżółąćęńś/ZZOLACENSzzolacens/' \
            | tr '[:upper:]' '[:lower:]' | sed 's/^ *//; s/ *$//')"
        case "$nazwa" in
            id) kol_id=$i ;;
            p|priorytet|sev) kol_p=$i ;;
            pozycja|opis|rzecz) kol_poz=$i ;;
            *dowod*|*gdzie*) kol_dow=$i ;;
            *bramka*|*propozycja*) kol_bram=$i ;;
            *zrodlo*) kol_zr=$i ;;
            data) kol_dat=$i ;;
        esac
    done < <(printf '%s\n' "$naglowek" | sed 's/^|//; s/|$//' | tr '|' '\n')

    local linia
    while IFS= read -r linia; do
        printf '%s' "$linia" | grep -qE '^\|[[:space:]]*[A-Za-z]+-?[0-9]+[[:space:]]*\|' || continue
        local pola=() f
        while IFS= read -r f; do pola+=("$(printf '%s' "$f" | sed 's/^ *//; s/ *$//')"); done \
            < <(printf '%s\n' "$linia" | sed 's/^|//; s/|$//' | tr '|' '\n')
        # Indeks 0 znaczy „kolumny nie ma w nagłówku". Bez tej osłony
        # `${pola[-1]}` sięgnąłby po ostatni element i po cichu podstawił
        # cudzą wartość.
        komorka() { [ "${1:-0}" -gt 0 ] && printf '%s' "${pola[$(($1-1))]-}"; }
        local id prio poz dow bram zr dat
        id="$(komorka "$kol_id")"; prio="$(komorka "$kol_p")"
        poz="$(komorka "$kol_poz")"; dow="$(komorka "$kol_dow")"
        bram="$(komorka "$kol_bram")"; zr="$(komorka "$kol_zr")"
        dat="$(komorka "$kol_dat")"
        local tytul="$(printf '%s' "$poz" | cut -c1-70)"
        printf '%s' "$poz" | grep -q '.\{71\}' && tytul="$tytul…"
        case "$prio" in
            P0|P1|P2|Inbox|'') ;;
            *) prio="TODO: wpływ (w źródle: $prio)" ;;
        esac
        zapisz_rekord "$id" "$dat" "$(lub_todo "$prio" 'wpływ')" \
            otwarte "$(lub_todo "${zr:+$zr ${dat:-}}" 'źródło pozycji')" \
            "$(lub_todo "$dow" 'dowód, że to jest problem')" \
            "$(lub_todo "$bram" 'komenda zamykająca')" '—' "$tytul" "$poz"
    done < "$PLIK"
}

# ── Parser: lista z polami w prozie ─────────────────────────────────────────
parsuj_liste() {
    local prio="" buf="" id="" tytul=""
    domknij() {
        [ -n "$id" ] || return 0
        local bramka=""
        bramka="$(printf '%s' "$buf" | grep -oiE '(propozycja|bramka)[^.]*[.:]' | head -1 | cut -c1-160)"
        zapisz_rekord "$id" '' "$(lub_todo "$prio" 'wpływ')" otwarte \
            "$(zrodlo_z_id "$id")" 'TODO: dowód, że to jest problem' \
            "$(lub_todo "$bramka" 'komenda zamykająca')" '—' "$tytul" "$buf"
        id=""; buf=""; tytul=""
    }
    local linia
    while IFS= read -r linia; do
        case "$linia" in
            '## '*)
                domknij
                prio="$(printf '%s' "$linia" | grep -oE 'P[0-2]' | head -1)"
                [ -n "$prio" ] || prio="Inbox"
                continue ;;
            '- ['*)
                domknij
                id="$(printf '%s' "$linia" | grep -oE '[A-Z][A-Z0-9]*-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]+' | head -1)"
                tytul="$(printf '%s' "$linia" | sed -E 's/^- \[[ x]\] +//; s/\*\*//g; s/^[A-Z0-9-]+ +//' | cut -c1-70)"
                buf="$(printf '%s' "$linia" | sed -E 's/^- \[[ x]\] +//')"
                continue ;;
        esac
        [ -n "$id" ] && buf="$buf
$linia"
    done < "$PLIK"
    domknij
}

# ── Parser: narracja ────────────────────────────────────────────────────────
parsuj_narracje() {
    local tytul="" buf="" w_kolejce=0
    domknij() {
        [ -n "$tytul" ] || return 0
        # Pozycja przekreślona jest domknięta — idzie do historii, nie do backlogu.
        if printf '%s' "$tytul" | grep -q '~~'; then
            printf -- '- %s — przeniesione z backlogu przy migracji %s\n' \
                "$(printf '%s' "$tytul" | tr -d '~')" "$DZIS" >> "$HISTORIA"
        else
            zapisz_rekord '' '' 'TODO: wpływ' otwarte \
                "migracja $DZIS" 'TODO: dowód, że to jest problem' \
                'TODO: komenda zamykająca' '—' \
                "$(printf '%s' "$tytul" | cut -c1-70)" "$buf"
        fi
        tytul=""; buf=""
    }
    local linia
    while IFS= read -r linia; do
        case "$linia" in
            '### '*)
                domknij
                tytul="$(printf '%s' "$linia" | sed 's/^### *//; s/\*\*//g')"
                w_kolejce=0
                printf '%s' "$tytul" | grep -qi 'kolejka' && w_kolejce=1
                continue ;;
            '## '*) domknij; w_kolejce=0; continue ;;
        esac
        if [ "$w_kolejce" -eq 1 ]; then
            printf '%s' "$linia" | grep -qE '^[0-9]+\. ' \
                && printf '%s\n' "$(printf '%s' "$linia" | sed 's/^[0-9]*\. *//' | cut -c1-60)" >> "$KOLEJKA"
        fi
        [ -n "$tytul" ] && buf="$buf
$linia"
    done < "$PLIK"
    domknij
}

# ── Identyfikatory ──────────────────────────────────────────────────────────
zrodlo_z_id() {
    local d; d="$(printf '%s' "$1" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)"
    [ -n "$d" ] && printf 'audyt %s' "$d" || printf 'migracja %s' "$DZIS"
}

# ── Przebieg ────────────────────────────────────────────────────────────────
KSZTALT="$(wykryj_ksztalt)"
if [ "$KSZTALT" = kontrakt ]; then
    printf 'BACKLOG_MIGRATION_SHAPE: kontrakt\n'
    printf 'BACKLOG_MIGRATION_IN: n/a (plik już zgodny)\n'
    printf 'BACKLOG_MIGRATION_OUT: n/a\n'
    printf 'BACKLOG_MIGRATION_TODO: 0\n'
    exit 0
fi
if [ "$KSZTALT" = nieznany ]; then
    printf 'BACKLOG_MIGRATION_SHAPE: nieznany\n' >&2
    printf 'Nie rozpoznaję kształtu pliku — nic nie zapisano.\n' >&2
    exit 1
fi

WEJSCIE="$(policz_wejscie "$KSZTALT")"
case "$KSZTALT" in
    tabela)   parsuj_tabele ;;
    lista)    parsuj_liste ;;
    narracja) parsuj_narracje ;;
esac
WYJSCIE="$(find "$REKORDY" -type f | wc -l | tr -d ' ')"
W_HISTORII="$(grep -c . "$HISTORIA" 2>/dev/null)" || W_HISTORII=0

printf 'BACKLOG_MIGRATION_SHAPE: %s\n' "$KSZTALT"
printf 'BACKLOG_MIGRATION_IN: %s\n' "$WEJSCIE"
printf 'BACKLOG_MIGRATION_OUT: %s\n' "$WYJSCIE"
printf 'BACKLOG_MIGRATION_HISTORY: %s\n' "$W_HISTORII"

# Niezmiennik bezstratności. Pozycja zgubiona przy migracji backlogu to
# zapomniana usterka, więc rozjazd przerywa bez zapisywania czegokolwiek.
if [ "$((WYJSCIE + W_HISTORII))" -ne "$WEJSCIE" ]; then
    printf 'BACKLOG_MIGRATION_TODO: n/a\n'
    printf '\n❌ NIEZMIENNIK BEZSTRATNOŚCI: wykryto %s pozycji, zapisano %s (+%s do historii). Nic nie zapisano.\n' \
        "$WEJSCIE" "$WYJSCIE" "$W_HISTORII" >&2
    exit 1
fi

# ── Złożenie pliku wynikowego ───────────────────────────────────────────────
WYNIK="$(mktemp)"
{
    printf '# Backlog — %s\n\n' "$(basename "$(cd "$(dirname "$PLIK")/../.." && pwd)")"
    printf 'Zmigrowany %s ze kształtu `%s`. Kontrakt pozycji: `backlog-contract.md`.\n' "$DZIS" "$KSZTALT"
    printf 'Sprawdzenie: `bash <toolkit>/templates/backlog-lint.sh .`\n\n'
    for sekcja in Do-wykonania Inbox; do
        case "$sekcja" in
            Do-wykonania)
                printf '## Do wykonania (kolejność = decyzja właściciela)\n\n'
                if [ -s "$KOLEJKA" ]; then
                    printf '<!-- kolejność ze źródła, do potwierdzenia przez /plan-naprawy:\n'
                    sed 's/^/  /' "$KOLEJKA"
                    printf '-->\n\n'
                fi ;;
            Inbox) printf '## Inbox\n\n' ;;
        esac
        if compgen -G "$REKORDY/*-$sekcja" > /dev/null; then
            cat "$REKORDY"/*-"$sekcja"
        else
            printf '_(pusto)_\n\n'
        fi
    done
    printf '## Poza kolejką (świadomie, z datą przeglądu)\n\n_(pusto)_\n\n'
    printf '## Czeka na decyzję właściciela\n\n_(pusto)_\n\n'
    printf '## Zablokowane (infra / zależności)\n\n_(pusto)_\n'
} > "$WYNIK"

TODO_N="$(grep -c 'TODO:' "$WYNIK" || true)"
printf 'BACKLOG_MIGRATION_TODO: %s\n' "$TODO_N"

if [ "$APPLY" -eq 1 ]; then
    KAT_HIST="$(dirname "$PLIK")/history"
    mkdir -p "$KAT_HIST"
    cp "$PLIK" "$KAT_HIST/backlog-przed-migracja-$DZIS.md"
    [ -s "$HISTORIA" ] && cat "$HISTORIA" >> "$KAT_HIST/completed-work.md"
    cp "$WYNIK" "$PLIK"
    printf '\n✅ Podmieniono %s. Oryginał: %s\n' "$PLIK" "$KAT_HIST/backlog-przed-migracja-$DZIS.md"
else
    cp "$WYNIK" "$PLIK.migrated"
    printf '\nZapisano %s (bez podmiany). Przejrzyj, potem uruchom z --apply.\n' "$PLIK.migrated"
fi
rm -f "$WYNIK"
exit 0
