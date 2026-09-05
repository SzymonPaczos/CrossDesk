#!/usr/bin/env bash
# audit.sh — cotygodniowy audyt CrossDesk (warstwa statyczna).
#
# Dopisuje sekcję `## Audyt YYYY-MM-DD` na górę `.claude/audit-log.md`.
# Cele:
# - Liczby. Brak osądu LLM tutaj (warstwa głęboka idzie osobno).
# - Tylko narzędzia z CI (nic nie instaluje). Brakujące narzędzie =
#   wpis `n/a`, nie crash.
# - Idempotentny: można uruchomić wielokrotnie tego samego dnia bez
#   psucia poprzednich wpisów.
#
# Stack pokryty: Python host (ruff, mypy --strict, pytest, bandit) +
# Rust guest/gui (cargo check, clippy, deny, audit) + proto (buf
# lint+format) + QML (qmllint) + sec (gitleaks worktree) + drift
# (Last Updated w architecture.md vs git) + decisions count.
#
# Procedura cotygodniowa (warstwa głęboka) → .claude/rules/audit.md.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Do not produce a fresh audit header using an outdated checklist.
bash "$REPO_ROOT/.claude/toolkit-check.sh" || exit $?

# Python tooling (ruff/mypy/pytest/bandit) lives in host/.venv, not on
# PATH — without this the whole Python section reported "n/a" (audit
# 2026-06-12). Same venv-first convention as .githooks/pre-commit.
if [ -d "$REPO_ROOT/host/.venv/bin" ]; then
  PATH="$REPO_ROOT/host/.venv/bin:$PATH"
fi

LOG="$REPO_ROOT/.claude/audit-log.md"
DATE="$(date '+%Y-%m-%d')"
SECTION=""

add() { SECTION+="$1"$'\n'; }
has() { command -v "$1" >/dev/null 2>&1; }
# grep -c already prints "0" on empty input (and exits 1); swallow the exit
# rather than echo a second "0" (which produced a stray line on Linux).
count_lines() { grep -cE '^' 2>/dev/null || true; }
# Parse YYYY-MM-DD → epoch seconds, portable across GNU (Linux, `date -d`)
# and BSD (macOS, `date -j -f`). Falls back to 0 if neither parses.
to_epoch() { date -d "$1" +%s 2>/dev/null || date -j -f '%Y-%m-%d' "$1" +%s 2>/dev/null || echo 0; }

# ----- Header --------------------------------------------------------
add "## Audyt $DATE"
add ""
add "**Git:** \`$(git rev-parse --short HEAD 2>/dev/null || echo unknown)\` on \`$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)\`"
add ""
add "### Warstwa statyczna (automat)"
add ""

# ----- Python host ---------------------------------------------------
add "**Python (\`host/\`)**"
add ""
if [ -d host ]; then
  if has ruff; then
    RUFF_HITS="$(cd host && ruff check src/ tests/ 2>/dev/null | grep -cE '^[^[:space:]].*:[0-9]+' || true)"
    add "- ruff findings: ${RUFF_HITS:-0}"
  else
    add "- ruff: n/a (not on PATH)"
  fi
  if has mypy; then
    MYPY_ERRS="$(cd host && mypy --strict src/ 2>&1 | grep -cE '^[^[:space:]].*: error:' || true)"
    MYPY_FILES="$(cd host && mypy --strict src/ 2>&1 | grep -oE 'in [0-9]+ source files' | grep -oE '[0-9]+' || true)"
    add "- mypy --strict errors: ${MYPY_ERRS:-0} (across ${MYPY_FILES:-?} files)"
  else
    add "- mypy: n/a"
  fi
  if has pytest; then
    PYTEST_COLLECT="$(cd host && pytest --collect-only -q 2>/dev/null | tail -3 | grep -oE '[0-9]+ tests? collected' | grep -oE '^[0-9]+' || true)"
    add "- pytest collected: ${PYTEST_COLLECT:-?}"
  else
    add "- pytest: n/a"
  fi
  if has bandit; then
    BANDIT_HIGH="$(cd host && bandit -ll -r src/ 2>/dev/null | grep -cE '^>> Issue.*Severity: (High|Medium)' || true)"
    add "- bandit medium/high: ${BANDIT_HIGH:-0}"
  else
    add "- bandit: n/a"
  fi
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
    CHECK_WARN="$(cd "$crate" && cargo check --workspace --message-format=short 2>&1 | grep -cE '^warning:' || true)"
    add "- $crate cargo check warnings: ${CHECK_WARN:-0}"
    CLIPPY_ERR="$(cd "$crate" && cargo clippy --workspace --message-format=short 2>&1 -- -D warnings | grep -cE '^error:' || true)"
    add "- $crate clippy errors (-D warnings): ${CLIPPY_ERR:-0}"
  elif [ -d "$crate" ]; then
    add "- $crate: cargo n/a"
  fi
