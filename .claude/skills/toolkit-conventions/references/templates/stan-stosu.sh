#!/usr/bin/env bash
# Inwentarz stosu — co JEST w repozytorium, nie czego brakuje.
#
# Audyt bez tej tabeli odpowiada wyłącznie na pytanie „co jest zepsute".
# Właściciel trzech dużych projektów potrzebuje najpierw odpowiedzi na pytanie
# „co tam w ogóle stoi" — bo w każdym repo stoi co innego, a w ciemno pracuje
# się źle.
#
# Każdy wiersz to fakt z dowodem: nazwa, czy obecne, i skąd to wiadomo.
# Brak jest wynikiem tak samo jak obecność i jest wypisywany.
#
# Użycie: stan-stosu.sh [--format text|signals] [ŚCIEŻKA]
# Kod wyjścia: 0 zawsze — to inwentarz, nie bramka.
set -uo pipefail

FORMAT=text
CEL=.
while [ $# -gt 0 ]; do
    case "$1" in
        --format) FORMAT="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *) CEL="$1"; shift ;;
    esac
done
cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

PLIKI="$(mktemp)"; trap 'rm -f "$PLIKI"' EXIT
git ls-files > "$PLIKI"
# Mianownik inwentarza: ile plików w ogóle wpadło pod obserwację. Inwentarz
# zawsze kończy się zerem, więc bez tej liczby „nic nie znalazłem" i „nie miałem
# czego szukać" wyglądają identycznie.
PLIKOW_OBEJRZANYCH="$(grep -c . "$PLIKI" || true)"

# licz <wzorzec-glob> — ile plików tego rodzaju
# grep -c zwraca 1 przy zerze trafień, więc `|| printf 0` dopisywałoby drugie
# zero do już wypisanego. Stąd `|| true` i normalizacja.
licz() { local n; n="$(grep -cE "$1" "$PLIKI" 2>/dev/null || true)"; printf '%s' "${n:-0}"; }

# szukaj <regex> <glob…> — pierwsze trafienie jako dowód, puste gdy brak
# Lockfile zawiera nazwy wszystkich zależności przechodnich, więc trafienie
# w nim nie dowodzi, że projekt czegoś używa — dowodzi, że coś tego używa.
# Wykluczamy je, inaczej „JEST" znaczyłoby „jest w drzewie zależności".
szukaj() {
    local wzor="$1"; shift
    git grep -l -iE "$wzor" -- "$@" 2>/dev/null \
        | grep -vE '(^|/)(node_modules|dist|build|\.next)/' \
        | grep -vE '(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|uv\.lock)$' \
        | awk '{ p = ($0 ~ /(^|\/)(spikes?|examples?|samples?|demo|scratch|playground)\//) ? 1 : 0; print p "\t" $0 }' \
        | sort -k1,1n | cut -f2- \
        | head -1
}

# To samo, ale bez plików testowych. SQLite w e2e to narzędzie testu;
# SQLite w migracji to źródło prawdy. Zasada dotyczy tylko drugiego.
szukaj_poza_testami() {
    local wzor="$1"; shift
    git grep -l -iE "$wzor" -- "$@" 2>/dev/null \
        | grep -vE '(^|/)(node_modules|dist|build|\.next)/' \
        | grep -vE '(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|uv\.lock)$' \
        | grep -vE '(^|/)(tests?|e2e|__tests__)/|(^|/)(test_|conftest)|\.(test|spec)\.[tj]sx?$' \
        | awk '{ p = ($0 ~ /(^|\/)(spikes?|examples?|samples?|demo|scratch|playground)\//) ? 1 : 0; print p "\t" $0 }' \
        | sort -k1,1n | cut -f2- \
        | head -1
}

# Ile miejsc deklaruje daną rzecz — odróżnia spike od produkcyjnego użycia.
ile_miejsc() {
    local wzor="$1"; shift
    git grep -l -iE "$wzor" -- "$@" 2>/dev/null \
        | grep -vE '(^|/)(node_modules|dist|build|\.next)/' \
        | grep -vE '(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|uv\.lock)$' \
        | grep -c . || true
}

WIERSZE="$(mktemp)"; trap 'rm -f "$PLIKI" "$WIERSZE"' EXIT

# wiersz <kategoria> <nazwa> <dowód-lub-pusto> [liczba]
wiersz() {
    local kat="$1" nazwa="$2" dowod="${3:-}" liczba="${4:-}"
    local stan; [ -n "$dowod" ] && stan=JEST || stan=BRAK
    printf '%s\t%s\t%s\t%s\t%s\n' "$kat" "$nazwa" "$stan" "${liczba:-—}" "${dowod:-—}" >> "$WIERSZE"
}

