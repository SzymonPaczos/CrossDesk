"""AppEntry — the typed representation of a single catalog entry.

This dataclass is the canonical in-memory form of an ``[[apps]]`` block
from ``catalog/apps.toml``.  It is intentionally separate from
:class:`~crossdesk_host.catalog.curated.CuratedApp` (which carries
CrossDesk-specific metadata like compatibility stars and known_issues)
so the two can evolve independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class AppEntry:
    """One app from the TOML catalog.

    All string fields are non-empty by construction — the loader skips
    entries that violate any of those invariants.
    """

    app_id: str
    """Unique kebab-case slug, e.g. ``"word"``."""

    name: str
    """Human-readable display name, e.g. ``"Microsoft Word"``."""

    win_executable: str
    """Full Windows path to the executable, e.g.
    ``"C:\\\\Program Files\\\\...\\\\WINWORD.EXE"``."""

    categories: List[str] = field(default_factory=list)
    """Freedesktop categories, e.g. ``["Office"]``."""

    mime_types: List[str] = field(default_factory=list)
    """MIME types this app handles, e.g.
    ``["application/msword", "application/vnd.openxmlformats-..."]``."""

    icon: str = ""
    """Icon name (freedesktop or vendor-specific) or empty string."""
