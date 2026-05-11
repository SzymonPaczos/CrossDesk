"""Microbench for the N1.2 suspend/resume FSM path.

N1.2 budget (REQUIREMENTS.md):
  Heartbeat round-trip (steady state): <20 ms p50, <100 ms p99
  Internal stress target: <5 ms p50, <30 ms p99

The suspend/resume FSM transition is triggered by the D-Bus
PrepareForSleep signal. We bench the pure FSM cost of entering and
exiting the SUSPENDED state because that's the host-side overhead we
own — the actual wall-clock time includes libvirt domain pause which is
hardware-bound.

Two paths are measured:
 1. suspend() call — transitions HEALTHY → SUSPENDED
 2. resume() call — transitions SUSPENDED → PROBING

Both must be negligible (sub-microsecond) so that they cannot be a
source of false-positive HARD_DESTROY latency.

Run via:

    cd host && python -m pytest benches/bench_N1_2_suspend.py \
        --benchmark-json=bench-out.json -q
    python ../scripts/bench_check.py bench-out.json
"""

from __future__ import annotations

import pytest

from crossdesk_host.watchdog import HeartbeatFsm, TickInput


@pytest.fixture
def healthy_fsm() -> HeartbeatFsm:
    """FSM that has seen enough pongs to be HEALTHY with a warm EWMA."""
    fsm = HeartbeatFsm()
    pong = TickInput(pong_received=True, rtt_ns=2_000_000)
    for _ in range(15):
        fsm.tick(pong)
    return fsm


def test_bench_N1_2_suspend_transition(
    benchmark,
    healthy_fsm: HeartbeatFsm,
) -> None:
    """Cost of entering SUSPENDED from HEALTHY.

    Called once per PrepareForSleep(true) D-Bus event so the path is
    infrequent, but it must complete before the systemd inhibitor is
    released — any latency here contributes directly to suspend latency.
    """

    def suspend_and_reset() -> None:
        healthy_fsm.suspend()
        # Reset to HEALTHY for the next benchmark iteration so we measure
        # the HEALTHY→SUSPENDED transition, not SUSPENDED→SUSPENDED.
        healthy_fsm.resume()
        # Re-drain back to HEALTHY
        pong = TickInput(pong_received=True, rtt_ns=2_000_000)
        for _ in range(5):
            healthy_fsm.tick(pong)

    benchmark(suspend_and_reset)


def test_bench_N1_2_resume_transition(benchmark) -> None:
    """Cost of exiting SUSPENDED and re-entering PROBING.

    Called once per PrepareForSleep(false) wakeup event — must complete
    before the host starts listening for heartbeats again.
    """
    fsm = HeartbeatFsm()

    def suspend_resume() -> None:
        fsm.suspend()
        fsm.resume()

    benchmark(suspend_resume)


def test_bench_N1_2_healthy_tick_rate(benchmark) -> None:
    """Throughput of the FSM tick path at steady-state HEALTHY.

    This bounds the maximum heartbeat rate we can sustain without the
    FSM becoming a bottleneck. N1.2-internal target: <5 ms p50 round-trip;
    a single tick at << 1 µs leaves ample room for the gRPC round-trip.
    """
    fsm = HeartbeatFsm()
    pong = TickInput(pong_received=True, rtt_ns=1_000_000)
    # Warm up the EWMA baseline so we measure the steady-state path.
    for _ in range(15):
        fsm.tick(pong)

    benchmark(fsm.tick, pong)
