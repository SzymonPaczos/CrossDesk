#!/usr/bin/env bash
# Bramka nad bramkami — `conventions/rules-as-gates.md` §10, §11 i §13.
#
# Sześć awarii z jednej doby okazało się jednym błędem powtórzonym sześć razy:
# parser liczby testów meldujący „collected: 0 tests" z kodem wyjścia zero;
# ruff na zepsutej konfiguracji meldujący zero naruszeń, bo w ogóle nie
# wystartował; bramka aktualności licząca 98 przeterminowanych pakietów w repo
# bez zależności; `unguarded_routes()` zwracające pustą listę przy jedenastu
# trasach bez strażnika; bramka sesji meldująca sukces po obejrzeniu 9 tras
# z 20; bramka typów zielona lokalnie i 252 błędy w formie wołanej przez CI.
#
# Żadna z nich nie wynikła ze zbyt łagodnej reguły. Wszystkie wynikły z tego,
# że **bramka nie potrafiła zawieść, bo nie zmierzyła przedmiotu.**
#
# Ten skrypt sprawdza pozostałe szablony i kończy się kodem 1, gdy któraś:
#
#   1. deklaruje mianownik ZERO, kończąc się powodzeniem — zero obejrzanych
#      rzeczy przy zielonym wyniku to zawsze porażka, bo znaczy, że narzędzie
#      nie wystartowało albo szukało nie tam;
#   2. rozjeżdża się z DRUGIM, niezależnym źródłem tej samej liczby — liczba
#      prawdziwa względem własnego przejścia i fałszywa względem rzeczywistości
#      jest bezwartościowa, nie „częściowa";
#   3. nie wypisuje mianownika w postaci maszynowo czytelnej — bez niego dwa
#      pierwsze warunki są niesprawdzalne;
#   4. nie ma przypisanego materiału ZNANEGO-ZŁEGO albo na nim nie czerwieni;
#   5. widzi MNIEJ rzeczy niż zapisano w `fixtures/mianowniki.baseline` —
#      spadek zakresu wymaga jawnego, zacommitowanego zatwierdzenia;
#   6. leży w `templates/`, a nie ma wiersza w `fixtures/rejestr-bramek.tsv`.
#
# Mianownik samego selfchecku: liczba wierszy rejestru. Drugie źródło: listing
# `templates/*.sh`. Rozjazd między nimi to warunek 6 — nowy szablon nie wejdzie
# do repozytorium bez fixture'u i bez deklaracji pochodzenia obu liczb.
#
# Użycie:
#   gate-selfcheck.sh [--format text|signals] [--tylko NAZWA]
#   gate-selfcheck.sh --samosprawdzenie      # trzy warunki na sztucznych bramkach
#   gate-selfcheck.sh --zapisz-mianowniki    # odśwież baseline zakresu
#
# Kody wyjścia: 0 = wszystkie bramki umieją zawieść i wiedzą, co mierzą,
#               1 = któraś nie umie, 2 = błąd użycia lub braki w repozytorium.
set -uo pipefail

# Skrypt bywa uruchamiany z hooka gita (pre-commit -> validate-toolkit.sh ->
# gates.sh). Git eksportuje wtedy GIT_DIR / GIT_WORK_TREE / GIT_INDEX_FILE, a
# każde `git init`, `git add` i `git commit` w katalogu tymczasowym trafia
# przez te zmienne do REPOZYTORIUM WOŁAJĄCEGO. Zmierzone 2026-09-08: komity
# „material fixture" i „feat: nowa galaz" wylądowały na gałęzi integracyjnej
# toolkitu, a HEAD przeskoczył na gałąź z fixture'u. Repozytoria tymczasowe
# muszą widzieć wyłącznie własny katalog.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR

FORMAT=text
TYLKO=""
TRYB=sprawdz
KORZEN_ARG=""