# ── Języki ──────────────────────────────────────────────────────────────────
for para in 'Python:\.py$' 'TypeScript:\.tsx?$' 'JavaScript:\.[cm]?jsx?$' \
            'Go:\.go$' 'Rust:\.rs$' 'Shell:\.sh$' 'SQL:\.sql$'; do
    nazwa="${para%%:*}"; wzor="${para#*:}"
    n="$(licz "$wzor")"
    [ "$n" -gt 0 ] && wiersz "Język" "$nazwa" "$(grep -m1 -E "$wzor" "$PLIKI")" "$n" \
                  || wiersz "Język" "$nazwa" "" 0
done

# ── Framework widoku ────────────────────────────────────────────────────────
wiersz "Widok" "Astro"   "$(szukaj '"astro"' '*/package.json' 'package.json')" "$(licz '\.astro$') plików"
wiersz "Widok" "Next"    "$(szukaj '"next"' '*/package.json' 'package.json')" "$(ile_miejsc '"next"' '*/package.json' 'package.json') pkg"
wiersz "Widok" "React"   "$(szukaj '"react"' '*/package.json' 'package.json')" "$(licz '\.tsx$')"
wiersz "Widok" "Vue"     "$(szukaj '"vue"' '*/package.json' 'package.json')"
wiersz "Widok" "Svelte"  "$(szukaj '"svelte"' '*/package.json' 'package.json')"

# ── Backend ─────────────────────────────────────────────────────────────────
wiersz "Backend" "FastAPI"  "$(szukaj 'fastapi' 'pyproject.toml' 'requirements*.txt')"
wiersz "Backend" "Flask"    "$(szukaj '^flask|"flask"' 'pyproject.toml' 'requirements*.txt')"
wiersz "Backend" "Django"   "$(szukaj 'django' 'pyproject.toml' 'requirements*.txt')"
wiersz "Backend" "Express"  "$(szukaj '"express"' '*/package.json' 'package.json')"

# ── Kontrakt danych ─────────────────────────────────────────────────────────
wiersz "Kontrakt" "Pydantic"    "$(szukaj 'pydantic' 'pyproject.toml' 'requirements*.txt')"
wiersz "Kontrakt" "Zod"         "$(szukaj '"zod"' '*/package.json' 'package.json')"
wiersz "Kontrakt" "OpenAPI"     "$(szukaj 'openapi' '*.yaml' '*.yml' '*.json' '*.py' '*.ts')"
wiersz "Kontrakt" "JSON Schema" "$(szukaj 'json.?schema' '*.json' '*.py' '*.ts')"

# ── Trwałość ────────────────────────────────────────────────────────────────
wiersz "Baza" "PostgreSQL"  "$(szukaj 'postgres' '*.yaml' '*.yml' '*.toml' '*/package.json')"
wiersz "Baza" "SQLite"      "$(szukaj_poza_testami 'sqlite' '*.py' '*.ts' '*.toml' '*.yaml')"
wiersz "Baza" "SQLAlchemy"  "$(szukaj 'sqlalchemy' 'pyproject.toml' 'requirements*.txt')"
wiersz "Baza" "Alembic"     "$(szukaj 'alembic' 'pyproject.toml' 'alembic.ini')"
wiersz "Baza" "Drizzle"     "$(szukaj 'drizzle' '*/package.json' 'package.json')"
wiersz "Baza" "Prisma"      "$(szukaj 'prisma' '*/package.json' 'package.json')"

# ── Typy i styl ─────────────────────────────────────────────────────────────
wiersz "Typy" "TypeScript"  "$(szukaj '"typescript"' '*/package.json' 'package.json')" "$(licz 'tsconfig')"
wiersz "Typy" "mypy"        "$(szukaj '\[tool\.mypy\]|mypy' 'pyproject.toml' 'mypy.ini' 'setup.cfg')"
wiersz "Styl" "ruff"        "$(szukaj '\[tool\.ruff|"ruff"' 'pyproject.toml' 'ruff.toml')"
wiersz "Styl" "black"       "$(szukaj '\[tool\.black\]' 'pyproject.toml')"
wiersz "Styl" "ESLint"      "$(szukaj 'eslint' '*/package.json' 'package.json' 'eslint.config.*')"
wiersz "Styl" "Prettier"    "$(szukaj 'prettier' '*/package.json' 'package.json')"
wiersz "Styl" "Biome"       "$(szukaj 'biome' '*/package.json' 'biome.json')"

