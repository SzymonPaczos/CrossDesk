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

Hibernation detection (FOLLOWUPS:696): on every suspend we stamp
``time.time()`` (wall) plus ``time.monotonic()``; on resume we compare
both. A *forward* wall jump > 1h that is matched by an equally large
monotonic delta is treated as hibernation (suspend-to-disk could last
hours/days, leaving AuthContext nonces and monotonic sequence
counters arbitrarily stale). NTP-only corrections move wall without
moving monotonic, so they are filtered out by the cross-check.
Detection fires a registered hook list — downstream components
(heartbeat FSM, AuthValidator, RailManager) opt into the resync; the
coordinator itself only emits a structured log and dispatches.
"""

from __future__ import annotations

import time
from typing import Callable, List, Optional

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.lifecycle.error_notifications import (
    notify_suspend_resume_failed,
)
from crossdesk_host.lifecycle.notifications import Notifier
from crossdesk_host.observability.log import get_logger
from crossdesk_host.watchdog import HeartbeatFsm

logger = get_logger("host.lifecycle.coordinator")

# Wall-clock jump beyond this many seconds, when corroborated by a
# matching monotonic delta, indicates hibernation rather than a normal
# screen-blank-style sleep. One hour is a generous floor: normal
# suspend-to-RAM cycles overnight rarely cross it, while
# suspend-to-disk frequently does.
HIBERNATION_WALL_THRESHOLD_S = 3600.0

# Wall and monotonic clocks drift apart even on the same boot
# (scheduler jitter, brief NTP slews, etc.). Allow ten seconds of
# slack before flagging a wall delta as an NTP jump unmatched by
# monotonic — well below the one-hour hibernation floor so the
# distinction is unambiguous.
HIBERNATION_CLOCK_MISMATCH_TOLERANCE_S = 10.0


HibernationHook = Callable[[float, float], None]
"""Hook signature: ``(wall_delta_s, monotonic_delta_s) -> None``.

Hooks run synchronously on the dispatch thread after libvirt has
resumed and the FSMs have left SUSPENDED. Exceptions raised by a hook
are logged but do not propagate — one misbehaving downstream must not
prevent the rest of the resume sequence.
"""


class LifecycleCoordinator:
    def __init__(
        self,
        libvirt_ctl: LibvirtController,
        notifier: Optional[Notifier] = None,
    ) -> None:
        self.libvirt_ctl = libvirt_ctl
        self.notifier = notifier
        self._registered_fsms: List[HeartbeatFsm] = []
        self._hibernation_hooks: List[HibernationHook] = []
        self._suspended = False
        self._suspend_wall_s: Optional[float] = None
        self._suspend_monotonic_s: Optional[float] = None

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

    def register_hibernation_hook(self, hook: HibernationHook) -> None:
        """Subscribe ``hook`` to hibernation-detected events.

        Hooks fire in registration order during ``on_resumed`` once
        hibernation has been detected — see module docstring for the
        criteria. The coordinator does not deduplicate by identity:
        callers must avoid registering the same hook twice.
        """
        self._hibernation_hooks.append(hook)

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
        self._suspend_wall_s = time.time()
        self._suspend_monotonic_s = time.monotonic()
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
        # Snapshot before clearing so the hook dispatch below sees the
        # same values that drove the detection.
        suspend_wall = self._suspend_wall_s
        suspend_monotonic = self._suspend_monotonic_s
        self._suspend_wall_s = None
        self._suspend_monotonic_s = None
        logger.info("lifecycle_resume_complete", fsms=len(self._registered_fsms))
        if suspend_wall is not None and suspend_monotonic is not None:
            self._maybe_detect_hibernation(suspend_wall, suspend_monotonic)

    def _maybe_detect_hibernation(
        self, suspend_wall_s: float, suspend_monotonic_s: float
    ) -> None:
        wall_delta = time.time() - suspend_wall_s
        monotonic_delta = time.monotonic() - suspend_monotonic_s
        # Backward wall jump (NTP correction backwards, DST fall-back)
        # cannot represent hibernation — the calendar can't run in
        # reverse across a single suspend.
        if wall_delta <= HIBERNATION_WALL_THRESHOLD_S:
            return
        # Wall jumped forward enough to look like hibernation, but
        # monotonic didn't follow → the kernel didn't actually sleep
        # for an hour, so an NTP daemon stepped the wall clock during
        # the brief suspend window.
        clock_skew = abs(wall_delta - monotonic_delta)
        if clock_skew > HIBERNATION_CLOCK_MISMATCH_TOLERANCE_S:
            logger.info(
                "lifecycle_clock_jump_ignored",
                wall_delta_s=round(wall_delta, 1),
                monotonic_delta_s=round(monotonic_delta, 1),
            )
            return
        logger.warning(
            "lifecycle_hibernation_detected",
            wall_delta_s=round(wall_delta, 1),
            monotonic_delta_s=round(monotonic_delta, 1),
            hooks=len(self._hibernation_hooks),
        )
        for hook in self._hibernation_hooks:
            try:
                hook(wall_delta, monotonic_delta)
            except Exception as exc:
                logger.warning(
                    "lifecycle_hibernation_hook_failed",
                    hook=getattr(hook, "__qualname__", repr(hook)),
                    error=str(exc),
                )
