"""LifecycleCoordinator unit tests.

Coverage of the suspend/resume orchestration, plus the two properties the
non-blocking split rests on: a slow libvirt pause must not freeze the event
loop, and the D-Bus handler must still move the FSMs into SUSPENDED
synchronously. Subscribing to a real bus needs systemd-logind and is not tested
here — the handler factory is, since that is where the ordering lives.
"""

from __future__ import annotations

import asyncio
import time
from typing import List, Tuple
from unittest.mock import MagicMock

import pytest

from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.lifecycle import LifecycleCoordinator
from crossdesk_host.lifecycle.dbus_listener import _make_handler
from crossdesk_host.watchdog import HeartbeatFsm, State


def _make() -> tuple[LibvirtControllerMock, LifecycleCoordinator, HeartbeatFsm]:
    libvirt = LibvirtControllerMock()
    coordinator = LifecycleCoordinator(libvirt)
    fsm = HeartbeatFsm()
    coordinator.register_fsm(fsm)
    return libvirt, coordinator, fsm


async def test_suspend_moves_fsm_to_suspended_then_calls_libvirt() -> None:
    libvirt, coordinator, fsm = _make()
    assert not coordinator.suspended
    await coordinator.on_prepare_for_sleep()
    assert coordinator.suspended
    assert fsm.state == State.SUSPENDED
    assert libvirt.hooks.suspend_count == 1
    assert libvirt.hooks.suspended is True


async def test_resume_calls_libvirt_then_unwinds_fsm_into_probing() -> None:
    libvirt, coordinator, fsm = _make()
    await coordinator.on_prepare_for_sleep()
    await coordinator.on_resumed()
    assert not coordinator.suspended
    assert libvirt.hooks.resume_count == 1
    assert libvirt.hooks.suspended is False
    # Resume re-enters PROBING (not HEALTHY) so the next pongs have to
    # actively demonstrate liveness through the recovery_ticks window.
    assert fsm.state == State.PROBING


async def test_double_suspend_is_idempotent() -> None:
    libvirt, coordinator, _ = _make()
    await coordinator.on_prepare_for_sleep()
    await coordinator.on_prepare_for_sleep()
    assert libvirt.hooks.suspend_count == 1


async def test_resume_without_suspend_is_noop() -> None:
    libvirt, coordinator, _ = _make()
    await coordinator.on_resumed()
    assert libvirt.hooks.resume_count == 0


async def test_unregister_fsm_stops_propagation() -> None:
    libvirt, coordinator, fsm = _make()
    coordinator.unregister_fsm(fsm)
    await coordinator.on_prepare_for_sleep()
    # libvirt still suspended, but FSM state untouched.
    assert libvirt.hooks.suspend_count == 1
    assert fsm.state == State.HEALTHY


async def test_multiple_fsms_all_suspended_and_resumed() -> None:
    libvirt = LibvirtControllerMock()
    coordinator = LifecycleCoordinator(libvirt)
    fsms = [HeartbeatFsm() for _ in range(3)]
    for f in fsms:
        coordinator.register_fsm(f)
    await coordinator.on_prepare_for_sleep()
    assert all(f.state == State.SUSPENDED for f in fsms)
    await coordinator.on_resumed()
    assert all(f.state == State.PROBING for f in fsms)


# ---------------------------------------------------------------------------
# Error-notification wiring (FOLLOWUPS:1019)
# ---------------------------------------------------------------------------


async def test_libvirt_suspend_failure_fires_notification_and_reraises() -> None:
    from unittest.mock import MagicMock

    from crossdesk_host.lifecycle.notifications import RecordingNotifier

    libvirt = MagicMock()
    libvirt.suspend.side_effect = RuntimeError("libvirt-side error")
    notifier = RecordingNotifier()
    coordinator = LifecycleCoordinator(libvirt, notifier=notifier)

    try:
        await coordinator.on_prepare_for_sleep()
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")
    assert len(notifier.calls) == 1
    assert "Sleep/resume" in notifier.calls[0].summary
    assert "libvirt-side error" in notifier.calls[0].body


