"""MIME associations and .desktop file management.

Generates standard freedesktop ``~/.local/share/applications/crossdesk-*.desktop``
files so each registered Windows app appears in the Linux app launcher, supports
file-open via MIME type associations, and registers Office URL scheme handlers.

All writes are idempotent — calling :func:`install_app` twice produces the same
file.  :func:`uninstall_app` and :func:`uninstall_all` mirror the
``~/.local/share/applications/crossdesk-*.desktop`` cleanup in ``uninstall.py``.

Usage (called by installer after an app is registered):
    from crossdesk_host.integrations.mime import install_app, install_office_handler
    install_app("notepad", display_name="Notepad", categories=["Utility"])
    install_office_handler()          # once, during install
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional, Sequence

_APPLICATIONS_DIR = Path.home() / ".local" / "share" / "applications"

_OFFICE_MIME_TYPES: List[str] = [
    "x-scheme-handler/ms-word",
    "x-scheme-handler/ms-excel",
    "x-scheme-handler/ms-powerpoint",
    "x-scheme-handler/ms-outlook",
    "x-scheme-handler/ms-access",
    "x-scheme-handler/ms-visio",
    "x-scheme-handler/ms-project",
    "x-scheme-handler/ms-teams",
    "x-scheme-handler/ms-whiteboard",
    "x-scheme-handler/ms-officeapp",
]


def install_app(
    app_id: str,
    display_name: str,
    categories: Sequence[str] = ("Utility",),
    mime_types: Sequence[str] = (),
    icon: Optional[str] = None,
    comment: str = "",
    *,
    applications_dir: Optional[Path] = None,
) -> Path:
    """Write ``crossdesk-<app_id>.desktop`` to the user applications directory.

    Returns the path of the written file.
    """
    dest = (applications_dir or _APPLICATIONS_DIR) / f"crossdesk-{app_id}.desktop"
    dest.parent.mkdir(parents=True, exist_ok=True)

    cats = ";".join(list(categories)) + ";"
    mimes = ";".join(list(mime_types)) + ";" if mime_types else ""
    icon_line = f"Icon={icon}" if icon else "Icon=application-x-executable"
    comment_line = f"Comment={comment}" if comment else ""

    lines = [
        "[Desktop Entry]",
        f"Name={display_name}",
        "Type=Application",
        f"Exec=crossdesk launch {app_id} %F",
        f"StartupWMClass=crossdesk-{app_id}",
        icon_line,
        f"Categories={cats}",
        "Terminal=false",
        "NoDisplay=false",
    ]
    if mimes:
        lines.append(f"MimeType={mimes}")
    if comment_line:
        lines.append(comment_line)

    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def install_office_handler(
    *, applications_dir: Optional[Path] = None
) -> Path:
    """Write the Microsoft Office URL scheme handler desktop file.

    Claims all ``x-scheme-handler/ms-*`` MIME types so links opened from a
    browser (e.g. ``ms-word://open?url=...``) route to the Windows guest
    via ``crossdesk launch``.  Analogous to ``winapps/apps/ms-office-protocol-
    handler.desktop``.
    """
    dest = (
        (applications_dir or _APPLICATIONS_DIR) / "crossdesk-ms-office-handler.desktop"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)

    mimes = ";".join(_OFFICE_MIME_TYPES) + ";"
    content = "\n".join([
        "[Desktop Entry]",
        "Name=CrossDesk Microsoft Office Protocol Handler",
        "Comment=Route Microsoft Office URI schemes to the Windows guest",
        "Exec=crossdesk launch manual %u",
        "Terminal=false",
        "Type=Application",
        f"MimeType={mimes}",
        "NoDisplay=true",
        "Categories=Office;Utility;",
    ]) + "\n"

    dest.write_text(content, encoding="utf-8")
    return dest


def update_mime_database(*, applications_dir: Optional[Path] = None) -> None:
    """Run ``update-desktop-database`` to pick up newly written .desktop files.

    Silently no-ops if the tool is not on PATH (e.g. non-freedesktop systems).
    """
    target = str(applications_dir or _APPLICATIONS_DIR)
    try:
        subprocess.run(
            ["update-desktop-database", target],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass


def uninstall_app(app_id: str, *, applications_dir: Optional[Path] = None) -> bool:
    """Remove ``crossdesk-<app_id>.desktop``.  Returns True if it existed."""
    target = (applications_dir or _APPLICATIONS_DIR) / f"crossdesk-{app_id}.desktop"
    if target.exists():
        target.unlink()
        return True
    return False


def uninstall_all(*, applications_dir: Optional[Path] = None) -> List[Path]:
    """Remove all ``crossdesk-*.desktop`` files.  Returns the removed paths."""
    base = applications_dir or _APPLICATIONS_DIR
    removed: List[Path] = []
    for p in base.glob("crossdesk-*.desktop"):
        p.unlink()
        removed.append(p)
    return removed