# ── Testy ───────────────────────────────────────────────────────────────────
wiersz "Testy" "pytest"      "$(szukaj 'pytest' 'pyproject.toml' 'pytest.ini' 'setup.cfg')" "$(licz 'test_.*\.py$|_test\.py$')"
wiersz "Testy" "Vitest"      "$(szukaj '"vitest"' '*/package.json' 'package.json')"
wiersz "Testy" "Jest"        "$(szukaj '"jest"' '*/package.json' 'package.json')"
wiersz "Testy" "node:test"   "$(szukaj 'node:test' '*.ts' '*.js' '*.mjs')"
wiersz "Testy" "Playwright"  "$(szukaj 'playwright' '*/package.json' 'package.json')" "$(licz '\.spec\.[tj]s$')"

# ── Warstwa agentowa ────────────────────────────────────────────────────────
wiersz "Agent" "LangGraph"   "$(szukaj 'langgraph' 'pyproject.toml' '*/package.json' 'package.json')"
wiersz "Agent" "LangChain"   "$(szukaj 'langchain' 'pyproject.toml' '*/package.json' 'package.json')"
wiersz "Agent" "CopilotKit"  "$(szukaj 'copilotkit' '*/package.json' 'package.json')"
wiersz "Agent" "MCP"         "$(szukaj 'modelcontextprotocol|mcp.?server|langchain-mcp' 'pyproject.toml' '*/package.json' '*.py' '*.ts')"
# Wzmianka w kodzie to nie użycie. HumanPen ma w komentarzu zdanie
# „wbudowany langgraph-checkpoint-sqlite jest wg dokumentacji…", po którym
# implementuje BaseCheckpointSaver SAM — a poprzednia wersja liczyła to jako
# checkpointer z biblioteki. Pytamy więc wyłącznie manifest zależności.
wiersz "Agent" "Checkpointer z biblioteki" "$(szukaj 'langgraph-checkpoint|langgraph_checkpoint' 'pyproject.toml' 'requirements*.txt' '*/package.json' 'package.json')"
wiersz "Agent" "Własny checkpointer" "$(szukaj 'class [A-Za-z]*Checkpoint[A-Za-z]*\(BaseCheckpointSaver' '*.py' '*.ts')"
wiersz "Agent" "LangSmith"   "$(szukaj 'langsmith' 'pyproject.toml' '*/package.json' '*.py')"
wiersz "Agent" "Langfuse"    "$(szukaj 'langfuse' 'pyproject.toml' '*/package.json' '*.py')"
wiersz "Agent" "OpenTelemetry" "$(szukaj 'opentelemetry|otel' 'pyproject.toml' '*/package.json' '*.py')"

# ── Wytwarzanie ─────────────────────────────────────────────────────────────
wiersz "Wytwarzanie" "Docker Compose" "$(szukaj 'services:' '*compose*.yaml' '*compose*.yml')"
wiersz "Wytwarzanie" "CI (GitHub)"    "$(git ls-files '.github/workflows/*' 2>/dev/null | head -1)" "$(git ls-files '.github/workflows/*' 2>/dev/null | grep -c .)"
wiersz "Wytwarzanie" "Lockfile npm"   "$(git ls-files '*package-lock.json' '*pnpm-lock.yaml' '*yarn.lock' 2>/dev/null | head -1)"
wiersz "Wytwarzanie" "Lockfile Python" "$(git ls-files '*uv.lock' '*poetry.lock' '*requirements.lock' 2>/dev/null | head -1)"
wiersz "Wytwarzanie" "Hooki gita"     "$(ls .githooks 2>/dev/null | head -1 | sed 's|^|.githooks/|')"


# ── Zasady stosu ────────────────────────────────────────────────────────────
# Inwentarz mówi, co stoi. Zasada mówi, co ma stać. Bez tej drugiej kolumny
# tabela melduje „Astro JEST" tym samym tonem co „React JEST", a to nie jest
# ta sama wiadomość: jednego chcemy, drugiego się pozbywamy.
#
# Zdania pochodzą z references/agentic-harness-2026-08.md, sekcja
# „Zalecenia wprost". Odstępstwo jest decyzją do zapisania, nie błędem —
# dlatego werdykt to zdanie, a nie kod wyjścia.
#
# format: nazwa|ma|zdanie   albo   nazwa|nie|zdanie
ZASADY="React|ma|używaj React do budowania widoku
Next|ma|używaj Next jako frameworka aplikacji
Astro|nie|nie używaj Astro w aplikacji — widok ma stać na Next
Vue|nie|nie dokładaj Vue obok Reacta — jeden framework widoku na aplikację
Svelte|nie|nie dokładaj Svelte obok Reacta — jeden framework widoku na aplikację
PostgreSQL|ma|używaj PostgreSQL jako bazy aplikacji
SQLite|nie|nie trzymaj stanu aplikacji w SQLite — to baza na testy, nie na produkcję
TypeScript|ma|używaj TypeScriptu w kodzie przeglądarki
Pydantic|ma|używaj Pydantica do opisu danych po stronie Pythona
Zod|ma|używaj Zoda do opisu danych po stronie TypeScriptu
LangGraph|ma|używaj LangGraph zamiast własnej pętli agenta
Checkpointer z biblioteki|ma|używaj checkpointera z biblioteki zamiast własnej tabeli na stan rozmowy
MCP|ma|podłączaj narzędzia przez MCP zamiast pisać własny protokół
Lockfile npm|ma|trzymaj lockfile w repozytorium, żeby build był powtarzalny
Lockfile Python|ma|trzymaj lockfile w repozytorium, żeby build był powtarzalny
CI (GitHub)|ma|uruchamiaj bramki w CI, nie tylko na swoim komputerze
Docker Compose|ma|opisz środowisko w compose, żeby dało się je odtworzyć"

