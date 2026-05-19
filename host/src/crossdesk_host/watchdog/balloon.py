"""Balloon hook seam — Phase 7 stub for virtio-balloon coordination.

When the host pauses the VM (autopause or D-Bus suspend), the virtio-balloon
target should drop so the host kernel can reclaim guest-side cold pages. When
the VM resumes, the target should climb back to the configured "active" size
before user-facing RAIL spawns try to allocate.

The real driver wiring (libvirt ``BalloonAdjust`` calls, polling
``memory.actual`` until convergence, backoff against guest OOM signals) is
Phase 7. This module ships only the Protocol + a ``NoopBalloonHook`` default
so call sites (autopause, lifecycle coordinator) can be wired today without
waiting for the driver.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class BalloonHook(Protocol):
    """Two-event surface invoked when the VM is being paused / resumed.

    Implementations should be cheap and non-blocking — these are called
    inline from the autopause / lifecycle coroutines, not as background
    tasks. Failures should be logged inside the implementation, not
    raised, so a balloon-side hiccup never blocks the VM from pausing.
    """

    def on_pause(self, reason: str) -> None:
        """VM is about to be paused (or just was, depending on caller).

        ``reason`` is a short tag — currently ``"idle"`` from autopause or
        ``"prepare_for_sleep"`` from the lifecycle coordinator. Future
        callers (manual ``crossdesk vm pause``, low-memory-pressure
        trigger) will add their own tags.
        """
        ...

    def on_resume(self) -> None:
        """VM is about to be resumed (or just was)."""
        ...


class NoopBalloonHook:
    """Default :class:`BalloonHook` — logs the events but does nothing else.

    Used as the autopause + lifecycle default until the Phase 7 balloon
    driver lands and replaces it at construction time.
    """

    def on_pause(self, reason: str) -> None:
        logger.debug("balloon_noop_on_pause reason=%s", reason)

    def on_resume(self) -> None:
        logger.debug("balloon_noop_on_resume")
