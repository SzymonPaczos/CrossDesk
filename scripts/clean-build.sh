#!/usr/bin/env bash
# Reclaim disk space by clearing every CrossDesk-side build cache.
#
# Safe to run any time. Next build will rebuild from scratch (slower until
# Cargo and pip rehydrate). Does NOT clear ~/.cargo/registry, sccache, or
# system package caches — only this project's local artifacts.
#
# Usage:
#   ./scripts/clean-build.sh           # show sizes, then clean
#   ./scripts/clean-build.sh --dry-run # show sizes only, do not clean
set -euo pipefail

cd "$(dirname "$0")/.."
DRY_RUN=${1:-}

show_size() {
    local path=$1
    if [[ -e $path ]]; then
        local size
        size=$(du -sh "$path" 2>/dev/null | cut -f1)
        printf "  %-50s %s\n" "$path" "$size"
    fi
}

echo "Sizes before clean:"
show_size guest/target
show_size gui/target
show_size host/.venv
show_size host/.mypy_cache
show_size host/.pytest_cache
show_size host/.ruff_cache
echo

if [[ $DRY_RUN == "--dry-run" ]]; then
    echo "Dry run — no changes."
    exit 0
fi

echo "Cleaning Rust target/..."
[[ -d guest/target ]] && (cd guest && cargo clean) || true
[[ -d gui/target ]] && (cd gui && cargo clean) || true

echo "Cleaning Python caches..."
find . -path ./third_party -prune -o -type d \( \
    -name __pycache__ -o \
    -name .mypy_cache -o \
    -name .pytest_cache -o \
    -name .ruff_cache \
\) -print -exec rm -rf {} + 2>/dev/null || true

# .venv intentionally left alone — recreating it costs minutes.
# Run `rm -rf host/.venv` manually if you really want to.

echo
echo "Done. Run 'cargo build' (in guest/ or gui/) and"
echo "'pip install -e .[mock,dev]' (in host/) to rebuild."
