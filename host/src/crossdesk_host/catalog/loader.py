"""Catalog loader — reads ``catalog/apps.toml`` into :class:`AppEntry` objects.

The bundled ``apps.toml`` sits alongside this module inside the installed
package; it is discovered via :func:`importlib.resources` so it works
whether the package is installed as a wheel, an editable install, or run
directly from the source tree.

Usage::

    from crossdesk_host.catalog.loader import load_catalog, find_app

    apps = load_catalog()                # all entries
    entry = find_app("word")             # one or None
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

from crossdesk_host.catalog.schema import AppEntry

if sys.version_info >= (3, 11):
    import tomllib as _tomllib  # type: ignore[import-not-found,unused-ignore]
else:  # pragma: no cover
    import tomli as _tomllib  # type: ignore[import-not-found]


def _bundled_toml_path() -> Path:
    """Return the path to the bundled ``apps.toml`` file.

    ``catalog/loader.py`` lives at
    ``host/src/crossdesk_host/catalog/loader.py`` so the sibling
    ``apps.toml`` is at the same level.
    """
    return Path(__file__).with_name("apps.toml")


def load_catalog(path: Optional[Path] = None) -> List[AppEntry]:
    """Load all app entries from a TOML catalog file.

    Args:
        path: Override the file to load.  Defaults to the bundled
              ``catalog/apps.toml``.

    Returns:
        A list of :class:`AppEntry` instances in file order.  Malformed
        entries (missing ``app_id``, ``name``, or ``win_executable``) are
        silently skipped so a single bad entry cannot break the whole
        catalog.  Returns an empty list if the file is missing.
    """
    resolved = path or _bundled_toml_path()
    if not resolved.exists():
        return []
    with resolved.open("rb") as fh:
        data = _tomllib.load(fh)

    out: List[AppEntry] = []
    for raw in data.get("apps", []):
        if not isinstance(raw, dict):
            continue
        app_id = raw.get("app_id", "")
        name = raw.get("name", "")
        win_executable = raw.get("win_executable", "")
        if not (app_id and name and win_executable):
            continue
        out.append(
            AppEntry(
                app_id=str(app_id),
                name=str(name),
                win_executable=str(win_executable),
                categories=list(raw.get("categories") or []),
                mime_types=list(raw.get("mime_types") or []),
                icon=str(raw.get("icon", "")),
            )
        )
    return out


def _catalog_index(path: Optional[Path] = None) -> Dict[str, AppEntry]:
    """Build a dict mapping app_id → AppEntry (internal helper)."""
    return {e.app_id: e for e in load_catalog(path)}


def find_app(app_id: str, path: Optional[Path] = None) -> Optional[AppEntry]:
    """Look up a single app by its slug.

    Returns ``None`` if no entry with that ``app_id`` exists in the catalog.
    """
    return _catalog_index(path).get(app_id)
