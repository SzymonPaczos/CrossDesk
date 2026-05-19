"""Contract tests for :mod:`crossdesk_host.lifecycle.error_notifications`.

The helpers wrap :class:`Notifier.notify` with prepared shapes for
each user-visible error path. Tests assert on the recorded call —
summary/body/urgency/icon/category — using :class:`RecordingNotifier`,
so no D-Bus or subprocess is touched.
"""

from __future__ import annotations

from crossdesk_host.lifecycle import error_notifications as en
from crossdesk_host.lifecycle.notifications import RecordingNotifier, Urgency


def test_vm_failed_to_start_critical() -> None:
    nf = RecordingNotifier()
    en.notify_vm_failed_to_start(nf, reason="libvirt domain refused to start")

    assert len(nf.calls) == 1
    call = nf.calls[0]
    assert "VM failed to start" in call.summary
    assert "libvirt" in call.body
    assert call.urgency is Urgency.CRITICAL
    assert call.icon == "dialog-error"
    assert call.category == "device.error"


def test_vm_failed_to_start_default_body_when_no_reason() -> None:
    nf = RecordingNotifier()
    en.notify_vm_failed_to_start(nf)
    assert "doctor" in nf.calls[0].body


def test_forced_stop_critical() -> None:
    nf = RecordingNotifier()
    en.notify_forced_stop(nf)

    call = nf.calls[0]
    assert "force-stopped" in call.summary
    assert call.urgency is Urgency.CRITICAL
    assert call.icon == "process-stop"


def test_rdp_drop_interpolates_app_name() -> None:
    nf = RecordingNotifier()
    en.notify_rdp_drop(nf, app_name="Microsoft Word")

    call = nf.calls[0]
    assert "Microsoft Word" in call.body
    assert call.urgency is Urgency.NORMAL
    assert call.icon == "network-error"


def test_rdp_drop_uses_generic_label_when_no_app() -> None:
    nf = RecordingNotifier()
    en.notify_rdp_drop(nf)
    assert "CrossDesk app" in nf.calls[0].body


def test_credentials_repair_includes_hint() -> None:
    nf = RecordingNotifier()
    en.notify_credentials_repair_needed(nf, hint="Run crossdesk vm credentials repair")

    call = nf.calls[0]
    assert "credentials" in call.summary.lower()
    assert "repair" in call.body
    assert call.icon == "dialog-password"


def test_credentials_repair_default_hint() -> None:
    nf = RecordingNotifier()
    en.notify_credentials_repair_needed(nf)
    assert "crossdesk vm credentials repair" in nf.calls[0].body


def test_suspend_resume_failed_normal_urgency() -> None:
    nf = RecordingNotifier()
    en.notify_suspend_resume_failed(nf, reason="libvirt pause timed out")

    call = nf.calls[0]
    assert "Sleep/resume" in call.summary
    assert "libvirt pause" in call.body
    assert call.urgency is Urgency.NORMAL
    assert call.icon == "dialog-warning"


def test_helpers_do_not_raise_with_empty_strings() -> None:
    """Every helper must accept the bare-defaults form so call sites
    can fire-and-forget without composing a reason string."""
    nf = RecordingNotifier()
    en.notify_vm_failed_to_start(nf)
    en.notify_forced_stop(nf)
    en.notify_rdp_drop(nf)
    en.notify_credentials_repair_needed(nf)
    en.notify_suspend_resume_failed(nf)
    assert len(nf.calls) == 5
