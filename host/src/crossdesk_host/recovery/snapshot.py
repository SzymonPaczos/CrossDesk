"""Recovery snapshot — frozen view of the system at HARD_DESTROY."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import contextlib


@dataclass(frozen=True)
class Suggestion:
    title: str
    detail: str
    action_label: Optional[str] = None  # GUI surfaces a button if set


@dataclass(frozen=True)
class RecoverySnapshot:
    timestamp: str
    fsm_transitions: List[str] = field(default_factory=list)
    rail_apps_at_destroy: List[str] = field(default_factory=list)
    active_mounts_at_destroy: List[str] = field(default_factory=list)
    log_tail: List[str] = field(default_factory=list)
    suggestions: List[Suggestion] = field(default_factory=list)
    soft_attempts_before_destroy: int = 0
    final_miss_count: int = 0


def _default_root() -> Path:
    return Path.home() / ".local" / "state" / "crossdesk" / "recovery"


def capture_snapshot(
    fsm_transitions: List[str],
    rail_apps: List[str],
    active_mounts: List[str],
    log_tail: List[str],
    soft_attempts: int,
    final_miss_count: int,
    root: Optional[Path] = None,
) -> Path:
    """Persist a snapshot under
    ``~/.local/state/crossdesk/recovery/<timestamp>/snapshot.json``.

    Returns the directory it was written to. The companion log_tail
    is stored as a separate file so the bundle exporter can grow
    different artefacts without rewriting the JSON.
    """
    root = root or _default_root()
    when = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target_dir = root / when
    target_dir.mkdir(parents=True, exist_ok=True)

    snapshot = RecoverySnapshot(
        timestamp=when,
        fsm_transitions=list(fsm_transitions),
        rail_apps_at_destroy=list(rail_apps),
        active_mounts_at_destroy=list(active_mounts),
        log_tail=list(log_tail[-200:]),
        suggestions=suggest_cause(rail_apps, soft_attempts, final_miss_count),
        soft_attempts_before_destroy=soft_attempts,
        final_miss_count=final_miss_count,
    )
    payload = json.dumps(asdict(snapshot), indent=2)
    _atomic_write(target_dir / "snapshot.json", payload)

    if log_tail:
        _atomic_write(target_dir / "log_tail.txt", "\n".join(log_tail[-1000:]))

    return target_dir


def _atomic_write(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def suggest_cause(
    rail_apps: List[str], soft_attempts: int, final_miss_count: int
) -> List[Suggestion]:
    """Heuristic explanations the GUI surfaces above the raw snapshot.

    These are best-effort guidance, not authoritative diagnoses. The
    full FSM trail is always available in the snapshot for users who
    want to dig in.
    """
    out: List[Suggestion] = []

    if final_miss_count >= 11 and soft_attempts >= 3:
        out.append(
            Suggestion(
                title="Sustained heartbeat silence",
                detail=(
                    "The guest stopped responding to heartbeats for at least "
                    f"{final_miss_count} consecutive ticks despite "
                    f"{soft_attempts} graceful-shutdown attempts. Most likely "
                    "cause: out-of-memory, disk-full, or a blocking driver."
                ),
                action_label="Increase RAM allocation",
            )
        )

    if any(
        "Photoshop" in name or "Premiere" in name or "AutoCAD" in name
        for name in rail_apps
    ):
        out.append(
            Suggestion(
                title="GPU-heavy app was running",
                detail=(
                    "A GPU-heavy Windows app was active. Software rendering "
                    "is usable but can hit OOM under load. Consider enabling "
                    "GPU passthrough (Phase 4.5) for these workloads."
                ),
                action_label="Enable GPU passthrough",
            )
        )

    if not out:
        out.append(
            Suggestion(
                title="Inspect the FSM transition trail",
                detail=(
                    "No automatic suggestions matched. The full transition "
                    "history and recent log lines are bundled with this "
                    "snapshot — useful when filing a bug report."
                ),
                action_label="Export diagnostic bundle",
            )
        )

    return out


def list_snapshots(root: Optional[Path] = None) -> List[Path]:
    """Return every snapshot directory, newest first."""
    root = root or _default_root()
    if not root.exists():
        return []
    return sorted(
        (p for p in root.iterdir() if p.is_dir() and (p / "snapshot.json").exists()),
        reverse=True,
    )
