"""RAIL window lifecycle manager.

Consumes ``RailWindowEvent`` frames from the ControlService stream and
turns them into FreeRDP RAIL sessions on the Linux side. Each
:class:`AppLaunchSpec` produces one ``xfreerdp`` invocation via the
:class:`FreeRDPInvocation` Protocol; the resulting window IDs are
tracked so we can:

- terminate the session cleanly on ``KIND_DESTROYED``,
- update WM hints on ``KIND_MOVED``/``KIND_RESIZED``/``KIND_TITLE_CHANGED``
  (skeleton today; live WM hint propagation is hardware-gated),
- handle out-of-order arrivals idempotently — ROADMAP Phase 4 SPOF
  warns that HWND ↔ Linux window state drift = ghost windows or
  orphaned processes; this module is the single place where that
  drift is priced and resolved.

Idempotency rules (matching the existing pin tests in
``test_rail_manager.py``):

- repeat ``KIND_CREATED`` for an existing HWND: warn, leave the
  original entry intact, no second spawn.
- ``KIND_DESTROYED`` for an unknown HWND: silent no-op (lost-CREATE
  case).
- ``KIND_MOVED`` / focus / title for an unknown HWND: warn and ignore
  — never silently materialise an entry from a geometry-only event.

The ``_windows`` mapping uses dict-of-dicts because the existing pin
tests assert on ``win["title"]`` shape; the cleanup to a typed
WindowState dataclass is queued for Week 11 alongside multi-monitor
work.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from crossdesk_host.abstractions.freerdp import FreeRDPInvocation, RailSession
from crossdesk_host.proto.crossdesk.v1 import control_pb2

# stdlib logger (not the structlog facade) so the pin tests' ``caplog``
# fixture can capture warnings; the migration to ``observability.log``
# is queued for Week 11 once the tests are rewritten to inspect state
# rather than log records.
logger = logging.getLogger(__name__)


class RailManager:
    def __init__(self, freerdp_inv: Optional[FreeRDPInvocation] = None) -> None:
        self._windows: Dict[int, Dict[str, Any]] = {}
        self._sessions: Dict[int, RailSession] = {}
        self._freerdp_inv = freerdp_inv

    def handle_rail_event(self, event: control_pb2.RailWindowEvent) -> None:
        hwnd = event.window_id
        kind = event.kind
        Kind = control_pb2.RailWindowEvent.Kind

        if kind == Kind.KIND_CREATED:
            self._handle_create(hwnd, event)
        elif kind == Kind.KIND_DESTROYED:
            self._handle_destroy(hwnd)
        elif kind == Kind.KIND_MOVED:
            self._handle_moved(hwnd, event)
        elif kind == Kind.KIND_RESIZED:
            self._handle_moved(hwnd, event)  # same path; geometry-only update
        elif kind == Kind.KIND_FOCUS_GAINED:
            self._handle_focus(hwnd)
        elif kind == Kind.KIND_TITLE_CHANGED:
            self._handle_title_change(hwnd, event)
        else:
            logger.debug("[%x] Unhandled event kind: %s", hwnd, int(kind))

    def _handle_create(self, hwnd: int, event: control_pb2.RailWindowEvent) -> None:
        if hwnd in self._windows:
            logger.warning("Window 0x%x already exists. Ignoring CREATE.", hwnd)
            return

        title = event.title or "<unnamed>"
        rect = event.geometry
        self._windows[hwnd] = {
            "title": title,
            "x": rect.x,
            "y": rect.y,
            "width": rect.width,
            "height": rect.height,
        }
        logger.info(
            "[RAIL] Creating native Wayland window for HWND 0x%x %r at (%d, %d) size %dx%d",
            hwnd,
            title,
            rect.x,
            rect.y,
            rect.width,
            rect.height,
        )

    def _handle_destroy(self, hwnd: int) -> None:
        if hwnd not in self._windows:
            logger.debug("Received DESTROY for unknown HWND 0x%x", hwnd)
            return
        logger.info("[RAIL] Destroying Wayland window for HWND 0x%x", hwnd)
        if hwnd in self._sessions and self._freerdp_inv is not None:
            try:
                self._freerdp_inv.terminate(self._sessions[hwnd])
            except Exception:
                logger.exception("FreeRDP terminate failed for HWND 0x%x", hwnd)
            del self._sessions[hwnd]
        del self._windows[hwnd]

    def _handle_moved(self, hwnd: int, event: control_pb2.RailWindowEvent) -> None:
        if hwnd not in self._windows:
            logger.warning(
                "Received MOVE for unknown HWND 0x%x. Cannot move a ghost window!",
                hwnd,
            )
            return
        rect = event.geometry
        win = self._windows[hwnd]
        win["x"] = rect.x
        win["y"] = rect.y
        win["width"] = rect.width
        win["height"] = rect.height
        logger.debug(
            "[RAIL] Moved HWND 0x%x to (%d, %d) [%dx%d]",
            hwnd,
            rect.x,
            rect.y,
            rect.width,
            rect.height,
        )

    def _handle_focus(self, hwnd: int) -> None:
        if hwnd in self._windows:
            logger.debug("[RAIL] Setting Wayland focus to HWND 0x%x", hwnd)

    def _handle_title_change(
        self, hwnd: int, event: control_pb2.RailWindowEvent
    ) -> None:
        if hwnd in self._windows:
            self._windows[hwnd]["title"] = event.title
            logger.debug("[RAIL] Title changed for HWND 0x%x: %s", hwnd, event.title)

    def register_session(self, hwnd: int, session: RailSession) -> None:
        """Associate a FreeRDP RAIL session with the HWND the guest
        will eventually report. Called by the per-launch flow that
        lands fully in Week 11 alongside D-Bus notifications."""
        self._sessions[hwnd] = session
