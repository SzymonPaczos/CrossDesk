#!/usr/bin/env bash
# Jeden builder: watchdog grupy procesów, raport JSON i niezależne bramki.
# Użycie: CODEX_GATE_SPEC=<spec.json> codex-builder.sh <worktree> <brief.md>
#          <raport.json poza worktree> [--model <model> | --color <tryb>]
# Szczegóły i ograniczenia: README.md w tym katalogu.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${CODEX_PYTHON:-python3}" "$here/builder-runner.py" "$@"
