"""DomainEventReactor + MockDomainEventSource + the recovery it now performs.

A crash logs and notifies, a benign stop stays quiet, and the mock source
delivers events through the same callback contract the real libvirt source uses.

The recovery tests below are the guard for MVP criterion #6. Live-verify on
2026-07-14 showed a `virsh destroy` produced no daemon reaction whatsoever: the
heartbeat FSM ticks off the gRPC stream, so the death that closes the stream also
silences the only thing watching. These pin the fix — and, just as importantly,
pin what must NOT happen: a guest the user shut down cleanly stays down.
"""

from __future__ import annotations

import asyncio

import pytest

from crossdesk_host.libvirt_ctl import libvirt_call
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.lifecycle.domain_events import (
    DomainEvent,
    DomainEventKind,
    DomainEventReactor,
    MockDomainEventSource,
    _map_lifecycle,
)
from crossdesk_host.lifecycle.notifications import RecordingNotifier


def test_crash_notifies() -> None:
    notifier = RecordingNotifier()
    reactor = DomainEventReactor(notifier)
    reactor.on_event(DomainEvent(DomainEventKind.CRASHED, reason="qemu-segv"))
    assert len(notifier.calls) == 1
    assert "qemu-segv" in notifier.calls[0].body


def test_benign_stop_is_quiet() -> None:
    notifier = RecordingNotifier()
    reactor = DomainEventReactor(notifier)
    reactor.on_event(DomainEvent(DomainEventKind.STOPPED, reason="shutdown"))
    assert notifier.calls == []  # a user-requested shutdown isn't a crash


def test_crash_without_notifier_is_safe() -> None:
    reactor = DomainEventReactor(notifier=None)
    # Must not raise on the crash path when no notifier is wired.
    reactor.on_event(DomainEvent(DomainEventKind.CRASHED, reason="x"))


async def test_mock_source_delivers_to_reactor() -> None:
    notifier = RecordingNotifier()
    reactor = DomainEventReactor(notifier)
    source = MockDomainEventSource()
    task = await source.start(reactor.on_event)

    source.emit(DomainEvent(DomainEventKind.CRASHED, reason="oom"))
    assert len(notifier.calls) == 1

    task.cancel()  # the parked keepalive task is the daemon's to cancel


async def test_emit_before_start_raises() -> None:
    source = MockDomainEventSource()
    with pytest.raises(RuntimeError, match="before start"):
        source.emit(DomainEvent(DomainEventKind.STOPPED))


# ---------------------------------------------------------------------------
# Recovery (MVP criterion #6)
# ---------------------------------------------------------------------------


def _dead_guest() -> LibvirtControllerMock:
    ctl = LibvirtControllerMock()
    ctl.hooks.running = False
    return ctl


def _reactor_for(ctl: LibvirtControllerMock) -> DomainEventReactor:
    async def recover() -> None:
        await libvirt_call(ctl.start)

    return DomainEventReactor(recover=recover)


async def test_destroyed_vm_is_recovered() -> None:
    """`virsh destroy` → the daemon brings the guest back. This is criterion #6."""
    ctl = _dead_guest()
    _reactor_for(ctl).on_event(DomainEvent(DomainEventKind.STOPPED, reason="destroyed"))
    await asyncio.sleep(0.05)

    assert ctl.hooks.start_count == 1
    assert ctl.hooks.running is True


async def test_crashed_vm_is_recovered() -> None:
    ctl = _dead_guest()
    _reactor_for(ctl).on_event(DomainEvent(DomainEventKind.CRASHED, reason="crashed"))
    await asyncio.sleep(0.05)

    assert ctl.hooks.running is True


async def test_recovery_starts_the_domain_rather_than_hard_destroying_it() -> None:
    """The trap, pinned.

    hard_destroy() is destroy() + create(), and destroy() on a domain that is
    already gone raises — so wiring the obvious method here would make recovery
    fail exactly when it is needed. Recovery must call start().
    """
    ctl = _dead_guest()
    _reactor_for(ctl).on_event(DomainEvent(DomainEventKind.STOPPED, reason="destroyed"))
    await asyncio.sleep(0.05)

    assert ctl.hooks.start_count == 1
    assert ctl.hooks.hard_destroy_count == 0, "recovery must not go through hard_destroy"


async def test_a_guest_that_shut_itself_down_stays_down() -> None:
    """The negative that keeps us from fighting the user.

    A clean shutdown — the user picking Shut Down in Windows, or
    `crossdesk vm shutdown` — is not a death. Resurrecting it would be a bug with
    a very short fuse.
    """
    ctl = _dead_guest()
    _reactor_for(ctl).on_event(DomainEvent(DomainEventKind.STOPPED, reason="shutdown"))
    await asyncio.sleep(0.05)

    assert ctl.hooks.start_count == 0
    assert ctl.hooks.running is False


async def test_recovery_is_idempotent_against_a_racing_restart() -> None:
    """hard_destroy's own create() may beat us to it; firing twice must be safe."""
    ctl = LibvirtControllerMock()
    ctl.hooks.running = True  # already back up
    _reactor_for(ctl).on_event(DomainEvent(DomainEventKind.STOPPED, reason="destroyed"))
    await asyncio.sleep(0.05)

    assert ctl.hooks.start_count == 1  # it was called...
    assert ctl.hooks.running is True  # ...and left the running domain alone


async def test_failed_recovery_does_not_take_the_daemon_down() -> None:
    ctl = _dead_guest()
    ctl.hooks.fail_next_start = True
    _reactor_for(ctl).on_event(DomainEvent(DomainEventKind.STOPPED, reason="destroyed"))
    await asyncio.sleep(0.05)

    assert ctl.hooks.running is False  # recovery failed, and we are still alive


def test_libvirt_lifecycle_mapping() -> None:
    """The real source's event mapping, against libvirt's own constants."""
    libvirt = pytest.importorskip("libvirt")

    destroyed = _map_lifecycle(
        libvirt.VIR_DOMAIN_EVENT_STOPPED, libvirt.VIR_DOMAIN_EVENT_STOPPED_DESTROYED
    )
    assert destroyed == DomainEvent(DomainEventKind.STOPPED, reason="destroyed")

    shutdown = _map_lifecycle(
        libvirt.VIR_DOMAIN_EVENT_STOPPED, libvirt.VIR_DOMAIN_EVENT_STOPPED_SHUTDOWN
    )
    assert shutdown == DomainEvent(DomainEventKind.STOPPED, reason="shutdown")

    crashed = _map_lifecycle(
        libvirt.VIR_DOMAIN_EVENT_STOPPED, libvirt.VIR_DOMAIN_EVENT_STOPPED_CRASHED
    )
    assert crashed is not None and crashed.kind is DomainEventKind.CRASHED

    # A start is not our business.
    assert _map_lifecycle(libvirt.VIR_DOMAIN_EVENT_STARTED, 0) is None
