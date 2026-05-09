"""Nautilus right-click extension — "Open in Windows app..." submenu.

Drop into ``~/.local/share/nautilus-python/extensions/`` on a GNOME
host with ``python3-nautilus`` installed. Spawns ``crossdesk launch
<app> <file>`` based on user choice; the daemon handles JIT mount
and RAIL launch.

Mac dev: this file is a static asset — never imported into the
running daemon. ``cargo check`` validates everything, the host
package ships it as install material.
"""

# pyright: reportMissingImports=false
# (gi.repository is GNOME-only; not present in our test environment)

from __future__ import annotations

import subprocess
from typing import Any, Iterable, List

try:
    from gi.repository import Nautilus, GObject  # type: ignore[import-not-found]
    HAVE_NAUTILUS = True
except ImportError:
    HAVE_NAUTILUS = False
    Nautilus = None  # type: ignore[assignment]
    GObject = None  # type: ignore[assignment]


_OPENABLE_MIMES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "image/png",
    "image/jpeg",
}

_DEFAULT_APP_FOR_MIME = {
    "application/msword": "word",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word",
    "application/vnd.ms-excel": "excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
    "application/vnd.ms-powerpoint": "powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "powerpoint",
    "text/plain": "notepad",
    "image/png": "paint",
    "image/jpeg": "paint",
}


if HAVE_NAUTILUS:

    class CrossDeskNautilusProvider(GObject.GObject, Nautilus.MenuProvider):  # type: ignore[misc]
        def get_file_items(self, files: Iterable[Any]) -> List[Any]:
            files = list(files)
            if not files:
                return []
            mimes = {f.get_mime_type() for f in files}
            if not mimes & _OPENABLE_MIMES:
                return []

            top = Nautilus.MenuItem(  # type: ignore[attr-defined]
                name="CrossDesk::OpenInWindowsApp",
                label="Open in Windows app...",
                tip="Open these files via CrossDesk-managed Windows apps",
            )
            submenu = Nautilus.Menu()  # type: ignore[attr-defined]
            top.set_submenu(submenu)

            chosen_app = next(
                (
                    _DEFAULT_APP_FOR_MIME.get(m, "auto")
                    for m in (f.get_mime_type() for f in files)
                ),
                "auto",
            )

            item = Nautilus.MenuItem(  # type: ignore[attr-defined]
                name=f"CrossDesk::Launch::{chosen_app}",
                label=f"Open with {chosen_app.title()}",
            )
            item.connect("activate", _on_activate, files, chosen_app)
            submenu.append_item(item)
            return [top]


def _on_activate(_menu_item: Any, files: List[Any], app_id: str) -> None:
    paths = [f.get_location().get_path() for f in files]
    for path in paths:
        if not path:
            continue
        try:
            subprocess.Popen(
                ["crossdesk", "launch", app_id, path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            continue
