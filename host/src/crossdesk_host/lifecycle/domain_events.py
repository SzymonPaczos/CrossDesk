"""Libvirt domain lifecycle events → explicit, reasoned VM-death detection.

Today the host learns the VM died only *indirectly*: heartbeats stop and
the watchdog FSM escalates to HARD_DESTROY. That's correct but slow and
blind to *why* — a QEMU crash, an OOM kill, and a deliberate ``virsh
destroy`` all read as "silence". Libvirt knows the moment the domain stops
and the reason; this module turns that into a structured
``vm_lifecycle_event`` log (carrying the libvirt reason) and a desktop
notification when the stop was an unexpected crash/failure.

The pattern mirrors :mod:`crossdesk_host.lifecycle.dbus_signals` (and the
``BalloonHook`` seam): a ``DomainEventSource`` Protocol so
:class:`DomainEventReactor` is unit-testable through
:class:`MockDomainEventSource` without a libvirt connection.

What ships here is the **tested handler + seam**. The real libvirt-backed
source is the Phase-3 follow-up that lands *with* the real libvirt
controller (the daemon runs ``LibvirtControllerMock`` today, so there are
no real domain events to listen to yet, and a hand-written libvirt
event-loop pump can't be verified without hardware — shipping it now would
be unrun scaffolding). The Phase-3 source registers
``VIR_DOMAIN_EVENT_ID_LIFECYCLE`` on the controller's connection
(``virEventRegisterDefaultImpl`` must run before ``libvirt.open``), maps
each ``VIR_DOMAIN_EVENT_STOPPED`` / ``_CRASHED`` to a :class:`DomainEvent`,
and feeds :meth:`DomainEventReactor.on_event`. Until then the watchdog
heartbeat path already surfaces a user-visible notification on VM death
(``HeartbeatServiceServicer`` → ``notify_forced_stop``); this adds the
*reasoned, immediate* layer on top.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Protocol, runtime_checkable

from crossdesk_host.lifecycle.error_notifications import notify_forced_stop
from crossdesk_host.lifecycle.notifications import Notifier
from crossdesk_host.observability import get_logger

logger = get_logger("host.lifecycle.domain_events")


class DomainEventKind(Enum):
    """The lifecycle transitions we react to. Names map onto libvirt's
    ``VIR_DOMAIN_EVENT_*`` lifecycle events; only the stop-side ones carry
    a meaningful "is this a failure" signal, so those are what we model."""

    STOPPED = "stopped"
    """Domain stopped for a benign reason (shutdown / destroyed / migrated)."""
    CRASHED = "crashed"
    """Domain stopped because QEMU crashed or failed to keep running —
    the case a user must be told about."""


@dataclass(frozen=True)
class DomainEvent:
    kind: DomainEventKind
    reason: str = ""
    """Libvirt's sub-reason string (e.g. ``crashed``, ``destroyed``,
    ``shutdown``), surfaced verbatim in the log for diagnostics."""


OnEvent = Callable[[DomainEvent], None]


@runtime_checkable
class DomainEventSource(Protocol):
    """Source of domain lifecycle events. ``start`` registers the callback
    and returns a task the daemon cancels on shutdown (same contract as
    :class:`crossdesk_host.lifecycle.dbus_signals.DBusSignalSource`)."""

    async def start(self, on_event: OnEvent) -> asyncio.Task[None]: ...


class DomainEventReactor:
    """Turns a :class:`DomainEvent` into a structured log and, on a crash,
    a user notification. Stateless beyond its notifier, so the daemon and
    tests share one instance."""

    def __init__(self, notifier: Optional[Notifier] = None) -> None:
        self._notifier = notifier

    def on_event(self, event: DomainEvent) -> None:
        if event.kind is DomainEventKind.CRASHED:
            logger.warning("vm_lifecycle_event", kind=event.kind.value, reason=event.reason)
            if self._notifier is not None:
                notify_forced_stop(
                    self._notifier,
                    reason=f"The VM stopped unexpectedly ({event.reason or 'crashed'}).",
                )
        else:
            # A benign stop (user shutdown / destroy) — record it, don't
            # alarm the user with a crash notification.
            logger.info("vm_lifecycle_event", kind=event.kind.value, reason=event.reason)


class MockDomainEventSource:
    """In-process fake. ``start`` parks a cancellable task (mirroring the
    real source so the daemon's shutdown cancels either without special-
    casing); tests then call :meth:`emit` to script lifecycle events."""

    def __init__(self) -> None:
        self._on_event: Optional[OnEvent] = None
        self._task: Optional[asyncio.Task[None]] = None

    async def start(self, on_event: OnEvent) -> asyncio.Task[None]:
        self._on_event = on_event
        self._task = asyncio.create_task(_keepalive())
        return self._task

    def emit(self, event: DomainEvent) -> None:
        if self._on_event is None:
            raise RuntimeError("emit called before start(); no callback bound yet")
        self._on_event(event)


async def _keepalive() -> None:
    # The real source's libvirt event loop (or the test driver) does the
    # work; we only need a cancellable task to hand back.
    while True:
        await asyncio.sleep(3600)
