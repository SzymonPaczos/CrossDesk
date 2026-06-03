"""Host-side consumer for the high-res Windows icons the agent extracts.

When the guest agent forwards a ``RailWindowEvent`` CREATED carrying
``icon_png`` (the app's ``.exe`` icon, PNG, typically 256×256 — see
``guest/crates/rail-bridge/src/icon.rs``), we turn it into the Linux
window's icon via the freedesktop route, with **no runtime X11 or
image-decode dependency**:

1. Write ``icon_png`` verbatim into the hicolor icon theme as
   ``~/.local/share/icons/hicolor/256x256/apps/crossdesk-<app_id>.png``
   (it is already a PNG, so no Pillow / decode needed).
2. (Re)write the app's ``.desktop`` with ``Icon=crossdesk-<app_id>`` and
   ``StartupWMClass=crossdesk-<app_id>`` (``integrations.mime.install_app``).

The desktop environment then matches the RAIL window — whose WM_CLASS we
set to ``crossdesk-<app_id>`` in ``display.rail_command.build_rail_argv`` —
to that ``.desktop`` and shows the real icon in the dock / alt-tab /
launcher. This is the ``.desktop`` path chosen by the owner (2026-06-03)
over a python-xlib ``_NET_WM_ICON`` setter; the trade-off is that it skips
the in-frame titlebar icon (which keeps FreeRDP's native 32×32) but needs
zero new host dependencies.

Correlation: ``icon_png`` is keyed by guest HWND on the control plane,
while the ``app_id`` is known only at launch. ``expect()`` / ``offer()``
bridge them — a launch registers the ``app_id`` it started and the next
CREATED-with-icon fulfils it. Because the agent emits CREATED only for
*newly created* windows, the window that appears right after a launch is
the launched app's (pre-existing system windows were already announced),
so the match is reliable for the common one-launch-at-a-time flow.
Concurrent launches can mis-assign; the robust fix (carry the app/exe
identity in ``RailWindowEvent``) is a proto change tracked in the backlog.

Best-effort throughout: any IO error is logged and swallowed — applying an
icon must never block a launch or a window event.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from crossdesk_host.integrations import mime

logger = logging.getLogger(__name__)

# Window icons land at the 256×256 hicolor size — the agent extracts at 256
# and desktops downscale for smaller dock sizes, so one entry suffices.
_DEFAULT_ICON_DIR = Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"

# A launch's icon expectation is only honoured if a window icon arrives within
# this window; a guest that never reports the launched window shouldn't leave a
# stale expectation that grabs an unrelated later window's icon.
_EXPECT_TTL_SECONDS = 60.0


@dataclass
class _Pending:
    app_id: str
    display_name: str
    at: float


class WindowIconStore:
    """Bridges launch-time ``app_id`` knowledge with control-plane icon bytes.

    One instance is shared by the management servicer (which calls
    :meth:`expect` per launch) and the RAIL manager (which calls
    :meth:`offer` per CREATED-with-icon). Not thread-safe by design: the
    daemon drives both from the same asyncio loop.
    """

    def __init__(
        self,
        *,
        icon_dir: Optional[Path] = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._icon_dir = icon_dir or _DEFAULT_ICON_DIR
        self._now = now
        self._pending: Optional[_Pending] = None

    def expect(self, app_id: str, display_name: str) -> None:
        """Record that *app_id* was just launched and its window icon is
        incoming. Overwrites any previous unfulfilled expectation (the most
        recent launch wins)."""
        self._pending = _Pending(
            app_id=app_id, display_name=display_name or app_id, at=self._now()
        )

    def offer(self, icon_png: bytes) -> Optional[str]:
        """Apply *icon_png* to the most-recently-expected launch. Returns the
        ``app_id`` the icon was applied to, or ``None`` (empty icon, no/expired
        expectation, or a write failure)."""
        if not icon_png:
            return None
        pending = self._pending
        if pending is None or (self._now() - pending.at) > _EXPECT_TTL_SECONDS:
            self._pending = None
            return None
        self._pending = None
        try:
            self._apply(pending.app_id, pending.display_name, icon_png)
        except Exception:  # boundary: icon decoration must never crash a launch
            logger.exception("failed to apply window icon for %s", pending.app_id)
            return None
        logger.info(
            "applied window icon for %s (%d bytes)", pending.app_id, len(icon_png)
        )
        return pending.app_id

    def _apply(self, app_id: str, display_name: str, icon_png: bytes) -> None:
        self._icon_dir.mkdir(parents=True, exist_ok=True)
        icon_name = f"crossdesk-{app_id}"
        (self._icon_dir / f"{icon_name}.png").write_bytes(icon_png)
        # (Re)write the .desktop so Icon resolves to the theme entry and
        # StartupWMClass matches the RAIL window's WM_CLASS.
        mime.install_app(app_id=app_id, display_name=display_name, icon=icon_name)
        self._refresh_caches()

    def _refresh_caches(self) -> None:
        """Nudge the icon-theme + desktop caches so the new icon shows without
        a re-login. Best-effort — many desktops pick up files directly, and the
        tools may be absent."""
        hicolor_root = self._icon_dir.parent.parent  # …/icons/hicolor
        applications = Path.home() / ".local" / "share" / "applications"
        for argv in (
            ["gtk-update-icon-cache", "-f", "-t", str(hicolor_root)],
            ["update-desktop-database", str(applications)],
        ):
            exe = shutil.which(argv[0])
            if exe is None:
                continue
            try:
                subprocess.run(
                    [exe, *argv[1:]], capture_output=True, timeout=15, check=False
                )
            except (OSError, subprocess.SubprocessError):
                pass
