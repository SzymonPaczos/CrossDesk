"""Real FreeRDP invocation. Spawns the first available
``xfreerdp``-family binary as a subprocess.

Binary fallback chain matches docs/EXECUTION_PLAN.md Week 8:
``xfreerdp`` → ``xfreerdp3`` → ``sdl-freerdp3`` → ``sdl3-freerdp``
→ ``flatpak run com.freerdp.FreeRDP``.

Linux-only at runtime; importable on Mac/Windows for type checking
but spawning will fail (no FreeRDP binary on PATH).
"""

from __future__ import annotations

import logging
import shutil
import signal
import subprocess
from typing import Sequence

from crossdesk_host.abstractions.freerdp import FreeRDPInvocation, RailSession

logger = logging.getLogger(__name__)

# Order matters — use the first binary that exists on PATH. xfreerdp
# (unversioned) takes precedence so distros that ship 2.x are still
# usable; the 3.x binaries are tried after as upstream begins to
# rename them.
_BINARY_CANDIDATES: Sequence[str] = (
    "xfreerdp",
    "xfreerdp3",
    "sdl-freerdp3",
    "sdl3-freerdp",
)
_FLATPAK_APP_ID = "com.freerdp.FreeRDP"

_TERMINATE_GRACE_SECONDS = 3.0


def _resolve_freerdp_binary() -> list[str]:
    """Return the argv prefix that invokes a working FreeRDP. Raises
    ``FileNotFoundError`` if nothing matches."""
    for binary in _BINARY_CANDIDATES:
        path = shutil.which(binary)
        if path is not None:
            return [path]
    flatpak = shutil.which("flatpak")
    if flatpak is not None:
        # We deliberately don't probe `flatpak info` here — that adds
        # latency on every spawn and the launch will fail loudly if
        # the app is not installed. Documented in
        # docs/PERIPHERALS.md as the last-resort fallback.
        return [flatpak, "run", _FLATPAK_APP_ID]
    raise FileNotFoundError(
        "no FreeRDP binary on PATH; install xfreerdp (>= 2.x) "
        "or `flatpak install com.freerdp.FreeRDP`"
    )


class RealFreeRDPInvocation(FreeRDPInvocation):
    """Spawns FreeRDP via subprocess.Popen and tracks the resulting
    process handle inside the ``RailSession``."""

    def __init__(self) -> None:
        # Maps pid → Popen so terminate/is_alive don't reach into
        # ``RailSession`` internals.
        self._processes: dict[int, subprocess.Popen[bytes]] = {}

    def spawn_rail(self, argv: list[str]) -> RailSession:
        full_argv = _resolve_freerdp_binary() + argv
        logger.info("spawning FreeRDP RAIL session: %s", " ".join(full_argv))
        proc = subprocess.Popen(full_argv)
        self._processes[proc.pid] = proc
        return RailSession(pid=proc.pid, argv=full_argv)

    def terminate(self, session: RailSession) -> None:
        proc = self._processes.get(session.pid)
        if proc is None:
            return
        if proc.poll() is not None:
            self._processes.pop(session.pid, None)
            return
        logger.info("terminating FreeRDP RAIL session pid=%d", session.pid)
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            logger.warning(
                "FreeRDP pid=%d ignored SIGTERM, escalating to SIGKILL",
                session.pid,
            )
            proc.kill()
            proc.wait()
        finally:
            self._processes.pop(session.pid, None)

    def is_alive(self, session: RailSession) -> bool:
        proc = self._processes.get(session.pid)
        if proc is None:
            return False
        return proc.poll() is None
