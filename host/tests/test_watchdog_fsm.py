"""Pure-FSM tests for the adaptive heartbeat watchdog.

Stage 1 of Week 5 — exercises every transition of the state machine
defined in ``host/src/crossdesk_host/watchdog/fsm.py`` without any
async or libvirt. Stage 2 will wire the FSM into ``ipc/heartbeat.py``;
the existing ``test_heartbeat_fsm.py`` pin-tests the inline FSM that
will be retired then.
"""

from __future__ import annotations

import pytest

from crossdesk_host.watchdog import (
    EwmaRtt,
    FsmConfig,
    HeartbeatFsm,
    RecoveryAction,
    State,
    TickInput,
)

NORMAL_RTT_NS = 1_000_000  # 1 ms — well under the k1*baseline trip line
HIGH_RTT_NS = 100_000_000  # 100 ms — enough to trip k1=3 against any baseline

PONG = TickInput(pong_received=True, rtt_ns=NORMAL_RTT_NS)
MISS = TickInput(pong_received=False)


def _drive(fsm: HeartbeatFsm, ticks: list[TickInput]) -> list:
    return [fsm.tick(t) for t in ticks]


def _warm_up_baseline(
    fsm: HeartbeatFsm, samples: int = 10, rtt_ns: int = NORMAL_RTT_NS
) -> None:
    for _ in range(samples):
        fsm.tick(TickInput(pong_received=True, rtt_ns=rtt_ns))


# ---------------------------------------------------------------------------
# Baseline state
# ---------------------------------------------------------------------------


def test_initial_state_is_healthy() -> None:
    fsm = HeartbeatFsm()
    assert fsm.state == State.HEALTHY


def test_pong_in_healthy_stays_healthy() -> None:
    fsm = HeartbeatFsm()
    out = fsm.tick(PONG)
    assert out.state == State.HEALTHY
    assert out.recovery_action == RecoveryAction.RECOVERY_ACTION_NONE
    assert out.consecutive_miss_count == 0


# ---------------------------------------------------------------------------
# Miss path: HEALTHY → DEGRADED → PROBING → SOFT_RECOVERY → HARD_DESTROY
# ---------------------------------------------------------------------------


def test_first_miss_transitions_healthy_to_degraded() -> None:
    fsm = HeartbeatFsm()
    out = fsm.tick(MISS)
    assert out.state == State.DEGRADED
    assert out.consecutive_miss_count == 1
    assert out.recovery_action == RecoveryAction.RECOVERY_ACTION_NONE


def test_misses_in_degraded_transition_to_probing_at_threshold() -> None:
    cfg = FsmConfig(miss_threshold=3, probing_extra=2, max_soft_attempts=3)
    fsm = HeartbeatFsm(cfg)
    outs = _drive(fsm, [MISS, MISS, MISS])
    assert outs[0].state == State.DEGRADED
    assert outs[1].state == State.DEGRADED
    assert outs[2].state == State.PROBING
    assert outs[2].recovery_action == RecoveryAction.RECOVERY_ACTION_OBSERVE


def test_probing_transitions_to_soft_recovery_with_graceful_action() -> None:
    cfg = FsmConfig(miss_threshold=3, probing_extra=2)
    fsm = HeartbeatFsm(cfg)
    outs = _drive(fsm, [MISS] * 5)
    assert outs[-1].state == State.SOFT_RECOVERY
    assert outs[-1].recovery_action == RecoveryAction.RECOVERY_ACTION_GRACEFUL_SHUTDOWN
    assert outs[-1].soft_attempts == 1
    assert outs[-1].next_action_after_seconds == cfg.backoff_initial_seconds


def test_soft_recovery_re_emits_graceful_with_exponential_backoff() -> None:
    cfg = FsmConfig(
        miss_threshold=3,
        probing_extra=2,
        max_soft_attempts=4,
        backoff_initial_seconds=5.0,
        backoff_max_seconds=60.0,
    )
    fsm = HeartbeatFsm(cfg)
    # 5 misses → SOFT_RECOVERY (attempt 1, backoff 5s)
    # +2 misses → attempt 2, backoff 10s
    # +2 misses → attempt 3, backoff 20s
    # +2 misses → attempt 4, backoff 40s
    outs = _drive(fsm, [MISS] * 11)
    actions = [
        o.recovery_action
        for o in outs
        if o.recovery_action == RecoveryAction.RECOVERY_ACTION_GRACEFUL_SHUTDOWN
    ]
    backoffs = [
        o.next_action_after_seconds
        for o in outs
        if o.recovery_action == RecoveryAction.RECOVERY_ACTION_GRACEFUL_SHUTDOWN
    ]
    assert len(actions) == 4
    assert backoffs == [5.0, 10.0, 20.0, 40.0]


