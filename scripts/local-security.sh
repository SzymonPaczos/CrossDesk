#!/bin/bash
# scripts/local-security.sh — local replacement for
# .github/workflows/security.yml (auto-triggers removed 2026-05-20
# to stop GitHub Actions billing).
#
# Runs the same scanners against the developer's machine. SARIF
# uploads (bandit, semgrep, CodeQL) are GitHub-hosted-only; for those
# trigger the GH workflow manually via the Actions UI before a
# release.
#
# Usage:
#     bash scripts/local-security.sh
#
# Exit code: 0 if all green, 1 if any scanner found something.

set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

export PATH="$PATH:$HOME/.cargo/bin:/usr/local/bin:/opt/homebrew/bin"

echo "════════════════════════════════════════════════"
echo " CrossDesk local security audit"
echo " (mirrors .github/workflows/security.yml)"
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

# ─── secrets: gitleaks ──────────────────────────────────────────────
if command -v gitleaks >/dev/null 2>&1; then
    run_job "gitleaks (history scan)" \
        bash -c "gitleaks detect --source . --no-banner --redact --exit-code 1"
else
    skip_job "gitleaks" "not installed (https://github.com/gitleaks/gitleaks)"
fi

# ─── python-security: pip-audit + bandit ────────────────────────────
if [ -x host/.venv/bin/python ]; then
    if command -v pip-audit >/dev/null 2>&1 || [ -x /tmp/audit-venv/bin/pip-audit ]; then
        PIP_AUDIT="$(command -v pip-audit || echo /tmp/audit-venv/bin/pip-audit)"
        run_job "pip-audit (Python deps)" bash -c "
            cd host && '$PIP_AUDIT' \
                -r <(.venv/bin/pip freeze 2>/dev/null \
                    | grep -v '^-e \|^crossdesk-host=')
        "
    else
        skip_job "pip-audit" "not installed (pip install pip-audit)"
    fi

    if command -v bandit >/dev/null 2>&1 || [ -x /tmp/audit-venv/bin/bandit ]; then
        BANDIT="$(command -v bandit || echo /tmp/audit-venv/bin/bandit)"
        # -ll: Low severity floor (matches CI). Config in
        # host/pyproject.toml [tool.bandit] handles the subprocess
        # noise whitelist.
        run_job "bandit (Python SAST)" bash -c "
            '$BANDIT' -c host/pyproject.toml -r host/src -ll --quiet
        "
    else
        skip_job "bandit" "not installed (pip install bandit)"
    fi
else
    skip_job "python-security: all" "host/.venv not found"
fi

# ─── rust-security: cargo audit + cargo deny ────────────────────────
if command -v cargo-audit >/dev/null 2>&1; then
    run_job "cargo audit (guest)" bash -c "cd guest && cargo audit --deny warnings"
    run_job "cargo audit (gui)" bash -c "cd gui && cargo audit --deny warnings"
else
    skip_job "cargo audit" "not installed (cargo install cargo-audit)"
fi

if command -v cargo-deny >/dev/null 2>&1; then
    run_job "cargo deny (guest)" bash -c "cd guest && cargo deny check --hide-inclusion-graph"
    run_job "cargo deny (gui)" bash -c "cd gui && cargo deny check --hide-inclusion-graph"
else
    skip_job "cargo deny" "not installed (cargo install cargo-deny)"
fi

# ─── semgrep + CodeQL: GH-hosted only ───────────────────────────────
skip_job "semgrep + CodeQL" \
    "SARIF upload needs GH security tab — run security.yml manually before release"

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
    echo "✅ Local security audit green."
    if [ ${#SKIPPED[@]} -gt 0 ]; then
        echo "   ${#SKIPPED[@]} scanner(s) skipped — install for full coverage."
    fi
    exit 0
else
    echo ""
    echo "❌ Failed scanners:"
    for j in "${FAILED[@]}"; do
        echo "   - $j"
    done
    exit 1
fi
