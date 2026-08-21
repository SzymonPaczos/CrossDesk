#!/usr/bin/env bash
# audit.sh — cotygodniowy audyt CrossDesk (warstwa statyczna).
#
# Dopisuje sekcję `## Audyt YYYY-MM-DD` na górę `.claude/audit-log.md`.
# Cele:
# - Liczby. Brak osądu LLM tutaj (warstwa głęboka idzie osobno).
# - Tylko narzędzia z CI (nic nie instaluje).
# - Trzy różne stany, nigdy zlepione w jeden: liczba · `n/a` (narzędzia nie ma)
#   · `BLOCKED` (narzędzie wystartowało i padło). Skan, który padł, NIE MA
#   prawa podać liczby — inaczej awaria wygląda dokładnie jak czysty przebieg.
# - Idempotentny: można uruchomić wielokrotnie tego samego dnia.
#
# Tryb próbny: `CROSSDESK_AUDIT_DRYRUN=1 bash .claude/audit.sh` liczy wszystko
# i drukuje sekcję, ale NIE dotyka audit-log.md.
#
# Stack pokryty: Python host (ruff, mypy --strict, pytest, bandit) + Rust
# guest/gui (cargo check, clippy, deny, audit) + proto (buf) + QML (qmllint)
# + sekrety (gitleaks) + higiena repo + aktualność runtime'ów + drift.
#
# Procedura (Kroki 00–5 i punkty głębokie 1–25) → .claude/skills/weekly-audit/,
# konkretyzacja CrossDeska → .claude/rules/audit.md.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Python tooling (ruff/mypy/pytest/bandit) lives in host/.venv, not on
# PATH — without this the whole Python section reported "n/a" (audit
# 2026-06-12). Same venv-first convention as .githooks/pre-commit.
HOST_VENV="brak"
if [ -d "$REPO_ROOT/host/.venv/bin" ]; then
  PATH="$REPO_ROOT/host/.venv/bin:$PATH"
  HOST_VENV="host/.venv"
fi

LOG="$REPO_ROOT/.claude/audit-log.md"
DATE="$(date '+%Y-%m-%d')"
TOOLKIT_DIR="${CROSSDESK_TOOLKIT_DIR:-$REPO_ROOT/../claude-toolkit}"
# Bez normalizacji w raporcie ląduje `/…/CrossDesk/../claude-toolkit`.
TOOLKIT_DIR="$(cd "$TOOLKIT_DIR" 2>/dev/null && pwd || printf '%s' "$TOOLKIT_DIR")"
SECTION=""

add() { SECTION+="$1"$'\n'; }
has() { command -v "$1" >/dev/null 2>&1; }
count_lines() { grep -cE '^' 2>/dev/null || true; }
to_epoch() { date -d "$1" +%s 2>/dev/null || date -j -f '%Y-%m-%d' "$1" +%s 2>/dev/null || echo 0; }

# metric <etykieta> <ok-rc-lista> <komenda...>
#
# Uruchamia komendę, łapie KOD WYJŚCIA i dopiero potem liczy trafienia.
# Kod spoza listy „to znaczy, że narzędzie zadziałało" daje `BLOCKED`, nie 0.
# Powód: `cmd | grep -c` gubi rc komendy przez potok, więc crash lintera
# raportował się jako „0 findings" — nie do odróżnienia od czystego repo.
# Filtr trafień czyta się ze zmiennej METRIC_FILTER (regex ERE); pusty = licz
# wszystkie linie.
METRIC_FILTER=''
metric() {
  local label="$1" ok_rcs="$2"; shift 2
  local out rc n
  out="$("$@" 2>&1)"; rc=$?
  if [[ " $ok_rcs " != *" $rc "* ]]; then
    add "- $label: **BLOCKED** (exit $rc — narzędzie padło, to nie jest 0 findings)"
    return
  fi
  if [ -n "$METRIC_FILTER" ]; then
    n="$(printf '%s\n' "$out" | grep -cE "$METRIC_FILTER" || true)"
  else
    n="$(printf '%s\n' "$out" | count_lines)"
  fi
  add "- $label: ${n:-0}"
}
in_dir() { local d="$1"; shift; ( cd "$REPO_ROOT/$d" 2>/dev/null || exit 127; "$@" ); }