async def test_libvirt_resume_failure_fires_notification_and_reraises() -> None:
    from unittest.mock import MagicMock

    from crossdesk_host.lifecycle.notifications import RecordingNotifier

    libvirt = MagicMock()
    libvirt.resume.side_effect = RuntimeError("resume broke")
    notifier = RecordingNotifier()
    coordinator = LifecycleCoordinator(libvirt, notifier=notifier)
    coordinator._suspended = True

    try:
        await coordinator.on_resumed()
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")
    assert any("resume broke" in c.body for c in notifier.calls)


async def test_no_notifier_means_no_notification_on_failure() -> None:
    from unittest.mock import MagicMock

    libvirt = MagicMock()
    libvirt.suspend.side_effect = RuntimeError("boom")
    coordinator = LifecycleCoordinator(libvirt, notifier=None)

    try:
        await coordinator.on_prepare_for_sleep()
    except RuntimeError:
        pass
    # We do not blow up on the notifier=None branch.


# ---------------------------------------------------------------------------
# Hibernation detection (FOLLOWUPS:696)
#
# These tests script ``time.time`` and ``time.monotonic`` through a shared
# ``FakeClock`` so the suspend/resume cycle takes microseconds of wall time
# regardless of the wall delta we want to model.
# ---------------------------------------------------------------------------


class _FakeClock:
    def __init__(self, wall: float = 1_000_000.0, monotonic: float = 100.0) -> None:
        self.wall = wall
        self.monotonic = monotonic

    def advance(self, *, wall: float, monotonic: float) -> None:
        self.wall += wall
        self.monotonic += monotonic


@pytest.fixture
def patched_clock(monkeypatch: pytest.MonkeyPatch) -> _FakeClock:
    clock = _FakeClock()
    # Patch the symbols the coordinator imported (``time.time``,
    # ``time.monotonic``) by replacing the underlying ``time`` module
    # functions — the coordinator does ``import time`` at module load,
    # so it resolves attributes against the live module each call.
    monkeypatch.setattr(time, "time", lambda: clock.wall)
    monkeypatch.setattr(time, "monotonic", lambda: clock.monotonic)
    return clock


async def test_short_sleep_does_not_trigger_hibernation(
    patched_clock: _FakeClock,
) -> None:
    libvirt, coordinator, _ = _make()
    events: List[Tuple[float, float]] = []
    coordinator.register_hibernation_hook(lambda w, m: events.append((w, m)))

    await coordinator.on_prepare_for_sleep()
    # Five-minute nap: well below the one-hour floor.
    patched_clock.advance(wall=300.0, monotonic=300.0)
    await coordinator.on_resumed()

    assert events == []


async def test_long_hibernation_fires_event_and_hooks(
    patched_clock: _FakeClock,
) -> None:
    libvirt, coordinator, _ = _make()
    events: List[Tuple[float, float]] = []
    coordinator.register_hibernation_hook(lambda w, m: events.append((w, m)))

    await coordinator.on_prepare_for_sleep()
    # Two-hour suspend with wall + monotonic in lockstep — the
    # canonical hibernation profile.
    patched_clock.advance(wall=7200.0, monotonic=7200.0)
    await coordinator.on_resumed()

    assert len(events) == 1
    wall_delta, mono_delta = events[0]
    assert wall_delta == pytest.approx(7200.0)
    assert mono_delta == pytest.approx(7200.0)


async def test_forward_ntp_jump_without_monotonic_match_is_ignored(
    patched_clock: _FakeClock,
) -> None:
    libvirt, coordinator, _ = _make()
    events: List[Tuple[float, float]] = []
    coordinator.register_hibernation_hook(lambda w, m: events.append((w, m)))

    await coordinator.on_prepare_for_sleep()
    # Wall jumped two hours forward (NTP stepped the system clock
    # after a long time offline) but monotonic moved a few seconds —
    # the host did NOT sleep that long.
    patched_clock.advance(wall=7200.0, monotonic=5.0)
    await coordinator.on_resumed()

    assert events == []


