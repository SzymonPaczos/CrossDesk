"""MockFreeRDPInvocation behaviours.

The real spawn path is exercised on hardware via the
``linux_only``-marked smoke tests. This file is the unit-level
contract: argv recording, deterministic pid sequence, lifecycle
state.
"""

from __future__ import annotations

import pytest

from crossdesk_host.abstractions.freerdp import FreeRDPInvocation, RailSession
from crossdesk_host.freerdp.mock import MockFreeRDPInvocation


def test_mock_satisfies_protocol() -> None:
    assert isinstance(MockFreeRDPInvocation(), FreeRDPInvocation)


def test_spawn_records_argv_and_returns_session() -> None:
    invoker = MockFreeRDPInvocation()
    argv = ["/v:127.0.0.1", "/app:program:notepad.exe"]

    session = invoker.spawn_rail(argv)

    assert isinstance(session, RailSession)
    assert session.pid == 1
    assert session.argv == argv
    assert invoker.hooks.spawn_count == 1
    assert invoker.hooks.spawned_argvs == [argv]


def test_spawn_pids_are_sequential() -> None:
    invoker = MockFreeRDPInvocation()
    s1 = invoker.spawn_rail(["a"])
    s2 = invoker.spawn_rail(["b"])
    s3 = invoker.spawn_rail(["c"])

    assert [s1.pid, s2.pid, s3.pid] == [1, 2, 3]
    assert invoker.hooks.spawned_argvs == [["a"], ["b"], ["c"]]


def test_is_alive_tracks_terminate_calls() -> None:
    invoker = MockFreeRDPInvocation()
    session = invoker.spawn_rail(["x"])

    assert invoker.is_alive(session) is True
    invoker.terminate(session)
    assert invoker.is_alive(session) is False
    assert invoker.hooks.terminate_count == 1

    # Idempotent re-terminate doesn't double-count.
    invoker.terminate(session)
    assert invoker.hooks.terminate_count == 1


def test_fail_next_spawn_raises_then_clears() -> None:
    invoker = MockFreeRDPInvocation()
    invoker.hooks.fail_next_spawn = True

    with pytest.raises(RuntimeError, match="mock-injected spawn_rail failure"):
        invoker.spawn_rail(["nope"])

    assert invoker.hooks.fail_next_spawn is False
    assert invoker.hooks.spawn_count == 0
    assert invoker.hooks.spawned_argvs == []

    # Subsequent call succeeds.
    session = invoker.spawn_rail(["yes"])
    assert session.pid == 1  # counter not advanced by failed spawn
