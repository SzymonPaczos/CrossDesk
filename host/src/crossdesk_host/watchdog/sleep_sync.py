"""Sleep/wake host-to-guest time sync — Phase 7 stub.

When the host suspends (laptop lid close, ``systemctl suspend``, etc.) and
resumes, the guest clock drifts. Windows has a built-in time sync service
(W32tm) but it can take minutes to correct; in the meantime timestamps on
files written from the host side (VirtioFS) and the guest side diverge.

The real implementation (Phase 7) will send a gRPC RPC to the guest agent
immediately on host-wake so the guest can call ``SetSystemTimeAsFileTime``
or trigger a W32tm resync. For now this module just logs the event so the
hook plumbing can be wired in without Phase 7 bloating the current diff.

Integration point: register ``on_host_sleep`` and ``on_host_wake`` with
the systemd inhibitor lock / dbus-next ``PrepareForSleep`` signal in
``host/src/crossdesk_host/lifecycle/``. That wiring is also Phase 7.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def on_host_sleep() -> None:
    """Called when the host is about to suspend.

    Phase 7 stub — logs only. The real implementation will notify the guest
    agent so it can flush pending writes and prepare for clock drift.
    """
    logger.info(
        "sleep_sync: host sleep event — "
        "guest time sync not yet implemented (Phase 7)"
    )


def on_host_wake() -> None:
    """Called when the host has resumed from suspend.

    Phase 7 stub — logs only. The real implementation will send a gRPC RPC
    to the guest agent to trigger a W32tm clock resync.
    """
    logger.info(
        "sleep_sync: host wake event — "
        "guest time sync not yet implemented (Phase 7)"
    )
