"""``org.freedesktop.portal.OpenURI`` portal client.

When a sandboxed app (Flatpak Firefox, Snap something) tries to open
a file with the system, it goes through the OpenURI portal. We
register CrossDesk as a handler for the relevant MIME types so that
double-clicking a `.docx` in any sandboxed file manager routes to
Word in the VM through us — without the sandbox needing direct
access to the host's libvirt or our gRPC socket.

The portal is implemented by xdg-desktop-portal (and a backend like
xdg-desktop-portal-kde / -gtk / -gnome). We don't implement the
portal itself; we register as a destination.

Mac dev: portal infrastructure is Linux-only; ``is_available`` is
``False``.
"""

from __future__ import annotations

import shutil
from typing import Protocol


class XdgPortal(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def announce_handler(self, app_id: str, mime_types: list[str]) -> None:
        """Register ``app_id`` as a candidate handler for ``mime_types``
        through the portal."""
        ...


class NullPortal(XdgPortal):
    name = "null"

    def is_available(self) -> bool:
        return False

    def announce_handler(self, app_id: str, mime_types: list[str]) -> None:
        return


class XdgMimePortal(XdgPortal):
    """Updates the user's MIME defaults via ``xdg-mime``. The portal
    layer is not strictly required for plain MIME registration —
    ``xdg-mime default`` handles the file-manager / sandbox case for
    most desktops. Real portal D-Bus integration lands when we want
    inline UI (file pickers, action buttons in chooser).
    """

    name = "xdg-mime"

    def is_available(self) -> bool:
        return shutil.which("xdg-mime") is not None

    def announce_handler(self, app_id: str, mime_types: list[str]) -> None:
        if not self.is_available():
            return
        import subprocess

        for mime in mime_types:
            try:
                subprocess.run(
                    ["xdg-mime", "default", f"{app_id}.desktop", mime],
                    check=False,
                    capture_output=True,
                    timeout=5.0,
                )
            except (subprocess.SubprocessError, OSError):
                continue


def detect_portal() -> XdgPortal:
    if XdgMimePortal().is_available():
        return XdgMimePortal()
    return NullPortal()
