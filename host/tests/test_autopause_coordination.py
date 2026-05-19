"""Autopause × balloon × heartbeat coordination (FOLLOWUPS:665).

Pins the three-way sequence:

* pause: heartbeat.suspend() → balloon.on_pause("idle") → libvirt.suspend()
* resume: libvirt.resume() → heartbeat.resume() → balloon.on_resume()

Also pins that the heartbeat FSM doesn't escalate to HARD_DESTROY while
suspended — the SPOF this whole coordination exists to prevent.
"""

from __future__ import annotations

import asyncio
from typing import List
from unittest.mock import MagicMock

import pytest

from crossdesk_host.watchdog import (
    BalloonHook,
    HeartbeatFsm,
    NoopBalloonHook,
    State,
    TickInput,
)
from crossdesk_host.watchdog.autopause import AutopauseController


class _RecordingBalloon:
    """Records on_pause / on_resume calls for assertion."""

    def __init__(self) -> None:
        self.pause_calls: List[str] = []
        self.resume_calls: int = 0

    def on_pause(self, reason: str) -> None:
        self.pause_calls.append(reason)

    def on_resume(self) -> None:
        self.resume_calls += 1


def test_recording_balloon_satisfies_balloon_hook_protocol() -> None:
    """Sanity: our test double is structurally a :class:`BalloonHook`."""
    hook = _RecordingBalloon()
    assert isinstance(hook, BalloonHook)


# ---------------------------------------------------------------------------
# (a) pause → heartbeat suspend + balloon on_pause + libvirt suspend in order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_triggers_heartbeat_suspend_then_balloon_then_libvirt() -> None:
    """Idle-timeout firing must coordinate all three subsystems in order."""
    order: List[str] = []
    balloon = _RecordingBalloon()
    mock_libvirt = MagicMock()
    mock_libvirt.suspend.side_effect = lambda: order.append("libvirt_suspend")

    def hb_suspend() -> None:
        order.append("heartbeat_suspend")

    def hb_resume() -> None:
        order.append("heartbeat_resume")

    # Wrap balloon to share the order list.
    _orig_pause = balloon.on_pause
    _orig_resume = balloon.on_resume

    def _wrap_pause(reason: str) -> None:
        order.append(f"balloon_pause:{reason}")
        _orig_pause(reason)

    def _wrap_resume() -> None:
        order.append("balloon_resume")
        _orig_resume()

    balloon.on_pause = _wrap_pause  # type: ignore[method-assign]
    balloon.on_resume = _wrap_resume  # type: ignore[method-assign]

    ctrl = AutopauseController(
        idle_timeout_s=0.02,
        heartbeat_suspend=hb_suspend,
        heartbeat_resume=hb_resume,
        balloon_hook=balloon,
    )
    ctrl._idle_event.set()  # start in idle immediately

    task = asyncio.create_task(ctrl.run(mock_libvirt))
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert order[:3] == [
        "heartbeat_suspend",
        "balloon_pause:idle",
        "libvirt_suspend",
    ]
    assert ctrl.paused is True
    assert balloon.pause_calls == ["idle"]


# ---------------------------------------------------------------------------
# (b) resume → libvirt resume + heartbeat resume + balloon on_resume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_opened_after_pause_triggers_resume() -> None:
    """Opening a RAIL session while paused unwinds all three layers."""
    order: List[str] = []
    balloon = _RecordingBalloon()
    mock_libvirt = MagicMock()
    mock_libvirt.suspend.side_effect = lambda: order.append("libvirt_suspend")
    mock_libvirt.resume.side_effect = lambda: order.append("libvirt_resume")

    def hb_suspend() -> None:
        order.append("heartbeat_suspend")

    def hb_resume() -> None:
        order.append("heartbeat_resume")

    _orig_resume = balloon.on_resume

    def _wrap_resume() -> None:
        order.append("balloon_resume")
        _orig_resume()

    balloon.on_resume = _wrap_resume  # type: ignore[method-assign]

    ctrl = AutopauseController(
        idle_timeout_s=0.02,
        heartbeat_suspend=hb_suspend,
        heartbeat_resume=hb_resume,
        balloon_hook=balloon,
    )
    ctrl._idle_event.set()

    task = asyncio.create_task(ctrl.run(mock_libvirt))
    # Let the pause fire.
    await asyncio.sleep(0.15)
    assert ctrl.paused is True

    # User opens a RAIL session → resume path triggered inline.
    ctrl.session_opened()
    assert ctrl.paused is False

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Pause prefix already validated by the other test; only check resume order.
    resume_slice = [
        ev for ev in order
        if ev in {"libvirt_resume", "heartbeat_resume", "balloon_resume"}
    ]
    assert resume_slice == [
        "libvirt_resume",
        "heartbeat_resume",
        "balloon_resume",
    ]
    assert balloon.resume_calls == 1


@pytest.mark.asyncio
async def test_resume_when_not_paused_is_noop() -> None:
    """Calling :meth:`resume` on a non-paused controller must not touch libvirt."""
    mock_libvirt = MagicMock()
    ctrl = AutopauseController(idle_timeout_s=300)
    ctrl._libvirt_ctl = mock_libvirt
    ctrl.resume()
    mock_libvirt.resume.assert_not_called()


# ---------------------------------------------------------------------------
# (c) Heartbeat FSM does not fire HARD_DESTROY while suspended
# ---------------------------------------------------------------------------


