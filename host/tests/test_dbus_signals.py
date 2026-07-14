"""Contract tests for :class:`MockDBusSignalSource`.

Verifies the mock drives :class:`LifecycleCoordinator` exactly like
the real systemd-logind listener: ``emit_prepare_for_sleep(starting=
True)`` maps to ``on_prepare_for_sleep`` (FSM suspend + libvirt
suspend, in that order), and ``starting=False`` maps to
``on_resumed`` (libvirt resume + FSM resume).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from crossdesk_host.lifecycle.coordinator import LifecycleCoordinator
from crossdesk_host.lifecycle.dbus_signals import (
    DBusSignalSource,
    MockDBusSignalSource,
)
from crossdesk_host.watchdog import HeartbeatFsm


def _coordinator() -> tuple[LifecycleCoordinator, MagicMock]:
    libvirt = MagicMock()
    return LifecycleCoordinator(libvirt_ctl=libvirt), libvirt


def test_mock_satisfies_protocol() -> None:
    assert isinstance(MockDBusSignalSource(), DBusSignalSource)


@pytest.mark.asyncio
async def test_emit_starting_true_suspends_coordinator() -> None:
    coord, libvirt = _coordinator()
    src = MockDBusSignalSource()
    task = await src.start(coord)

    await src.emit_prepare_for_sleep(starting=True)
    assert coord.suspended is True
    assert libvirt.suspend.call_count == 1
    assert libvirt.resume.call_count == 0

    task.cancel()


@pytest.mark.asyncio
async def test_emit_starting_false_resumes_coordinator() -> None:
    coord, libvirt = _coordinator()
    src = MockDBusSignalSource()
    task = await src.start(coord)

    await src.emit_prepare_for_sleep(starting=True)
    await src.emit_prepare_for_sleep(starting=False)
    assert coord.suspended is False
    assert libvirt.suspend.call_count == 1
    assert libvirt.resume.call_count == 1

    task.cancel()


@pytest.mark.asyncio
async def test_scripted_suspend_cycle_pin_fsm_state() -> None:
    coord, _ = _coordinator()
    fsm = HeartbeatFsm()
    coord.register_fsm(fsm)
    src = MockDBusSignalSource()
    task = await src.start(coord)

    await src.emit_prepare_for_sleep(starting=True)
    assert fsm.state.value == "SUSPENDED"
    await src.emit_prepare_for_sleep(starting=False)
    assert fsm.state.value == "PROBING"

    task.cancel()


@pytest.mark.asyncio
async def test_double_suspend_is_idempotent() -> None:
    coord, libvirt = _coordinator()
    src = MockDBusSignalSource()
    task = await src.start(coord)

    await src.emit_prepare_for_sleep(starting=True)
    await src.emit_prepare_for_sleep(starting=True)
    assert libvirt.suspend.call_count == 1

    task.cancel()


@pytest.mark.asyncio
async def test_resume_before_suspend_is_idempotent() -> None:
    coord, libvirt = _coordinator()
    src = MockDBusSignalSource()
    task = await src.start(coord)

    await src.emit_prepare_for_sleep(starting=False)
    assert coord.suspended is False
    assert libvirt.resume.call_count == 0

    task.cancel()


async def test_emit_before_start_raises() -> None:
    src = MockDBusSignalSource()
    with pytest.raises(RuntimeError, match="before start"):
        await src.emit_prepare_for_sleep(starting=True)
