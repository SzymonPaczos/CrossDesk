"""Libvirt domain lifecycle events → explicit, reasoned VM-death detection.

Today the host learns the VM died only *indirectly*: heartbeats stop and
the watchdog FSM escalates to HARD_DESTROY. That's correct but slow and
blind to *why* — a QEMU crash, an OOM kill, and a deliberate ``virsh
destroy`` all read as "silence". Libvirt knows the moment the domain stops
and the reason; this module turns that into a structured
``vm_lifecycle_event`` log (carrying the libvirt reason) and a desktop
notification when the stop was an unexpected crash/failure.

**The indirect path does not actually work.** Live-verified 2026-07-14: a
``virsh destroy`` against the running guest produced *no daemon reaction at
all* — no log line, no FSM escalation, the VM simply stayed dead. The reason
is structural: the heartbeat FSM ticks off the gRPC ``request_iterator``, so
VM death closes the very stream that drives it and the FSM goes silent. It
escalates when the guest is *alive but unhealthy*; it cannot see a guest that
is *gone*. Without a libvirt-backed source, nothing in the daemon ever learns
the domain stopped — which is why criterion #6 could never pass.

So this module now ships the real thing:

* :class:`LibvirtDomainEventSource` registers ``VIR_DOMAIN_EVENT_ID_LIFECYCLE``
  on its own ``qemu:///session`` connection and pumps libvirt's event loop on a
  daemon thread, marshalling each callback back onto asyncio.
* :class:`DomainEventReactor` no longer merely logs: on a death-like stop it
  *recovers*, by starting the domain again.

The ``DomainEventSource`` Protocol (mirroring
:mod:`crossdesk_host.lifecycle.dbus_signals` and the ``BalloonHook`` seam) keeps
the reactor unit-testable through :class:`MockDomainEventSource`, with no libvirt
connection required.

Recovery is deliberately **not** ``hard_destroy``: that destroys first, and
``destroy`` on an already-dead domain raises. Recovery-from-death calls
:meth:`LibvirtController.start`, which is idempotent, so it is safe even when it
races ``hard_destroy``'s own restart.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, Protocol, Set, runtime_checkable

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
Recover = Callable[[], Awaitable[None]]

# Stop reasons that mean the VM *died* rather than being put away on purpose.
# `destroyed` is in here because that is exactly what criterion #6 tests: a
# `virsh destroy` (or anything that kills QEMU) must bring the guest back.
# `shutdown` is NOT: a guest that shut itself down — or that the user stopped
# with `crossdesk vm shutdown` — must stay down, or we would be fighting them.
DEATH_REASONS = frozenset({"destroyed", "crashed", "failed"})


def is_death(event: DomainEvent) -> bool:
    """Should this stop be recovered from?"""
    if event.kind is DomainEventKind.CRASHED:
        return True
    return event.reason in DEATH_REASONS


@runtime_checkable
class DomainEventSource(Protocol):
    """Source of domain lifecycle events. ``start`` registers the callback
    and returns a task the daemon cancels on shutdown (same contract as
    :class:`crossdesk_host.lifecycle.dbus_signals.DBusSignalSource`)."""

    async def start(self, on_event: OnEvent) -> asyncio.Task[None]: ...


class DomainEventReactor:
    """Reacts to a :class:`DomainEvent`: structured log, user notification on a
    crash, and — the part that makes criterion #6 possible — **recovery**.

    ``recover`` is optional so tests (and a daemon on the mock backend) can
    exercise the logging path without restarting anything.
    """

    def __init__(
        self,
        notifier: Optional[Notifier] = None,
        recover: Optional[Recover] = None,
    ) -> None:
        self._notifier = notifier
        self._recover = recover
        # asyncio keeps only weak refs to tasks; without a strong one a recovery
        # in flight can be garbage-collected mid-restart.
        self._pending: Set["asyncio.Task[None]"] = set()

    def on_event(self, event: DomainEvent) -> None:
        death = is_death(event)
        if event.kind is DomainEventKind.CRASHED or death:
            logger.warning(
                "vm_lifecycle_event",
                kind=event.kind.value,
                reason=event.reason,
                recovering=self._recover is not None,
            )
            if self._notifier is not None:
                notify_forced_stop(
                    self._notifier,
                    reason=f"The VM stopped unexpectedly ({event.reason or 'crashed'}).",
                )
        else:
            # A deliberate stop (guest shutdown / save / migrate). Record it, do
            # not alarm the user — and do not resurrect what they put away.
            logger.info("vm_lifecycle_event", kind=event.kind.value, reason=event.reason)

        if death and self._recover is not None:
            task = asyncio.create_task(self._recover_now(event))
            self._pending.add(task)
            task.add_done_callback(self._pending.discard)

    async def _recover_now(self, event: DomainEvent) -> None:
        assert self._recover is not None
        logger.warning("vm_recovery_begin", reason=event.reason)
        try:
            await self._recover()
        except Exception as exc:  # noqa: BLE001 — a failed restart must not kill the daemon
            logger.error("vm_recovery_failed", reason=event.reason, error=str(exc))
            return
        logger.warning("vm_recovery_complete", reason=event.reason)


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


class LibvirtDomainEventSource:
    """Real ``VIR_DOMAIN_EVENT_ID_LIFECYCLE`` events for one domain.

    Two awkward libvirt facts shape this:

    1. ``virEventRegisterDefaultImpl()`` must run **before** the connection is
       opened — it installs the handle/timeout plumbing the connection registers
       itself against. So this class opens its own connection rather than reusing
       the controller's, which may already be connected by the time we start.
    2. Someone has to *pump* that event loop. ``virEventRunDefaultImpl()`` blocks,
       so it runs on a daemon thread, and callbacks arrive on that thread — which
       means they get marshalled back onto asyncio with ``call_soon_threadsafe``
       before anything downstream touches loop state.
    """

    def __init__(self, domain_name: str, uri: str = "qemu:///session") -> None:
        self.domain_name = domain_name
        self._uri = uri
        self._conn: Any = None
        self._pump: Optional[threading.Thread] = None

    async def start(self, on_event: OnEvent) -> "asyncio.Task[None]":
        try:
            import libvirt
        except ImportError as exc:
            raise RuntimeError(
                "libvirt-python is not installed; install with "
                "`pip install crossdesk-host[linux]` on a Linux host."
            ) from exc

        loop = asyncio.get_running_loop()

        # Must precede libvirt.open() — see the class docstring.
        libvirt.virEventRegisterDefaultImpl()
        conn = libvirt.open(self._uri)
        if conn is None:
            raise RuntimeError(f"libvirt.open({self._uri!r}) returned None")
        self._conn = conn

        def _on_lifecycle(
            _conn: Any, domain: Any, event: int, detail: int, _opaque: Any
        ) -> None:
            # Runs on the libvirt pump thread, NOT the event loop.
            try:
                if domain.name() != self.domain_name:
                    return
                mapped = _map_lifecycle(event, detail)
            except Exception:  # noqa: BLE001 — never let the pump thread die
                logger.exception("libvirt_event_callback_failed")
                return
            if mapped is not None:
                loop.call_soon_threadsafe(on_event, mapped)

        conn.domainEventRegisterAny(
            None,  # all domains; filtered by name in the callback
            libvirt.VIR_DOMAIN_EVENT_ID_LIFECYCLE,
            _on_lifecycle,
            None,
        )

        self._pump = threading.Thread(
            target=self._run_pump, name="libvirt-events", daemon=True
        )
        self._pump.start()
        logger.info("libvirt_domain_events_subscribed", domain=self.domain_name)
        return asyncio.create_task(_keepalive())

    def _run_pump(self) -> None:
        import libvirt

        while True:
            # Blocks until libvirt has something to deliver. Returns < 0 on a
            # loop error, at which point events are dead and staying in the loop
            # would just spin.
            if libvirt.virEventRunDefaultImpl() < 0:
                logger.error("libvirt_event_loop_stopped")
                return


def _map_lifecycle(event: int, detail: int) -> Optional[DomainEvent]:
    """Map a libvirt lifecycle event to ours, or ``None`` if we don't care.

    Only the stop side carries a "did this die" signal, so starts/resumes/etc.
    map to nothing.
    """
    import libvirt

    if event == libvirt.VIR_DOMAIN_EVENT_CRASHED:
        return DomainEvent(kind=DomainEventKind.CRASHED, reason="crashed")

    if event == libvirt.VIR_DOMAIN_EVENT_STOPPED:
        reasons = {
            libvirt.VIR_DOMAIN_EVENT_STOPPED_SHUTDOWN: "shutdown",
            libvirt.VIR_DOMAIN_EVENT_STOPPED_DESTROYED: "destroyed",
            libvirt.VIR_DOMAIN_EVENT_STOPPED_CRASHED: "crashed",
            libvirt.VIR_DOMAIN_EVENT_STOPPED_MIGRATED: "migrated",
            libvirt.VIR_DOMAIN_EVENT_STOPPED_SAVED: "saved",
            libvirt.VIR_DOMAIN_EVENT_STOPPED_FAILED: "failed",
            libvirt.VIR_DOMAIN_EVENT_STOPPED_FROM_SNAPSHOT: "from_snapshot",
        }
        reason = reasons.get(detail, f"unknown({detail})")
        kind = (
            DomainEventKind.CRASHED
            if reason in ("crashed", "failed")
            else DomainEventKind.STOPPED
        )
        return DomainEvent(kind=kind, reason=reason)

    return None


async def _keepalive() -> None:
    # The real source's libvirt event loop (or the test driver) does the
    # work; we only need a cancellable task to hand back.
    while True:
        await asyncio.sleep(3600)
