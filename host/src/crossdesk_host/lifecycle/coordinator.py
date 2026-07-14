"""LifecycleCoordinator — orchestrates host suspend/resume against the
heartbeat FSM and the libvirt domain.

The Linux-only D-Bus listener (``.dbus_listener``) drives this on
``org.freedesktop.login1.Manager.PrepareForSleep`` (and the matching resume)
signals; the management ``Suspend`` / ``Resume`` RPCs drive it too.

Ordering matters and is documented in
``docs/LIFECYCLE.md``: on suspend we move every registered FSM into
SUSPENDED *before* asking libvirt to pause the domain — otherwise a
stalled heartbeat across the pause could trip false-positive
HARD_DESTROY. On resume we go libvirt-first so the guest is actually
running when FSMs leave SUSPENDED into the PROBING grace window.

**The two halves cost wildly different amounts of time, and that shapes the
API.** Moving the FSMs is pure Python and instant. Pausing the domain is a
blocking libvirt C call that can take seconds against a slow storage backend and
forever against a wedged libvirtd. The D-Bus signal handler runs *on the event
loop* (dbus-next dispatches it there), so doing both inline froze the entire
daemon — heartbeats, gRPC, everything — at precisely the moment the host was
going to sleep. Hence the split:

* :meth:`suspend_fsms` stays **synchronous**. It is the actual data-loss
  protection, and we hold no systemd delay inhibitor (that is still a Phase-7
  stub in ``watchdog/sleep_sync.py``), so nothing is waiting for us: the kernel
  can freeze the moment the handler yields. This has to land before the freeze,
  not on some later loop iteration.
* the libvirt half is **offloaded and deadline-bound** through ``libvirt_call``,
  so a slow pause costs latency instead of a frozen daemon.
* :meth:`on_prepare_for_sleep` / :meth:`on_resumed` compose the two in the
  correct order for callers that can await.

Resume needs no such care: the FSMs sit parked in SUSPENDED and cannot escalate
until we release them, so the whole sequence can run off the loop.

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
from typing import Callable, List, Optional, Protocol

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.libvirt_ctl import libvirt_call
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


class Suspendable(Protocol):
    """Anything the coordinator can move in/out of SUSPENDED in bulk.

    Satisfied by a single :class:`HeartbeatFsm` and by
    ``HeartbeatServiceServicer`` (whose ``suspend`` / ``resume`` fan the
    call out to every active per-channel FSM, including channels that
    attach mid-suspend — it tracks its own ``suspended`` flag for that).
    Wiring the servicer in as the ``fsm_group`` lets the daemon keep one
    source of truth for live FSMs instead of mirroring the registry here.
    """

    def suspend(self) -> None: ...

    def resume(self) -> None: ...


class LifecycleCoordinator:
    def __init__(
        self,
        libvirt_ctl: LibvirtController,
        notifier: Optional[Notifier] = None,
        fsm_group: Optional[Suspendable] = None,
    ) -> None:
        self.libvirt_ctl = libvirt_ctl
        self.notifier = notifier
        # Optional bulk FSM owner (the heartbeat servicer). Preferred over
        # register_fsm for the daemon: it already tracks every live channel
        # and inherits SUSPENDED onto late-attaching ones.
        self._fsm_group = fsm_group
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

    def suspend_fsms(self) -> None:
        """Move every registered FSM into SUSPENDED. Synchronous, on purpose.

        This is the half that must never be deferred: an FSM still ticking
        across the host's sleep piles up missed pongs and escalates to
        HARD_DESTROY, which on the real controller is ``virsh destroy`` — the VM
        and everything unsaved in it, gone. Since the daemon holds no systemd
        delay inhibitor, the kernel is free to freeze as soon as the D-Bus
        handler yields, so this runs *inside* the handler rather than in a task.

        Idempotent: ``HeartbeatFsm.suspend`` is, and the servicer tracks its own
        flag, so a repeated PrepareForSleep is harmless.
        """
        if self._suspended:
            return
        logger.info("lifecycle_suspend_begin", fsms=len(self._registered_fsms))
        for fsm in self._registered_fsms:
            fsm.suspend()
        if self._fsm_group is not None:
            self._fsm_group.suspend()

    async def pause_domain(self) -> None:
        """Pause the domain off the event loop, bounded by a deadline.

        Call :meth:`suspend_fsms` first — see the module's ordering contract.
        """
        if self._suspended:
            return
        try:
            await libvirt_call(self.libvirt_ctl.suspend)
        except Exception as exc:
            # FSMs already moved into SUSPENDED; libvirt-side failure means the
            # host went to sleep with the VM technically still running. Surface
            # to the user; the caller must still see the exception so its
            # supervisor can react.
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

    async def on_prepare_for_sleep(self) -> None:
        """FSMs into SUSPENDED, then pause the domain — for callers that await."""
        if self._suspended:
            return
        self.suspend_fsms()
        await self.pause_domain()

    async def on_resumed(self) -> None:
        if not self._suspended:
            return
        logger.info("lifecycle_resume_begin")
        try:
            await libvirt_call(self.libvirt_ctl.resume)
        except Exception as exc:
            if self.notifier is not None:
                notify_suspend_resume_failed(
                    self.notifier,
                    reason=f"libvirt resume raised: {exc}",
                )
            raise
        for fsm in self._registered_fsms:
            fsm.resume()
        if self._fsm_group is not None:
            self._fsm_group.resume()
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
