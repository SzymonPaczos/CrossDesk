"""Microbench for the adaptive heartbeat FSM.

Pin the per-tick cost so a regression in the hot path (one tick per
ping interval per session) shows up before it eats the N1.2 heartbeat
RTT budget. Run via ``pytest --benchmark-only host/benches/`` or
``pytest host/benches/bench_heartbeat_fsm.py --benchmark-json=out.json``
followed by ``bench_check.py``.
"""

from __future__ import annotations

import pytest

from crossdesk_host.watchdog import HeartbeatFsm, TickInput


@pytest.fixture
def fsm() -> HeartbeatFsm:
    return HeartbeatFsm()


def test_bench_pong_tick_healthy(benchmark, fsm: HeartbeatFsm) -> None:
    pong = TickInput(pong_received=True, rtt_ns=1_000_000)
    benchmark(fsm.tick, pong)


def test_bench_miss_tick(benchmark) -> None:
    """Single miss starting from HEALTHY — measures the most common
    transition path."""
    fsm = HeartbeatFsm()
    miss = TickInput(pong_received=False)
    benchmark(fsm.tick, miss)


def test_bench_full_recovery_cycle(benchmark) -> None:
    """16 ticks: a full DEGRADED → SOFT_RECOVERY → HARD_DESTROY ramp.

    Bench wraps the whole cycle so any regression in transition logic
    aggregates rather than getting hidden in the per-tick noise floor.
    """
    miss = TickInput(pong_received=False)

    def cycle() -> None:
        fsm = HeartbeatFsm()
        for _ in range(16):
            fsm.tick(miss)

    benchmark(cycle)
