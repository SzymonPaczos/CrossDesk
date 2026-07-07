"""Boot-probe hook on the heartbeat servicer.

FOLLOWUPS:899-908 — when the FSM first enters PROBING (asymmetric
break: VSOCK listener bound but guest agent hung), the servicer
fires the optional ``boot_probe`` callable once. The probe runs as
a fire-and-forget asyncio task; its only effect is a structured log
line. These tests pin the behaviour without changing FSM transitions
or AuthValidator semantics.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Coroutine, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from crossdesk_host.ipc.heartbeat import BootProbe, HeartbeatServiceServicer
from crossdesk_host.proto.crossdesk.v1 import common_pb2, heartbeat_pb2
from crossdesk_host.watchdog import FsmConfig
from tests.conftest import FakeServicerContext

# -----------------------------------------------------------------
# Unit: _run_boot_probe direct
# -----------------------------------------------------------------


def _make_servicer(
    boot_probe: Optional[BootProbe], timeout_s: float = 0.05
) -> HeartbeatServiceServicer:
    auth = MagicMock()
    auth.verify_auth_context = AsyncMock()
    libvirt = MagicMock()
    return HeartbeatServiceServicer(
        auth,
        libvirt,
        config=FsmConfig(boot_probe_timeout_seconds=timeout_s),
        boot_probe=boot_probe,
    )


async def test_run_boot_probe_logs_success(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def probe() -> bool:
        return True

    servicer = _make_servicer(probe)
    caplog.set_level(logging.INFO, logger="crossdesk_host.ipc.heartbeat")

    await servicer._run_boot_probe(probe)

    assert any(
        "heartbeat_boot_probe_result" in rec.message and "True" in rec.message
        for rec in caplog.records
    )


async def test_run_boot_probe_logs_falsey(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def probe() -> bool:
        return False

    servicer = _make_servicer(probe)
    caplog.set_level(logging.INFO, logger="crossdesk_host.ipc.heartbeat")

    await servicer._run_boot_probe(probe)

    assert any(
        "heartbeat_boot_probe_result" in rec.message and "False" in rec.message
        for rec in caplog.records
    )


async def test_run_boot_probe_timeout_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def slow_probe() -> bool:
        await asyncio.sleep(60.0)
        return True

    servicer = _make_servicer(slow_probe, timeout_s=0.02)
    caplog.set_level(logging.WARNING, logger="crossdesk_host.ipc.heartbeat")

    await servicer._run_boot_probe(slow_probe)

    assert any(
        "heartbeat_boot_probe_timeout" in rec.message for rec in caplog.records
    )


async def test_run_boot_probe_exception_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def broken_probe() -> bool:
        raise RuntimeError("simulated transport failure")

    servicer = _make_servicer(broken_probe)
    caplog.set_level(logging.WARNING, logger="crossdesk_host.ipc.heartbeat")

    await servicer._run_boot_probe(broken_probe)

    assert any(
        "heartbeat_boot_probe_error" in rec.message
        and "simulated transport failure" in rec.message
        for rec in caplog.records
    )


# -----------------------------------------------------------------
# Integration: Channel fires probe exactly once on PROBING entry
# -----------------------------------------------------------------


def _pong(seq: int = 1) -> heartbeat_pb2.GuestFrame:
    return heartbeat_pb2.GuestFrame(
        auth=common_pb2.AuthContext(
            peer_cert_fingerprint="ff" * 32, stream_nonce=b"hb", sequence=seq
        ),
        pong=heartbeat_pb2.Pong(sequence=seq),
    )


async def _drive(
    ticks: List[object],
    monkeypatch: pytest.MonkeyPatch,
    servicer: HeartbeatServiceServicer,
) -> List[Coroutine[Any, Any, None]]:
    """Run Channel against scripted ticks; return the list of
    coroutines passed to ``asyncio.create_task`` for inspection."""
    iter_ticks = iter(ticks)
    spawned: List[Coroutine[Any, Any, None]] = []
    real_wait_for = asyncio.wait_for

    async def fake_wait_for(awaitable: Any, timeout: float) -> Any:
        # libvirt_call() recovery offloads are Futures, not coroutines — run
        # them for real rather than consuming a scripted ping/pong tick.
        if not asyncio.iscoroutine(awaitable):
            return await real_wait_for(awaitable, timeout)
        try:
            tick = next(iter_ticks)
        except StopIteration:
            raise StopAsyncIteration
        if tick is asyncio.TimeoutError:
            raise asyncio.TimeoutError
        if tick is StopAsyncIteration:
            raise StopAsyncIteration
        if asyncio.iscoroutine(awaitable):
            awaitable.close()
        return tick

    async def fake_sleep(_seconds: float) -> None:
        return None

    real_create_task = asyncio.create_task

    def fake_create_task(coro: Coroutine[Any, Any, None]) -> "asyncio.Task[None]":
        spawned.append(coro)
        # Close the coroutine so we don't leak warnings; we only care
        # that one was scheduled, not that it actually ran.
        coro.close()
        return real_create_task(_noop())

    async def _noop() -> None:
        return None

    monkeypatch.setattr("crossdesk_host.ipc.heartbeat.asyncio.wait_for", fake_wait_for)
    monkeypatch.setattr("crossdesk_host.ipc.heartbeat.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(
        "crossdesk_host.ipc.heartbeat.asyncio.create_task", fake_create_task
    )

    async def empty_iter() -> AsyncIterator[heartbeat_pb2.GuestFrame]:
        if False:
            yield  # pragma: no cover
        return

    async for _ in servicer.Channel(empty_iter(), FakeServicerContext()):
        pass

    return spawned


async def test_probe_task_scheduled_once_on_probing_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def probe() -> bool:
        return True

    servicer = _make_servicer(probe)
    # 3 misses → HEALTHY→DEGRADED→PROBING (probe scheduled on 3rd miss);
    # then pong recovery (back to HEALTHY); then 3 more misses (would
    # re-enter PROBING) — probe must NOT schedule a second task.
    spawned = await _drive(
        [asyncio.TimeoutError] * 3
        + [_pong(1), _pong(2), _pong(3)]
        + [asyncio.TimeoutError] * 3
        + [StopAsyncIteration],
        monkeypatch,
        servicer,
    )

    assert len(spawned) == 1


async def test_probe_task_not_scheduled_when_probe_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    servicer = _make_servicer(None)
    spawned = await _drive(
        [asyncio.TimeoutError] * 5 + [StopAsyncIteration],
        monkeypatch,
        servicer,
    )

    assert spawned == []


async def test_probe_task_not_scheduled_on_healthy_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def probe() -> bool:
        return True

    servicer = _make_servicer(probe)
    spawned = await _drive(
        [_pong(1), _pong(2), _pong(3), StopAsyncIteration],
        monkeypatch,
        servicer,
    )

    assert spawned == []
