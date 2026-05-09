"""Notifier unit tests (Week 11)."""

from __future__ import annotations

from crossdesk_host.lifecycle.notifications import (
    NotificationCall,
    RecordingNotifier,
    Urgency,
)


def test_recording_notifier_captures_call() -> None:
    n = RecordingNotifier()
    n.notify("VM hard-destroyed", body="recovering", urgency=Urgency.CRITICAL)
    assert n.calls == [
        NotificationCall(
            summary="VM hard-destroyed",
            body="recovering",
            urgency=Urgency.CRITICAL,
            icon="",
            category="",
        )
    ]


def test_recording_notifier_default_urgency() -> None:
    n = RecordingNotifier()
    n.notify("Hello")
    assert n.calls[0].urgency == Urgency.NORMAL


def test_recording_notifier_multiple_calls() -> None:
    n = RecordingNotifier()
    n.notify("first")
    n.notify("second", urgency=Urgency.LOW)
    n.notify("third", icon="dialog-error", category="device.error")
    assert [c.summary for c in n.calls] == ["first", "second", "third"]
    assert n.calls[2].icon == "dialog-error"
    assert n.calls[2].category == "device.error"
