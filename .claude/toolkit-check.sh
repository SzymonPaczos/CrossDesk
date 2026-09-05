#!/usr/bin/env bash
# Resolve only the configured or established local clone locations.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -n "${CROSSDESK_TOOLKIT_ROOT:-}" ]; then
    TOOLKIT_PATH="$CROSSDESK_TOOLKIT_ROOT"
elif [ -f "$REPO_ROOT/../claude-toolkit/scripts/toolkit-sync.sh" ]; then
    TOOLKIT_PATH="$REPO_ROOT/../claude-toolkit"
else
    TOOLKIT_PATH="$HOME/Projects/dev/claude-toolkit"
fi
if [ ! -f "$TOOLKIT_PATH/scripts/toolkit-sync.sh" ]; then
    echo "Toolkit preflight blocked: set CROSSDESK_TOOLKIT_ROOT to the local clone." >&2
    exit 2
fi
exec bash "$TOOLKIT_PATH/scripts/toolkit-sync.sh" check "$REPO_ROOT"