while [ $# -gt 0 ]; do
    case "$1" in
        --format)            FORMAT="${2:-}"; shift 2 ;;
        --tylko)             TYLKO="${2:-}"; shift 2 ;;
        --samosprawdzenie)   TRYB=samosprawdzenie; shift ;;
        --zapisz-mianowniki) TRYB=zapisz; shift ;;
        -h|--help)           sed -n '2,42p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  KORZEN_ARG="$1"; shift ;;
    esac
done

# Ścieżka wskazuje KORZEŃ z katalogami `templates/` i `fixtures/` — domyślnie
# ten, obok którego skrypt leży. Argument jest przyjmowany, bo rejestr reguł
# woła każdą bramkę jednakowo, ścieżką projektu; bramka, którą trzeba wołać
# inaczej niż pozostałe, jest drugą definicją tego, jak się ją uruchamia.
TU="$(cd "$(dirname "$0")" && pwd)"
KORZEN="$(cd "${KORZEN_ARG:-$TU/..}" 2>/dev/null && pwd)" || {
    printf 'nie ma katalogu: %s\n' "${KORZEN_ARG:-$TU/..}" >&2; exit 2; }
[ -d "$KORZEN/templates" ] && TU="$KORZEN/templates"
FIXTURES="$KORZEN/fixtures"
REJESTR="$FIXTURES/rejestr-bramek.tsv"
BASELINE="$FIXTURES/mianowniki.baseline"

if [ ! -f "$REJESTR" ]; then
    printf 'SELFCHECK_GATES_TOTAL: n/a — %s nie ma rejestru bramek\n' "$KORZEN"
    printf 'W tym repozytorium nie da się sprawdzić, czy bramki umieją zawieść:\n' >&2
    printf 'brak %s. Zainstaluj warstwę bramek z toolkitu albo napisz własny rejestr.\n' "$REJESTR" >&2
    exit 2
fi
[ -d "$FIXTURES/known-good" ] || { printf 'brak %s\n' "$FIXTURES/known-good" >&2; exit 2; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# ── Narzędzia wspólne ───────────────────────────────────────────────────────

# materializuj <katalog-fixture> <cel> — kopia materiału jako świeże repo git.
# Fixture leży w repozytorium jako zwykłe pliki (repo w repo nie działa),
# więc repozytorium powstaje dopiero tutaj i tylko na czas sprawdzenia.
materializuj() {
    local zrodlo="$1" cel="$2"
    mkdir -p "$cel"
    cp -a "$zrodlo/." "$cel/" 2>/dev/null || return 1
    (
        cd "$cel" || exit 1
        git init -q --initial-branch=main .
        git config user.email bramka@test.invalid
        git config user.name  gate-selfcheck
        git config commit.gpgsign false
        git config core.hooksPath /dev/null
        if [ -f PRZED.sh ]; then bash PRZED.sh >/dev/null 2>&1; rm -f PRZED.sh; fi
        git add -A
        git commit -qm "material fixture"
    ) >/dev/null 2>&1
}

podstaw() { printf '%s' "$1" | sed "s|{FIXTURE}|$2|g; s|{TOOLKIT}|$KORZEN|g"; }

# wartosc_sygnalu <plik-wyjścia> <NAZWA> — pierwsza liczba po „NAZWA: ".
# Puste, gdy sygnału nie ma. Dosłowne „n/a", gdy bramka zgłosiła brak pomiaru —
# to jest poprawna odpowiedź i różni się od zera.
wartosc_sygnalu() {
    local w
    w="$(grep -m1 -E "^$2: " "$1" 2>/dev/null | sed "s/^$2: //")"
    [ -n "$w" ] || { printf ''; return 1; }
    case "$w" in
        n/a*) printf 'n/a'; return 0 ;;
    esac
    printf '%s' "$w" | grep -oE '^[0-9]+' | head -1
}

# ── Warunki. Osobne funkcje, żeby dało się je sprawdzić pojedynczo ──────────
# Każda zwraca 0, gdy bramka warunek SPEŁNIA, i 1, gdy go łamie.

