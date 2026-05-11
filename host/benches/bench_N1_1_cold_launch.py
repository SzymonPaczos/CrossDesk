"""Microbench for the N1.1 cold-launch hot path.

N1.1 budgets (REQUIREMENTS.md):
  Lightweight app (Notepad, calc, cmd): ≤3 s p50, ≤6 s p99
  Productivity app (Word, Outlook, VS Code): ≤8 s p50, ≤15 s p99

The wall-clock cost of an actual cold launch is dominated by Windows
boot and FreeRDP RAIL session negotiation — both hardware-bound and
unsuitable for a unit microbench. Instead we measure the per-launch
host-side cost that we *can* control: the metric recording path that
``launch_duration_seconds.observe()`` goes through on every launch.

This isolates our in-process overhead from the external latency so any
regression in the recording hot path appears in the bench results even
before a real Windows VM is available.

Run via:

    cd host && python -m pytest benches/bench_N1_1_cold_launch.py \
        --benchmark-json=bench-out.json -q
    python ../scripts/bench_check.py bench-out.json
"""

from __future__ import annotations

import pytest

from crossdesk_host.observability.metrics import Histogram, Registry


@pytest.fixture
def registry() -> Registry:
    """Fresh registry per bench invocation — avoids cross-bench histogram
    pollution from the module-level REGISTRY singleton."""
    return Registry()


def test_bench_N1_1_launch_metric_record(benchmark) -> None:
    """Cost of recording a single launch-duration observation.

    This is the in-process portion of launch latency that our code owns.
    Histogram.observe() must stay sub-microsecond so the recording overhead
    is negligible relative to the seconds-scale N1.1 budget.
    """
    hist = Histogram()
    # 2.5 s is the midpoint of the N1.1a p50 budget
    benchmark(hist.observe, 2.5)


def test_bench_N1_1_registry_snapshot(benchmark, registry: Registry) -> None:
    """Cost of snapshotting the metrics registry.

    The GetMetrics RPC calls registry.snapshot() on every request.
    Pre-populate with realistic data so the bench reflects a warm registry
    rather than an empty one.
    """
    hist = registry.histogram("launch_duration_seconds")
    counter = registry.counter("launches_total")
    for i in range(50):
        hist.observe(float(i) * 0.05 + 0.3)
        counter.inc()

    benchmark(registry.snapshot)
