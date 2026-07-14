"""Deadline + executor offload for blocking libvirt calls (libvirt_ctl.aio).

The daemon's servicers reach libvirt from async context; ``libvirt_call`` runs
the blocking binding in a thread and bounds it so a hung domain can't freeze
the event loop.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from crossdesk_host.libvirt_ctl import LIBVIRT_MAX_WORKERS, aio, libvirt_call


def _default_executor_workers() -> int:
    """How many threads asyncio's *default* executor gets on this machine."""
    return min(32, (os.cpu_count() or 1) + 4)


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


async def test_hung_libvirt_does_not_starve_the_rest_of_the_daemon() -> None:
    """A wedged libvirtd must not take unrelated executor work down with it.

    Regression for the 2026-07-12 security review NOTE. ``libvirt_call`` used to
    offload onto asyncio's *default* executor, and a timed-out libvirt call keeps
    its thread (the C call can't be cancelled). Enough stuck calls therefore filled
    the shared pool, and from then on every other ``run_in_executor`` in the daemon
    starved. Swamping libvirt with more hung calls than the default pool even has
    workers must now leave unrelated offloads untouched.
    """
    release = threading.Event()

    def blocks_until_released() -> None:
        release.wait(timeout=30)

    hung = [
        asyncio.create_task(libvirt_call(blocks_until_released, timeout=20.0))
        for _ in range(_default_executor_workers() + 2)
    ]
    try:
        await asyncio.sleep(0.2)  # let the pool pick up what it can

        loop = asyncio.get_running_loop()
        unrelated = loop.run_in_executor(None, lambda: "still serving")
        assert await asyncio.wait_for(unrelated, timeout=2.0) == "still serving"
    finally:
        release.set()
        await asyncio.gather(*hung, return_exceptions=True)


async def test_pool_is_bounded_so_a_storm_cannot_leak_unbounded_threads() -> None:
    """Only LIBVIRT_MAX_WORKERS calls run at once; the surplus queues.

    That cap is the blast radius of a wedged libvirtd. It also strengthens the
    deadline: a queued future has not entered the C call yet, so ``wait_for`` can
    genuinely cancel it instead of leaking one thread per stuck call.
    """
    lock = threading.Lock()
    release = threading.Event()
    running = 0
    peak = 0

    def occupy_a_thread() -> None:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        release.wait(timeout=30)
        with lock:
            running -= 1

    tasks = [
        asyncio.create_task(libvirt_call(occupy_a_thread, timeout=20.0))
        for _ in range(LIBVIRT_MAX_WORKERS + 3)
    ]
    try:
        for _ in range(50):
            await asyncio.sleep(0.02)
            with lock:
                if peak >= LIBVIRT_MAX_WORKERS:
                    break
        # On the shared default executor all LIBVIRT_MAX_WORKERS + 3 would have
        # been running at once (it has far more threads than that).
        with lock:
            assert peak == LIBVIRT_MAX_WORKERS
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)


def test_shutdown_drops_queued_work_without_joining_a_parked_thread() -> None:
    """Daemon shutdown must not block on a thread stuck inside a libvirt C call.

    Runs against a stand-in pool: shutting down the real module-level executor
    would leave every later test unable to schedule a libvirt call.
    """
    stand_in = ThreadPoolExecutor(max_workers=1, thread_name_prefix="libvirt-test")
    with patch.object(aio, "_executor", stand_in):
        started = threading.Event()
        release = threading.Event()

        def parked_in_libvirt() -> None:
            started.set()
            release.wait(timeout=30)

        parked = stand_in.submit(parked_in_libvirt)
        queued = stand_in.submit(lambda: "never runs")
        assert started.wait(timeout=5)

        t0 = time.monotonic()
        aio.shutdown_libvirt_executor()
        elapsed = time.monotonic() - t0

        assert elapsed < 1.0, "shutdown joined the parked thread instead of returning"
        assert queued.cancelled(), "queued libvirt work should be dropped, not run"

        release.set()
        parked.result(timeout=5)