# ----- Nagłówek maszynowy --------------------------------------------
# Wzorzec pełnego wpisu: .claude/templates/audit-log-entry.md
HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
PREV_AUDIT=""
if [ -f "$LOG" ]; then
  PREV_AUDIT="$(grep -oE '^## Audyt [0-9-]+' "$LOG" | head -1 | grep -oE '[0-9-]+' || true)"
fi
TOOLKIT_VER="brak locka"
[ -f "$REPO_ROOT/.claude/toolkit.lock" ] && \
  TOOLKIT_VER="$(awk '/^toolkit_version/{print $2; exit}' "$REPO_ROOT/.claude/toolkit.lock")"

add "## Audyt $DATE"
add ""
add '```text'
add "TOOLKIT_VERSION:      $TOOLKIT_VER"
add "AUDITED_REVISION:     $HEAD_SHA"
add "BRANCH:               $BRANCH"
add "PREVIOUS_AUDIT:       ${PREV_AUDIT:-pierwszy audyt}"
if [ -n "$PREV_AUDIT" ]; then
  # Zakres = wszystko, co weszło od poprzedniego audytu. Enumeracja plików
  # z promptu przepuszcza znaleziska w plikach, których nikt nie wymienił.
  SINCE_N="$(git log --oneline --since="$PREV_AUDIT" 2>/dev/null | count_lines)"
  SINCE_MERGES="$(git log --oneline --merges --since="$PREV_AUDIT" 2>/dev/null | count_lines)"
  add "DIFF_RANGE_OR_SCOPE:  --since=$PREV_AUDIT..HEAD (${SINCE_N:-0} commitów, ${SINCE_MERGES:-0} merge'y)"
else
  add "DIFF_RANGE_OR_SCOPE:  pełne repo (pierwszy audyt)"
fi
add "PYTHON_ENV:           $HOST_VENV$([ "$HOST_VENV" = brak ] && echo '  ← DEGRADED: mierzone poza venvem projektu')"
add "DOCS_SOURCE:          <wypełnia agent: nazwa serwera dokumentacji | n/a (pamięć modelu)>"
add "SECURITY_REVIEW:      <wypełnia agent>"
add "RED_TEAM:             <wypełnia agent>"
add "DEEP_REVIEW:          <wypełnia agent: tak/nie>"
add '```'
add ""

# ----- Krok 00: wersja toolkitu --------------------------------------
add "### Krok 00 — wersja toolkitu"
add ""
if [ -x "$TOOLKIT_DIR/scripts/toolkit-sync.sh" ]; then
  SYNC_OUT="$(bash "$TOOLKIT_DIR/scripts/toolkit-sync.sh" check "$REPO_ROOT" 2>&1)"
  SYNC_RC=$?
  MASTER_VER="$(printf '%s' "$SYNC_OUT" | head -1 | grep -oE '[0-9]{4}\.[0-9]{2}\.[0-9]{2}' | head -1 || true)"
  DRIFT_N="$(printf '%s\n' "$SYNC_OUT" | grep -cE 'MASTER NOWSZY|ZMIENIONY LOKALNIE|BEZ STEMPLA' || true)"
  LOCAL_N="$(printf '%s\n' "$SYNC_OUT" | grep -cE 'LOKALNY \(zadeklarowany\)' || true)"
  add "- master: ${MASTER_VER:-?} · projekt: $TOOLKIT_VER"
  add "- kopie rozjechane (do \`update\`): ${DRIFT_N:-0}"
  add "- odstępstwa zadeklarowane (\`toolkit.local\`): ${LOCAL_N:-0}"
  [ "${DRIFT_N:-0}" -gt 0 ] && add "- ⚠️  audyt na nieaktualnej checkliście sprawdza wczorajsze ryzyka — \`update\` PRZED oceną (exit $SYNC_RC)"
else
  add "- **DEGRADED** — brak mastera w \`$TOOLKIT_DIR\`; nie ma czym porównać checklisty"
  add "  (ustaw \`CROSSDESK_TOOLKIT_DIR\` albo sklonuj toolkit obok repo)"
fi
add ""

add "### Warstwa statyczna (automat)"
add ""

