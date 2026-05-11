"""User-facing settings persisted to ``~/.config/crossdesk/settings.toml``.

Mirror of the ``Settings`` proto message in mgmt.proto, plus a tiny
TOML reader/writer with the same atomic-rename semantics as the
install state machine. Defaults match what install_cmd assumes.

Why a separate module from credentials.py: credentials carry secrets
(0600 file mode); settings are user preferences (default umask). They
also tend to evolve at different cadences — settings grow new fields,
credentials stay stable.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

if sys.version_info >= (3, 11):
    import tomllib as _tomllib  # type: ignore[import-not-found,unused-ignore]
else:  # pragma: no cover
    import tomli as _tomllib  # type: ignore[import-not-found]


def _default_path() -> Path:
    return Path.home() / ".config" / "crossdesk" / "settings.toml"


@dataclass
class Settings:
    """Snapshot of user preferences. Field names match ``mgmt.proto``."""

    language: str = "auto"
    theme: str = "system"
    telemetry_enabled: bool = False
    keyring_enabled: bool = True
    lean_mode: bool = False
    network_mode: str = "nat"
    hidpi_scale: int = 0  # auto-detect
    multi_monitor_placement: bool = True

    auto_suspend_on_idle: bool = False
    auto_suspend_after_seconds: int = 1800
    auto_suspend_on_lid: bool = False
    auto_resume_on_launch: bool = True

    miss_threshold: int = 3
    recovery_ticks: int = 3
    backoff_initial_seconds: float = 5.0
    max_soft_attempts: int = 3


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _to_toml(s: Settings) -> str:
    lines = []
    for key, value in asdict(s).items():
        if isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
        else:
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
    return "\n".join(lines) + "\n"


def save(settings: Settings, path: Optional[Path] = None) -> None:
    if path is None:
        path = _default_path()
    _atomic_write(path, _to_toml(settings))


def load(path: Optional[Path] = None) -> Settings:
    if path is None:
        path = _default_path()
    if not path.exists():
        return Settings()
    with path.open("rb") as f:
        data: Dict[str, Any] = _tomllib.load(f)
    # Ignore unknown keys silently — forward compat across upgrades.
    s = Settings()
    for key in s.__dataclass_fields__:
        if key in data:
            setattr(s, key, data[key])
    return s


def default_path() -> Path:
    return _default_path()


def clamp(s: Settings) -> Settings:
    """Return a copy with values clamped to legal ranges. Used by the
    UpdateSettings RPC so the GUI sees what landed if anything was
    out of bounds."""
    if s.hidpi_scale not in (0, 100, 140, 180):
        s.hidpi_scale = 0
    if s.theme not in ("system", "light", "dark"):
        s.theme = "system"
    if s.network_mode not in ("nat", "bridged"):
        s.network_mode = "nat"
    if s.miss_threshold < 1:
        s.miss_threshold = 1
    if s.recovery_ticks < 1:
        s.recovery_ticks = 1
    if s.max_soft_attempts < 1:
        s.max_soft_attempts = 1
    if s.backoff_initial_seconds < 0.1:
        s.backoff_initial_seconds = 0.1
    if s.auto_suspend_after_seconds < 60:
        s.auto_suspend_after_seconds = 60
    return s
