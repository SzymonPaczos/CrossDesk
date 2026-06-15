"""RailSupervisor — FreeRDP session monitoring behaviour.

Drives the supervisor over ``MockFreeRDPInvocation`` (whose ``wait`` is
unblocked by ``simulate_exit``) and a ``RecordingNotifier`` so each exit
class can be asserted without a real subprocess: clean close stays quiet,
a non-zero exit notifies + logs the crash, an exit we asked for stays
quiet, and the on-exit callback fires for the launcher to drop its handle.
"""

from __future__ import annotations

from crossdesk_host.display.rail_supervisor import RailSupervisor
from crossdesk_host.freerdp.mock import MockFreeRDPInvocation
from crossdesk_host.lifecycle.notifications import RecordingNotifier


def _spawn(inv: MockFreeRDPInvocation):  # type: ignore[no-untyped-def]
    return inv.spawn_rail(["/v:localhost"], log_label="notepad")


async def test_clean_exit_is_quiet() -> None:
    inv = MockFreeRDPInvocation()
    notifier = RecordingNotifier()
    sup = RailSupervisor(inv, notifier=notifier)
    session = _spawn(inv)

    task = sup.supervise(session, app_id="notepad", display_name="Notepad")
    inv.simulate_exit(session, returncode=0)
    await task

    assert notifier.calls == []  # a user closing the window is not a "drop"
    assert sup.active_count() == 0


async def test_nonzero_exit_notifies_and_clears() -> None:
    inv = MockFreeRDPInvocation()
    notifier = RecordingNotifier()
    sup = RailSupervisor(inv, notifier=notifier)
    session = _spawn(inv)

    task = sup.supervise(session, app_id="notepad", display_name="Notepad")
    inv.simulate_exit(session, returncode=1)
    await task

    assert len(notifier.calls) == 1
    assert "dropped" in notifier.calls[0].summary.lower()
    assert "Notepad" in notifier.calls[0].body
    assert sup.active_count() == 0


async def test_expected_terminate_does_not_notify() -> None:
    inv = MockFreeRDPInvocation()
    notifier = RecordingNotifier()
    sup = RailSupervisor(inv, notifier=notifier)
    session = _spawn(inv)

    task = sup.supervise(session, app_id="notepad", display_name="Notepad")
    sup.terminate(session)  # marks expected + (mock) unblocks wait with -15
    await task

    assert notifier.calls == []  # an exit we requested is not a crash


async def test_on_exit_callback_fires() -> None:
    inv = MockFreeRDPInvocation()
    sup = RailSupervisor(inv)
    session = _spawn(inv)
    seen: list[tuple[int, int]] = []

    task = sup.supervise(
        session,
        app_id="notepad",
        on_exit=lambda s, rc: seen.append((s.pid, rc)),
    )
    inv.simulate_exit(session, returncode=3)
    await task

    assert seen == [(session.pid, 3)]


async def test_no_notifier_is_safe() -> None:
    inv = MockFreeRDPInvocation()
    sup = RailSupervisor(inv)  # notifier=None
    session = _spawn(inv)
    task = sup.supervise(session, app_id="notepad")
    inv.simulate_exit(session, returncode=1)
    await task  # must not raise despite the crash path having no notifier
    assert sup.active_count() == 0


async def test_spawn_threads_log_label() -> None:
    inv = MockFreeRDPInvocation()
    inv.spawn_rail(["/v:localhost"], log_label="word")
    assert inv.hooks.spawned_labels == ["word"]


async def test_shutdown_all_terminates_and_drains() -> None:
    inv = MockFreeRDPInvocation()
    notifier = RecordingNotifier()
    sup = RailSupervisor(inv, notifier=notifier)
    s1 = inv.spawn_rail(["a"], log_label="a")
    s2 = inv.spawn_rail(["b"], log_label="b")
    sup.supervise(s1, app_id="a")
    sup.supervise(s2, app_id="b")

    # shutdown_all terminates each session (mock terminate unblocks wait),
    # then drains the monitor tasks.
    await sup.shutdown_all(timeout=2.0)

    assert sup.active_count() == 0
    assert s1.pid in inv.hooks.terminated_pids
    assert s2.pid in inv.hooks.terminated_pids
    assert notifier.calls == []  # shutdown-driven exits are expected, quiet


def test_read_log_tail_absent_is_empty() -> None:
    inv = MockFreeRDPInvocation()
    sup = RailSupervisor(inv)
    session = inv.spawn_rail(["a"], log_label="a")
    # Mock has no capture log; the tail reader degrades to "".
    assert sup._read_log_tail(session) == ""