# ----- Python host ---------------------------------------------------
add "**Python (\`host/\`)**"
add ""
if [ -d host ]; then
  # ruff: 0 = czysto, 1 = są findings, wszystko inne = awaria narzędzia.
  if has ruff; then
    METRIC_FILTER='^[^[:space:]].*:[0-9]+' metric "ruff findings" "0 1" \
      bash -c 'cd host && ruff check src/ tests/'
  else add "- ruff: n/a (not on PATH)"; fi
  # mypy: 0 = czysto, 1 = błędy typów, 2 = błąd użycia/awaria.
  if has mypy; then
    MYPY_OUT="$(in_dir host mypy --strict src/ 2>&1)"; MYPY_RC=$?
    if [ "$MYPY_RC" -gt 1 ]; then
      add "- mypy --strict: **BLOCKED** (exit $MYPY_RC)"
    else
      MYPY_ERRS="$(printf '%s\n' "$MYPY_OUT" | grep -cE '^[^[:space:]].*: error:' || true)"
      MYPY_FILES="$(printf '%s\n' "$MYPY_OUT" | grep -oE 'checked [0-9]+ source files' | grep -oE '[0-9]+' || true)"
      # Brakujący moduł/stub to luka ŚRODOWISKA, nie błąd typów w kodzie.
      # Bez tego rozdzielenia audyt na maszynie bez `host/.venv` raportuje
      # „mypy: 1 błąd" i wygląda jak regresja — a to tylko niezainstalowana
      # zależność (punkt 14g: odtwarzalność środowiska).
      MYPY_ENV="$(printf '%s\n' "$MYPY_OUT" | grep -cE '\[import-(not-found|untyped)\]' || true)"
      MYPY_REAL=$(( ${MYPY_ERRS:-0} - ${MYPY_ENV:-0} ))
      [ "$MYPY_REAL" -lt 0 ] && MYPY_REAL=0
      add "- mypy --strict errors: ${MYPY_REAL} (across ${MYPY_FILES:-?} files, env=${HOST_VENV})"
      [ "${MYPY_ENV:-0}" -gt 0 ] && add "- mypy: **DEGRADED** — braki importu: ${MYPY_ENV} (środowisko niekompletne, nie regresja typów): $(printf '%s\n' "$MYPY_OUT" | grep -oE 'named \"[^\"]+\"' | sort -u | tr '\n' ' ')"
    fi
  else add "- mypy: n/a"; fi
  # pytest --collect-only: 0 = zebrane, 5 = brak testów; reszta = awaria.
  if has pytest; then
    PYT_OUT="$(in_dir host pytest --collect-only -q 2>&1)"; PYT_RC=$?
    if [ "$PYT_RC" -ne 0 ] && [ "$PYT_RC" -ne 5 ]; then
      add "- pytest collected: **BLOCKED** (exit $PYT_RC — kolekcja padła)"
    else
      PYTEST_COLLECT="$(printf '%s\n' "$PYT_OUT" | tail -3 | grep -oE '[0-9]+ tests? collected' | grep -oE '^[0-9]+' || true)"
      add "- pytest collected: ${PYTEST_COLLECT:-?}"
    fi
  else add "- pytest: n/a"; fi
  if has bandit; then
    METRIC_FILTER='^>> Issue.*Severity: (High|Medium)' metric "bandit medium/high" "0 1" \
      bash -c 'cd host && bandit -ll -r src/'
  else add "- bandit: n/a"; fi
  # Ratchet (audit 2026-07-07 / P1-3): every blocking libvirt/filesystem call
  # reachable from a gRPC servicer must go through libvirt_call() (executor +
  # deadline). A direct invocation on the same line as no libvirt_call() is a
  # regression — the bound-method/lambda args passed TO libvirt_call don't match.
  LIBVIRT_DIRECT="$(grep -rn 'self\.\(libvirt_ctl\|filesystem_ctl\)\.[a-z_]*(' host/src/crossdesk_host/ipc/ 2>/dev/null | grep -vc 'libvirt_call' || true)"
  add "- servicer direct blocking libvirt/fs calls (want 0): ${LIBVIRT_DIRECT:-0}"
else
  add "- host/ missing"
fi
add ""

