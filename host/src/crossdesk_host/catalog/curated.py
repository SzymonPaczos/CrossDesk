"""Curated tier loader — parses ``infra/apps/curated.toml``."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

if sys.version_info >= (3, 11):
    import tomllib as _tomllib  # type: ignore[import-not-found,unused-ignore]
else:  # pragma: no cover
    import tomli as _tomllib  # type: ignore[import-not-found]


@dataclass(frozen=True)
class CuratedApp:
    id: str
    display_name: str
    display_name_pl: Optional[str]
    executable: str
    mime_types: List[str] = field(default_factory=list)
    category: str = "Other"
    icon: str = ""
    stars: int = 0
    known_issues: Optional[str] = None

    def localized_name(self, locale: str) -> str:
        if locale.startswith("pl") and self.display_name_pl:
            return self.display_name_pl
        return self.display_name


def load_curated(path: Optional[Path] = None) -> List[CuratedApp]:
    """Load curated entries from a TOML file. Defaults to the bundled
    ``infra/apps/curated.toml`` resolved relative to the repo root.

    Returns an empty list if the file is missing — callers fall back
    to the discovered tier without crashing.
    """
    if path is None:
        path = _bundled_path()
    if not path.exists():
        return []
    with path.open("rb") as f:
        data = _tomllib.load(f)
    apps: List[CuratedApp] = []
    for raw in data.get("app", []):
        if not isinstance(raw, dict) or "id" not in raw:
            continue
        apps.append(
            CuratedApp(
                id=str(raw["id"]),
                display_name=str(raw.get("display_name", raw["id"])),
                display_name_pl=raw.get("display_name_pl"),
                executable=str(raw.get("executable", "")),
                mime_types=list(raw.get("mime_types") or []),
                category=str(raw.get("category", "Other")),
                icon=str(raw.get("icon", "")),
                stars=int(raw.get("stars", 0)),
                known_issues=raw.get("known_issues"),
            )
        )
    return apps


def _bundled_path() -> Path:
    # Resolve relative to the package's repo-root layout.
    # ``crossdesk_host.catalog`` lives at host/src/crossdesk_host/catalog/
    # so going up four levels lands on the repo root.
    here = Path(__file__).resolve()
    return here.parents[4] / "infra" / "apps" / "curated.toml"
