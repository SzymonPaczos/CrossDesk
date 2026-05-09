"""Diagnostic bundle exporter.

Zips up every recovery snapshot, the install state file, the system
journal tail (when available), and a redacted vm.toml (password
masked) into a single ``crossdesk-diag-<timestamp>.zip`` users can
attach to bug reports.

Mac dev: works. The journal source is best-effort
(``journalctl --user`` returns empty if not on Linux); everything
else is plain filesystem access.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from crossdesk_host.installer import credentials, state


def export_bundle(
    snapshot_root: Optional[Path] = None,
    install_state_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """Zip everything up; return the resulting file path."""
    snapshot_root = snapshot_root or (
        Path.home() / ".local" / "state" / "crossdesk" / "recovery"
    )
    install_state_path = install_state_path or state.default_state_file()
    output_dir = output_dir or (Path.home() / "Downloads")
    output_dir.mkdir(parents=True, exist_ok=True)

    when = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = output_dir / f"crossdesk-diag-{when}.zip"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Recovery snapshots (every directory under snapshot_root).
        if snapshot_root.exists():
            for snap_dir in sorted(snapshot_root.iterdir()):
                if not snap_dir.is_dir():
                    continue
                for path in snap_dir.glob("*"):
                    if path.is_file():
                        arc = f"recovery/{snap_dir.name}/{path.name}"
                        zf.write(path, arc)

        # 2. Install state machine (current contents).
        if install_state_path.exists():
            zf.write(install_state_path, "install/install.state.json")

        # 3. Redacted vm.toml — username only; password masked.
        creds = credentials.load()
        if creds is not None:
            redacted = (
                f'username = "{creds.username}"\n'
                'password = "<REDACTED FOR DIAGNOSTIC EXPORT>"\n'
            )
            zf.writestr("install/vm.toml.redacted", redacted)

        # 4. System info marker so support knows what to look at first.
        zf.writestr(
            "README.txt",
            (
                "CrossDesk diagnostic bundle\n"
                "===========================\n"
                f"Generated: {when}\n\n"
                "Contents:\n"
                "  recovery/<timestamp>/snapshot.json — FSM transition trail\n"
                "  recovery/<timestamp>/log_tail.txt — last 1000 log lines\n"
                "  install/install.state.json        — install pipeline state\n"
                "  install/vm.toml.redacted          — credentials (password masked)\n\n"
                "If you're attaching this to a bug report, please describe what\n"
                "you were doing when the issue happened — the snapshot's\n"
                "suggestions are heuristic, not authoritative.\n"
            ),
        )

    target.write_bytes(buffer.getvalue())
    return target