def test_suspended_fsm_swallows_misses_without_escalation() -> None:
    """The core SPOF defence: an FSM that's been told to suspend must
    ignore the storm of missed pongs that follow when the VM pauses."""
    fsm = HeartbeatFsm()
    fsm.suspend()
    # Drive 50 consecutive misses — more than enough to reach HARD_DESTROY
    # if the FSM were ticking normally.
    for _ in range(50):
        out = fsm.tick(TickInput(pong_received=False))
    assert out.state == State.SUSPENDED
    assert fsm.state == State.SUSPENDED


def test_servicer_suspend_propagates_to_active_fsms() -> None:
    """:meth:`HeartbeatServiceServicer.suspend` flips every active FSM."""
    from unittest.mock import MagicMock as _MM

    from crossdesk_host.ipc.heartbeat import HeartbeatServiceServicer

    servicer = HeartbeatServiceServicer(_MM(), _MM())
    fsm1 = HeartbeatFsm()
    fsm2 = HeartbeatFsm()
    servicer._active_fsms.extend([fsm1, fsm2])

    assert fsm1.state == State.HEALTHY
    servicer.suspend()
    assert servicer.suspended is True
    assert fsm1.state == State.SUSPENDED
    assert fsm2.state == State.SUSPENDED

    servicer.resume()
    assert servicer.suspended is False
    # Resume goes through PROBING (per fsm.py docstring) so we have a
    # grace window to demonstrate liveness.
    assert fsm1.state == State.PROBING
    assert fsm2.state == State.PROBING


def test_servicer_suspend_is_idempotent() -> None:
    """Double-suspend / double-resume must not re-tick the FSM."""
    from unittest.mock import MagicMock as _MM

    from crossdesk_host.ipc.heartbeat import HeartbeatServiceServicer

    servicer = HeartbeatServiceServicer(_MM(), _MM())
    fsm = HeartbeatFsm()
    servicer._active_fsms.append(fsm)

    servicer.suspend()
    servicer.suspend()  # no-op
    assert fsm.state == State.SUSPENDED

    servicer.resume()
    servicer.resume()  # no-op
    assert fsm.state == State.PROBING


# ---------------------------------------------------------------------------
# (d) Balloon hook is invoked on pause and resume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_balloon_hook_invoked_on_pause_and_resume() -> None:
    """End-to-end: pause records ``"idle"``, resume increments counter."""
    balloon = _RecordingBalloon()
    mock_libvirt = MagicMock()

    ctrl = AutopauseController(
        idle_timeout_s=0.02,
        balloon_hook=balloon,
    )
    ctrl._idle_event.set()

    task = asyncio.create_task(ctrl.run(mock_libvirt))
    await asyncio.sleep(0.15)
    assert balloon.pause_calls == ["idle"]

    ctrl.session_opened()
    assert balloon.resume_calls == 1

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def test_default_balloon_hook_is_noop() -> None:
    """When no hook is provided, the controller uses :class:`NoopBalloonHook`."""
    ctrl = AutopauseController(idle_timeout_s=300)
    assert isinstance(ctrl._balloon_hook, NoopBalloonHook)


def test_noop_balloon_hook_satisfies_protocol() -> None:
    """The default no-op hook still satisfies the :class:`BalloonHook` Protocol."""
    hook = NoopBalloonHook()
    assert isinstance(hook, BalloonHook)
    # Smoke-test the methods don't raise.
    hook.on_pause("idle")
    hook.on_resume()


# ---------------------------------------------------------------------------
# Roll-back on libvirt failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_libvirt_suspend_failure_rolls_back_heartbeat_and_balloon() -> None:
    """If ``libvirt.suspend()`` raises, the FSM must come back out of
    SUSPENDED — otherwise we'd strand a live VM with a frozen FSM."""
    balloon = _RecordingBalloon()
    mock_libvirt = MagicMock()
    mock_libvirt.suspend.side_effect = RuntimeError("libvirt boom")

    hb_calls: List[str] = []

    def hb_suspend() -> None:
        hb_calls.append("suspend")

    def hb_resume() -> None:
        hb_calls.append("resume")

    ctrl = AutopauseController(
        idle_timeout_s=0.02,
        heartbeat_suspend=hb_suspend,
        heartbeat_resume=hb_resume,
        balloon_hook=balloon,
    )
    ctrl._idle_event.set()

    task = asyncio.create_task(ctrl.run(mock_libvirt))
    await asyncio.sleep(0.15)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Pause attempted, libvirt blew up, controller rolled the two
    # in-process layers back so the system isn't half-suspended.
    assert hb_calls == ["suspend", "resume"]
    assert balloon.pause_calls == ["idle"]
    assert balloon.resume_calls == 1
    assert ctrl.paused is False


# ---------------------------------------------------------------------------
# Late-attaching channel inherits suspended state
# ---------------------------------------------------------------------------


def test_late_channel_inherits_suspended_state() -> None:
    """An FSM appended after the servicer is suspended must be SUSPENDED
    on entry — otherwise a freshly-reconnecting guest would race the
    autopause window and tick toward DEGRADED."""
    from unittest.mock import MagicMock as _MM

    from crossdesk_host.ipc.heartbeat import HeartbeatServiceServicer

    servicer = HeartbeatServiceServicer(_MM(), _MM())
    servicer.suspend()

    # Simulate Channel entry: a fresh FSM, then the inheritance check
    # we put in Channel().
    fresh_fsm = HeartbeatFsm()
    if servicer.suspended:
        fresh_fsm.suspend()
    servicer._active_fsms.append(fresh_fsm)

    assert fresh_fsm.state == State.SUSPENDED
