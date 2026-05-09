"""systemd-logind D-Bus listener (Linux-only).

Subscribes to ``org.freedesktop.login1.Manager.PrepareForSleep`` on the
system bus and calls ``LifecycleCoordinator.on_prepare_for_sleep`` /
``on_resumed`` accordingly. The signal is emitted twice per
suspend/resume cycle: first with ``starting=True`` shortly before the
kernel suspends, then with ``starting=False`` after wake.

End-to-end verification of this listener requires a Linux host with
``systemd-logind`` and ``dbus-next`` installed (the latter is gated
behind ``[project.optional-dependencies] linux``). On Mac/Windows the
module imports cleanly but ``start_listener`` raises immediately so a
mistaken non-Linux call site is loud rather than silent.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from crossdesk_host.lifecycle.coordinator import LifecycleCoordinator
from crossdesk_host.observability.log import get_logger

logger = get_logger("host.lifecycle.dbus")


async def start_listener(coordinator: LifecycleCoordinator) -> asyncio.Task[None]:
    """Connect to the system bus and subscribe to ``PrepareForSleep``.

    Returns a long-running task whose only purpose is to keep the
    listener alive; the caller cancels it on shutdown.

    Raises ``RuntimeError`` if ``dbus-next`` isn't installed.
    """
    try:
        from dbus_next import BusType  # type: ignore[import-not-found]
        from dbus_next.aio import MessageBus  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "dbus-next not installed; install with "
            "`pip install crossdesk-host[linux]`"
        ) from exc

    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    introspection = await bus.introspect(
        "org.freedesktop.login1", "/org/freedesktop/login1"
    )
    proxy = bus.get_proxy_object(
        "org.freedesktop.login1", "/org/freedesktop/login1", introspection
    )
    manager = proxy.get_interface("org.freedesktop.login1.Manager")

    handler: Callable[[bool], None] = _make_handler(coordinator)
    manager.on_prepare_for_sleep(handler)

    logger.info("dbus_listener_subscribed")
    return asyncio.create_task(_keepalive())


def _make_handler(coordinator: LifecycleCoordinator) -> Callable[[bool], None]:
    def _on_prepare_for_sleep(starting: Any) -> None:
        # dbus-next delivers a bool; widen the annotation so the proxy
        # signature matches without an explicit cast.
        if bool(starting):
            logger.info("dbus_prepare_for_sleep_start")
            coordinator.on_prepare_for_sleep()
        else:
            logger.info("dbus_prepare_for_sleep_end")
            coordinator.on_resumed()

    return _on_prepare_for_sleep


async def _keepalive() -> None:
    # The bus's signal dispatch is driven by the bus connection itself;
    # we only need to keep this task alive so the caller has something
    # cancellable. Sleeping in a long loop is enough — the bus does the work.
    while True:
        await asyncio.sleep(3600)
