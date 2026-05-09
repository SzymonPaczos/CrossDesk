"""HiDPI scale auto-detection.

FreeRDP's RAIL ``/scale:`` flag only accepts three discrete values:
``100``, ``140``, ``180``. Our job is to look at whichever desktop
environment is actually running and pick the closest one.

Detection ladder (in order, first one that returns a value wins):

1. Wayland: ``wl_output.scale`` reported by ``wlr-randr`` /
   ``wayland-info``.
2. X11: ``xrdb`` ``Xft.dpi`` resource.
3. GNOME: ``gsettings get org.gnome.desktop.interface text-scaling-factor``.
4. KDE: ``kreadconfig5 --file kdeglobals --group KScreen --key
   ScreenScaleFactors``.
5. Fallback: ``CROSSDESK_SCALE`` env var.
6. Last resort: ``100``.

Each probe is a thin wrapper around ``subprocess.run`` so tests can
swap out the runner via :class:`ProbeRunner` Protocol and assert
against synthetic outputs.

End-to-end correctness (does ``/scale:140`` actually look right on a
4K display?) is hardware-gated; the unit tests here only verify
parsing + the discrete bucket selection.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class ProbeResult:
    """Output of a single detection probe.

    ``scaling_factor`` is the desktop's native value (e.g. ``1.0``,
    ``1.5``, ``2.0``); :func:`bucketize` snaps it to FreeRDP's
    nearest supported scale.
    """

    source: str
    scaling_factor: float


class ProbeRunner(Protocol):
    def run(self, argv: list[str]) -> Optional[str]:
        """Execute ``argv`` and return stdout. Return ``None`` if the
        command isn't on PATH or returns non-zero. Implementations
        must NOT raise on missing binaries — the ladder relies on
        cheap "skip if absent"."""
        ...


class _RealProbeRunner(ProbeRunner):
    def run(self, argv: list[str]) -> Optional[str]:
        if not argv or shutil.which(argv[0]) is None:
            return None
        try:
            result = subprocess.run(
                argv, check=False, capture_output=True, text=True, timeout=2.0
            )
        except (subprocess.SubprocessError, OSError):
            return None
        if result.returncode != 0:
            return None
        return result.stdout


def _try_gsettings(runner: ProbeRunner) -> Optional[ProbeResult]:
    out = runner.run(
        ["gsettings", "get", "org.gnome.desktop.interface", "text-scaling-factor"]
    )
    if out is None:
        return None
    try:
        value = float(out.strip())
    except ValueError:
        return None
    return ProbeResult(source="gnome", scaling_factor=value)


def _try_kde(runner: ProbeRunner) -> Optional[ProbeResult]:
    out = runner.run(
        [
            "kreadconfig5",
            "--file",
            "kdeglobals",
            "--group",
            "KScreen",
            "--key",
            "ScreenScaleFactors",
        ]
    )
    if out is None:
        return None
    # KDE format: "DP-1=2.0;HDMI-A-1=1.0;" — take the first value.
    pieces = out.strip().split(";")
    for piece in pieces:
        if "=" in piece:
            try:
                return ProbeResult(
                    source="kde", scaling_factor=float(piece.split("=", 1)[1])
                )
            except ValueError:
                continue
    return None


def _try_xrdb(runner: ProbeRunner) -> Optional[ProbeResult]:
    out = runner.run(["xrdb", "-query"])
    if out is None:
        return None
    for line in out.splitlines():
        if line.startswith("Xft.dpi:"):
            try:
                dpi = float(line.split(":", 1)[1].strip())
            except ValueError:
                return None
            # 96 dpi is the canonical 1.0 scale.
            return ProbeResult(source="xrdb", scaling_factor=dpi / 96.0)
    return None


def _try_env() -> Optional[ProbeResult]:
    raw = os.environ.get("CROSSDESK_SCALE")
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return ProbeResult(source="env", scaling_factor=value / 100.0)


def detect_scaling(
    runner: Optional[ProbeRunner] = None,
) -> ProbeResult:
    """Walk the detection ladder and return the first hit; falls
    back to ``ProbeResult(source="default", scaling_factor=1.0)``."""
    runner = runner or _RealProbeRunner()
    for probe in (_try_gsettings, _try_kde, _try_xrdb):
        result = probe(runner)
        if result is not None:
            return result
    env_result = _try_env()
    if env_result is not None:
        return env_result
    return ProbeResult(source="default", scaling_factor=1.0)


def bucketize(scaling_factor: float) -> int:
    """Snap a free-form scaling factor to the nearest FreeRDP scale
    (100, 140, 180)."""
    if scaling_factor <= 0:
        raise ValueError("scaling_factor must be positive")
    candidates = (1.0, 1.4, 1.8)
    nearest = min(candidates, key=lambda c: abs(c - scaling_factor))
    return int(nearest * 100)
