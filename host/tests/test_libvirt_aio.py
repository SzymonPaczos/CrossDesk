"""Deadline + executor offload for blocking libvirt calls (libvirt_ctl.aio).

The daemon's servicers reach libvirt from async context; ``libvirt_call`` runs
the blocking binding in a thread and bounds it so a hung domain can't freeze
the event loop.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from crossdesk_host.libvirt_ctl import libvirt_call


async def test_returns_result() -> None:
    assert await libvirt_call(lambda: 42) == 42


async def test_propagates_exception() -> None:
    def boom() -> None:
        raise RuntimeError("libvirt exploded")

    with pytest.raises(RuntimeError, match="libvirt exploded"):
        await libvirt_call(boom)


async def test_deadline_bounds_a_blocking_call() -> None:
    t0 = time.monotonic()
    with pytest.raises(asyncio.TimeoutError):
        await libvirt_call(lambda: time.sleep(0.5), timeout=0.05)
    # Returned on the deadline, not after the full 0.5s sleep.
    assert time.monotonic() - t0 < 0.5


async def test_loop_stays_live_during_blocked_call() -> None:
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        try:
            while True:
                await asyncio.sleep(0.001)
                ticks += 1
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(ticker())
    # The blocking sleep runs in a thread; the loop stays free, so the ticker
    # keeps advancing while we wait on the executor.
    await libvirt_call(lambda: time.sleep(0.1))
    task.cancel()
    await task
    assert ticks > 0