def test_backoff_caps_at_max() -> None:
    cfg = FsmConfig(
        miss_threshold=3,
        probing_extra=2,
        max_soft_attempts=10,
        backoff_initial_seconds=5.0,
        backoff_max_seconds=15.0,
    )
    fsm = HeartbeatFsm(cfg)
    outs = _drive(fsm, [MISS] * 15)
    backoffs = [
        o.next_action_after_seconds
        for o in outs
        if o.recovery_action == RecoveryAction.RECOVERY_ACTION_GRACEFUL_SHUTDOWN
    ]
    # 5, 10, capped at 15 from attempt 3 onward
    assert backoffs[:2] == [5.0, 10.0]
    assert all(b == 15.0 for b in backoffs[2:])


def test_max_soft_attempts_transitions_to_hard_destroy() -> None:
    cfg = FsmConfig(miss_threshold=3, probing_extra=2, max_soft_attempts=3)
    fsm = HeartbeatFsm(cfg)
    # 5 misses → SOFT (attempt 1), 7 misses → attempt 2, 9 misses → attempt 3,
    # 11 misses → attempt 4 > max (3) → HARD_DESTROY.
    outs = _drive(fsm, [MISS] * 11)
    assert outs[-1].state == State.HARD_DESTROY
    assert outs[-1].recovery_action == RecoveryAction.RECOVERY_ACTION_HARD_DESTROY


def test_hard_destroy_is_terminal() -> None:
    cfg = FsmConfig(miss_threshold=3, probing_extra=2, max_soft_attempts=3)
    fsm = HeartbeatFsm(cfg)
    _drive(fsm, [MISS] * 11)  # land in HARD_DESTROY
    assert fsm.state == State.HARD_DESTROY
    # Further misses and pongs neither escape nor re-fire.
    out = fsm.tick(MISS)
    assert out.state == State.HARD_DESTROY
    assert out.recovery_action == RecoveryAction.RECOVERY_ACTION_NONE
    out = fsm.tick(PONG)
    assert out.state == State.HARD_DESTROY
    assert out.recovery_action == RecoveryAction.RECOVERY_ACTION_NONE


# ---------------------------------------------------------------------------
# Recovery: pongs unwind partial degradation
# ---------------------------------------------------------------------------


def test_pong_during_degraded_recovers_after_recovery_ticks() -> None:
    cfg = FsmConfig(miss_threshold=3, recovery_ticks=3)
    fsm = HeartbeatFsm(cfg)
    fsm.tick(MISS)  # → DEGRADED
    fsm.tick(MISS)
    out = fsm.tick(PONG)
    assert out.state == State.DEGRADED
    assert out.consecutive_miss_count == 0
    assert out.healthy_streak == 1
    out = fsm.tick(PONG)
    assert out.healthy_streak == 2
    out = fsm.tick(PONG)
    assert out.state == State.HEALTHY
    assert out.healthy_streak == 0


def test_pong_during_soft_recovery_recovers_after_recovery_ticks() -> None:
    cfg = FsmConfig(miss_threshold=3, probing_extra=2, recovery_ticks=3)
    fsm = HeartbeatFsm(cfg)
    _drive(fsm, [MISS] * 5)
    assert fsm.state == State.SOFT_RECOVERY
    out = fsm.tick(PONG)
    assert out.state == State.SOFT_RECOVERY  # one pong is not enough
    out = fsm.tick(PONG)
    out = fsm.tick(PONG)
    assert out.state == State.HEALTHY
    assert out.soft_attempts == 0


def test_miss_after_partial_recovery_resets_healthy_streak() -> None:
    cfg = FsmConfig(miss_threshold=3, recovery_ticks=3)
    fsm = HeartbeatFsm(cfg)
    fsm.tick(MISS)  # → DEGRADED
    fsm.tick(PONG)  # streak=1
    fsm.tick(PONG)  # streak=2
    out = fsm.tick(MISS)  # streak resets, miss_count=1 again
    assert out.state == State.DEGRADED
    assert out.healthy_streak == 0
    assert out.consecutive_miss_count == 1


