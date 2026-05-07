"""Mock FreeRDP invocation. Records every spawn call to an in-memory
list and returns a fake ``RailSession`` with a synthesised pid; never
spawns a real subprocess.

Used by `rail_manager` unit tests to assert the exact argv that
production would pass to ``xfreerdp`` without depending on any
FreeRDP install.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crossdesk_host.abstractions.freerdp import FreeRDPInvocation, RailSession

logger = logging.getLogger(__name__)


@dataclass
class MockHooks:
    """Knobs flipped by tests to drive deterministic failure scenarios."""

    fail_next_spawn: bool = False
    """If ``True``, the next ``spawn_rail`` raises ``RuntimeError``
    instead of recording. Cleared after firing."""

    spawn_count: int = 0
    terminate_count: int = 0

    spawned_argvs: list[list[str]] = field(default_factory=list)
    """Each entry is the argv passed to ``spawn_rail``. Tests assert
    this list against expected RAIL command construction."""

    live_pids: set[int] = field(default_factory=set)
    """Synthesised pids that haven't been terminated yet. Drives
    ``is_alive`` so the same mock instance can serve multiple
    concurrent sessions deterministically."""


class MockFreeRDPInvocation(FreeRDPInvocation):
    """Records argv to ``hooks.spawned_argvs`` and returns a
    ``RailSession`` with a deterministic synthesised pid (1, 2, 3,
    ...). No subprocess ever gets spawned."""

    def __init__(self) -> None:
        self.hooks = MockHooks()
        self._next_pid = 1

    def spawn_rail(self, argv: list[str]) -> RailSession:
        if self.hooks.fail_next_spawn:
            self.hooks.fail_next_spawn = False
            raise RuntimeError("mock-injected spawn_rail failure")
        pid = self._next_pid
        self._next_pid += 1
        self.hooks.spawn_count += 1
        self.hooks.spawned_argvs.append(list(argv))
        self.hooks.live_pids.add(pid)
        logger.debug(
            "[FREERDP MOCK] spawn_rail pid=%d argv=%s", pid, argv
        )
        return RailSession(pid=pid, argv=list(argv))

    def terminate(self, session: RailSession) -> None:
        if session.pid not in self.hooks.live_pids:
            return
        self.hooks.live_pids.discard(session.pid)
        self.hooks.terminate_count += 1
        logger.debug("[FREERDP MOCK] terminate pid=%d", session.pid)

    def is_alive(self, session: RailSession) -> bool:
        return session.pid in self.hooks.live_pids
