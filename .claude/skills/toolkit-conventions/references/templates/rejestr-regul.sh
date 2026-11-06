#!/usr/bin/env bash
# Rejestr reguł — stan KAŻDEJ konwencji toolkitu w tym repozytorium.
#
# Raport z audytu pokazywał dotąd wyłącznie to, co audyt znalazł. Reguła,
# której nikt nie sprawdził, i reguła, która wyszła czysto, wyglądały tak samo:
# nie było ich widać. Przy trzech dużych projektach, gdzie w każdym brakuje
# czegoś innego, to jest różnica między „sprawdzone" a „nie wiem".
#
# Ten rejestr wypisuje wszystkie konwencje z toolkitu i przy każdej mówi:
#   SPRAWDZONA   — jest bramka, uruchomiła się, oto wynik
#   CZYTANA      — nie ma bramki, rozstrzyga ją czytanie w audycie
#   NIE DOTYCZY  — technologii, o której mówi reguła, nie ma w tym repo
#
# Użycie: rejestr-regul.sh [--format text|signals] [--bez-bramek] [ŚCIEŻKA]
# Kod wyjścia: 0 zawsze — to rejestr, nie bramka. Bramki mają własne kody.
set -uo pipefail

FORMAT=text
BEZ_BRAMEK=0
POKRYCIE=0
CEL=.
while [ $# -gt 0 ]; do
    case "$1" in
        --format) FORMAT="${2:-}"; shift 2 ;;
        --bez-bramek) BEZ_BRAMEK=1; shift ;;
        --sprawdz-pokrycie) POKRYCIE=1; BEZ_BRAMEK=1; shift ;;
        -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *) CEL="$1"; shift ;;
    esac
done

TU="$(cd "$(dirname "$0")" && pwd)"
# W repo toolkitu: templates/../conventions. Po instalacji skilla:
# references/templates/../conventions. Ta sama ścieżka działa w obu miejscach.
KONWENCJE="$TU/../conventions"
[ -d "$KONWENCJE" ] || { printf 'nie widzę konwencji w %s\n' "$KONWENCJE" >&2; exit 2; }

cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }
PROJEKT="$(pwd)"