warunek_mianownik_istnieje() { [ -n "${1:-}" ]; }

warunek_zero_na_zielonym() {          # <wartość> <kod-wyjścia>
    local w="${1:-}" kod="${2:-1}"
    [ "$w" = "n/a" ] && return 0
    [ "$kod" -eq 0 ] && [ "${w:-0}" -eq 0 ] && return 1
    return 0
}

warunek_bez_rozjazdu() {              # <wartość-bramki> <wartość-kontroli>
    local a="${1:-}" b="${2:-}"
    [ "$a" = "n/a" ] && return 0
    [ -n "$b" ] || return 0
    [ "$b" = "n/a" ] && return 0
    [ "$a" = "$b" ]
}

warunek_bez_spadku_zakresu() {        # <wartość> <baseline>
    local w="${1:-}" b="${2:-}"
    [ -n "$b" ] || return 1
    [ "$w" = "n/a" ] && return 0
    [ "${w:-0}" -ge "$b" ]
}

# ── Tryb: samosprawdzenie ───────────────────────────────────────────────────
# Trzy sztuczne bramki w repozytorium, po jednej na warunek. Każdy warunek
# sprawdzany w OBIE strony: na materiale, który ma go złamać, i na wartości,
# która ma go spełnić. Warunek zielony po obu stronach byłby zepsuty, nie
# ciekawy (`rules-as-gates.md` §13), więc obie strony są tu wypisane.
if [ "$TRYB" = samosprawdzenie ]; then
    SZTUCZNE="$FIXTURES/known-bad/gate-selfcheck"
    [ -d "$SZTUCZNE/bramki" ] || { printf 'brak sztucznych bramek w %s\n' "$SZTUCZNE" >&2; exit 2; }
    materializuj "$SZTUCZNE" "$TMP/sztuczne" || { printf 'nie udało się zbudować fixture\n' >&2; exit 2; }
    R="$TMP/sztuczne"
    KONTROLA="$(cd "$R" && find . -path ./.git -prune -o -type f -name '*.py' -print | grep -c .)"

    ZLE=0; LINIE="$TMP/samo"
    : > "$LINIE"
    zapisz() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$LINIE"; }

    # Warunek 1 — mianownik zero przy kodzie wyjścia 0.
    bash "$R/bramki/zero-mianownika.sh" "$R" > "$TMP/o1" 2>&1; K1=$?
    W1="$(wartosc_sygnalu "$TMP/o1" FAKE_TOTAL)"
    if warunek_zero_na_zielonym "$W1" "$K1"; then
        zapisz "warunek 1 (zero na zielonym)" "NIE ZLAPAL" "FAKE_TOTAL=$W1 kod=$K1 — a miał być odrzucony"; ZLE=1
    else
        zapisz "warunek 1 (zero na zielonym)" "ZLAPAL" "FAKE_TOTAL=$W1 przy kodzie wyjścia $K1"
    fi
    if warunek_zero_na_zielonym "$KONTROLA" 0; then
        zapisz "warunek 1 — strona zielona" "PRZEPUSCIL" "mianownik $KONTROLA przy kodzie 0 jest poprawny"
    else
        zapisz "warunek 1 — strona zielona" "FALSZYWY ALARM" "odrzucił poprawny mianownik $KONTROLA"; ZLE=1
    fi

    # Warunek 2 — rozjazd z drugim źródłem.
    bash "$R/bramki/rozjazd.sh" "$R" > "$TMP/o2" 2>&1; K2=$?
    W2="$(wartosc_sygnalu "$TMP/o2" FAKE_TOTAL)"
    if warunek_bez_rozjazdu "$W2" "$KONTROLA"; then
        zapisz "warunek 2 (rozjazd)" "NIE ZLAPAL" "bramka $W2, kontrola $KONTROLA — a miał być odrzucony"; ZLE=1
    else
        zapisz "warunek 2 (rozjazd)" "ZLAPAL" "bramka $W2, kontrola $KONTROLA, różnica $((KONTROLA - W2))"
    fi
    if warunek_bez_rozjazdu "$KONTROLA" "$KONTROLA"; then
        zapisz "warunek 2 — strona zielona" "PRZEPUSCIL" "$KONTROLA = $KONTROLA, brak rozjazdu"
    else
        zapisz "warunek 2 — strona zielona" "FALSZYWY ALARM" "odrzucił zgodne liczby"; ZLE=1
    fi

    # Warunek 3 — brak mianownika w ogóle.
    bash "$R/bramki/bez-mianownika.sh" "$R" > "$TMP/o3" 2>&1; K3=$?
    W3="$(wartosc_sygnalu "$TMP/o3" FAKE_TOTAL || true)"
    if warunek_mianownik_istnieje "$W3"; then
        zapisz "warunek 3 (brak mianownika)" "NIE ZLAPAL" "znalazł wartość '$W3' — a miał nie znaleźć nic"; ZLE=1
    else
        zapisz "warunek 3 (brak mianownika)" "ZLAPAL" "w wyjściu nie ma linii FAKE_TOTAL (kod wyjścia $K3)"
    fi
    if warunek_mianownik_istnieje "$KONTROLA"; then
        zapisz "warunek 3 — strona zielona" "PRZEPUSCIL" "mianownik $KONTROLA jest obecny"
    else
        zapisz "warunek 3 — strona zielona" "FALSZYWY ALARM" "nie zobaczył obecnego mianownika"; ZLE=1
    fi

    if [ "$FORMAT" = text ]; then
        printf 'Samosprawdzenie na sztucznych bramkach z %s\n\n' "fixtures/known-bad/gate-selfcheck/bramki"
        awk -F'\t' '{printf "  %-34s %-16s %s\n", $1, $2, $3}' "$LINIE"
        printf '\n'
    fi
    printf 'SELFCHECK_SELFTEST_CASES: %s\n' "$(grep -c . "$LINIE")"
    printf 'SELFCHECK_SELFTEST_FAILED: %s\n' "$(grep -cE 'NIE ZLAPAL|FALSZYWY ALARM' "$LINIE" || true)"
    [ "$ZLE" -eq 0 ] || {
        printf '\n❌ Selfcheck nie łapie warunku, który miał łapać. Bramka nad bramkami,\n' >&2
        printf '   która sama nie działa, jest tym samym problemem o poziom wyżej.\n' >&2
        exit 1
    }
    exit 0
