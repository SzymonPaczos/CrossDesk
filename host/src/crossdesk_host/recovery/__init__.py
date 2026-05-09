"""Post-HARD_DESTROY recovery diagnostics (Phase 9 / Week 37).

When the heartbeat FSM forces ``HARD_DESTROY`` we capture a snapshot
of:

- the FSM transition trail leading to the destroy,
- the last RAIL events (which apps had open windows),
- active JIT mounts (which files might lose unsaved state),
- the last 200 log lines,
- a summary suggesting probable cause + next steps.

Snapshots land at ``~/.local/state/crossdesk/recovery/<timestamp>/``
and surface in the Manager's Dashboard as a dismissible card. The
snapshot also forms the seed of a diagnostic bundle export.
"""

from crossdesk_host.recovery.bundle import export_bundle
from crossdesk_host.recovery.snapshot import (
    RecoverySnapshot,
    Suggestion,
    capture_snapshot,
    list_snapshots,
    suggest_cause,
)

__all__ = [
    "RecoverySnapshot",
    "Suggestion",
    "capture_snapshot",
    "export_bundle",
    "list_snapshots",
    "suggest_cause",
]
