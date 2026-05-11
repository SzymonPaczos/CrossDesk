"""User-added apps tier — `+ Add custom .exe` from the GUI."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class UserApp:
    id: str
    display_name: str
    executable: str
    mime_types: List[str] = field(default_factory=list)
    category: str = "User"
    icon: str = ""


def _default_dir() -> Path:
    return Path.home() / ".local" / "share" / "crossdesk" / "apps" / "user"


def save_user_app(app: UserApp, directory: Optional[Path] = None) -> Path:
    """Persist a user-added app entry as ``<id>.json`` under
    ``~/.local/share/crossdesk/apps/user/`` (or supplied dir)."""
    target_dir = directory or _default_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{app.id}.json"
    payload = json.dumps(asdict(app), indent=2)

    fd, tmp = tempfile.mkstemp(
        dir=str(target_dir), prefix=target.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp, target)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    return target


def load_user_apps(directory: Optional[Path] = None) -> List[UserApp]:
    target_dir = directory or _default_dir()
    if not target_dir.exists():
        return []
    out: List[UserApp] = []
    for entry in sorted(target_dir.glob("*.json")):
        try:
            with entry.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        try:
            out.append(
                UserApp(
                    id=str(data["id"]),
                    display_name=str(data.get("display_name", data["id"])),
                    executable=str(data.get("executable", "")),
                    mime_types=list(data.get("mime_types") or []),
                    category=str(data.get("category", "User")),
                    icon=str(data.get("icon", "")),
                )
            )
        except KeyError:
            continue
    return out