fi

# ── Tryb: sprawdzenie wszystkich bramek ────────────────────────────────────
WYNIKI="$TMP/wyniki"; : > "$WYNIKI"
MIANOWNIKI="$TMP/mianowniki"; : > "$MIANOWNIKI"

BRAK_MIANOWNIKA=0; ZERO_NA_ZIELONYM=0; ROZJAZD=0
BRAK_NEGATYWU=0; NEGATYW_ZIELONY=0; BEZ_KONTROLI=0; SPADEK_ZAKRESU=0; OK=0; WSZYSTKICH=0

baseline_dla() { awk -F'\t' -v n="$1" '$1==n {print $2}' "$BASELINE" 2>/dev/null | head -1; }

while IFS=$'\t' read -r bramka rodzaj sygnal dz poch_b poch_k niezal env args; do
    case "$bramka" in ''|'#'*) continue ;; esac
    # `-` znaczy „pusto". TAB jest białym znakiem IFS, więc `read` sklei dwa
    # sąsiadujące tabulatory i pusta kolumna zniknie, przesuwając następne.
    [ "$env" = "-" ] && env=""
    [ -z "$TYLKO" ] || [ "$TYLKO" = "$bramka" ] || continue
    WSZYSTKICH=$((WSZYSTKICH + 1))
    powody=""
    dodaj() { powody="$powody; $1"; }

    if [ ! -f "$TU/$bramka" ]; then
        dodaj "szablonu nie ma w templates/"
        printf '%s\tBRAK\t\t\t%s\n' "$bramka" "${powody#; }" >> "$WYNIKI"
        BRAK_MIANOWNIKA=$((BRAK_MIANOWNIKA + 1))
        continue
    fi

    # ── strona zielona: materiał, na którym bramka ma przejść i coś policzyć
    dobry="$FIXTURES/known-good/${bramka%.sh}"
    kod_g=""; wartosc=""
    if [ -d "$dobry" ]; then
        materializuj "$dobry" "$TMP/g-${bramka%.sh}"
        R="$TMP/g-${bramka%.sh}"
        a="$(podstaw "$args" "$R")"; e="$(podstaw "$env" "$R")"
        # shellcheck disable=SC2086
        if [ -n "$e" ]; then env $e bash "$TU/$bramka" $a > "$TMP/out-g" 2>&1; kod_g=$?
        else bash "$TU/$bramka" $a > "$TMP/out-g" 2>&1; kod_g=$?; fi
        wartosc="$(wartosc_sygnalu "$TMP/out-g" "$sygnal" || true)"
    else
        dodaj "brak fixtures/known-good/${bramka%.sh}"
    fi

    # ── warunek 3: mianownik w postaci maszynowo czytelnej
    if ! warunek_mianownik_istnieje "$wartosc"; then
        dodaj "nie wypisał '$sygnal: <n>'"
        BRAK_MIANOWNIKA=$((BRAK_MIANOWNIKA + 1))
    else
        printf '%s\t%s\n' "$bramka" "$wartosc" >> "$MIANOWNIKI"

        # ── warunek 1: zero obejrzanych rzeczy przy zielonym wyniku
        if ! warunek_zero_na_zielonym "$wartosc" "${kod_g:-1}"; then
            dodaj "mianownik 0 przy kodzie wyjścia 0 — narzędzie nie wystartowało albo szukało nie tam"
            ZERO_NA_ZIELONYM=$((ZERO_NA_ZIELONYM + 1))
        fi

        # ── warunek 2: rozjazd z drugim, niezależnym źródłem
        kontrola=""
        case "$niezal" in
            nie*) BEZ_KONTROLI=$((BEZ_KONTROLI + 1)) ;;
            *)
                if [ -n "$dz" ] && [ -d "$dobry" ]; then
                    kontrola="$(cd "$TMP/g-${bramka%.sh}" && bash -c "$(podstaw "$dz" "$TMP/g-${bramka%.sh}")" 2>/dev/null | tr -cd '0-9')"
                fi
                if [ -z "$kontrola" ]; then
                    BEZ_KONTROLI=$((BEZ_KONTROLI + 1))
                    dodaj "mianownik bez niezależnej kontroli, powód: drugie źródło nic nie zwróciło"
                elif ! warunek_bez_rozjazdu "$wartosc" "$kontrola"; then
                    dodaj "rozjazd: bramka $wartosc, kontrola $kontrola, różnica $((kontrola - wartosc))"
                    ROZJAZD=$((ROZJAZD + 1))
                fi ;;
        esac

        # ── warunek 5: zapadka na zakres
        b="$(baseline_dla "$bramka")"
        if [ "$TRYB" != zapisz ]; then
            if [ -z "$b" ]; then
                dodaj "brak wiersza w fixtures/mianowniki.baseline — zakres nie jest zatwierdzony"
                SPADEK_ZAKRESU=$((SPADEK_ZAKRESU + 1))
            elif ! warunek_bez_spadku_zakresu "$wartosc" "$b"; then
                dodaj "spadek zakresu: widzi $wartosc, baseline mówi $b — spadek wymaga zacommitowanego zatwierdzenia"
                SPADEK_ZAKRESU=$((SPADEK_ZAKRESU + 1))
            fi
        fi
    fi

    # ── warunek 4: przypadek negatywny
    if [ "$rodzaj" = inwentarz ]; then
        # Inwentarz świadomie zawsze kończy się zerem. Wymagamy, żeby to było
        # napisane w nagłówku pliku — inaczej „zawsze zielony" jest nie do
        # odróżnienia od bramki, która przestała działać.
        grep -q 'Kod wyjścia: 0 zawsze' "$TU/$bramka" \
            || { dodaj "inwentarz bez zdania 'Kod wyjścia: 0 zawsze' w nagłówku"; BRAK_NEGATYWU=$((BRAK_NEGATYWU + 1)); }
    else
        zly="$FIXTURES/known-bad/${bramka%.sh}"
        if [ ! -d "$zly" ]; then
            dodaj "brak materiału znanego-złego w fixtures/known-bad/${bramka%.sh}"
            BRAK_NEGATYWU=$((BRAK_NEGATYWU + 1))
        else
            materializuj "$zly" "$TMP/b-${bramka%.sh}"
            R="$TMP/b-${bramka%.sh}"
            a="$(podstaw "$args" "$R")"; e="$(podstaw "$env" "$R")"
            [ "$bramka" = dependency-currency.sh ] && e="$e STRICT_EOL=1"
            # shellcheck disable=SC2086
            if [ -n "$e" ]; then env $e bash "$TU/$bramka" $a > "$TMP/out-b" 2>&1; kod_b=$?
            else bash "$TU/$bramka" $a > "$TMP/out-b" 2>&1; kod_b=$?; fi
            if [ "$kod_b" -eq 0 ]; then
                dodaj "na materiale znanym-złym wyszła na zielono (kod 0) — przestała umieć zawieść"
                NEGATYW_ZIELONY=$((NEGATYW_ZIELONY + 1))
            elif [ "$kod_b" -ne 1 ]; then
                dodaj "na materiale znanym-złym kod $kod_b zamiast 1 (2 = błąd użycia, nie werdykt)"
                NEGATYW_ZIELONY=$((NEGATYW_ZIELONY + 1))
            fi
        fi
    fi

    if [ -z "$powody" ]; then
        OK=$((OK + 1))
        printf '%s\tOK\t%s\t%s\t%s\n' "$bramka" "$sygnal" "$wartosc" "mianownik potwierdzony niezależnie" >> "$WYNIKI"
    else
        printf '%s\tZLE\t%s\t%s\t%s\n' "$bramka" "$sygnal" "${wartosc:-—}" "${powody#; }" >> "$WYNIKI"
    fi
