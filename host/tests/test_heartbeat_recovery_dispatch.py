"""_dispatch_recovery_action offloads the blocking libvirt recovery calls with
a deadline, so a hung domain can't stall the heartbeat channel loop.

Drives the dispatch method directly with a scripted TickOutput and a fake
controller (MagicMock records the calls) — no real libvirt (autouse guard).
"""

from __future__ import annotations

import logging
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from crossdesk_host.ipc.heartbeat import HeartbeatServiceServicer
from crossdesk_host.watchdog import RecoveryAction, State, TickOutput


def _out(action: Any) -> TickOutput:
    return TickOutput(
        state=State.HEALTHY,
        recovery_action=action,
        consecutive_miss_count=0,
        healthy_streak=0,
        soft_attempts=1,
        ewma_rtt_ns=None,
        baseline_rtt_ns=None,
        next_action_after_seconds=0.0,
    )


def _servicer(libvirt_ctl: MagicMock) -> HeartbeatServiceServicer:
    auth = MagicMock()
    auth.verify_auth_context = AsyncMock()
    return HeartbeatServiceServicer(auth, libvirt_ctl)


def _patch_fast_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import crossdesk_host.ipc.heartbeat as hb

    real = hb.libvirt_call

    async def fast(fn: Any, *, timeout: float = 0.05) -> Any:
        return await real(fn, timeout=0.05)

    monkeypatch.setattr(hb, "libvirt_call", fast)


async def test_hard_destroy_dispatched_and_returns_true() -> None:
    libvirt = MagicMock()
    servicer = _servicer(libvirt)
    result = await servicer._dispatch_recovery_action(
        _out(RecoveryAction.RECOVERY_ACTION_HARD_DESTROY)
    )
    assert result is True
    libvirt.hard_destroy.assert_called_once_with()


async def test_hard_destroy_timeout_still_breaks_channel(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _patch_fast_timeout(monkeypatch)
    libvirt = MagicMock()
    libvirt.hard_destroy.side_effect = lambda: time.sleep(0.5)
    servicer = _servicer(libvirt)

    with caplog.at_level(logging.CRITICAL, logger="crossdesk_host.ipc.heartbeat"):
        result = await servicer._dispatch_recovery_action(
            _out(RecoveryAction.RECOVERY_ACTION_HARD_DESTROY)
        )

    # Timeout still breaks the channel — the next channel's FSM re-evaluates.
    assert result is True
    assert any(
        "heartbeat_hard_destroy_timeout" in r.getMessage() for r in caplog.records
    )


async def test_graceful_shutdown_dispatched_and_returns_false() -> None:
    libvirt = MagicMock()
    servicer = _servicer(libvirt)
    result = await servicer._dispatch_recovery_action(
        _out(RecoveryAction.RECOVERY_ACTION_GRACEFUL_SHUTDOWN)
    )
    assert result is False
    libvirt.graceful_shutdown.assert_called_once_with()


async def test_graceful_shutdown_timeout_returns_false(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _patch_fast_timeout(monkeypatch)
    libvirt = MagicMock()
    libvirt.graceful_shutdown.side_effect = lambda: time.sleep(0.5)
    servicer = _servicer(libvirt)

    with caplog.at_level(logging.WARNING, logger="crossdesk_host.ipc.heartbeat"):
        result = await servicer._dispatch_recovery_action(
            _out(RecoveryAction.RECOVERY_ACTION_GRACEFUL_SHUTDOWN)
        )

    assert result is False
    assert any(
        "heartbeat_graceful_shutdown_timeout" in r.getMessage() for r in caplog.records
    )
