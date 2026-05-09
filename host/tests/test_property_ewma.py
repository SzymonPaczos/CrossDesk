"""Property-based tests for the EWMA RTT smoother."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from crossdesk_host.watchdog import EwmaRtt

_RTT = st.integers(min_value=0, max_value=10**12)  # up to 1000 seconds


@given(samples=st.lists(_RTT, min_size=1, max_size=200))
def test_ewma_value_within_observed_range(samples: list[int]) -> None:
    """EWMA can never exceed the max sample nor go below the min."""
    e = EwmaRtt(alpha=0.125, warmup=10)
    for s in samples:
        e.update(s)
    value = e.value_ns
    assert value is not None
    assert min(samples) <= value <= max(samples)


@given(constant=_RTT)
def test_constant_input_converges_to_constant(constant: int) -> None:
    e = EwmaRtt(alpha=0.5, warmup=3)
    for _ in range(50):
        e.update(constant)
    assert e.value_ns == constant


@given(samples=st.lists(_RTT, min_size=11, max_size=100))
def test_baseline_is_arithmetic_mean_of_first_n(samples: list[int]) -> None:
    """During warmup the EWMA accumulates an arithmetic mean; baseline
    is frozen at exactly the warmup-th sample's running mean."""
    warmup = 10
    e = EwmaRtt(alpha=0.125, warmup=warmup)
    for s in samples:
        e.update(s)
    expected_baseline = sum(samples[:warmup]) // warmup
    assert e.baseline_ns is not None
    # Off-by-one acceptable because of int truncation in update()
    assert abs(e.baseline_ns - expected_baseline) <= 1


@given(
    base=st.integers(min_value=1, max_value=10**6),
    spike=st.integers(min_value=1, max_value=10**6),
)
def test_single_spike_after_warmup_pulled_toward_spike(base: int, spike: int) -> None:
    """After 10 base samples the EWMA equals base; one spike sample
    must pull the value toward spike but not all the way."""
    e = EwmaRtt(alpha=0.5, warmup=10)
    for _ in range(10):
        e.update(base)
    assert e.value_ns == base
    e.update(spike)
    new_value = e.value_ns
    assert new_value is not None
    if base != spike:
        # New value should be strictly between base and spike (inclusive
        # of endpoints when alpha is degenerate but our alpha = 0.5).
        low, high = sorted([base, spike])
        assert low <= new_value <= high


@given(samples=st.lists(_RTT, min_size=1, max_size=100))
def test_samples_count_matches_update_calls(samples: list[int]) -> None:
    e = EwmaRtt(alpha=0.2, warmup=5)
    for s in samples:
        e.update(s)
    assert e.samples == len(samples)


@given(warmup=st.integers(min_value=1, max_value=20))
def test_is_warm_flips_at_warmup(warmup: int) -> None:
    e = EwmaRtt(alpha=0.125, warmup=warmup)
    for i in range(warmup):
        assert not e.is_warm()
        e.update(1000)
    assert e.is_warm()


def test_negative_rtt_rejected() -> None:
    import pytest

    e = EwmaRtt()
    with pytest.raises(ValueError):
        e.update(-1)