# ----- Rust ----------------------------------------------------------
add "**Rust (\`guest/\`, \`gui/\`)**"
add ""
for crate in guest gui; do
  if [ -d "$crate" ] && has cargo; then
    METRIC_FILTER='^warning:' metric "$crate cargo check warnings" "0 101" \
      bash -c "cd $crate && cargo check --workspace --message-format=short"
    METRIC_FILTER='^error:' metric "$crate clippy errors (-D warnings)" "0 101" \
      bash -c "cd $crate && cargo clippy --workspace --message-format=short -- -D warnings"
  elif [ -d "$crate" ]; then
    add "- $crate: cargo n/a"
  fi
done
if has cargo-deny; then
  for crate in guest gui; do
    if [ -f "$crate/deny.toml" ]; then
      METRIC_FILTER='^(error|warning)\[' metric "$crate cargo-deny issues" "0 1 2" \
        bash -c "cd $crate && cargo deny check"
    fi
  done
else add "- cargo-deny: n/a"; fi
if has cargo-audit; then
  for crate in guest gui; do
    if [ -d "$crate" ]; then
      METRIC_FILTER='^Vulnerability:' metric "$crate cargo-audit vulns" "0 1" \
        bash -c "cd $crate && cargo audit"
    fi
  done
else add "- cargo-audit: n/a"; fi
add ""

# ----- Proto ---------------------------------------------------------
add "**Proto (\`proto/\`)**"
add ""
if has buf; then
  METRIC_FILTER='^[^[:space:]].*:[0-9]+' metric "buf lint findings" "0 100" \
    bash -c 'cd proto && buf lint'
  METRIC_FILTER='^(\+\+\+|---)' metric "buf format diff lines" "0 100" \
    bash -c 'cd proto && buf format --diff'
else add "- buf: n/a"; fi
PROTO_FILES="$(find proto -name '*.proto' 2>/dev/null | count_lines)"
add "- .proto files: ${PROTO_FILES:-0}"
add ""

# ----- QML -----------------------------------------------------------
add "**QML (\`gui/\`)**"
add ""
if has qmllint; then
  QML_OUT="$(find gui -name '*.qml' -print0 2>/dev/null | xargs -0 qmllint 2>&1)"; QML_RC=$?
  if [ "$QML_RC" -gt 1 ]; then
    add "- qmllint: **BLOCKED** (exit $QML_RC)"
  else
    QML_WARN="$(printf '%s\n' "$QML_OUT" | grep -cE '^Warning:' || true)"
    add "- qmllint warnings: ${QML_WARN:-0}"
  fi
else add "- qmllint: n/a"; fi
add ""

# ----- TODO / dead-code heuristics -----------------------------------
add "**Code hygiene**"
add ""
TODO_FILES="$(grep -rEl 'TODO|FIXME|HACK|XXX' \
  --include='*.py' --include='*.rs' --include='*.qml' \
  host/src guest gui 2>/dev/null | count_lines)"
add "- files with TODO/FIXME/HACK/XXX (src only): ${TODO_FILES:-0}"
TEST_FILES_PY="$(find host -name 'test_*.py' 2>/dev/null | count_lines)"
# Rust: count #[test] / #[tokio::test] occurrences (unit tests live
# inside src/ mod tests blocks, not under tests/ dirs).
TEST_ANNOTS_RS="$(grep -rEh '^\s*#\[(test|tokio::test)' --include='*.rs' guest gui 2>/dev/null | count_lines)"
add "- test files (python): ${TEST_FILES_PY:-0}"
add "- #[test] annotations (rust): ${TEST_ANNOTS_RS:-0}"
add ""

