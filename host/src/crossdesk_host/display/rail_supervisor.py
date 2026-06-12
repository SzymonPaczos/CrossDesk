"""Supervises spawned FreeRDP RAIL sessions for the lifetime of the daemon.

The launch path (``ManagementService.Launch``) spawns one ``xfreerdp``
per app and, before this module, did nothing further: a session that
crashed or whose window the user closed was never awaited, so the
process lingered as a zombie ``<defunct>`` and the daemon never learned
the connection had dropped — the user just saw a dead window with no
message and no log of why.

:class:`RailSupervisor` closes that gap. For each session it starts one
asyncio task that awaits the FreeRDP process exit (which also reaps it),
classifies the exit, and:

- **we terminated it** (daemon shutdown / explicit stop) → info log, quiet.
- **clean exit, code 0** (user closed the window) → info log, quiet.
- **non-zero exit** (connection failure / crash) → warning log carrying
  the captured FreeRDP error banner, plus a user-facing "connection
  dropped" notification.

The captured banner comes from the per-app log the real invocation tees
FreeRDP's output into (``freerdp/real.py``); the mock has none and the
tail is simply empty.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Dict, Optional, Set

from crossdesk_host.abstractions.freerdp import FreeRDPInvocation, RailSession
from crossdesk_host.lifecycle.error_notifications import notify_rdp_drop
from crossdesk_host.lifecycle.notifications import Notifier
from crossdesk_host.observability import get_logger

logger = get_logger("host.display.rail_supervisor")

# Callback invoked (best-effort) when a supervised session exits, so the
# launcher can drop its own handle. Receives the session and exit code.
ExitCallback = Callable[[RailSession, int], None]


class RailSupervisor:
    def __init__(
        self,
        freerdp_inv: FreeRDPInvocation,
        notifier: Optional[Notifier] = None,
    ) -> None:
        self._freerdp = freerdp_inv
        self._notifier = notifier
        self._tasks: Dict[int, asyncio.Task[None]] = {}
        # pids we asked to stop, so their exit doesn't read as a crash.
        self._expected: Set[int] = set()

    def supervise(
        self,
        session: RailSession,
        *,
        app_id: str,
        display_name: str = "",
        on_exit: Optional[ExitCallback] = None,
    ) -> asyncio.Task[None]:
        """Start watching ``session``. Returns the monitor task (mostly
        for tests to await)."""
        task = asyncio.create_task(
            self._monitor(session, app_id, display_name or app_id, on_exit)
        )
        self._tasks[session.pid] = task
        return task

    async def _monitor(
        self,
        session: RailSession,
        app_id: str,
        display_name: str,
        on_exit: Optional[ExitCallback],
    ) -> None:
        try:
            returncode = await self._freerdp.wait(session)
        except Exception:
            # A failure in the wait machinery itself must not kill the
            # supervisor or leak the task silently.
            logger.exception("freerdp_supervise_failed", app_id=app_id, pid=session.pid)
            self._tasks.pop(session.pid, None)
            self._expected.discard(session.pid)
            return

        expected = session.pid in self._expected
        self._expected.discard(session.pid)
        self._tasks.pop(session.pid, None)

        if expected:
            logger.info(
                "freerdp_session_terminated",
                app_id=app_id,
                pid=session.pid,
                returncode=returncode,
            )
        elif returncode == 0:
            logger.info(
                "freerdp_session_closed",
                app_id=app_id,
                pid=session.pid,
                returncode=returncode,
            )
        else:
            tail = self._read_log_tail(session)
            logger.warning(
                "freerdp_session_crashed",
                app_id=app_id,
                pid=session.pid,
                returncode=returncode,
                freerdp_output=tail,
            )
            if self._notifier is not None:
                notify_rdp_drop(self._notifier, app_name=display_name)

        if on_exit is not None:
            try:
                on_exit(session, returncode)
            except Exception:
                logger.exception("freerdp_on_exit_failed", app_id=app_id, pid=session.pid)

    def _read_log_tail(self, session: RailSession) -> str:
        reader = getattr(self._freerdp, "read_log_tail", None)
        if reader is None:
            return ""
        try:
            return str(reader(session))
        except Exception:
            return ""

    def terminate(self, session: RailSession) -> None:
        """Stop a session and mark its exit expected so the monitor logs
        a clean termination rather than a crash."""
        self._expected.add(session.pid)
        self._freerdp.terminate(session)

    async def shutdown_all(self, timeout: float = 5.0) -> None:
        """Terminate every supervised session and await the monitor tasks.
        Called on daemon shutdown so no FreeRDP child outlives the daemon
        and no monitor task is left pending."""
        for pid in list(self._tasks.keys()):
            self._expected.add(pid)
            # terminate() only reads .pid; a bare session is enough.
            self._freerdp.terminate(RailSession(pid=pid))
        tasks = list(self._tasks.values())
        if not tasks:
            return
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("rail_supervisor_shutdown_timeout", pending=len(self._tasks))

    def active_count(self) -> int:
        return len(self._tasks)
