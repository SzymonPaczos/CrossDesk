"""Transport-agnostic D-Bus signal source for the lifecycle coordinator.

The real systemd-logind subscription lives in
:mod:`crossdesk_host.lifecycle.dbus_listener`; this module factors
out the contract so unit tests (and Mac dev hosts) can drive
:class:`LifecycleCoordinator` through scripted suspend/resume
events without a session bus.

Wiring: :func:`dbus_listener.start_listener` calls
``SystemDBusSignalSource().start(coordinator)`` in production; tests
construct :class:`MockDBusSignalSource`, call ``start``, and then
:meth:`MockDBusSignalSource.emit_prepare_for_sleep` to flip the
coordinator into / out of the suspended state.
"""

from __future__ import annotations

import asyncio
from typing import Optional, Protocol, runtime_checkable

from crossdesk_host.lifecycle.coordinator import LifecycleCoordinator


@runtime_checkable
class DBusSignalSource(Protocol):
    """A source of ``PrepareForSleep`` signals that drives the
    coordinator. Implementations must:

    - register the coordinator on :meth:`start` (returning a task the
      caller can cancel on shutdown);
    - call ``coordinator.on_prepare_for_sleep()`` when the host is
      about to suspend (signal arg ``starting=True``);
    - call ``coordinator.on_resumed()`` after wake (arg
      ``starting=False``).
    """

    async def start(
        self, coordinator: LifecycleCoordinator
    ) -> asyncio.Task[None]: ...


class MockDBusSignalSource:
    """In-process fake. ``start`` parks the coordinator; tests then
    call :meth:`emit_prepare_for_sleep` to script the lifecycle.

    The returned task is a sleep loop the caller can cancel, mirroring
    the real listener's contract — that way the same daemon shutdown
    code that cancels the production listener also cancels the mock
    without special-casing.
    """

    def __init__(self) -> None:
        self._coordinator: Optional[LifecycleCoordinator] = None
        self._task: Optional[asyncio.Task[None]] = None

    async def start(
        self, coordinator: LifecycleCoordinator
    ) -> asyncio.Task[None]:
        self._coordinator = coordinator
        self._task = asyncio.create_task(_keepalive())
        return self._task

    async def emit_prepare_for_sleep(self, *, starting: bool) -> None:
        """Drive the coordinator as if a real ``PrepareForSleep``
        signal arrived. ``starting=True`` for the about-to-suspend
        signal, ``False`` for the post-wake signal.

        Awaits the full sequence, unlike the production handler, which spawns
        the libvirt half so it never blocks the loop — a test wants the settled
        state, not the race.
        """
        if self._coordinator is None:
            raise RuntimeError(
                "emit_prepare_for_sleep called before start(); "
                "the coordinator hasn't been bound yet"
            )
        if starting:
            await self._coordinator.on_prepare_for_sleep()
        else:
            await self._coordinator.on_resumed()


async def _keepalive() -> None:
    # Matches dbus_listener._keepalive: the bus connection (or the
    # test driver) does the work; we only need a cancellable task.
    while True:
        await asyncio.sleep(3600)
