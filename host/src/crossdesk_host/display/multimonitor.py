"""Multi-monitor placement for RAIL windows.

WinApps' README warns that ``/multimon`` causes black screens; we
side-step the FreeRDP feature entirely and place each RAIL window
ourselves. The placement choice is purely a function of the window's
desired geometry and the enumerated host monitors — a pure transform
that's easy to mock and unit-test.

Placement rule (Phase 4 minimum, intentionally simple):

- Pick the monitor whose viewport contains the window's centre.
- If no monitor contains the centre, pick the one whose viewport
  centre is closest (Euclidean distance).
- Tie-break by listing order — the compositor's primary tends to
  come first in ``xrandr``/``wlr-randr`` output.

Anything fancier (per-app sticky monitor memory, per-display HiDPI
scale picking) is queued for after MVP — Phase 4 acceptance only
requires that *some* monitor is chosen consistently.

Enumeration probes (Wayland first, then X11) reuse the
:class:`crossdesk_host.display.hidpi.ProbeRunner` Protocol so tests
can script outputs via the same scripted-runner pattern that pins
the HiDPI ladder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from crossdesk_host.display.hidpi import ProbeRunner, RealProbeRunner


@dataclass(frozen=True)
class Monitor:
    name: str
    x: int
    y: int
    width: int
    height: int

    @property
    def centre(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    def contains(self, px: int, py: int) -> bool:
        return (
            self.x <= px < self.x + self.width and self.y <= py < self.y + self.height
        )


@dataclass(frozen=True)
class WindowGeometry:
    x: int
    y: int
    width: int
    height: int

    @property
    def centre(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)


def choose_monitor(window: WindowGeometry, monitors: list[Monitor]) -> Monitor:
    if not monitors:
        raise ValueError("at least one monitor is required")

    cx, cy = window.centre
    cx_int, cy_int = int(cx), int(cy)

    for monitor in monitors:
        if monitor.contains(cx_int, cy_int):
            return monitor

    def squared_distance(monitor: Monitor) -> float:
        mx, my = monitor.centre
        dx = mx - cx
        dy = my - cy
        return dx * dx + dy * dy

    best: Monitor = monitors[0]
    best_d = squared_distance(best)
    for monitor in monitors[1:]:
        d = squared_distance(monitor)
        if d < best_d:
            best = monitor
            best_d = d
    return best


# Wayland (wlr-randr) stanzas are space-indented with header lines like
#     DP-1 "Display Name (DP-1)"
# followed by indented "Position: x,y" and the current mode under
# "Modes:" -> "  WIDTHxHEIGHT px, …Hz (… current …)".
_WLR_HEADER_RE = re.compile(r"^(\S+)\s+\"")
_WLR_POSITION_RE = re.compile(r"^\s*Position:\s*(-?\d+),(-?\d+)\s*$")
_WLR_CURRENT_MODE_RE = re.compile(
    r"^\s*(\d+)x(\d+)\s*px,.*current"
)

# xrandr "connected" rows look like:
#     DP-1 connected primary 1920x1080+0+0 (normal left inverted right …) 600mm x 340mm
# We accept any "connected" output (primary or not). Disconnected
# rows omit the geometry block entirely so the regex naturally
# rejects them.
_XRANDR_CONNECTED_RE = re.compile(
    r"^(\S+)\s+connected(?:\s+primary)?\s+(\d+)x(\d+)\+(-?\d+)\+(-?\d+)"
)


def _parse_wlr_randr(text: str) -> List[Monitor]:
    monitors: List[Monitor] = []
    current_name: Optional[str] = None
    current_x: Optional[int] = None
    current_y: Optional[int] = None
    current_w: Optional[int] = None
    current_h: Optional[int] = None

    def flush() -> None:
        if (
            current_name is not None
            and current_x is not None
            and current_y is not None
            and current_w is not None
            and current_h is not None
        ):
            monitors.append(
                Monitor(
                    name=current_name,
                    x=current_x,
                    y=current_y,
                    width=current_w,
                    height=current_h,
                )
            )

    for raw in text.splitlines():
        header = _WLR_HEADER_RE.match(raw)
        if header:
            flush()
            current_name = header.group(1)
            current_x = current_y = current_w = current_h = None
            continue
        pos = _WLR_POSITION_RE.match(raw)
        if pos:
            current_x = int(pos.group(1))
            current_y = int(pos.group(2))
            continue
        mode = _WLR_CURRENT_MODE_RE.match(raw)
        if mode:
            current_w = int(mode.group(1))
            current_h = int(mode.group(2))
    flush()
    return monitors


def _parse_xrandr(text: str) -> List[Monitor]:
    monitors: List[Monitor] = []
    for raw in text.splitlines():
        m = _XRANDR_CONNECTED_RE.match(raw)
        if not m:
            continue
        monitors.append(
            Monitor(
                name=m.group(1),
                x=int(m.group(4)),
                y=int(m.group(5)),
                width=int(m.group(2)),
                height=int(m.group(3)),
            )
        )
    return monitors


def enumerate_monitors(runner: Optional[ProbeRunner] = None) -> List[Monitor]:
    """Probe the active display server for connected monitors.

    Tries ``wlr-randr`` first (Wayland compositors that implement
    ``wlr-output-management``), then ``xrandr`` (X11 / XWayland).
    Returns ``[]`` if neither tool is on PATH or both produce
    unparseable output — callers should fall back to a single
    virtual monitor spanning the window's reported geometry, which
    is exactly the Phase 4 default before this enumeration exists.
    """
    runner = runner or RealProbeRunner()
    out = runner.run(["wlr-randr"])
    if out:
        parsed = _parse_wlr_randr(out)
        if parsed:
            return parsed
    out = runner.run(["xrandr", "--query"])
    if out:
        parsed = _parse_xrandr(out)
        if parsed:
            return parsed
    return []