done < "$REJESTR"

# ── warunek 6: szablon bez wiersza w rejestrze ──────────────────────────────
# Mianownik samego selfchecku, sprawdzony drugim źródłem: rejestr kontra
# listing katalogu. To jest ta linia, przez którą nowy szablon nie wejdzie do
# repozytorium bez fixture'u i bez zadeklarowanego pochodzenia obu liczb.
W_REJESTRZE="$(awk -F'\t' '!/^#/ && NF {print $1}' "$REJESTR" | sort -u)"
W_KATALOGU="$(cd "$TU" && ls -1 ./*.sh 2>/dev/null | sed 's|^\./||' | grep -v '^gate-selfcheck\.sh$' | sort -u)"
NIEZAREJESTROWANE="$(comm -13 <(printf '%s\n' "$W_REJESTRZE") <(printf '%s\n' "$W_KATALOGU"))"
N_NIEZAREJ="$(printf '%s' "$NIEZAREJESTROWANE" | grep -c . || true)"
N_REJESTR="$(printf '%s' "$W_REJESTRZE" | grep -c . || true)"
N_KATALOG="$(printf '%s' "$W_KATALOGU" | grep -c . || true)"

if [ "$TRYB" = zapisz ]; then
    # Nagłówek pliku przenosi się na nową wersję. Bez tego każde odświeżenie
    # baseline'u kasowało zdanie, które tłumaczy, dlaczego spadek tej liczby
    # jest awarią — i po kilku odświeżeniach zostawał sam słupek liczb, którego
    # nikt nie umie zinterpretować przy przeglądzie.
    if [ -f "$BASELINE" ]; then
        grep -E '^[[:space:]]*(#|$)' "$BASELINE" > "$BASELINE.nowy"
    else
        : > "$BASELINE.nowy"
    fi
    sort "$MIANOWNIKI" >> "$BASELINE.nowy" && mv "$BASELINE.nowy" "$BASELINE"
    printf 'Zapisano %s wierszy do %s\n' "$(grep -c . "$BASELINE")" "$BASELINE"
    exit 0