async def test_backward_wall_jump_is_ignored(patched_clock: _FakeClock) -> None:
    libvirt, coordinator, _ = _make()
    events: List[Tuple[float, float]] = []
    coordinator.register_hibernation_hook(lambda w, m: events.append((w, m)))

    await coordinator.on_prepare_for_sleep()
    # DST fall-back or a backwards NTP step inside the sleep window:
    # wall ran backwards, monotonic ticked forward a few minutes.
    patched_clock.advance(wall=-3600.0, monotonic=180.0)
    await coordinator.on_resumed()

    assert events == []


async def test_hooks_fire_in_registration_order(patched_clock: _FakeClock) -> None:
    libvirt, coordinator, _ = _make()
    order: List[str] = []
    coordinator.register_hibernation_hook(lambda _w, _m: order.append("first"))
    coordinator.register_hibernation_hook(lambda _w, _m: order.append("second"))
    coordinator.register_hibernation_hook(lambda _w, _m: order.append("third"))

    await coordinator.on_prepare_for_sleep()
    patched_clock.advance(wall=4000.0, monotonic=4000.0)
    await coordinator.on_resumed()

    assert order == ["first", "second", "third"]


async def test_misbehaving_hook_does_not_block_later_hooks(
    patched_clock: _FakeClock,
) -> None:
    libvirt, coordinator, _ = _make()
    survivors: List[str] = []

    def explode(_w: float, _m: float) -> None:
        raise RuntimeError("hook boom")

    coordinator.register_hibernation_hook(explode)
    coordinator.register_hibernation_hook(
        lambda _w, _m: survivors.append("ran-anyway")
    )

    await coordinator.on_prepare_for_sleep()
    patched_clock.advance(wall=4000.0, monotonic=4000.0)
    await coordinator.on_resumed()

    assert survivors == ["ran-anyway"]


async def test_resume_without_prior_suspend_does_not_consult_clock(
    patched_clock: _FakeClock,
) -> None:
    libvirt, coordinator, _ = _make()
    events: List[Tuple[float, float]] = []
    coordinator.register_hibernation_hook(lambda w, m: events.append((w, m)))

    # No on_prepare_for_sleep first → resume short-circuits before the
    # hibernation block.
    patched_clock.advance(wall=10_000.0, monotonic=10_000.0)
    await coordinator.on_resumed()

    assert events == []
    assert libvirt.hooks.resume_count == 0


class _OrderRecorder:
    def __init__(self) -> None:
        self.order: List[str] = []


class _FsmGroupSpy:
    """Stands in for the heartbeat servicer's bulk suspend/resume."""

    def __init__(self, rec: _OrderRecorder) -> None:
        self._rec = rec
        self.suspend_count = 0
        self.resume_count = 0

    def suspend(self) -> None:
        self.suspend_count += 1
        self._rec.order.append("fsm_group.suspend")

    def resume(self) -> None:
        self.resume_count += 1
        self._rec.order.append("fsm_group.resume")


class _LibvirtSpy(LibvirtControllerMock):
    def __init__(self, rec: _OrderRecorder) -> None:
        super().__init__()
        self._rec = rec

    def suspend(self) -> None:
        super().suspend()
        self._rec.order.append("libvirt.suspend")

    def resume(self) -> None:
        super().resume()
        self._rec.order.append("libvirt.resume")


async def test_fsm_group_suspended_before_libvirt() -> None:
    rec = _OrderRecorder()
    group = _FsmGroupSpy(rec)
    coordinator = LifecycleCoordinator(_LibvirtSpy(rec), fsm_group=group)
    await coordinator.on_prepare_for_sleep()
    assert group.suspend_count == 1
    # FSMs must be SUSPENDED before the VM pauses, else missed pongs across
    # the pause escalate to a false-positive HARD_DESTROY.
    assert rec.order == ["fsm_group.suspend", "libvirt.suspend"]


