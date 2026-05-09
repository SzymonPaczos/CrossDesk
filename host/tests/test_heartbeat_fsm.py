"""Heartbeat FSM and recovery-action tests.

Phase 3 SPOF (ROADMAP): false-positive HARD_DESTROY = `virsh destroy` while a
user is mid-edit = data loss. False-negative = hung session never recovers.
These tests pin the miss-threshold curve (DEGRADED → PROBING → SOFT_RECOVERY →
HARD_DESTROY) and confirm the libvirt actions fire in the right order.

The Servicer's `Channel` coroutine sleeps + waits internally; we patch both
`asyncio.sleep` and `asyncio.wait_for` in the heartbeat module so tests run in
milliseconds and we can script which pings get a pong vs. time out.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, List
from unittest.mock import AsyncMock, MagicMock  # noqa: F401

import pytest

from crossdesk_host.ipc import heartbeat as heartbeat_module
from crossdesk_host.ipc.heartbeat import HeartbeatServiceServicer
from crossdesk_host.proto.crossdesk.v1 import common_pb2, heartbeat_pb2
from tests.conftest import FakeServicerContext


def _pong(seq: int = 1) -> heartbeat_pb2.GuestFrame:
    return heartbeat_pb2.GuestFrame(
        auth=common_pb2.AuthContext(
            peer_cert_fingerprint="ff" * 32, stream_nonce=b"hb", sequence=seq
        ),
        pong=heartbeat_pb2.Pong(sequence=seq),
    )


# A "tick" is what wait_for yields per iteration: either a Pong frame or a
# TimeoutError (representing miss). End the script with StopAsyncIteration to
# close the stream cleanly.
Tick = object  # heartbeat_pb2.GuestFrame | type[asyncio.TimeoutError] | type[StopAsyncIteration]


async def _drive(
    ticks: List[Tick],
    libvirt_ctl: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run HeartbeatService.Channel against a scripted tick sequence."""

    iter_ticks = iter(ticks)

    async def fake_wait_for(awaitable, timeout: float):
        # We don't actually await the underlying request_iterator — the script
        # decides what each tick produces.
        try:
            tick = next(iter_ticks)
        except StopIteration:
            raise StopAsyncIteration
        if tick is asyncio.TimeoutError:
            raise asyncio.TimeoutError
        if tick is StopAsyncIteration:
            raise StopAsyncIteration
        # Cancel the real awaitable to avoid "coroutine was never awaited"
        if asyncio.iscoroutine(awaitable):
            awaitable.close()
        return tick

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(heartbeat_module.asyncio, "wait_for", fake_wait_for)
    monkeypatch.setattr(heartbeat_module.asyncio, "sleep", fake_sleep)

    auth_validator = MagicMock()
    auth_validator.verify_auth_context = AsyncMock()
    servicer = HeartbeatServiceServicer(auth_validator, libvirt_ctl)

    async def empty_request_iterator() -> AsyncIterator[heartbeat_pb2.GuestFrame]:
        # Real iterator is never read because fake_wait_for short-circuits.
        if False:
            yield  # pragma: no cover
        return

    ctx = FakeServicerContext()
    out: List[heartbeat_pb2.HostFrame] = []
    async for hf in servicer.Channel(empty_request_iterator(), ctx):
        out.append(hf)
    return out


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_all_pongs_received_no_libvirt_action(monkeypatch) -> None:
    libvirt = MagicMock()
    out = await _drive(
        [_pong(1), _pong(2), _pong(3), _pong(4), _pong(5), StopAsyncIteration],
        libvirt,
        monkeypatch,
    )
    assert libvirt.graceful_shutdown.call_count == 0
    assert libvirt.hard_destroy.call_count == 0
    # Ping fires at top of loop, then waits for pong. 5 pongs + StopAsync ⇒
    # at least 5 pings emitted; the 6th ping precedes the stream close.
    assert len(out) >= 5
    assert all(hf.WhichOneof("payload") == "ping" for hf in out)