fi

if [ "$FORMAT" = text ]; then
    printf 'Bramka nad bramkami — %s szablonów z %s\n\n' "$WSZYSTKICH" "fixtures/rejestr-bramek.tsv"
    awk -F'\t' '$2=="ZLE" || $2=="BRAK"' "$WYNIKI" > "$TMP/zle" || true
    if [ -s "$TMP/zle" ]; then
        while IFS=$'\t' read -r b st sy wa po; do
            printf '  ❌ %-26s %s\n' "$b" "$po"
        done < "$TMP/zle"
        printf '\n'
    fi
    awk -F'\t' '$2=="OK"' "$WYNIKI" | while IFS=$'\t' read -r b st sy wa po; do
        printf '  ✅ %-26s %s: %s\n' "$b" "$sy" "$wa"
    done
    printf '\n'
    if [ "$N_NIEZAREJ" -gt 0 ]; then
        printf 'Szablony bez wiersza w rejestrze:\n'
        printf '%s\n' "$NIEZAREJESTROWANE" | sed 's/^/  ❌ /'
        printf '\n'
    fi
fi

printf 'SELFCHECK_GATES_TOTAL: %s\n' "$WSZYSTKICH"
printf 'SELFCHECK_GATES_OK: %s\n' "$OK"
printf 'SELFCHECK_TEMPLATES_ON_DISK: %s\n' "$N_KATALOG"
printf 'SELFCHECK_UNREGISTERED: %s\n' "$N_NIEZAREJ"
printf 'SELFCHECK_MISSING_DENOMINATOR: %s\n' "$BRAK_MIANOWNIKA"
printf 'SELFCHECK_ZERO_ON_GREEN: %s\n' "$ZERO_NA_ZIELONYM"
printf 'SELFCHECK_DENOMINATOR_MISMATCH: %s\n' "$ROZJAZD"
printf 'SELFCHECK_MISSING_NEGATIVE_CASE: %s\n' "$BRAK_NEGATYWU"
printf 'SELFCHECK_NEGATIVE_CASE_GREEN: %s\n' "$NEGATYW_ZIELONY"
printf 'SELFCHECK_NO_SECOND_SOURCE: %s\n' "$BEZ_KONTROLI"
printf 'SELFCHECK_SCOPE_DROPS: %s\n' "$SPADEK_ZAKRESU"

SUMA=$(( BRAK_MIANOWNIKA + ZERO_NA_ZIELONYM + ROZJAZD + BRAK_NEGATYWU + NEGATYW_ZIELONY + SPADEK_ZAKRESU + N_NIEZAREJ ))
if [ "$SUMA" -gt 0 ]; then
    printf '\n❌ %s bramek nie potrafi zawieść albo nie wie, co zmierzyło. Bramka bez\n' "$SUMA" >&2
    printf '   mianownika i bez materiału znanego-złego jest atrapą: przechodzi tak samo\n' >&2
    printf '   wtedy, gdy repozytorium jest czyste, jak wtedy, gdy narzędzie nie wystartowało.\n' >&2
    printf '   Czym to sprawdzić: `bash templates/gate-selfcheck.sh --format text`\n' >&2
    exit 1
fi
exit 0