# nazwa-konwencji | bramka lub — | koszyk | powód | sonda stosowalności
#
# Sonda stoi NA KOŃCU, bo `tresc:<regex>` sama zawiera pionowe kreski —
# `read -r … sonda` bierze wtedy całą resztę linii i nic się nie gubi.
#
# Sonda: `zawsze`, `pliki:<glob…>` (dotyczy, gdy git zna taki plik) albo
# `tresc:<regex>:<glob…>` (dotyczy, gdy taki wzorzec jest w treści).
# Reguła bez sondy dotyczy każdego repozytorium — i tak ma być, bo domyślne
# „nie dotyczy" byłoby cichym zwalnianiem się z reguł.
#
# Koszyk — jedna z trzech kategorii, obowiązkowa dla każdej konwencji:
#   bramka        rozstrzyga skrypt kończący się kodem 1
#   do-zrobienia  da się sprawdzić mechanicznie, ale nie tanio — powód obok
#   czytanie      rozstrzyga czytanie i tak zostaje; plik konwencji mówi to wprost
#
# Suma trzech koszyków MUSI równać się liczbie plików w `conventions/`.
# Pilnuje tego tryb `--sprawdz-pokrycie`, wpięty do CI. Dzięki temu nowa
# konwencja nie wejdzie do korpusu bez przypisania — a to jest dokładnie ta
# droga, którą korpus urósł do trzydziestu jeden reguł bez pokrycia.
MAPA='
api-contract-design|—|do-zrobienia|zestawienie tras z plikiem kontraktu wymaga parsera OpenAPI; grep dawalby falszywe alarmy na kazdym aliasie|tresc:openapi|fastapi|@app\.(get|post)|router\.:*.py:*.ts
architecture-change|—|czytanie|klasyfikacja ZOSTAJE/ADAPTUJ/PORT/ODRZUC i kolejnosc decyzji odraczalnych to osad, nie wzorzec|zawsze
architecture-principles|—|czytanie|skala MUSI/POWINIEN i test decyzji projektowej rozstrzygaja sie w rozmowie, nie greperm|zawsze
backend-layers|layer-direction.sh|bramka||pliki:*.py:*.go:*.rs
background-work|claim-release.sh|bramka||pliki:*.py
agent-communication|—|czytanie|przeglad ocenia jezyk, zgodnosc twierdzen z dowodami i jawnosc zakresu; koszyk nie potwierdza wykonania oceny|zawsze
backlog-contract|backlog-lint.sh|bramka||zawsze
backlog-premise-audit|—|czytanie|obalanie przeslanek pozycji backlogu to lektura z narzucona kolejnoscia, nie wzorzec; regex po prozie dawal 79 trafien na 707, w wiekszosci falszywych|zawsze
change-provenance|—|do-zrobienia|tani kawalek sprawdza .githooks/commit-msg w trybie WARN; sprawdzenie Task-Ref wobec briefow wymaga historii i katalogu briefow|zawsze
ci-cd|—|do-zrobienia|pinowanie akcji do SHA i minimalne permissions wymagaja rozbioru YAML-a; grep myli komentarz z wartoscia|zawsze
ci-pipeline-architecture|ci-effective-work.sh|bramka||pliki:.github/workflows/*:.gitlab-ci.yml
code-structure|code-structure.sh|bramka||zawsze
contract-canon|contract-enums.sh|bramka||zawsze
context-budget|—|do-zrobienia|budzet bajtow liczy wc -c, ale zbior plikow ladowanych zawsze zalezy od narzedzia (importy @, rules bez paths:, AGENTS.md dla Codexa); do czasu szablonu bramki mierzy audyt tygodniowy|zawsze
data-modeling|—|do-zrobienia|warunek na stanie poprzednim i zakres wlasciciela w repozytorium wymagaja AST; heurystyka greperm daje za duzo falszywych alarmow|tresc:sqlalchemy|drizzle|prisma|CREATE TABLE:*.py:*.ts:*.sql
document-claim-drift|—|czytanie|rejestr faktow przeliczalnych i lista wartosci wycofanych to dane projektu, nie toolkitu; checker jest per projekt, a status decyzji rozstrzyga czytanie|zawsze
dependency-currency|dependency-currency.sh|bramka||zawsze
design-system-foundations|—|do-zrobienia|kontrast wymaga rozwiazania zmiennych CSS i renderu; sam grep po literalach koloru zlapalby ulamek reguly|pliki:*.tsx:*.astro:*.vue:*.css
instruction-style|—|czytanie|review ocenia cel, zakres i czytelnosc instrukcji; scripts/register-lint.sh podaje pomocnicze metryki bez blokady|zawsze
forms-and-validation|—|do-zrobienia|powiazanie schematu z komponentem i etykiety pol wymagaja AST JSX|tresc:<form|onSubmit|useForm:*.tsx:*.astro:*.vue
frontend-architecture|—|do-zrobienia|kierunek app-features-shared da sie sprawdzic, ale wymaga deklaracji warstw per projekt; bez niej bramka zgaduje|pliki:*.tsx:*.astro:*.vue:*.svelte
issue-reporting|—|do-zrobienia|sekcje zgloszenia i para obraz przed/po zyja w trackerze, nie w repozytorium; wymaga jego API|zawsze
module-paths|import-depth.sh|bramka||pliki:*.ts:*.tsx:*.js:*.jsx
multi-agent-delivery|—|czytanie|kiedy uruchomic zespol i siedem soczewek red-teamu to osad; rozlacznosc zakresow sprawdza scripts/check-active-overlap.sh, ale reszta reguly nie|zawsze
local-gate-orchestration|—|do-zrobienia|zamki, sloty i nadzor procesow to pomocniki w templates/local-gates/ z testem offline scripts/test-local-gate-templates.sh; zgodnosc hookow projektu z protokolem sprawdza review i audyt|pliki:.githooks/pre-push
naming-conventions|identifier-language.sh|bramka||zawsze
negative-verification|negative-verification.sh|bramka||zawsze
production-operations|—|czytanie|rytual PROD-DECLARE wymaga jednoznacznego polecenia wlasciciela w biezacej rozmowie - tego nie zastapi zaden skrypt|zawsze
progressive-delivery|—|do-zrobienia|manifest wydania i metryki DORA sa sprawdzalne, ale mieszkaja w systemie wydan, a nie w repozytorium|zawsze
project-state-layout|—|do-zrobienia|uklad .claude/ da sie sprawdzic greperm; brakuje ustalenia, ktore projekty juz zmigrowaly, zeby bramka nie stanela na czerwonym w dniu wprowadzenia|zawsze
pull-request-review|—|czytanie|czy twierdzenie w opisie ma pokrycie w tescie to lektura diffu i opisu naraz; mechanicznie da sie sprawdzic rebase i zbior FAILED, ale nie te regule|zawsze
quality-gates-and-dod|ruff-ratchet.sh|bramka||pliki:*.py
reliability-and-observability|—|do-zrobienia|timeout i backoff przy kazdym wywolaniu zewnetrznym wymagaja AST; grep nie odrozni wywolania od nazwy zmiennej|zawsze
repo-hygiene-gates|repo-hygiene.sh|bramka||zawsze
rules-as-gates|gate-selfcheck.sh|bramka||zawsze
runtime-boundaries|runtime-boundaries.sh|bramka||pliki:*.tsx:*.astro:*.ts
security-verification-gates|route-guards.sh|bramka||zawsze
stack-composition|stan-stosu.sh|do-zrobienia|stan-stosu.sh jest inwentarzem, nie bramka - zawsze konczy sie zerem; dwie zaleznosci tej samej roli wymagaja tabeli rol, ktorej jeszcze nie ma|zawsze
test-execution-economy|—|czytanie|koszt tokenowy biegu testow mierzy sie w sesji, nie w repo; dobor dowodu oraz preferencje budzetu rozstrzyga review|zawsze
test-quality-baseline|—|czytanie|czternascie wlasnosci suity to checklista audytu z wynikiem per wlasnosc, nie kod wyjscia|zawsze
test-evidence|test-evidence.sh|bramka||zawsze
third-party-assets-privacy|—|do-zrobienia|poziom 1 (grep po CDN) jest tani i wart zrobienia; poziomy 2-4 wymagaja artefaktu builda i uruchomionej aplikacji|pliki:*.tsx:*.astro:*.html:*.css
tool-adoption-and-measurement|document-numbers.sh|bramka||zawsze
toolkit-sync|—|do-zrobienia|sprawdza to scripts/toolkit-sync.sh check, ale to skrypt toolkitu, nie szablon w rejestrze bramek - do wpiecia po ujednoliceniu wywolania|zawsze
typescript-javascript|—|do-zrobienia|tsc --noEmit jest bramka projektu, nie toolkitu; szablon musialby zakladac zainstalowany toolchain i konfiguracje|pliki:*.ts:*.tsx:*.js:*.jsx
ui-copy|ui-copy-lint.sh|bramka||pliki:*.tsx:*.astro:*.vue:*.html:*.py
'

WYNIK="$(mktemp)"; KOSZYKI="$(mktemp)"; trap 'rm -f "$WYNIK" "$KOSZYKI"' EXIT

# dotyczy <sonda> — 0 gdy reguła ma zastosowanie
dotyczy() {
    local sonda="$1"
    case "$sonda" in
        zawsze) return 0 ;;
        pliki:*)
            local globy="${sonda#pliki:}"
            local IFS=:; set -- $globy
            git ls-files -- "$@" 2>/dev/null | grep -q . ;;
        tresc:*)
            local reszta="${sonda#tresc:}"
            local wzor="${reszta%%:*}" globy="${reszta#*:}"
            local IFS=:; set -- $globy
            git grep -qiE "$wzor" -- "$@" 2>/dev/null ;;
        *) return 0 ;;
    esac
}

# streszczenie <plik-wyjścia-bramki> — jedna linia po polsku z sygnałów
streszczenie() {
    grep -E '^[A-Z_]+: ' "$1" 2>/dev/null \
        | grep -viE ': *(brak|n/a|—) *$' \
        | head -3 | tr '\n' ' ' | sed 's/ *$//'
}

while IFS='|' read -r nazwa bramka koszyk powod sonda; do
    [ -n "$nazwa" ] || continue
    plik="$KONWENCJE/$nazwa.md"
    printf '%s\t%s\n' "$nazwa" "$koszyk" >> "$KOSZYKI"
    [ -f "$plik" ] || { printf '%s\t?\tBRAK PLIKU\t—\tkonwencji nie ma w toolkicie\n' "$nazwa" >> "$WYNIK"; continue; }
    tytul="$(grep -m1 '^# ' "$plik" | sed 's/^# Konwencja: //; s/^# //')"

    if ! dotyczy "$sonda"; then
        printf '%s\t%s\tNIE DOTYCZY\t—\ttechnologii, o której mówi ta reguła, nie ma w repo\n' \
            "$nazwa" "$tytul" >> "$WYNIK"
        continue
    fi

    if [ "$bramka" = "—" ]; then
        case "$koszyk" in
            czytanie)     stan="CZYTANA";      opis="rozstrzyga czytanie i tak zostaje — $powod" ;;
            do-zrobienia) stan="DO ZROBIENIA"; opis="da się sprawdzić, ale nie tanio: $powod" ;;
            *)            stan="CZYTANA";      opis="reguła bez przypisanego koszyka — to jest błąd rejestru" ;;
        esac
        printf '%s\t%s\t%s\t—\t%s\n' "$nazwa" "$tytul" "$stan" "$opis" >> "$WYNIK"
        continue
    fi

    if [ "$BEZ_BRAMEK" -eq 1 ] || [ ! -f "$TU/$bramka" ]; then
        stan=$([ "$BEZ_BRAMEK" -eq 1 ] && printf 'POMINIETA' || printf 'BRAK BRAMKI')
        opis=$([ "$BEZ_BRAMEK" -eq 1 ] && printf 'pominięta na życzenie (--bez-bramek)' \
                                       || printf "bramka %s nie jest zainstalowana" "$bramka")
        printf '%s\t%s\t%s\t%s\t%s\n' "$nazwa" "$tytul" "$stan" "$bramka" "$opis" >> "$WYNIK"
        continue
    fi

    out="$(mktemp)"
    if timeout 180 bash "$TU/$bramka" "$PROJEKT" > "$out" 2>&1; then kod=0; else kod=$?; fi
    linia="$(streszczenie "$out")"
    [ -n "$linia" ] || linia="bramka nic nie wypisała"
    case "$kod" in
        0)   stan="SPRAWDZONA" ;;
        124) stan="NIE DOKONCZYLA"; linia="przerwana po 180 s" ;;
        *)   stan="CZERWONA" ;;
    esac
    printf '%s\t%s\t%s\t%s\t%s\n' "$nazwa" "$tytul" "$stan" "$bramka" "$linia" >> "$WYNIK"
    rm -f "$out"
done <<< "$MAPA"

WSZYSTKICH="$(grep -c . "$WYNIK" || true)"
SPRAWDZONYCH="$(awk -F'\t' '$3=="SPRAWDZONA"||$3=="CZERWONA"' "$WYNIK" | grep -c . || true)"
CZERWONYCH="$(awk -F'\t' '$3=="CZERWONA"' "$WYNIK" | grep -c . || true)"
CZYTANYCH="$(awk -F'\t' '$3=="CZYTANA"' "$WYNIK" | grep -c . || true)"
NIEDOTYCZY="$(awk -F'\t' '$3=="NIE DOTYCZY"' "$WYNIK" | grep -c . || true)"
DOZROBIENIA="$(awk -F'\t' '$3=="DO ZROBIENIA"' "$WYNIK" | grep -c . || true)"

# ── Pokrycie: suma trzech koszyków kontra pliki na dysku ────────────────────
# Dwie liczby z dwóch źródeł: pierwsza z tablicy MAPA wpisanej w ten skrypt,
# druga z listingu katalogu conventions/. Rozjazd znaczy konwencję bez wiersza
# albo wiersz bez konwencji — w obu przypadkach korpus rośnie bez przypisania.
K_BRAMKA="$(awk -F'\t' '$2=="bramka"' "$KOSZYKI" | grep -c . || true)"
K_ZROBIC="$(awk -F'\t' '$2=="do-zrobienia"' "$KOSZYKI" | grep -c . || true)"
K_CZYTAC="$(awk -F'\t' '$2=="czytanie"' "$KOSZYKI" | grep -c . || true)"
K_BEZ="$(awk -F'\t' '$2!="bramka" && $2!="do-zrobienia" && $2!="czytanie"' "$KOSZYKI" | grep -c . || true)"
K_SUMA=$(( K_BRAMKA + K_ZROBIC + K_CZYTAC ))
NA_DYSKU="$(ls -1 "$KONWENCJE"/*.md 2>/dev/null | grep -c . || true)"

if [ "$FORMAT" = signals ]; then
    awk -F'\t' '{gsub(/-/,"_",$1); printf "REGULA_%s: %s\n", toupper($1), $3}' "$WYNIK"
else
    printf 'Rejestr reguł — %s konwencji z toolkitu\n' "$WSZYSTKICH"
    for grupa in CZERWONA SPRAWDZONA "NIE DOKONCZYLA" "BRAK BRAMKI" "DO ZROBIENIA" CZYTANA "NIE DOTYCZY"; do
        awk -F'\t' -v g="$grupa" '$3==g' "$WYNIK" > /tmp/.rr.$$ 2>/dev/null || true
        grep -q . /tmp/.rr.$$ 2>/dev/null || continue
        printf '\n%s\n' "$grupa"
        while IFS=$'\t' read -r nazwa tytul stan bramka opis; do
            printf '  %-32s %s\n' "$nazwa" "$tytul"
            printf '  %-32s   %s\n' "" "$(printf '%s' "$opis" | cut -c1-92)"
        done < /tmp/.rr.$$
    done
    rm -f /tmp/.rr.$$
fi

printf '\nREGUL_WSZYSTKICH: %s\n' "$WSZYSTKICH"
printf 'REGUL_SPRAWDZONYCH_BRAMKA: %s\n' "$SPRAWDZONYCH"
printf 'REGUL_CZERWONYCH: %s\n' "$CZERWONYCH"
printf 'REGUL_CZYTANYCH: %s\n' "$CZYTANYCH"
printf 'REGUL_DO_ZROBIENIA: %s\n' "$DOZROBIENIA"
printf 'REGUL_NIE_DOTYCZY: %s\n' "$NIEDOTYCZY"
printf 'KOSZYK_BRAMKA: %s\n' "$K_BRAMKA"
printf 'KOSZYK_DO_ZROBIENIA: %s\n' "$K_ZROBIC"
printf 'KOSZYK_CZYTANIE: %s\n' "$K_CZYTAC"
printf 'KOSZYK_SUMA: %s\n' "$K_SUMA"
printf 'KONWENCJI_NA_DYSKU: %s\n' "$NA_DYSKU"

if [ "$POKRYCIE" -eq 1 ]; then
    if [ "$K_BEZ" -gt 0 ]; then
        printf '\n❌ %s konwencji nie ma przypisanego koszyka. Reguła bez koszyka wygląda\n' "$K_BEZ" >&2
        printf '   na egzekwowaną, a nie jest — i to jest ta miękkość, o którą chodzi.\n' >&2
        exit 1
    fi
    if [ "$K_SUMA" -ne "$NA_DYSKU" ]; then
        printf '\n❌ Suma trzech koszyków to %s, a w conventions/ leży %s plików (różnica %s).\n' \
            "$K_SUMA" "$NA_DYSKU" "$(( NA_DYSKU - K_SUMA ))" >&2
        printf '   Konwencja bez wiersza w rejestrze nie jest przypisana do żadnej kategorii,\n' >&2
        printf '   więc nikt nie wie, czy rozstrzyga ją bramka, czy czytanie.\n' >&2
        printf '   Czym to sprawdzić: `ls conventions/*.md` kontra tablica MAPA w tym skrypcie.\n' >&2
        exit 1
    fi
fi
exit 0
