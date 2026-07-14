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
from typing import Any, Callable, Coroutine, Set

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
        from dbus_next import BusType  # type: ignore[import,attr-defined]
        from dbus_next.aio import MessageBus  # type: ignore[import,attr-defined]
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
    manager.on_prepare_for_sleep(handler)  # type: ignore[attr-defined]

    logger.info("dbus_listener_subscribed")
    return asyncio.create_task(_keepalive())


def _log_if_failed(task: "asyncio.Task[None]", phase: str) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.warning("lifecycle_dbus_task_failed", phase=phase, error=str(exc))


def _make_handler(coordinator: LifecycleCoordinator) -> Callable[[bool], None]:
    # asyncio holds only weak references to tasks, so a suspend/resume in flight
    # can be garbage-collected out from under us. Keep a strong ref until done.
    background: Set["asyncio.Task[None]"] = set()

    def _spawn(coro: Coroutine[Any, Any, None], phase: str) -> None:
        task = asyncio.create_task(coro)
        background.add(task)
        task.add_done_callback(background.discard)
        task.add_done_callback(lambda t: _log_if_failed(t, phase))

    def _on_prepare_for_sleep(starting: Any) -> None:
        # dbus-next delivers a bool; widen the annotation so the proxy
        # signature matches without an explicit cast. It also dispatches this
        # callback ON the event loop, so anything blocking here freezes the
        # whole daemon.
        if bool(starting):
            logger.info("dbus_prepare_for_sleep_start")
            # Synchronously, before this handler returns. We hold no systemd
            # delay inhibitor, so nothing waits for us — the kernel may freeze
            # as soon as we yield, and an FSM still ticking across the sleep
            # escalates to HARD_DESTROY (= virsh destroy).
            coordinator.suspend_fsms()
            # The libvirt pause is the slow half; awaiting it inline is what
            # used to block the loop.
            _spawn(coordinator.pause_domain(), "suspend")
        else:
            logger.info("dbus_prepare_for_sleep_end")
            # Nothing races on resume: the FSMs are parked in SUSPENDED and
            # cannot escalate until on_resumed releases them, which it does only
            # after libvirt is back.
            _spawn(coordinator.on_resumed(), "resume")

    return _on_prepare_for_sleep


async def _keepalive() -> None:
    # The bus's signal dispatch is driven by the bus connection itself;
    # we only need to keep this task alive so the caller has something
    # cancellable. Sleeping in a long loop is enough — the bus does the work.
    while True:
        await asyncio.sleep(3600)
