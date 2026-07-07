"""Real FreeRDP invocation. Spawns the first available
``xfreerdp``-family binary as a subprocess.

Binary fallback chain matches docs/EXECUTION_PLAN.md Week 8:
``xfreerdp`` → ``xfreerdp3`` → ``sdl-freerdp3`` → ``sdl3-freerdp``
→ ``flatpak run com.freerdp.FreeRDP``.

Override the auto-detect by setting ``CROSSDESK_FREERDP_BIN`` to a
binary name on PATH (e.g. ``xfreerdp3``) or an absolute path. When
set, the env value takes precedence over the candidate chain and
spawning raises ``FileNotFoundError`` if the pinned binary is
absent — no silent fall-back. Useful for CI pinning, debug runs,
and dev boxes with multiple FreeRDP installs.

Linux-only at runtime; importable on Mac/Windows for type checking
but spawning will fail (no FreeRDP binary on PATH).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path
from typing import IO, Optional, Sequence

from crossdesk_host.abstractions.freerdp import FreeRDPInvocation, RailSession
from crossdesk_host.observability import redact_secret_flags

logger = logging.getLogger(__name__)

_ENV_PIN = "CROSSDESK_FREERDP_BIN"

_LOG_TAIL_BYTES = 4096
"""How much of a crashed session's captured output to include in the
exit log line — enough for the FreeRDP error banner, bounded so a chatty
session can't bloat a single log record."""


def freerdp_log_dir() -> Path:
    """Directory holding per-app FreeRDP capture logs. Under the XDG
    state dir so ``crossdesk logs --component freerdp`` and a beta user's
    "send me your logs" both find them."""
    return Path.home() / ".local" / "state" / "crossdesk" / "logs"


def freerdp_app_log_path(label: str) -> Path:
    """Per-app capture log path. ``label`` (app_id) is sanitised to a
    filesystem-safe token so a launch-by-path app_id can't escape the
    logs dir."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", label) or "app"
    return freerdp_log_dir() / f"freerdp-{safe}.log"

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
    pinned = os.environ.get(_ENV_PIN)
    if pinned:
        # An explicit pin must not silently fall back — the operator
        # asked for this binary specifically (typically CI/test).
        path = shutil.which(pinned) if "/" not in pinned else (pinned if os.access(pinned, os.X_OK) else None)
        if path is not None:
            return [path]
        raise FileNotFoundError(
            f"{_ENV_PIN}={pinned!r} not executable or not on PATH"
        )
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


class _Tracked:
    """A spawned FreeRDP process plus the capture-log file we redirect
    its output into (``None`` when no ``log_label`` was given)."""

    __slots__ = ("proc", "log_file", "log_path")

    def __init__(
        self,
        proc: subprocess.Popen[bytes],
        log_file: Optional[IO[bytes]],
        log_path: Optional[Path],
    ) -> None:
        self.proc = proc
        self.log_file = log_file
        self.log_path = log_path


class RealFreeRDPInvocation(FreeRDPInvocation):
    """Spawns FreeRDP via subprocess.Popen and tracks the resulting
    process handle inside the ``RailSession``."""

    def __init__(self) -> None:
        # Maps pid → tracked process so terminate/wait/is_alive don't
        # reach into ``RailSession`` internals.
        self._processes: dict[int, _Tracked] = {}
        # Capture-log paths survive reaping so read_log_tail works in the
        # post-exit window when the supervisor builds its log line.
        self._last_log_path: dict[int, Path] = {}

    def spawn_rail(self, argv: list[str], log_label: str = "") -> RailSession:
        full_argv = _resolve_freerdp_binary() + argv
        # Scrub the credential flags (/p:, /pth:) before logging — the argv
        # in memory (RailSession.argv) keeps the real values for the spawn.
        logger.info(
            "spawning FreeRDP RAIL session: %s",
            " ".join(redact_secret_flags(full_argv)),
        )
        log_file: Optional[IO[bytes]] = None
        log_path: Optional[Path] = None
        if log_label:
            log_path = freerdp_app_log_path(log_label)
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                # Append so re-launching the same app keeps history; the
                # rotation of these files is left to the size cap a future
                # caller can add — FreeRDP output per session is small.
                # 0600 at creation: the capture may echo a FreeRDP banner
                # carrying connection details, so keep it owner-only.
                log_file = open(
                    log_path, "ab", opener=lambda p, f: os.open(p, f, 0o600)
                )
            except OSError as exc:
                # Capture is best-effort: if we can't open the file, spawn
                # anyway with inherited stderr rather than block the launch.
                logger.warning("freerdp capture log %s unopenable: %s", log_path, exc)
                log_file = None
                log_path = None
        proc = subprocess.Popen(
            full_argv,
            stdout=log_file if log_file is not None else None,
            stderr=subprocess.STDOUT if log_file is not None else None,
        )
        self._processes[proc.pid] = _Tracked(proc, log_file, log_path)
        return RailSession(pid=proc.pid, argv=full_argv)

    def terminate(self, session: RailSession) -> None:
        tracked = self._processes.get(session.pid)
        if tracked is None:
            return
        proc = tracked.proc
        if proc.poll() is not None:
            self._reap_tracked(session.pid)
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
            self._reap_tracked(session.pid)

    async def wait(self, session: RailSession) -> int:
        tracked = self._processes.get(session.pid)
        if tracked is None:
            return 0
        proc = tracked.proc
        # Block a thread-pool thread on the OS wait so the event loop stays
        # free; this also reaps the child (no zombie). No polling.
        returncode = await asyncio.get_running_loop().run_in_executor(
            None, proc.wait
        )
        self._reap_tracked(session.pid)
        return returncode

    def read_log_tail(self, session: RailSession, max_bytes: int = _LOG_TAIL_BYTES) -> str:
        """Return the last ``max_bytes`` of the session's capture log as
        text, or '' if there is none. One-shot: consumes the remembered
        path so it doesn't leak. Used to attach the FreeRDP error banner
        to the exit log line after ``wait`` returns."""
        path = self._last_log_path.pop(session.pid, None)
        if path is None:
            return ""
        try:
            data = path.read_bytes()
        except OSError:
            return ""
        return data[-max_bytes:].decode("utf-8", errors="replace").strip()

    def is_alive(self, session: RailSession) -> bool:
        tracked = self._processes.get(session.pid)
        if tracked is None:
            return False
        return tracked.proc.poll() is None

    def _reap_tracked(self, pid: int) -> None:
        tracked = self._processes.pop(pid, None)
        if tracked is None:
            return
        if tracked.log_path is not None:
            self._last_log_path[pid] = tracked.log_path
        if tracked.log_file is not None:
            try:
                tracked.log_file.close()
            except OSError:
                pass
