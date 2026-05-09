"""Adaptive heartbeat watchdog (Phase 3).

Pure FSM + EWMA helpers. ``ipc/heartbeat.py`` wires these into the
servicer; this package has no async, no I/O, no libvirt.
"""

from crossdesk_host.watchdog.ewma import EwmaRtt
from crossdesk_host.watchdog.fsm import (
    FsmConfig,
    HeartbeatFsm,
    RecoveryAction,
    State,
    TickInput,
    TickOutput,
)

__all__ = [
    "EwmaRtt",
    "FsmConfig",
    "HeartbeatFsm",
    "RecoveryAction",
    "State",
    "TickInput",
    "TickOutput",
]
