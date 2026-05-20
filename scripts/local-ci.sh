#!/bin/bash
# scripts/local-ci.sh — run everything .github/workflows/ci.yml checks,
# locally, on demand. Sequential; aggregates failures so you see all
# problems in one pass instead of fix-rerun-fix-rerun.
#
# Usage:
#     bash scripts/local-ci.sh                 # full CI
#     RUN_MICROBENCH=1 bash scripts/local-ci.sh  # also run perf gate
#
# Exit code: 0 if all green, 1 if any job failed.

set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

export PATH="$PATH:$HOME/.cargo/bin:/usr/local/bin:/opt/homebrew/bin"

echo "════════════════════════════════════════════════"
echo " CrossDesk local CI (mirrors .github/workflows/ci.yml)"
echo "════════════════════════════════════════════════"

FAILED=()
PASSED=()
SKIPPED=()

run_job() {
    local name="$1"; shift
    echo ""
    echo "── ${name} ──"
    if "$@"; then
        echo "✅ ${name}"
        PASSED+=("$name")
    else
        echo "❌ ${name}"
        FAILED+=("$name")
    fi
}

skip_job() {
    local name="$1"
    local reason="$2"
    echo ""
    echo "── ${name} ── (skipped: ${reason})"
    SKIPPED+=("$name")
}

# ─── python-host job ────────────────────────────────────────────────
if [ -x host/.venv/bin/ruff ]; then
    run_job "python-host: ruff" bash -c "cd host && .venv/bin/ruff check src/"
else
    skip_job "python-host: ruff" "host/.venv not found"
fi

if [ -x host/.venv/bin/mypy ]; then
    # --python-version=3.12 matches the CI target. Newer dev-box pythons
    # would otherwise flag the tomli fallback `# type: ignore` blocks as
    # unused — they're legitimate for the 3.10/3.11 path.
    run_job "python-host: mypy --strict" bash -c "cd host && .venv/bin/mypy --strict --python-version=3.12 src/"
else
    skip_job "python-host: mypy" "host/.venv not found"
fi

run_job "python-host: mock-import gate" bash -c '
    bad=$(cd host && grep -rE "from crossdesk_host\.[^[:space:]]+\.mock import" src/ \
            | grep -v "src/crossdesk_host/integrations/keyring/__init__\.py:" \
            | grep -v "src/crossdesk_host/filesystem_ctl/__init__\.py:" \
            | grep -v "src/crossdesk_host/daemon\.py:" \
            || true)
    if [ -n "$bad" ]; then
        echo "production code imports a mock module outside the whitelist:"
        echo "$bad"
        exit 1
    fi
'

if [ -x host/.venv/bin/pytest ]; then
    run_job "python-host: pytest" bash -c "cd host && .venv/bin/pytest -q --no-header --ignore=benches/"
else
    skip_job "python-host: pytest" "host/.venv not found"
fi

# ─── rust-guest-cross-compile job ───────────────────────────────────
if command -v cargo >/dev/null 2>&1; then
    run_job "rust-guest: cargo check (native)" \
        bash -c "cd guest && cargo check --workspace --quiet"
    run_job "rust-guest: cargo test --features ipc-vsock/mock" \
        bash -c "cd guest && cargo test --workspace --features ipc-vsock/mock --quiet"
    run_job "rust-guest: cargo clippy -D warnings" \
        bash -c "cd guest && cargo clippy --workspace --quiet -- -D warnings"
    # Cross-compile check is the actual CI gate; skip on dev box without MinGW.
    if rustup target list --installed 2>/dev/null | grep -q x86_64-pc-windows-gnu; then
        run_job "rust-guest: cargo check (x86_64-pc-windows-gnu)" \
            bash -c "cd guest && cargo check --workspace --target x86_64-pc-windows-gnu --quiet"
    else
        skip_job "rust-guest: cargo check (windows-gnu)" "target not installed"
    fi
else
    skip_job "rust-guest: all" "cargo not found"
fi

# ─── rust-gui job ───────────────────────────────────────────────────
if command -v cargo >/dev/null 2>&1; then
    run_job "rust-gui: cargo check" bash -c "cd gui && cargo check --workspace --quiet"
    run_job "rust-gui: cargo test" bash -c "cd gui && cargo test --workspace --quiet"
fi

# qmllint — only fail if local qmllint is recent enough not to error on
# legitimate CXX-Qt-registered types. Per ci.yml comment, Qt 6.4.2 on
# Ubuntu 24.04 is too old; locally we may have 6.5+.
QMLLINT_BIN=""
for cand in qmllint /usr/lib/qt6/bin/qmllint /opt/homebrew/opt/qt/bin/qmllint; do
    if command -v "$cand" >/dev/null 2>&1 || [ -x "$cand" ]; then
        QMLLINT_BIN="$cand"
        break
    fi
done
if [ -n "$QMLLINT_BIN" ] && [ -d gui/crates/crossdesk-gui/qml ]; then
    run_job "rust-gui: qmllint" bash -c "
        cd gui && find crates/crossdesk-gui/qml -name '*.qml' -print0 \
            | xargs -0 -n 1 '$QMLLINT_BIN'"
else
    skip_job "rust-gui: qmllint" "qmllint not found"
fi

# ─── proto job ──────────────────────────────────────────────────────
if command -v buf >/dev/null 2>&1; then
    run_job "proto: buf lint" bash -c "cd proto && buf lint"
    run_job "proto: buf format --diff" bash -c "cd proto && buf format --diff --exit-code"
else
    skip_job "proto: buf" "buf not installed"
fi

# ─── i18n-extract job ───────────────────────────────────────────────
if command -v xgettext >/dev/null 2>&1 && [ -x scripts/i18n.sh ]; then
    run_job "i18n: .pot extraction sync" bash -c '
        bash scripts/i18n.sh extract >/dev/null 2>&1 || true
        git diff --exit-code -- \
            i18n/crossdesk-host.pot \
            gui/crates/crossdesk-gui/i18n/crossdesk_en.ts \
            gui/crates/crossdesk-gui/i18n/crossdesk_pl.ts
    '
else
    skip_job "i18n: extraction" "xgettext or scripts/i18n.sh missing"
fi

# ─── microbench job (opt-in, ~30s) ──────────────────────────────────
if [ "${RUN_MICROBENCH:-0}" = "1" ] && [ -x host/.venv/bin/pytest ]; then
    run_job "microbench: bench run + check" bash -c "
        cd host && .venv/bin/pytest benches/ \
            --benchmark-only --benchmark-json=bench-results.json -q \
        && cd .. && python3 scripts/bench_check.py \
            --baseline .github/perf-baselines.json \
            --results host/bench-results.json
    "
else
    skip_job "microbench" "set RUN_MICROBENCH=1 to enable"
fi

# ─── Summary ────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════"
echo " Summary"
echo "════════════════════════════════════════════════"
echo " ✅ passed:  ${#PASSED[@]}"
echo " ❌ failed:  ${#FAILED[@]}"
echo " ⏭  skipped: ${#SKIPPED[@]}"

if [ ${#FAILED[@]} -eq 0 ]; then
    echo ""
    echo "✅ Local CI green. Safe to push."
    exit 0
else
    echo ""
    echo "❌ Failed jobs:"
    for j in "${FAILED[@]}"; do
        echo "   - $j"
    done
    exit 1
fi
