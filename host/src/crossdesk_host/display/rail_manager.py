import logging
from typing import Any, Dict

from crossdesk_host.proto.crossdesk.v1 import control_pb2

logger = logging.getLogger(__name__)

class RailManager:
    """Tracks RAIL windows on the host side. POC stub — real impl drives FreeRDP/Wayland."""

    def __init__(self) -> None:
        self._windows: Dict[int, Dict[str, Any]] = {}

    def handle_rail_event(self, event: control_pb2.RailWindowEvent) -> None:
        hwnd = event.window_id
        kind = event.kind

        if kind == control_pb2.RailWindowEvent.Kind.KIND_CREATED:
            self._handle_create(hwnd, event)
        elif kind == control_pb2.RailWindowEvent.Kind.KIND_DESTROYED:
            self._handle_destroy(hwnd)
        elif kind == control_pb2.RailWindowEvent.Kind.KIND_MOVED:
            self._handle_moved(hwnd, event)
        elif kind == control_pb2.RailWindowEvent.Kind.KIND_RESIZED:
            self._handle_moved(hwnd, event) # używamy tej samej logiki
        elif kind == control_pb2.RailWindowEvent.Kind.KIND_FOCUS_GAINED:
            self._handle_focus(hwnd)
        elif kind == control_pb2.RailWindowEvent.Kind.KIND_TITLE_CHANGED:
            self._handle_title_change(hwnd, event)
        else:
            logger.debug(f"[{hwnd}] Unhandled event kind: {kind}")

    def _handle_create(self, hwnd: int, event: control_pb2.RailWindowEvent) -> None:
        if hwnd in self._windows:
            logger.warning(f"Window 0x{hwnd:x} already exists. Ignoring CREATE.")
            return

        title = event.title if event.title else "<unnamed>"
        rect = event.geometry
        
        # W docelowym systemie wywołalibyśmy API FreeRDP lub Wayland Compositor.
        logger.info(f"[RAIL] Creating native Wayland window for HWND 0x{hwnd:x} '{title}' "
                    f"at ({rect.x}, {rect.y}) size {rect.width}x{rect.height}")
        
        self._windows[hwnd] = {
            "title": title,
            "x": rect.x,
            "y": rect.y,
            "width": rect.width,
            "height": rect.height,
        }

    def _handle_destroy(self, hwnd: int) -> None:
        if hwnd not in self._windows:
            # Okno mogło być zignorowane lub przegapiliśmy CREATE
            logger.debug(f"Received DESTROY for unknown HWND 0x{hwnd:x}")
            return
            
        logger.info(f"[RAIL] Destroying Wayland window for HWND 0x{hwnd:x}")
        del self._windows[hwnd]

    def _handle_moved(self, hwnd: int, event: control_pb2.RailWindowEvent) -> None:
        if hwnd not in self._windows:
            logger.warning(f"Received MOVE for unknown HWND 0x{hwnd:x}. Cannot move a ghost window!")
            return

        rect = event.geometry
        win = self._windows[hwnd]
        win["x"] = rect.x
        win["y"] = rect.y
        win["width"] = rect.width
        win["height"] = rect.height
        
        logger.debug(f"[RAIL] Moved HWND 0x{hwnd:x} to ({rect.x}, {rect.y}) [{rect.width}x{rect.height}]")

    def _handle_focus(self, hwnd: int) -> None:
        if hwnd in self._windows:
            logger.debug(f"[RAIL] Setting Wayland focus to HWND 0x{hwnd:x}")

    def _handle_title_change(self, hwnd: int, event: control_pb2.RailWindowEvent) -> None:
        if hwnd in self._windows:
            self._windows[hwnd]["title"] = event.title
            logger.debug(f"[RAIL] Title changed for HWND 0x{hwnd:x}: {event.title}")
