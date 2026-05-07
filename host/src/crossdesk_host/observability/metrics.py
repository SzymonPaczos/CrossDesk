"""In-memory metrics registry per DEC-0006.

Lock-free counters and gauges, hdrhistogram-backed histograms.
Singleton ``REGISTRY`` is the canonical instance for production code;
tests build a fresh ``Registry`` to avoid cross-test contamination.

Names follow the standard Prometheus convention (``_total`` suffix
for counters, ``_seconds`` / ``_bytes`` for unit-bearing observables).
``snapshot()`` returns a JSON-serialisable dict that the future
``ControlService.GetMetrics`` RPC can return verbatim.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict

from hdrh.histogram import HdrHistogram

_PERCENTILES = (50.0, 90.0, 99.0, 99.9)


def _percentile_key(p: float) -> str:
    """`50.0 → p50`, `99.9 → p99_9` so JSON keys are ergonomic."""
    if p == int(p):
        return f"p{int(p)}"
    return f"p{str(p).replace('.', '_')}"


@dataclass
class Counter:
    """Monotonic counter. ``inc()`` is the only mutator."""

    _value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def inc(self, amount: int = 1) -> None:
        with self._lock:
            self._value += amount

    def value(self) -> int:
        with self._lock:
            return self._value


@dataclass
class Gauge:
    """Float gauge that can move in either direction. Used for
    instantaneous samples (current FSM state, mount count, RSS)."""

    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set(self, value: float) -> None:
        with self._lock:
            self._value = float(value)

    def value(self) -> float:
        with self._lock:
            return self._value


class Histogram:
    """Latency-distribution histogram backed by hdrhistogram.

    ``observe(value)`` accepts seconds (or any other unit consistent
    with the metric name); we scale to integer microseconds internally
    so the hdrhistogram resolution covers a useful range without
    losing precision on sub-millisecond samples.
    """

    _SCALE = 1_000_000  # seconds → microseconds

    def __init__(self) -> None:
        # 1 µs … 60 s with 2 significant digits — covers everything
        # from heartbeat RTT (single-digit ms) to launch latency
        # (tens of seconds) without overflow.
        self._hist = HdrHistogram(1, 60 * self._SCALE, 2)
        self._count = 0
        self._lock = threading.Lock()

    def observe(self, seconds: float) -> None:
        scaled = max(1, int(seconds * self._SCALE))
        with self._lock:
            self._hist.record_value(scaled)
            self._count += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            count = self._count
            percentiles = {
                _percentile_key(p): self._hist.get_value_at_percentile(p) / self._SCALE
                for p in _PERCENTILES
            }
        return {"count": count, **percentiles}


@dataclass
class Registry:
    """Container for all named metrics. One instance per process; the
    module-level ``REGISTRY`` is the production singleton."""

    counters: Dict[str, Counter] = field(default_factory=dict)
    gauges: Dict[str, Gauge] = field(default_factory=dict)
    histograms: Dict[str, Histogram] = field(default_factory=dict)

    def counter(self, name: str) -> Counter:
        if name not in self.counters:
            self.counters[name] = Counter()
        return self.counters[name]

    def gauge(self, name: str) -> Gauge:
        if name not in self.gauges:
            self.gauges[name] = Gauge()
        return self.gauges[name]

    def histogram(self, name: str) -> Histogram:
        if name not in self.histograms:
            self.histograms[name] = Histogram()
        return self.histograms[name]

    def snapshot(self) -> Dict[str, Any]:
        return {
            "counters": {n: c.value() for n, c in self.counters.items()},
            "gauges": {n: g.value() for n, g in self.gauges.items()},
            "histograms": {n: h.snapshot() for n, h in self.histograms.items()},
        }


# Production singleton. Construct from anywhere via
# `from crossdesk_host.observability.metrics import REGISTRY`.
REGISTRY = Registry()


# Canonical metric names spec'd in docs/EXECUTION_PLAN.md week 3 +
# FOLLOWUPS Observability. Centralised so callers don't drift.
class MetricNames:
    LAUNCHES_TOTAL = "launches_total"
    HEARTBEAT_MISSES_TOTAL = "heartbeat_misses_total"
    MOUNT_ATTACHES_TOTAL = "mount_attaches_total"
    AUTH_CONTEXT_REJECTIONS_TOTAL = "auth_context_rejections_total"

    HEARTBEAT_RTT_SECONDS = "heartbeat_rtt_seconds"
    LAUNCH_DURATION_SECONDS = "launch_duration_seconds"
    MOUNT_LIFETIME_SECONDS = "mount_lifetime_seconds"

    VM_STATE = "vm_state"
    CURRENT_MOUNTS = "current_mounts"
    HOST_RSS_BYTES = "host_rss_bytes"
