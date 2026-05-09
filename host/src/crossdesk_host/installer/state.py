"""Atomic install state machine.

Persists per-step progress to ``~/.local/state/crossdesk/install.state.json``
so a partially-installed system can resume from the next un-completed
step instead of rerunning everything (downloading the ISO again, etc).

Atomicity: each save writes to a sibling ``.tmp`` file, fsyncs it,
then ``os.rename`` swaps it into place. ``rename`` is atomic on the
same filesystem on POSIX, which is exactly the property we need —
the on-disk file either reflects the previous state OR the new one,
never an interleaved partial.

The set of steps is open-ended: ``Step`` is just a string so the
installer can add new phases (download_iso, create_domain, run_unattend,
register_agent, post_install_tweaks, …) without churning the state
schema.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

_SCHEMA_VERSION = 1


def _default_state_file() -> Path:
    # Resolve at call time, not at import — tests monkey-patch ``HOME`` and
    # expect the new value to take effect; baking ``Path.home()`` into a
    # module constant would freeze the path at first import.
    return Path.home() / ".local" / "state" / "crossdesk" / "install.state.json"


@dataclass
class InstallState:
    """In-memory snapshot of the install progress.

    Each entry in ``steps`` maps a step name to a status string
    (``pending``, ``running``, ``done``, ``failed``). The order of
    insertion is preserved so callers can iterate steps in declaration
    order via ``steps_in_order()``.
    """

    schema_version: int = _SCHEMA_VERSION
    steps: Dict[str, str] = field(default_factory=dict)
    last_error: Optional[str] = None

    def mark(self, step: str, status: str) -> None:
        if status not in ("pending", "running", "done", "failed"):
            raise ValueError(f"unknown status {status!r}")
        self.steps[step] = status
        if status == "done":
            self.last_error = None

    def is_done(self, step: str) -> bool:
        return self.steps.get(step) == "done"

    def first_unfinished(self) -> Optional[str]:
        for step, status in self.steps.items():
            if status != "done":
                return step
        return None

    def steps_in_order(self) -> list[str]:
        return list(self.steps.keys())


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def save(state: InstallState, path: Optional[Path] = None) -> None:
    if path is None:
        path = _default_state_file()
    payload = json.dumps(
        {
            "schema_version": state.schema_version,
            "steps": state.steps,
            "last_error": state.last_error,
        },
        indent=2,
        sort_keys=False,
    )
    _atomic_write(path, payload)


def load(path: Optional[Path] = None) -> InstallState:
    if path is None:
        path = _default_state_file()
    if not path.exists():
        return InstallState()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError(
            f"install state schema {data.get('schema_version')!r} "
            f"!= expected {_SCHEMA_VERSION}; remove {path} to start fresh"
        )
    state = InstallState(
        schema_version=data["schema_version"],
        last_error=data.get("last_error"),
    )
    state.steps = dict(data.get("steps", {}))
    return state


def default_state_file() -> Path:
    return _default_state_file()