# ----- Aktualność runtime'ów (punkt 15) ------------------------------
# Runtime po EOL = P0: po tej dacie nie ma poprawek bezpieczeństwa.
# Skrypt podaje ZADEKLAROWANE wersje; datę EOL potwierdza agent przy źródle
# dokumentacji (DOCS_SOURCE) — nie zgaduje jej z pamięci.
add "**Dependency currency (punkt 15)**"
add ""
PY_REQ="$(grep -m1 -oE 'requires-python[[:space:]]*=[[:space:]]*"[^"]+"' host/pyproject.toml 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 || true)"
add "- declared \`requires-python\`: ${PY_REQ:-brak deklaracji} (EOL do potwierdzenia przy DOCS_SOURCE)"
CI_PY="$(grep -rhoE "python-version: *['\"]?[0-9]+\.[0-9]+" .github/workflows/ 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | sort -u | tr '\n' ' ' || true)"
add "- python w matrycy CI: ${CI_PY:-n/a} (rozbieżność z deklaracją = osobne ustalenie)"
RUST_TC="$(cat rust-toolchain.toml rust-toolchain 2>/dev/null | grep -m1 -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo 'brak pinu (stable)')"
add "- rust toolchain: $RUST_TC"
add "- lockfile'y: Cargo.lock guest=$([ -f guest/Cargo.lock ] && echo tak || echo NIE) · gui=$([ -f gui/Cargo.lock ] && echo tak || echo NIE) · python=$([ -f host/uv.lock ] || [ -f host/requirements.txt ] && echo tak || echo NIE)"
if [ -x .claude/templates/dependency-currency.sh ]; then
  add "- bramka aktualności: \`.claude/templates/dependency-currency.sh\` (szkielet — dopisz ekosystemy przed użyciem)"
fi
add ""

# ----- Higiena repo (punkt 14 / repo-hygiene-gates.md) ---------------
add "**Higiena repo (punkt 14)**"
add ""
BR_NO_UPSTREAM="$(git branch -vv 2>/dev/null | grep -vcE '\[[^]]+\]' || true)"
BR_AHEAD="$(git branch -vv 2>/dev/null | grep -cE '\[.*ahead ' || true)"
add "- gałęzie bez upstreamu: ${BR_NO_UPSTREAM:-0} · ahead of upstream: ${BR_AHEAD:-0}"
STASHES="$(git stash list 2>/dev/null | count_lines)"
add "- stash entries: ${STASHES:-0}"
PRUNABLE="$(git worktree list --porcelain 2>/dev/null | grep -c prunable || true)"
add "- worktree prunable: ${PRUNABLE:-0}"
MERGED_REMOTE="$(git branch -r --merged 2>/dev/null | grep -vE 'origin/(HEAD|main)$' | count_lines)"
add "- zmergowane gałęzie na origin (do sprzątnięcia): ${MERGED_REMOTE:-0}"
JUNK="$(git ls-files 2>/dev/null | grep -icE '\.bak$|BACKUP|_b64' || true)"
add "- tracked \`.bak\`/\`BACKUP\`/\`_b64\`: ${JUNK:-0}"
# 14d — integralność referencyjna: martwy link z .claude/*.md do „jedynej
# kopii" jest P0. Sprawdzamy tylko ścieżki markdown wyglądające na pliki repo.
DEAD_LINKS=0
while IFS= read -r target; do
  [ -n "$target" ] || continue
  [ -e "$REPO_ROOT/$target" ] || DEAD_LINKS=$((DEAD_LINKS + 1))
done < <(grep -rhoE '\]\(\.\./[A-Za-z0-9_./-]+\.(md|sh|py|rs|toml|xml)\)' .claude/*.md 2>/dev/null \
         | sed -E 's/^\]\(\.\.\///; s/\)$//' | sort -u)
add "- martwe linki w \`.claude/*.md\` (14d): ${DEAD_LINKS}"
add ""

# ----- Drift ---------------------------------------------------------
add "**Drift & meta**"
add ""
if [ -f .claude/architecture.md ]; then
  ARCH_TS="$(grep -oE '\*\*Last Updated:\*\* [0-9-]+' .claude/architecture.md | grep -oE '[0-9-]+' | head -1 || true)"
  if [ -n "${ARCH_TS:-}" ]; then
    ARCH_AGE_DAYS="$(( ($(date +%s) - $(to_epoch "$ARCH_TS")) / 86400 ))"
    add "- architecture.md Last Updated: $ARCH_TS (${ARCH_AGE_DAYS}d ago)"
  fi
fi
if [ -f .claude/rules/decisions.md ]; then
  DEC_META="$(grep -cE '^## DEC-META-[0-9]+' .claude/rules/decisions.md 2>/dev/null || true)"
  add "- META decisions: ${DEC_META:-0}"
fi
if [ -f docs/DECISIONS.md ]; then
  DEC_NNNN="$(grep -cE '^## DEC-[0-9]+' docs/DECISIONS.md 2>/dev/null || true)"
  add "- ADR DEC-NNNN total: ${DEC_NNNN:-0}"
fi
# Punkt 4 — dryf twierdzeń liczbowych. Liczby load-bearing z prozy, przeliczone
# komendą. Rozjazd z tekstem w AGENTS.md/PLAN.md to finding, nie kosmetyka.
SUBPKGS="$(find host/src/crossdesk_host -mindepth 1 -maxdepth 1 -type d ! -name __pycache__ 2>/dev/null | count_lines)"
add "- host subpackages (AGENTS.md „Repository layout\" twierdzi liczbę): ${SUBPKGS:-0}"
CRIT_LIVE="$(grep -cE '^\| *[0-9]+ \|.*✅ live' PLAN.md 2>/dev/null || true)"
add "- kryteria akceptacji ✅ live (PLAN.md): ${CRIT_LIVE:-0}/12"
add ""

# ----- Security ------------------------------------------------------
add "**Security**"
add ""
if has gitleaks; then
  GL_OUT="$(gitleaks detect --no-banner --no-git --source . 2>&1)"; GL_RC=$?
  # gitleaks: 0 = czysto, 1 = znaleziska, reszta = awaria narzędzia.
  if [ "$GL_RC" -gt 1 ]; then
    add "- gitleaks: **BLOCKED** (exit $GL_RC)"
  else
    LEAKS="$(printf '%s\n' "$GL_OUT" | grep -cE 'Finding:' || true)"
    add "- gitleaks worktree findings: ${LEAKS:-0}"
  fi
else
  add "- gitleaks: n/a (use \`CROSSDESK_FULL_AUDIT=1 git push\` for history scan)"
fi
if has zizmor && [ -d .github/workflows ]; then
  METRIC_FILTER='^(error|warning|note)\[' metric "zizmor findings" "0 13 14" \
    zizmor --config .github/zizmor.yml .github/workflows/
else
  add "- zizmor: n/a"
fi
# Punkt 8 — bramka dowodzi wartości tym, że BLOKUJE. Sam fakt, że hook nie
# krzyczy na zdrowym repo, nie jest dowodem na nic.
if [ -f "$TOOLKIT_DIR/templates/test-gates.sh" ]; then
  add "- gate self-test: \`bash $TOOLKIT_DIR/templates/test-gates.sh .githooks/pre-push\` (uruchom ręcznie; wynik do raportu)"
else
  add "- gate self-test: n/a (brak \`templates/test-gates.sh\`)"
fi
add ""

# ----- Audit cadence -------------------------------------------------
add "**Cadence**"
add ""
if [ -n "${PREV_AUDIT:-}" ]; then
  LAST_AGE_DAYS="$(( ($(date +%s) - $(to_epoch "$PREV_AUDIT")) / 86400 ))"
  add "- previous audit: $PREV_AUDIT (${LAST_AGE_DAYS}d ago)"
  [ "$LAST_AGE_DAYS" -gt 7 ] && add "- ⚠️  kadencja przekroczona (>7 dni) — patrz preflight w \`.githooks/pre-push\`"
else
  add "- previous audit: none yet"
fi
add ""

add "**Do przeglądu agentem (warstwa głęboka):** punkty 1–25 z"
add "\`.claude/skills/weekly-audit/references/kontrola-glebokosci.md\`,"
add "skonkretyzowane dla CrossDeska w \`.claude/rules/audit.md\`."
add ""
add "---"
add ""

# ----- Write to log file (prepend section after header) --------------
if [ "${CROSSDESK_AUDIT_DRYRUN:-0}" = "1" ]; then
  echo "$SECTION"
  echo "DRY-RUN: $LOG nietknięty."
  exit 0
fi

if [ ! -f "$LOG" ]; then
  printf '# Audit Log\n\nNewest audit first. Format: each run dopisuje sekcję `## Audyt YYYY-MM-DD` na górę.\n\n' > "$LOG"
fi

TMP="$(mktemp)"
head -4 "$LOG" > "$TMP"
printf '%s' "$SECTION" >> "$TMP"
tail -n +5 "$LOG" >> "$TMP"
mv "$TMP" "$LOG"

echo "$SECTION"
echo "Wrote section to $LOG"