done
if has cargo-deny; then
  for crate in guest gui; do
    if [ -f "$crate/deny.toml" ]; then
      DENY_VIOL="$(cd "$crate" && cargo deny check 2>&1 | grep -cE '^(error|warning)\[' || true)"
      add "- $crate cargo-deny issues: ${DENY_VIOL:-0}"
    fi
  done
else
  add "- cargo-deny: n/a"
fi
if has cargo-audit; then
  for crate in guest gui; do
    if [ -d "$crate" ]; then
      AUDIT_VULN="$(cd "$crate" && cargo audit 2>&1 | grep -cE '^Vulnerability:' || true)"
      add "- $crate cargo-audit vulns: ${AUDIT_VULN:-0}"
    fi
  done
else
  add "- cargo-audit: n/a"
fi
add ""

# ----- Proto ---------------------------------------------------------
add "**Proto (\`proto/\`)**"
add ""
if has buf; then
  BUF_LINT="$(cd proto && buf lint 2>&1 | grep -cE '^[^[:space:]].*:[0-9]+' || true)"
  add "- buf lint findings: ${BUF_LINT:-0}"
  BUF_FMT="$(cd proto && buf format --diff 2>&1 | grep -cE '^(\+\+\+|---)' || true)"
  add "- buf format diff lines: ${BUF_FMT:-0}"
else
  add "- buf: n/a"
fi
PROTO_FILES="$(find proto -name '*.proto' 2>/dev/null | count_lines)"
add "- .proto files: ${PROTO_FILES:-0}"
add ""

# ----- QML -----------------------------------------------------------
add "**QML (\`gui/\`)**"
add ""
if has qmllint; then
  QML_WARN="$(find gui -name '*.qml' -print0 2>/dev/null | xargs -0 qmllint 2>&1 | grep -cE '^Warning:' || true)"
  add "- qmllint warnings: ${QML_WARN:-0}"
else
  add "- qmllint: n/a"
fi
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
  # grep -c always prints the count on stdout AND exits non-zero when
  # the count is 0 — `|| echo 0` doubles up the "0\n0"; use `|| true`.
  DEC_META="$(grep -cE '^## DEC-META-[0-9]+' .claude/rules/decisions.md 2>/dev/null || true)"
  add "- META decisions (status: aktywna): ${DEC_META:-0}"
fi
if [ -f docs/DECISIONS.md ]; then
  DEC_NNNN="$(grep -cE '^## DEC-[0-9]+' docs/DECISIONS.md 2>/dev/null || true)"
  add "- ADR DEC-NNNN total: ${DEC_NNNN:-0}"
fi
add ""

# ----- Security ------------------------------------------------------
add "**Security**"
add ""
if has gitleaks; then
  LEAKS="$(gitleaks detect --no-banner --no-git --source . 2>&1 | grep -cE 'Finding:' 2>/dev/null || true)"
  add "- gitleaks worktree findings: ${LEAKS:-0}"
else
  add "- gitleaks: n/a (use \`CROSSDESK_FULL_AUDIT=1 git push\` for history scan)"
fi
add ""

# ----- Audit cadence -------------------------------------------------
add "**Cadence**"
add ""
if [ -f "$LOG" ]; then
  LAST_AUDIT="$(grep -oE '^## Audyt [0-9-]+' "$LOG" | head -2 | tail -1 | grep -oE '[0-9-]+' || true)"
  if [ -n "${LAST_AUDIT:-}" ]; then
    LAST_AGE_DAYS="$(( ($(date +%s) - $(to_epoch "$LAST_AUDIT")) / 86400 ))"
    add "- previous audit: $LAST_AUDIT (${LAST_AGE_DAYS}d ago)"
  else
    add "- previous audit: none yet"
  fi
else
  add "- previous audit: log file does not exist yet (this run creates it)"
fi
add ""

add "**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z \`.claude/rules/decisions.md\` + \`docs/DECISIONS.md\`, MCP/skills. Procedura: \`.claude/rules/audit.md\`."
add ""
add "---"
add ""

# ----- Write to log file (prepend section after header) --------------
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
