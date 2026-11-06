#!/usr/bin/env bash
# Run from the main checkout root. The helper holds the frontend class lock,
# then a heavy slot, and stops the git process group before releasing either.
# Hooks must verify inherited tokens instead of acquiring the same lock again.
set -euo pipefail
GATE_HELPER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/heavy-slot.py"
export GATE_HELPER
exec python3 -I "$GATE_HELPER" push "$@"