# werdykt <nazwa> <stan> — zdanie po polsku albo puste, gdy zasady nie ma
werdykt() {
    printf '%s\n' "$ZASADY" | while IFS='|' read -r n ocz zdanie; do
        [ "$n" = "$1" ] || continue
        if [ "$ocz" = ma ]; then
            [ "$2" = JEST ] && printf 'zgodne' || printf '%s' "$zdanie"
        else
            [ "$2" = JEST ] && printf '%s' "$zdanie" || printf 'zgodne'
        fi
        break
    done
}

# ── Wyjście ─────────────────────────────────────────────────────────────────
if [ "$FORMAT" = signals ]; then
    printf 'STOS_PLIKOW: %s\n' "$PLIKOW_OBEJRZANYCH"
    awk -F'\t' '{printf "STOS_%s_%s: %s\n", toupper($1), toupper(gensub(/[^A-Za-z0-9]/,"_","g",$2)), $3}' "$WIERSZE" 2>/dev/null \
      || awk -F'\t' '{gsub(/[^A-Za-z0-9]/,"_",$2); printf "STOS_%s_%s: %s\n", toupper($1), toupper($2), $3}' "$WIERSZE"
    exit 0
fi

ODSTEPSTWA="$(mktemp)"; trap 'rm -f "$PLIKI" "$WIERSZE" "$ODSTEPSTWA"' EXIT

KAT=""
while IFS=$'\t' read -r kat nazwa stan liczba dowod; do
    if [ "$kat" != "$KAT" ]; then printf '\n%s\n' "$kat"; KAT="$kat"; fi
    if [ "$stan" = JEST ]; then znak="✓"; else znak="·"; fi
    w="$(werdykt "$nazwa" "$stan")"
    case "$w" in
        "")       ocena="" ;;
        zgodne)   ocena="  ← zgodne z zasadą" ;;
        *)        ocena="  ← $w"; printf '%s\t%s\t%s\n' "$nazwa" "$stan" "$w" >> "$ODSTEPSTWA" ;;
    esac
    printf '  %s %-26s %-6s %-7s %s%s\n' "$znak" "$nazwa" "$stan" "$liczba" \
        "$(printf '%s' "$dowod" | cut -c1-40)" "$ocena"
done < "$WIERSZE"

# Odstępstwa osobno, bo w tabeli toną. Każde jest zdaniem, nie kodem.
printf '\nOdstępstwa od zasad stosu\n'
if [ -s "$ODSTEPSTWA" ]; then
    while IFS=$'\t' read -r nazwa stan zdanie; do
        if [ "$stan" = JEST ]; then powod="jest w repo"; else powod="nie ma go w repo"; fi
        printf '  • %s (%s) — %s\n' "$nazwa" "$powod" "$zdanie"
    done < "$ODSTEPSTWA"
    printf '\n  Odstępstwo jest decyzją do zapisania w rejestrze, nie błędem do naprawy\n'
    printf '  na miejscu. Jeśli zostaje — ma mieć powód, właściciela i datę przeglądu.\n'
else
    printf '  brak — stos zgadza się z zasadami\n'
fi

printf '\nSTOS_PLIKOW: %s\n' "$PLIKOW_OBEJRZANYCH"
printf 'STOS_JEST: %s\nSTOS_BRAK: %s\nSTOS_ZASAD: %s\nSTOS_ODSTEPSTW: %s\n' \
    "$(awk -F'\t' '$3=="JEST"' "$WIERSZE" | grep -c .)" \
    "$(awk -F'\t' '$3=="BRAK"' "$WIERSZE" | grep -c .)" \
    "$(printf '%s\n' "$ZASADY" | grep -c .)" \
    "$(grep -c . "$ODSTEPSTWA" || true)"
exit 0
