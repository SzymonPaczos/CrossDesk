"""FreeRDP invocation Protocol — host-side abstraction for the
``xfreerdp`` subprocess that renders each RAIL application as a
native Linux window.

The real implementation (``crossdesk_host.freerdp.real``) spawns
``xfreerdp``/``xfreerdp3``/``sdl-freerdp3``/``sdl3-freerdp`` (or the
flatpak fallback) with a fully-built RAIL argv. The mock
(``crossdesk_host.freerdp.mock``) records argv to a list and returns
a fake session, so unit tests for `rail_manager` can assert command
construction without spawning anything.

The argv-construction logic itself lives in `display/rail_manager.py`
(Phase 4 / Week 8); the abstraction here only covers the spawn /
terminate / liveness surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class RailSession:
    """Handle returned by ``FreeRDPInvocation.spawn_rail``.

    Carries enough state for callers to terminate the session, query
    its liveness, and (in tests) inspect the exact argv that was
    invoked. Real and mock both populate ``argv``; only real
    populates a non-zero ``pid``.
    """

    pid: int
    argv: list[str] = field(default_factory=list)
    """Full command line that was (or would be) executed. Tests
    assert against this without spawning a subprocess."""


@runtime_checkable
class FreeRDPInvocation(Protocol):
    """Subprocess surface for spawning RAIL sessions.

    Implementations are deliberately blocking: spawning, polling,
    and terminating a subprocess are short, fast operations that
    consumers can call from a small thread pool or directly from
    rail-event handlers without async wrapping.
    """

    def spawn_rail(self, argv: list[str], log_label: str = "") -> RailSession:
        """Spawn an ``xfreerdp`` (or equivalent) RAIL session.

        Real implementations run the binary discovery chain
        (xfreerdp → xfreerdp3 → sdl-freerdp3 → sdl3-freerdp →
        flatpak); the resolved binary is prepended to ``argv``.
        Raises ``FileNotFoundError`` if no FreeRDP binary is found
        on PATH and no flatpak install matches.

        ``log_label`` (typically the app_id) names the per-app file the
        real implementation tees FreeRDP's stdout+stderr into, so a crash
        reason is captured rather than lost to the inherited stderr. Empty
        means "don't capture" (the mock ignores it).
        """
        ...

    def terminate(self, session: RailSession) -> None:
        """Stop a session. Sends SIGTERM, escalates to SIGKILL after
        a short grace period if the process is still alive. No-op if
        the session was already terminated or never started."""
        ...

    def is_alive(self, session: RailSession) -> bool:
        """``True`` if the session's subprocess is still running."""
        ...

    async def wait(self, session: RailSession) -> int:
        """Block until the session's subprocess exits; return its exit
        code (negative if killed by signal ``-N``).

        Reaps the process — this is the call that prevents the zombie
        ``<defunct>`` left when nothing ever ``wait()``s a spawned
        FreeRDP. Must not block the event loop (real implementations run
        the OS wait on a thread). Returns immediately for a session that
        already exited or never started."""
        ...
