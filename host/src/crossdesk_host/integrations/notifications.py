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

import asyncio
from typing import Any, Optional

from crossdesk_host.lifecycle.notifications import Notifier, Urgency

_URGENCY_LEVEL = {Urgency.LOW: 0, Urgency.NORMAL: 1, Urgency.CRITICAL: 2}

_NOTIF_BUS = "org.freedesktop.Notifications"
_NOTIF_PATH = "/org/freedesktop/Notifications"
_NOTIF_IFACE = "org.freedesktop.Notifications"


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
                import dbus_next  # type: ignore[import]  # noqa: F401

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
        # Best-effort: a failed notification must not take down the daemon.
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
        try:
            loop = asyncio.get_running_loop()
            # Inside a running event loop (daemon context): schedule
            # fire-and-forget so the caller is not blocked.
            loop.create_task(
                self._send_async(summary, body, urgency, icon, category)
            )
        except RuntimeError:
            # No running event loop (CLI or test context).
            asyncio.run(self._send_async(summary, body, urgency, icon, category))

    async def _send_async(
        self,
        summary: str,
        body: str,
        urgency: Urgency,
        icon: str,
        category: str,
    ) -> None:
        from dbus_next.aio import MessageBus  # type: ignore[import,attr-defined]
        from dbus_next import Variant  # type: ignore[import,attr-defined]

        hints: dict[str, Any] = {
            "urgency": Variant("y", _URGENCY_LEVEL[urgency])
        }
        if category:
            hints["category"] = Variant("s", category)

        bus = await MessageBus().connect()
        try:
            introspection = await bus.introspect(_NOTIF_BUS, _NOTIF_PATH)
            obj = bus.get_proxy_object(_NOTIF_BUS, _NOTIF_PATH, introspection)
            iface = obj.get_interface(_NOTIF_IFACE)
            await iface.call_notify(  # type: ignore[attr-defined]
                self.app_name,
                0,       # replaces_id: 0 = new notification each call
                icon,
                summary,
                body,
                [],      # actions
                hints,
                5000,    # expire_timeout_ms
            )
        finally:
            bus.disconnect()  # type: ignore[no-untyped-call]
