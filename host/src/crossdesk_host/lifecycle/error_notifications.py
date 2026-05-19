"""High-level error-notification helpers.

Thin layer over :class:`Notifier` that bakes in the
summary/body/urgency/icon/category combination for each
user-visible error path the host can surface. Call sites pass in
their ``Notifier`` (``SubprocessNotifier`` in production,
``DBusNotifier`` once it lands, ``RecordingNotifier`` in tests) and
get a stable wire shape regardless of which transport carries the
notification.

Strings are wrapped in ``_()`` so the i18n extractor (``scripts/i18n.sh
extract``) picks them up; the .pot template is the source of truth
for translators.

Per FOLLOWUPS Week 11 P0: wire host-side errors (VM won't start,
forced stop, RDP drop, credentials repair needed) to
``org.freedesktop.Notifications`` via ``notify-send`` /
``dbus-next``. The notifier itself is opaque here; this module
shapes *what* gets sent.
"""

from __future__ import annotations

from crossdesk_host.i18n import _
from crossdesk_host.lifecycle.notifications import Notifier, Urgency


def notify_vm_failed_to_start(notifier: Notifier, reason: str = "") -> None:
    """VM startup failed — libvirt rejected the domain or it crashed
    immediately after launch. Critical urgency because the user can't
    do anything until they see this."""
    notifier.notify(
        summary=_("CrossDesk: VM failed to start"),
        body=reason or _("Run: crossdesk doctor"),
        urgency=Urgency.CRITICAL,
        icon="dialog-error",
        category="device.error",
    )


def notify_forced_stop(notifier: Notifier, reason: str = "") -> None:
    """Watchdog hard-destroyed the VM after sustained silence.
    Critical because in-flight work in the guest is lost."""
    notifier.notify(
        summary=_("CrossDesk: VM was force-stopped"),
        body=reason or _("Heartbeat watchdog detected the guest was unresponsive."),
        urgency=Urgency.CRITICAL,
        icon="process-stop",
        category="device.error",
    )


def notify_rdp_drop(notifier: Notifier, app_name: str = "") -> None:
    """FreeRDP RAIL session exited unexpectedly (network blip, guest
    side closed the channel, etc.). Normal urgency — usually
    auto-reconnect will recover transparently."""
    name = app_name or _("a CrossDesk app")
    notifier.notify(
        summary=_("CrossDesk: Connection dropped"),
        body=_("{name} disconnected; reconnecting…").format(name=name),
        urgency=Urgency.NORMAL,
        icon="network-error",
        category="network.disconnected",
    )


def notify_credentials_repair_needed(notifier: Notifier, hint: str = "") -> None:
    """Guest LogonUserW rejected the credentials from vm.toml. User
    must run ``crossdesk vm credentials repair`` (or the equivalent
    repair hint) before RAIL sessions can spawn."""
    notifier.notify(
        summary=_("CrossDesk: Guest credentials need repair"),
        body=hint or _("Run: crossdesk vm credentials repair"),
        urgency=Urgency.NORMAL,
        icon="dialog-password",
        category="device.error",
    )


def notify_suspend_resume_failed(notifier: Notifier, reason: str = "") -> None:
    """Sleep/wake coordination with the guest agent failed — usually
    means we couldn't pause libvirt on suspend or the guest didn't
    re-establish the control stream on resume."""
    notifier.notify(
        summary=_("CrossDesk: Sleep/resume sync failed"),
        body=reason or _("Run: crossdesk doctor"),
        urgency=Urgency.NORMAL,
        icon="dialog-warning",
        category="device.error",
    )
