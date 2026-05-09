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
