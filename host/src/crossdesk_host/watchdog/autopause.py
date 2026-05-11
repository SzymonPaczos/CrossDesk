"""Autopause controller — suspend the VM after N seconds of no active RAIL sessions.

When no Windows apps are being displayed (all RAIL sessions closed), there is no
reason to keep the guest VM running. After ``idle_timeout_s`` seconds of idle time
the controller calls ``libvirt_ctl.suspend()`` and logs a WARNING so the operator
knows why the VM went quiet.

Usage pattern (called from the RAIL manager or daemon):

    ctrl = AutopauseController(idle_timeout_s=300)
    task = asyncio.create_task(ctrl.run(libvirt_ctl))

    # When a RAIL session opens:
    ctrl.session_opened()

    # When a RAIL session closes:
    ctrl.session_closed()

    # On daemon shutdown:
    task.cancel()

FSM integration is a Phase 7 stub — the FSM must be moved into SUSPENDED before
calling ``libvirt_ctl.suspend()`` so that heartbeat misses across the pause do not
trip a false-positive HARD_DESTROY. That wiring is deferred because it requires
coordinating with the HeartbeatServiceServicer and the Phase 3 heartbeat FSM; for
now the module logs a placeholder and calls suspend() directly.
"""

from __future__ import annotations

import asyncio
import logging

from crossdesk_host.abstractions.libvirt import LibvirtController

logger = logging.getLogger(__name__)


class AutopauseController:
    """Tracks active RAIL sessions and suspends the VM when idle.

    Thread-safety: designed for single-threaded asyncio use. Call
    ``session_opened`` / ``session_closed`` from coroutines on the same
    event loop as ``run``.
    """

    def __init__(self, idle_timeout_s: int = 300) -> None:
        self.idle_timeout_s = idle_timeout_s
        self._active_sessions: int = 0
        # Event is set when session count drops to 0; cleared when any
        # session opens. ``run`` waits on this to avoid busy-looping.
        self._idle_event: asyncio.Event = asyncio.Event()

    @property
    def active_sessions(self) -> int:
        """Number of currently open RAIL sessions (read-only)."""
        return self._active_sessions

    def session_opened(self) -> None:
        """Record that a new RAIL session has been opened.

        Clears the idle event so any pending suspend timer is cancelled.
        """
        self._active_sessions += 1
        # A new session arrived — clear idle so the run() wait_for doesn't
        # fire. The timeout coroutine inside run() will raise TimeoutError
        # and the outer loop will restart with a fresh wait.
        self._idle_event.clear()
        logger.debug(
            "autopause: session opened (active_sessions=%d)", self._active_sessions
        )

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

    async def run(self, libvirt_ctl: LibvirtController) -> None:
        """Autopause loop. Runs until cancelled by the caller.

        The loop waits for the idle event (set when session count reaches 0),
        then waits ``idle_timeout_s`` seconds. If no new session opened during
        the wait, the VM is suspended. If a session opens, the timeout fires a
        ``TimeoutError`` via ``asyncio.wait_for`` and the loop restarts.

        No busy-looping: the ``asyncio.Event`` drives all transitions.
        """
        logger.info(
            "autopause: running (idle_timeout_s=%d)", self.idle_timeout_s
        )
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
                    logger.warning(
                        "autopause: idle for %ds with no active RAIL sessions — "
                        "suspending VM",
                        self.idle_timeout_s,
                    )
                    # Phase 7 stub: in the real implementation the FSM must be
                    # moved into SUSPENDED before calling libvirt_ctl.suspend()
                    # so that heartbeat misses across the pause don't trip a
                    # false-positive HARD_DESTROY.
                    logger.info(
                        "autopause: FSM SUSPENDED transition — Phase 7 stub "
                        "(FSM wiring deferred; calling suspend() directly)"
                    )
                    try:
                        libvirt_ctl.suspend()
                    except RuntimeError as exc:
                        logger.error("autopause: suspend() failed: %s", exc)
                    # Reset idle_event so the loop blocks until sessions return.
                    self._idle_event.clear()
                else:
                    # Session count went back up between the timeout firing
                    # and our check — race resolved in favour of not suspending.
                    logger.debug(
                        "autopause: timeout fired but sessions are active again "
                        "(active_sessions=%d) — skipping suspend",
                        self._active_sessions,
                    )
                    self._idle_event.clear()

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
