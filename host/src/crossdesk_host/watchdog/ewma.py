"""EWMA RTT smoothing for the adaptive heartbeat.

Pure helper. The FSM uses this to decide HEALTHY → DEGRADED on
``ewma_rtt > k1 * baseline``. Mirrors the TCP RTO style smoothing
(RFC 6298): SRTT exponentially weighted toward the latest sample.

Why a class instead of a free function: the smoothed value is stateful
across samples, and the baseline (auto-anchored from the first ``warmup``
samples) needs to be remembered across ticks. Keeping that state inside
``EwmaRtt`` keeps the FSM purely concerned with state transitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class EwmaRtt:
    """Exponentially-weighted moving average of round-trip times in ns.

    The first ``warmup`` samples are averaged into ``baseline_ns`` so that
    the threshold ``k1 * baseline`` adapts to whatever transport the host
    is actually running on (sub-millisecond on AF_VSOCK, ~1-5 ms on TCP
    loopback in dev). After warmup, samples feed the EWMA proper.
    """

    alpha: float = 0.125
    warmup: int = 10
    _value_ns: Optional[float] = None
    _baseline_ns: Optional[float] = None
    _samples_seen: int = 0
    _warmup_sum_ns: int = 0

    def update(self, rtt_ns: int) -> int:
        if rtt_ns < 0:
            raise ValueError("rtt_ns must be non-negative")
        self._samples_seen += 1
        if self._samples_seen <= self.warmup:
            self._warmup_sum_ns += rtt_ns
            self._value_ns = self._warmup_sum_ns / self._samples_seen
            if self._samples_seen == self.warmup:
                self._baseline_ns = self._value_ns
        else:
            assert self._value_ns is not None
            self._value_ns = (1 - self.alpha) * self._value_ns + self.alpha * rtt_ns
        return int(self._value_ns)

    @property
    def value_ns(self) -> Optional[int]:
        return None if self._value_ns is None else int(self._value_ns)

    @property
    def baseline_ns(self) -> Optional[int]:
        return None if self._baseline_ns is None else int(self._baseline_ns)

    @property
    def samples(self) -> int:
        return self._samples_seen

    def is_warm(self) -> bool:
        return self._samples_seen >= self.warmup
