"""LifecycleCoordinator unit tests.

Pure-logic coverage of the suspend/resume orchestration. The dbus_listener
module needs systemd-logind on a real Linux box and is intentionally not
tested here.
"""

from __future__ import annotations

from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.lifecycle import LifecycleCoordinator
from crossdesk_host.watchdog import HeartbeatFsm, State


def _make() -> tuple[LibvirtControllerMock, LifecycleCoordinator, HeartbeatFsm]:
    libvirt = LibvirtControllerMock()
    coordinator = LifecycleCoordinator(libvirt)
    fsm = HeartbeatFsm()
    coordinator.register_fsm(fsm)
    return libvirt, coordinator, fsm


def test_suspend_moves_fsm_to_suspended_then_calls_libvirt() -> None:
    libvirt, coordinator, fsm = _make()
    assert not coordinator.suspended
    coordinator.on_prepare_for_sleep()
    assert coordinator.suspended
    assert fsm.state == State.SUSPENDED
    assert libvirt.hooks.suspend_count == 1
    assert libvirt.hooks.suspended is True


def test_resume_calls_libvirt_then_unwinds_fsm_into_probing() -> None:
    libvirt, coordinator, fsm = _make()
    coordinator.on_prepare_for_sleep()
    coordinator.on_resumed()
    assert not coordinator.suspended
    assert libvirt.hooks.resume_count == 1
    assert libvirt.hooks.suspended is False
    # Resume re-enters PROBING (not HEALTHY) so the next pongs have to
    # actively demonstrate liveness through the recovery_ticks window.
    assert fsm.state == State.PROBING


def test_double_suspend_is_idempotent() -> None:
    libvirt, coordinator, _ = _make()
    coordinator.on_prepare_for_sleep()
    coordinator.on_prepare_for_sleep()
    assert libvirt.hooks.suspend_count == 1


def test_resume_without_suspend_is_noop() -> None:
    libvirt, coordinator, _ = _make()
    coordinator.on_resumed()
    assert libvirt.hooks.resume_count == 0


def test_unregister_fsm_stops_propagation() -> None:
    libvirt, coordinator, fsm = _make()
    coordinator.unregister_fsm(fsm)
    coordinator.on_prepare_for_sleep()
    # libvirt still suspended, but FSM state untouched.
    assert libvirt.hooks.suspend_count == 1
    assert fsm.state == State.HEALTHY


def test_multiple_fsms_all_suspended_and_resumed() -> None:
    libvirt = LibvirtControllerMock()
    coordinator = LifecycleCoordinator(libvirt)
    fsms = [HeartbeatFsm() for _ in range(3)]
    for f in fsms:
        coordinator.register_fsm(f)
    coordinator.on_prepare_for_sleep()
    assert all(f.state == State.SUSPENDED for f in fsms)
    coordinator.on_resumed()
    assert all(f.state == State.PROBING for f in fsms)


# ---------------------------------------------------------------------------
# Error-notification wiring (FOLLOWUPS:1019)
# ---------------------------------------------------------------------------


def test_libvirt_suspend_failure_fires_notification_and_reraises() -> None:
    from unittest.mock import MagicMock

    from crossdesk_host.lifecycle.notifications import RecordingNotifier

    libvirt = MagicMock()
    libvirt.suspend.side_effect = RuntimeError("libvirt-side error")
    notifier = RecordingNotifier()
    coordinator = LifecycleCoordinator(libvirt, notifier=notifier)

    try:
        coordinator.on_prepare_for_sleep()
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")
    assert len(notifier.calls) == 1
    assert "Sleep/resume" in notifier.calls[0].summary
    assert "libvirt-side error" in notifier.calls[0].body


def test_libvirt_resume_failure_fires_notification_and_reraises() -> None:
    from unittest.mock import MagicMock

    from crossdesk_host.lifecycle.notifications import RecordingNotifier

    libvirt = MagicMock()
    libvirt.resume.side_effect = RuntimeError("resume broke")
    notifier = RecordingNotifier()
    coordinator = LifecycleCoordinator(libvirt, notifier=notifier)
    coordinator._suspended = True

    try:
        coordinator.on_resumed()
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")
    assert any("resume broke" in c.body for c in notifier.calls)