# ---------------------------------------------------------------------------
# RTT-driven HEALTHY → DEGRADED (proto's "ewma_rtt > k1*baseline" trip)
# ---------------------------------------------------------------------------


def test_low_rtt_keeps_healthy_through_warmup() -> None:
    cfg = FsmConfig(ewma_warmup=5, baseline_multiplier_k1=3.0)
    fsm = HeartbeatFsm(cfg)
    _warm_up_baseline(fsm, samples=5, rtt_ns=NORMAL_RTT_NS)
    out = fsm.tick(TickInput(pong_received=True, rtt_ns=NORMAL_RTT_NS))
    assert out.state == State.HEALTHY


def test_high_rtt_after_warmup_transitions_healthy_to_degraded() -> None:
    cfg = FsmConfig(ewma_warmup=5, baseline_multiplier_k1=3.0)
    fsm = HeartbeatFsm(cfg)
    _warm_up_baseline(fsm, samples=5, rtt_ns=NORMAL_RTT_NS)
    # Inject samples high enough to drag EWMA past 3*baseline.
    for _ in range(20):
        out = fsm.tick(TickInput(pong_received=True, rtt_ns=HIGH_RTT_NS))
    assert out.state == State.DEGRADED


def test_high_rtt_before_warmup_does_not_trip() -> None:
    cfg = FsmConfig(ewma_warmup=10, baseline_multiplier_k1=3.0)
    fsm = HeartbeatFsm(cfg)
    # One huge sample early — must not trip because baseline isn't set yet.
    out = fsm.tick(TickInput(pong_received=True, rtt_ns=HIGH_RTT_NS))
    assert out.state == State.HEALTHY


# ---------------------------------------------------------------------------
# SUSPENDED state (Week 7 lifecycle)
# ---------------------------------------------------------------------------


def test_suspend_moves_state_to_suspended() -> None:
    fsm = HeartbeatFsm()
    fsm.suspend()
    assert fsm.state == State.SUSPENDED


def test_suspended_ignores_misses() -> None:
    fsm = HeartbeatFsm()
    fsm.suspend()
    for _ in range(50):
        out = fsm.tick(MISS)
    # No transition out of SUSPENDED, no recovery action emitted
    # despite 50 consecutive missed heartbeats.
    assert out.state == State.SUSPENDED
    assert out.recovery_action == RecoveryAction.RECOVERY_ACTION_NONE


def test_resume_from_suspended_enters_probing() -> None:
    fsm = HeartbeatFsm()
    fsm.suspend()
    fsm.resume()
    assert fsm.state == State.PROBING


def test_resume_grants_grace_window_before_recovery() -> None:
    cfg = FsmConfig(miss_threshold=3, probing_extra=2, max_soft_attempts=3)
    fsm = HeartbeatFsm(cfg)
    fsm.suspend()
    fsm.resume()
    # PROBING state on resume; first miss does not arm SOFT_RECOVERY
    # because miss_count starts at 0 and needs to reach miss_threshold +
    # probing_extra = 5.
    out = fsm.tick(MISS)
    assert out.state == State.PROBING
    assert out.recovery_action == RecoveryAction.RECOVERY_ACTION_NONE


# ---------------------------------------------------------------------------
# EWMA helper
# ---------------------------------------------------------------------------


def test_ewma_initial_has_no_value() -> None:
    e = EwmaRtt(alpha=0.125, warmup=3)
    assert e.value_ns is None
    assert e.baseline_ns is None
    assert not e.is_warm()


def test_ewma_warmup_uses_arithmetic_mean() -> None:
    e = EwmaRtt(alpha=0.125, warmup=3)
    e.update(100)
    e.update(200)
    e.update(300)
    assert e.value_ns == 200  # (100 + 200 + 300) / 3
    assert e.baseline_ns == 200
    assert e.is_warm()


def test_ewma_post_warmup_uses_smoothing() -> None:
    e = EwmaRtt(alpha=0.5, warmup=2)
    e.update(100)
    e.update(200)  # baseline = 150
    assert e.baseline_ns == 150
    e.update(400)  # 0.5*150 + 0.5*400 = 275
    assert e.value_ns == 275
    assert e.baseline_ns == 150  # baseline frozen


def test_ewma_rejects_negative_rtt() -> None:
    e = EwmaRtt()
    with pytest.raises(ValueError):
        e.update(-1)
