"""Compatibility ratings — display-only at v1.0.

Each app has a curated star rating (0-5) baked into ``curated.toml``.
Per-user community ratings (the post-1.0 "submission flow") aggregate
into a separate dataset; here we just load whatever JSON file the
distribution shipped with the latest catalog refresh and present it
alongside the curated stars.

Phase 9 polish hooks the daemon's ``ratings.json`` updater into a
periodic refresh; today the file is static.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class Rating:
    app_id: str
    stars: float  # community average, 0.0-5.0
    sample_size: int = 0
    notes: str = ""


def _default_path() -> Path:
    return Path.home() / ".local" / "share" / "crossdesk" / "ratings.json"


def load_ratings(path: Optional[Path] = None) -> Dict[str, Rating]:
    p = path or _default_path()
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Rating] = {}
    for app_id, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        try:
            out[app_id] = Rating(
                app_id=app_id,
                stars=float(entry.get("stars", 0.0)),
                sample_size=int(entry.get("sample_size", 0)),
                notes=str(entry.get("notes", "")),
            )
        except (TypeError, ValueError):
            continue
    return out


def average_rating(curated_stars: int, community: Optional[Rating]) -> float:
    """Weighted blend of curated + community ratings.

    Curated is treated as a single n=1 sample; community averages over
    its real sample_size. With sample_size=0 the curated rating wins.
    """
    if community is None or community.sample_size <= 0:
        return float(curated_stars)
    total_n = 1 + community.sample_size
    return (curated_stars + community.stars * community.sample_size) / total_n