async def test_fsm_group_resumed_after_libvirt() -> None:
    rec = _OrderRecorder()
    group = _FsmGroupSpy(rec)
    coordinator = LifecycleCoordinator(_LibvirtSpy(rec), fsm_group=group)
    await coordinator.on_prepare_for_sleep()
    rec.order.clear()
    await coordinator.on_resumed()
    assert group.resume_count == 1
    # Guest must be running again before FSMs leave SUSPENDED into PROBING.
    assert rec.order == ["libvirt.resume", "fsm_group.resume"]


async def test_fsm_group_and_registered_fsm_both_fire() -> None:
    rec = _OrderRecorder()
    group = _FsmGroupSpy(rec)
    fsm = HeartbeatFsm()
    coordinator = LifecycleCoordinator(_LibvirtSpy(rec), fsm_group=group)
    coordinator.register_fsm(fsm)
    await coordinator.on_prepare_for_sleep()
    assert fsm.state == State.SUSPENDED
    assert group.suspend_count == 1


# ---------------------------------------------------------------------------
# Non-blocking split (backlog C-3)
# ---------------------------------------------------------------------------


async def test_slow_libvirt_suspend_does_not_freeze_the_event_loop() -> None:
    """A slow domain pause must cost latency, not a frozen daemon.

    The coordinator used to call ``libvirt_ctl.suspend()`` straight through, and
    dbus-next dispatches the PrepareForSleep handler *on the event loop* — so a
    slow (or wedged) libvirtd froze heartbeats, gRPC and everything else at
    exactly the moment the host was going to sleep.
    """
    libvirt = MagicMock()
    libvirt.suspend.side_effect = lambda: time.sleep(0.3)
    coordinator = LifecycleCoordinator(libvirt)

    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        try:
            while True:
                await asyncio.sleep(0.005)
                ticks += 1
        except asyncio.CancelledError:
            pass

    beating = asyncio.create_task(ticker())
    await coordinator.on_prepare_for_sleep()
    beating.cancel()
    await beating

    assert libvirt.suspend.called
    # Blocking the loop would have starved the ticker to ~0 ticks.
    assert ticks > 5, "the event loop was frozen while libvirt paused the domain"


async def test_dbus_handler_suspends_fsms_before_it_returns() -> None:
    """The FSM move must land *inside* the signal callback, not in the task.

    The daemon holds no systemd delay inhibitor (still a Phase-7 stub), so the
    kernel may freeze the moment the handler yields. If the FSM suspend were
    deferred along with the libvirt call, a freeze in that window would leave the
    FSMs ticking across the entire sleep — missed pongs, HARD_DESTROY, and on the
    real controller that is ``virsh destroy``.
    """
    libvirt = LibvirtControllerMock()
    coordinator = LifecycleCoordinator(libvirt)
    fsm = HeartbeatFsm()
    coordinator.register_fsm(fsm)

    handler = _make_handler(coordinator)
    handler(True)  # dbus-next calls this synchronously, on the loop

    # Already true, before the loop has had a chance to run the spawned task:
    # this is the data-loss protection.
    assert fsm.state == State.SUSPENDED
    # ...while the slow half has explicitly NOT run yet — that is the fix.
    assert libvirt.hooks.suspend_count == 0

    await asyncio.sleep(0.05)  # let the spawned pause_domain task finish
    assert libvirt.hooks.suspend_count == 1
    assert coordinator.suspended


async def test_dbus_handler_resume_runs_off_the_loop() -> None:
    """Resume can defer wholesale: parked FSMs cannot escalate."""
    libvirt = LibvirtControllerMock()
    coordinator = LifecycleCoordinator(libvirt)
    fsm = HeartbeatFsm()
    coordinator.register_fsm(fsm)

    handler = _make_handler(coordinator)
    handler(True)
    await asyncio.sleep(0.05)
    assert coordinator.suspended

    handler(False)
    await asyncio.sleep(0.05)
    assert not coordinator.suspended
    assert libvirt.hooks.resume_count == 1
    assert fsm.state == State.PROBING
