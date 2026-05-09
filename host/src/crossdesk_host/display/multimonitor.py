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
"""

from __future__ import annotations

from dataclasses import dataclass


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
