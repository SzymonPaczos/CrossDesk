"""Microbench for the N1.6 failed-VM recovery decision path.

N1.6 budgets (REQUIREMENTS.md):
  N1.6a — destroy + start (cold path): ≤90 s from kill to next successful launch
  N1.6b — snapshot revert (warm path): ≤20 s from kill to next successful launch

The 90 s / 20 s budgets are dominated by Windows boot and libvirt domain
operations — hardware-bound and unsuitable for a unit microbench.
What we *can* measure here is the FSM decision latency: how quickly does
the FSM recognise a failing VM and escalate to HARD_DESTROY? Any
regression in this path delays the start of recovery.

Benches cover:
 1. The miss-to-HARD_DESTROY escalation path (N1.6a precursor — the FSM
    must decide to destroy before the 90 s clock can even start)
 2. Metric recording during recovery (launch_duration_seconds.observe
    on recovery success)

Run via:

    cd host && python -m pytest benches/bench_N1_6_recovery.py \
        --benchmark-json=bench-out.json -q
    python ../scripts/bench_check.py bench-out.json
"""

from __future__ import annotations

from crossdesk_host.observability.metrics import Histogram
from crossdesk_host.watchdog import HeartbeatFsm, TickInput
from crossdesk_host.watchdog.fsm import State


def test_bench_N1_6_escalation_to_hard_destroy(benchmark) -> None:
    """Time to drive the FSM from HEALTHY to HARD_DESTROY via consecutive misses.

    In production the FSM is ticked once per heartbeat window, but the bench
    drives it synchronously to measure pure FSM decision throughput. A
    regression here means the host takes longer to *decide* to destroy the
    VM, which adds directly to the N1.6a wall-clock budget.

    Default FsmConfig: 3 misses → PROBING, 2 more → SOFT_RECOVERY,
    3 SOFT_RECOVERY × 3 retries → HARD_DESTROY = ~8 miss ticks minimum.
    We drive 16 to account for the retry amplification.
    """
    miss = TickInput(pong_received=False)

    def escalation_cycle() -> None:
        fsm = HeartbeatFsm()
        ticks = 0
        while fsm.state != State.HARD_DESTROY and ticks < 32:
            fsm.tick(miss)
            ticks += 1

    benchmark(escalation_cycle)


def test_bench_N1_6_recovery_metric_record(benchmark) -> None:
    """Cost of recording recovery latency into the histogram.

    ``launch_duration_seconds`` records the elapsed time from HARD_DESTROY
    back to the next successful launch (which is what N1.6a measures).
    This bench pins the per-recovery recording overhead to sub-microsecond.
    """
    hist = Histogram()
    # N1.6a budget is ≤90 s — use 45 s as a realistic mid-budget sample
    benchmark(hist.observe, 45.0)


def test_bench_N1_6_fsm_miss_tick(benchmark) -> None:
    """Per-miss-tick cost starting from a fresh HEALTHY FSM.

    Granular pin for the miss-handling branch. Each miss-tick is called
    once per heartbeat interval during a failing VM so any regression
    accumulates across the window before HARD_DESTROY is declared.
    """
    miss = TickInput(pong_received=False)
    fsm = HeartbeatFsm()

    benchmark(fsm.tick, miss)
