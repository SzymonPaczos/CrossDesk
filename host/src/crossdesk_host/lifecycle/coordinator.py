"""LifecycleCoordinator — orchestrates host suspend/resume against the
heartbeat FSM and the libvirt domain.

Pure synchronous logic. The Linux-only D-Bus listener
(``.dbus_listener``) calls these methods on
``org.freedesktop.login1.Manager.PrepareForSleep`` (and the matching
resume) signals; tests call them directly to exercise the suspend path
without needing a real session bus.

Ordering matters and is documented in
``docs/LIFECYCLE.md``: on suspend we move every registered FSM into
SUSPENDED *before* asking libvirt to pause the domain — otherwise a
stalled heartbeat across the pause could trip false-positive
HARD_DESTROY. On resume we go libvirt-first so the guest is actually
running when FSMs leave SUSPENDED into the PROBING grace window.
"""

from __future__ import annotations

from typing import List, Optional

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.lifecycle.error_notifications import (
    notify_suspend_resume_failed,
)
from crossdesk_host.lifecycle.notifications import Notifier
from crossdesk_host.observability.log import get_logger
from crossdesk_host.watchdog import HeartbeatFsm

logger = get_logger("host.lifecycle.coordinator")


class LifecycleCoordinator:
    def __init__(
        self,
        libvirt_ctl: LibvirtController,
        notifier: Optional[Notifier] = None,
    ) -> None:
        self.libvirt_ctl = libvirt_ctl
        self.notifier = notifier
        self._registered_fsms: List[HeartbeatFsm] = []
        self._suspended = False

    @property
    def suspended(self) -> bool:
        return self._suspended

    def register_fsm(self, fsm: HeartbeatFsm) -> None:
        # Identity (`is`) rather than equality: HeartbeatFsm is a dataclass,
        # so two freshly-constructed instances compare equal by structural
        # field values until they diverge.
        if not any(existing is fsm for existing in self._registered_fsms):
            self._registered_fsms.append(fsm)

    def unregister_fsm(self, fsm: HeartbeatFsm) -> None:
        self._registered_fsms = [
            existing for existing in self._registered_fsms if existing is not fsm
        ]

    def on_prepare_for_sleep(self) -> None:
        if self._suspended:
            return
        logger.info("lifecycle_suspend_begin", fsms=len(self._registered_fsms))
        for fsm in self._registered_fsms:
            fsm.suspend()
        try:
            self.libvirt_ctl.suspend()
        except Exception as exc:
            # FSMs already moved into SUSPENDED above; libvirt-side
            # failure means the host went to sleep with the VM
            # technically still running. Surface to the user; the
            # daemon must still see the exception so its supervisor
            # can react.
            if self.notifier is not None:
                notify_suspend_resume_failed(
                    self.notifier,
                    reason=f"libvirt suspend raised: {exc}",
                )
            raise
        self._suspended = True
        logger.info("lifecycle_suspend_complete")

    def on_resumed(self) -> None:
        if not self._suspended:
            return
        logger.info("lifecycle_resume_begin")
        try:
            self.libvirt_ctl.resume()
        except Exception as exc:
            if self.notifier is not None:
                notify_suspend_resume_failed(
                    self.notifier,
                    reason=f"libvirt resume raised: {exc}",
                )
            raise
        for fsm in self._registered_fsms:
            fsm.resume()
        self._suspended = False
        logger.info("lifecycle_resume_complete", fsms=len(self._registered_fsms))
