"""In-memory metrics registry tests.

Verifies counter/gauge/histogram primitives behave correctly under
single-threaded use and that the snapshot shape matches what the
future ``ControlService.GetMetrics`` RPC will return.
"""
from __future__ import annotations

import threading

from crossdesk_host.observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    Registry,
)


def test_counter_increments_default_step() -> None:
    c = Counter()
    c.inc()
    c.inc()
    c.inc()
    assert c.value() == 3


def test_counter_inc_with_amount() -> None:
    c = Counter()
    c.inc(5)
    c.inc(7)
    assert c.value() == 12


def test_counter_thread_safe() -> None:
    c = Counter()

    def hammer() -> None:
        for _ in range(1000):
            c.inc()

    threads = [threading.Thread(target=hammer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert c.value() == 8000


def test_gauge_set_and_read() -> None:
    g = Gauge()
    g.set(42.5)
    assert g.value() == 42.5
    g.set(0)
    assert g.value() == 0


def test_histogram_records_and_percentiles_close() -> None:
    h = Histogram()
    # Hammer 1ms samples; p50 should be near 0.001s.
    for _ in range(1000):
        h.observe(0.001)

    snap = h.snapshot()
    assert snap["count"] == 1000
    # hdrhistogram is approximate; require within 30% of 1ms.
    assert 0.0007 <= snap["p50"] <= 0.0013, snap


def test_histogram_observe_floor_for_sub_microsecond() -> None:
    """Sub-microsecond observations clamp to 1µs (the histogram's
    minimum recordable value) — they don't crash."""
    h = Histogram()
    h.observe(0.0)  # was 0; clamped to 1µs internally
    snap = h.snapshot()
    assert snap["count"] == 1
    assert snap["p50"] >= 0.000001


def test_registry_returns_shared_instance() -> None:
    reg = Registry()
    a = reg.counter("requests_total")
    b = reg.counter("requests_total")
    assert a is b
    a.inc(3)
    assert b.value() == 3


def test_registry_snapshot_shape() -> None:
    reg = Registry()
    reg.counter("c1").inc(2)
    reg.gauge("g1").set(7.5)
    reg.histogram("h1").observe(0.005)

    snap = reg.snapshot()
    assert snap["counters"] == {"c1": 2}
    assert snap["gauges"] == {"g1": 7.5}
    assert snap["histograms"]["h1"]["count"] == 1
    assert "p50" in snap["histograms"]["h1"]
    assert "p99" in snap["histograms"]["h1"]
