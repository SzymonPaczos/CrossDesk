"""Autopause controller — suspend the VM after N seconds of no active RAIL sessions.

When no Windows apps are being displayed (all RAIL sessions closed), there is no
reason to keep the guest VM running. After ``idle_timeout_s`` seconds of idle time
the controller calls ``libvirt_ctl.suspend()`` and logs a WARNING so the operator
knows why the VM went quiet.

Usage pattern (called from the RAIL manager or daemon):

    ctrl = AutopauseController(
        idle_timeout_s=300,
        heartbeat_suspend=heartbeat_servicer.suspend,
        heartbeat_resume=heartbeat_servicer.resume,
        balloon_hook=NoopBalloonHook(),  # Phase 7 driver swaps this in
    )
    task = asyncio.create_task(ctrl.run(libvirt_ctl))

    # When a RAIL session opens:
    ctrl.session_opened()  # triggers resume() if currently paused

    # When a RAIL session closes:
    ctrl.session_closed()

    # On daemon shutdown:
    task.cancel()

Three-way coordination (FOLLOWUPS:665):

1. **Heartbeat FSM** — before calling ``libvirt_ctl.suspend()`` we invoke
   ``heartbeat_suspend()`` so every active Channel's FSM transitions into
   SUSPENDED. Missed pongs across the pause then become no-ops instead of
   trip-wires escalating toward HARD_DESTROY. Mirrors
   :class:`LifecycleCoordinator.on_prepare_for_sleep` ordering.
2. **virtio-balloon** — ``balloon_hook.on_pause("idle")`` fires inline; the
   Phase 7 driver implementation will drop the balloon target so the host
   can reclaim guest cold pages. The default :class:`NoopBalloonHook` just
   logs.
3. **libvirt** — last, because the host needs the FSM + balloon adjustments
   committed before the guest actually stops ticking. On resume we go
   libvirt-first so the guest is running by the time the FSM exits
   SUSPENDED into the PROBING grace window.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.watchdog.balloon import BalloonHook, NoopBalloonHook

logger = logging.getLogger(__name__)

HeartbeatSuspendCallable = Callable[[], None]
"""Signature for the heartbeat suspend / resume callbacks injected
into :class:`AutopauseController`. Typically bound to
:meth:`crossdesk_host.ipc.heartbeat.HeartbeatServiceServicer.suspend`
and :meth:`...resume`. Default is a no-op so unit tests that don't
care about FSM coordination can leave them unset."""


def _noop() -> None:
    """Default heartbeat suspend/resume — used until daemon wiring lands."""


class AutopauseController:
    """Tracks active RAIL sessions and suspends the VM when idle.

    Thread-safety: designed for single-threaded asyncio use. Call
    ``session_opened`` / ``session_closed`` from coroutines on the same
    event loop as ``run``.
    """

    def __init__(
        self,
        idle_timeout_s: float = 300,
        *,
        heartbeat_suspend: HeartbeatSuspendCallable = _noop,
        heartbeat_resume: HeartbeatSuspendCallable = _noop,
        balloon_hook: Optional[BalloonHook] = None,
    ) -> None:
        self.idle_timeout_s = idle_timeout_s
        self._heartbeat_suspend = heartbeat_suspend
        self._heartbeat_resume = heartbeat_resume
        self._balloon_hook: BalloonHook = balloon_hook or NoopBalloonHook()
        self._active_sessions: int = 0
        # Event is set when session count drops to 0; cleared when any
        # session opens. ``run`` waits on this to avoid busy-looping.
        self._idle_event: asyncio.Event = asyncio.Event()
        self._paused: bool = False
        self._libvirt_ctl: Optional[LibvirtController] = None

    @property
    def active_sessions(self) -> int:
        """Number of currently open RAIL sessions (read-only)."""
        return self._active_sessions

    @property
    def paused(self) -> bool:
        """``True`` between an idle-timeout pause and a matching resume."""
        return self._paused

    def session_opened(self) -> None:
        """Record that a new RAIL session has been opened.

        Clears the idle event so any pending suspend timer is cancelled.
        If the VM is currently paused (idle-timeout fired earlier), this
        also triggers :meth:`resume` so the FSM exits SUSPENDED and the
        balloon hook signals the driver to climb back to active size.
        """
        self._active_sessions += 1
        # A new session arrived — clear idle so the run() wait_for doesn't
        # fire. The timeout coroutine inside run() will raise TimeoutError
        # and the outer loop will restart with a fresh wait.
        self._idle_event.clear()
        logger.debug(
            "autopause: session opened (active_sessions=%d)", self._active_sessions
        )
        if self._paused:
            self.resume()

    def session_closed(self) -> None:
        """Record that a RAIL session has been closed.

        When the count reaches zero, signals the idle event so ``run``
        can start the suspend timer.
        """
        if self._active_sessions > 0:
            self._active_sessions -= 1
        if self._active_sessions == 0:
            self._idle_event.set()
        logger.debug(
            "autopause: session closed (active_sessions=%d)", self._active_sessions
        )

    def resume(self) -> None:
        """Resume an idle-paused VM. Safe to call when not paused (no-op).

        Ordering mirrors :class:`LifecycleCoordinator.on_resumed` —
        libvirt-first so the guest is ticking before the FSM exits
        SUSPENDED into the PROBING grace window.
        """
        if not self._paused:
            return
        if self._libvirt_ctl is None:
            # Should never happen: pause-path always sets _libvirt_ctl.
            # Belt-and-braces in case a caller invokes resume() before
            # the run() loop ever stamped it.
            logger.warning("autopause: resume() called with no libvirt_ctl")
            self._paused = False
            return
        logger.info("autopause_resume_begin")
        try:
            self._libvirt_ctl.resume()
        except RuntimeError as exc:
            logger.error("autopause: libvirt resume() failed: %s", exc)
        self._heartbeat_resume()
        self._balloon_hook.on_resume()
        self._paused = False
        logger.info("autopause_resume_complete")

    async def run(self, libvirt_ctl: LibvirtController) -> None:
        """Autopause loop. Runs until cancelled by the caller.

        The loop waits for the idle event (set when session count reaches 0),
        then waits ``idle_timeout_s`` seconds. If no new session opened during
        the wait, the VM is suspended. If a session opens, the timeout fires a
        ``TimeoutError`` via ``asyncio.wait_for`` and the loop restarts.

        No busy-looping: the ``asyncio.Event`` drives all transitions.
        """
        logger.info(
            "autopause: running (idle_timeout_s=%s)", self.idle_timeout_s
        )
        self._libvirt_ctl = libvirt_ctl
        while True:
            # Park until we become idle (session count == 0).
            await self._idle_event.wait()

            # Attempt to wait out the full idle timeout. If a session opens
            # during the wait, session_opened() clears _idle_event but we're
            # already past the wait() call — so we use wait_for on a re-arm of
            # the event: wait for the event to become *set again* after being
            # cleared by session_opened(). The simpler approach: wait for
            # a "cancel" signal represented by _idle_event being cleared
            # (session_opened clears it) within the timeout window.
            #
            # Pattern: wait idle_timeout_s; if _idle_event is still set
            # (still idle), proceed with suspend. If cleared (new session
            # arrived), loop back and wait for the next idle period.
            try:
                await asyncio.wait_for(
                    self._wait_for_session_open(), timeout=self.idle_timeout_s
                )
                # A session opened before the timeout — restart the outer loop
                # which will block on _idle_event.wait() again.
                logger.debug(
                    "autopause: session opened during idle window — suspend cancelled"
                )
            except asyncio.TimeoutError:
                # Full idle_timeout_s elapsed with no new session.
                if self._active_sessions == 0:
                    self._pause(libvirt_ctl)
                else:
                    # Session count went back up between the timeout firing
                    # and our check — race resolved in favour of not suspending.
                    logger.debug(
                        "autopause: timeout fired but sessions are active again "
                        "(active_sessions=%d) — skipping suspend",
                        self._active_sessions,
                    )
                    self._idle_event.clear()

    def _pause(self, libvirt_ctl: LibvirtController) -> None:
        """Coordinated three-way pause: heartbeat → balloon → libvirt.

        Order matters: heartbeat FSMs must be SUSPENDED before the
        VM stops sending pongs, otherwise miss counts will escalate
        toward HARD_DESTROY across the pause. Balloon adjustments go
        next so the driver can drop the target before the guest is
        frozen. libvirt suspend is last.
        """
        if self._paused:
            return
        logger.warning(
            "autopause: idle for %ss with no active RAIL sessions — suspending VM",
            self.idle_timeout_s,
        )
        logger.info("autopause_pause_begin")
        # 1. Heartbeat FSMs first — see _pause docstring + FOLLOWUPS:665.
        self._heartbeat_suspend()
        # 2. Balloon hook — Phase 7 driver drops the target here.
        self._balloon_hook.on_pause("idle")
        # 3. libvirt last; once the domain pauses, no more pongs flow.
        try:
            libvirt_ctl.suspend()
        except RuntimeError as exc:
            logger.error("autopause: suspend() failed: %s", exc)
            # Roll back the heartbeat side so we don't strand a live VM
            # with FSMs stuck in SUSPENDED.
            self._heartbeat_resume()
            self._balloon_hook.on_resume()
            self._idle_event.clear()
            return
        self._paused = True
        # Reset idle_event so the loop blocks until sessions return.
        self._idle_event.clear()
        logger.info("autopause_pause_complete")

    async def _wait_for_session_open(self) -> None:
        """Coroutine that completes when _idle_event is cleared.

        session_opened() clears the event; this coroutine polls until
        the event is no longer set. Used inside wait_for so that a session
        opening cancels the pending suspend timer via TimeoutError suppression.
        """
        # Spin at 50ms resolution — cheap compared to the idle_timeout_s
        # granularity (minutes). An asyncio.Event that fires on "cleared"
        # would be cleaner but the stdlib only exposes "set"; this is the
        # conventional approach for "wait until condition is false".
        while self._idle_event.is_set():
            await asyncio.sleep(0.05)
