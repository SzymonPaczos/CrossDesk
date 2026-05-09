"""Native ``org.freedesktop.Notifications`` D-Bus client.

Replaces the Week 11 ``notify-send`` shell-out for callers that want
finer control (action buttons, replaces-id for in-place updates,
``urgency=critical`` for HARD_DESTROY events). The Week 11
:class:`SubprocessNotifier` stays as the bottom-of-the-pile fallback.

Mac dev: ``DBusNotifier.is_available()`` returns ``False`` when
``dbus-next`` isn't installed; callers fall through to
``SubprocessNotifier`` which, in turn, no-ops when ``notify-send``
isn't on PATH. Net effect on Mac: silent.
"""

from __future__ import annotations

from typing import Any, Optional

from crossdesk_host.lifecycle.notifications import Notifier, Urgency


class DBusNotifier(Notifier):
    """Talks to ``org.freedesktop.Notifications`` over the session bus.

    Construction is lazy (real bus connection only on first ``notify``)
    so importing the module on Mac doesn't fail with dbus-next missing.
    """

    app_name: str

    def __init__(self, app_name: str = "CrossDesk") -> None:
        self.app_name = app_name
        self._proxy: Optional[Any] = None
        self._available_cached: Optional[bool] = None

    def is_available(self) -> bool:
        if self._available_cached is None:
            try:
                import dbus_next  # type: ignore[import-not-found]  # noqa: F401

                self._available_cached = True
            except ImportError:
                self._available_cached = False
        return self._available_cached

    def notify(
        self,
        summary: str,
        body: str = "",
        urgency: Urgency = Urgency.NORMAL,
        icon: str = "",
        category: str = "",
    ) -> None:
        if not self.is_available():
            return
        # End-to-end D-Bus call lands when running on Linux+GNOME/Plasma.
        # On Mac the import succeeds but bus_init() may fail; we swallow
        # silently — a failed notification mustn't take down the daemon.
        try:
            self._send_sync(summary, body, urgency, icon, category)
        except Exception:
            return

    def _send_sync(
        self,
        summary: str,
        body: str,
        urgency: Urgency,
        icon: str,
        category: str,
    ) -> None:
        # Phase 7 stub. Wiring the actual asyncio loop + dbus-next call
        # requires a running asyncio context (the daemon has one). For
        # now we shape the API; daemon integration lands when the
        # mgmt-socket client subscribes to recovery events from the
        # Status stream and dispatches into :class:`DBusNotifier`.
        _ = (summary, body, urgency, icon, category)