def test_no_notifier_means_no_notification_on_failure() -> None:
    from unittest.mock import MagicMock

    libvirt = MagicMock()
    libvirt.suspend.side_effect = RuntimeError("boom")
    coordinator = LifecycleCoordinator(libvirt, notifier=None)

    try:
        coordinator.on_prepare_for_sleep()
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


import time
from typing import List, Tuple

import pytest


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


def test_short_sleep_does_not_trigger_hibernation(
    patched_clock: _FakeClock,
) -> None:
    libvirt, coordinator, _ = _make()
    events: List[Tuple[float, float]] = []
    coordinator.register_hibernation_hook(lambda w, m: events.append((w, m)))

    coordinator.on_prepare_for_sleep()
    # Five-minute nap: well below the one-hour floor.
    patched_clock.advance(wall=300.0, monotonic=300.0)
    coordinator.on_resumed()

    assert events == []


def test_long_hibernation_fires_event_and_hooks(
    patched_clock: _FakeClock,
) -> None:
    libvirt, coordinator, _ = _make()
    events: List[Tuple[float, float]] = []
    coordinator.register_hibernation_hook(lambda w, m: events.append((w, m)))

    coordinator.on_prepare_for_sleep()
    # Two-hour suspend with wall + monotonic in lockstep — the
    # canonical hibernation profile.
    patched_clock.advance(wall=7200.0, monotonic=7200.0)
    coordinator.on_resumed()

    assert len(events) == 1
    wall_delta, mono_delta = events[0]
    assert wall_delta == pytest.approx(7200.0)
    assert mono_delta == pytest.approx(7200.0)


def test_forward_ntp_jump_without_monotonic_match_is_ignored(
    patched_clock: _FakeClock,
) -> None:
    libvirt, coordinator, _ = _make()
    events: List[Tuple[float, float]] = []
    coordinator.register_hibernation_hook(lambda w, m: events.append((w, m)))

    coordinator.on_prepare_for_sleep()
    # Wall jumped two hours forward (NTP stepped the system clock
    # after a long time offline) but monotonic moved a few seconds —
    # the host did NOT sleep that long.
    patched_clock.advance(wall=7200.0, monotonic=5.0)
    coordinator.on_resumed()

    assert events == []


def test_backward_wall_jump_is_ignored(patched_clock: _FakeClock) -> None:
    libvirt, coordinator, _ = _make()
    events: List[Tuple[float, float]] = []
    coordinator.register_hibernation_hook(lambda w, m: events.append((w, m)))

    coordinator.on_prepare_for_sleep()
    # DST fall-back or a backwards NTP step inside the sleep window:
    # wall ran backwards, monotonic ticked forward a few minutes.
    patched_clock.advance(wall=-3600.0, monotonic=180.0)
    coordinator.on_resumed()

    assert events == []


def test_hooks_fire_in_registration_order(patched_clock: _FakeClock) -> None:
    libvirt, coordinator, _ = _make()
    order: List[str] = []
    coordinator.register_hibernation_hook(lambda _w, _m: order.append("first"))
    coordinator.register_hibernation_hook(lambda _w, _m: order.append("second"))
    coordinator.register_hibernation_hook(lambda _w, _m: order.append("third"))

    coordinator.on_prepare_for_sleep()
    patched_clock.advance(wall=4000.0, monotonic=4000.0)
    coordinator.on_resumed()

    assert order == ["first", "second", "third"]


def test_misbehaving_hook_does_not_block_later_hooks(
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

    coordinator.on_prepare_for_sleep()
    patched_clock.advance(wall=4000.0, monotonic=4000.0)
    coordinator.on_resumed()

    assert survivors == ["ran-anyway"]


def test_resume_without_prior_suspend_does_not_consult_clock(
    patched_clock: _FakeClock,
) -> None:
    libvirt, coordinator, _ = _make()
    events: List[Tuple[float, float]] = []
    coordinator.register_hibernation_hook(lambda w, m: events.append((w, m)))

    # No on_prepare_for_sleep first → resume short-circuits before the
    # hibernation block.
    patched_clock.advance(wall=10_000.0, monotonic=10_000.0)
    coordinator.on_resumed()

    assert events == []
    assert libvirt.hooks.resume_count == 0

