"""DomainEventReactor + MockDomainEventSource.

Pins the handler logic the Phase-3 libvirt source will feed: a crash logs
+ notifies, a benign stop stays quiet, and the mock source delivers events
to the reactor through the same callback contract the real source will use.
"""

from __future__ import annotations

import pytest

from crossdesk_host.lifecycle.domain_events import (
    DomainEvent,
    DomainEventKind,
    DomainEventReactor,
    MockDomainEventSource,
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