# ---------------------------------------------------------------------------
# Recovery FSM
# ---------------------------------------------------------------------------


async def test_single_miss_does_not_trigger_libvirt(monkeypatch) -> None:
    libvirt = MagicMock()
    await _drive(
        [_pong(1), asyncio.TimeoutError, _pong(2), StopAsyncIteration],
        libvirt,
        monkeypatch,
    )
    assert libvirt.graceful_shutdown.call_count == 0
    assert libvirt.hard_destroy.call_count == 0


async def test_soft_recovery_triggers_graceful_shutdown(monkeypatch) -> None:
    """SOFT_RECOVERY arms when miss_count > miss_threshold + 2 (>5 misses)."""
    libvirt = MagicMock()
    misses = [asyncio.TimeoutError] * 6  # exceeds threshold (3) + 2
    await _drive(misses + [StopAsyncIteration], libvirt, monkeypatch)
    assert libvirt.graceful_shutdown.call_count >= 1
    assert libvirt.hard_destroy.call_count == 0


async def test_hard_destroy_triggers_after_sustained_silence(monkeypatch) -> None:
    """HARD_DESTROY fires after max_soft_attempts (default 3) graceful retries.

    With FsmConfig defaults (miss_threshold=3, probing_extra=2,
    max_soft_attempts=3): 5 misses → SOFT attempt 1, 7 → attempt 2,
    9 → attempt 3, 11 → attempt 4 > max → HARD_DESTROY.
    """
    libvirt = MagicMock()
    # 11 misses → HARD_DESTROY → break (no StopAsyncIteration needed)
    await _drive([asyncio.TimeoutError] * 11, libvirt, monkeypatch)
    assert libvirt.hard_destroy.call_count == 1
    assert libvirt.graceful_shutdown.call_count == 3


async def test_recovery_resets_state_after_pong(monkeypatch) -> None:
    """Pong after DEGRADED brings state back to HEALTHY (verified indirectly:
    a recovered stream that then gets ONE more miss must NOT trigger any
    libvirt action — miss_count is reset to 0 on recovery)."""
    libvirt = MagicMock()
    await _drive(
        [
            _pong(1),
            asyncio.TimeoutError,  # → DEGRADED, miss=1
            asyncio.TimeoutError,  # miss=2
            _pong(2),  # → HEALTHY, miss reset to 0
            asyncio.TimeoutError,  # → DEGRADED, miss=1 again
            _pong(3),  # → HEALTHY again
            StopAsyncIteration,
        ],
        libvirt,
        monkeypatch,
    )
    assert libvirt.graceful_shutdown.call_count == 0
    assert libvirt.hard_destroy.call_count == 0


# ---------------------------------------------------------------------------
# Auth enforcement on every pong
# ---------------------------------------------------------------------------


async def test_auth_validator_called_for_every_pong(monkeypatch) -> None:
    libvirt = MagicMock()
    auth_called: List[int] = []

    iter_ticks = iter([_pong(1), _pong(2), _pong(3), StopAsyncIteration])

    async def fake_wait_for(awaitable, timeout):
        try:
            tick = next(iter_ticks)
        except StopIteration:
            raise StopAsyncIteration
        if tick is StopAsyncIteration:
            raise StopAsyncIteration
        if asyncio.iscoroutine(awaitable):
            awaitable.close()
        return tick

    async def fake_sleep(_):
        return None

    monkeypatch.setattr(heartbeat_module.asyncio, "wait_for", fake_wait_for)
    monkeypatch.setattr(heartbeat_module.asyncio, "sleep", fake_sleep)

    validator = MagicMock()

    async def _record(*_args, **_kwargs):
        auth_called.append(1)

    validator.verify_auth_context = AsyncMock(side_effect=_record)

    servicer = HeartbeatServiceServicer(validator, libvirt)

    async def empty_iter() -> AsyncIterator[heartbeat_pb2.GuestFrame]:
        if False:
            yield
        return

    async for _ in servicer.Channel(empty_iter(), FakeServicerContext()):
        pass

    assert sum(auth_called) == 3
