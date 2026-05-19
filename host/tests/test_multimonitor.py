"""Multi-monitor placement tests (Week 11)."""

from __future__ import annotations

import pytest

from crossdesk_host.display.multimonitor import (
    Monitor,
    WindowGeometry,
    choose_monitor,
)


def test_centre_inside_a_monitor_picks_it() -> None:
    monitors = [
        Monitor(name="DP-1", x=0, y=0, width=1920, height=1080),
        Monitor(name="HDMI-1", x=1920, y=0, width=2560, height=1440),
    ]
    win = WindowGeometry(x=2000, y=100, width=400, height=300)
    chosen = choose_monitor(win, monitors)
    assert chosen.name == "HDMI-1"


def test_centre_in_first_monitor_picks_first() -> None:
    monitors = [
        Monitor(name="DP-1", x=0, y=0, width=1920, height=1080),
        Monitor(name="HDMI-1", x=1920, y=0, width=2560, height=1440),
    ]
    win = WindowGeometry(x=100, y=100, width=400, height=300)
    chosen = choose_monitor(win, monitors)
    assert chosen.name == "DP-1"


def test_centre_outside_all_picks_nearest() -> None:
    monitors = [
        Monitor(name="DP-1", x=0, y=0, width=100, height=100),
        Monitor(name="HDMI-1", x=1000, y=1000, width=100, height=100),
    ]
    # Centre at (550, 550); DP-1's centre at (50, 50) is closer than (1050, 1050).
    win = WindowGeometry(x=500, y=500, width=100, height=100)
    chosen = choose_monitor(win, monitors)
    assert chosen.name == "DP-1"


def test_tie_breaker_uses_list_order() -> None:
    monitors = [
        Monitor(name="primary", x=0, y=0, width=100, height=100),
        Monitor(name="mirror", x=0, y=0, width=100, height=100),
    ]
    win = WindowGeometry(x=200, y=200, width=10, height=10)
    chosen = choose_monitor(win, monitors)
    assert chosen.name == "primary"


def test_empty_monitor_list_rejected() -> None:
    win = WindowGeometry(x=0, y=0, width=10, height=10)
    with pytest.raises(ValueError):
        choose_monitor(win, [])


def test_single_monitor_always_chosen() -> None:
    monitors = [Monitor(name="solo", x=0, y=0, width=100, height=100)]
    win = WindowGeometry(x=10000, y=10000, width=10, height=10)
    chosen = choose_monitor(win, monitors)
    assert chosen.name == "solo"


# ---------------------------------------------------------------------------
# enumerate_monitors — parser ladder
# ---------------------------------------------------------------------------


class _ScriptedRunner:
    """Same shape as the hidpi test scripted-runner; maps binary
    basename to canned stdout (or None to simulate "not on PATH")."""

    def __init__(self, scripted: dict[str, str | None]) -> None:
        self.scripted = scripted

    def run(self, argv: list[str]) -> str | None:
        if not argv:
            return None
        return self.scripted.get(argv[0])


_WLR_TWO_OUTPUTS = """\
DP-1 "AOC 4K27 (DP-1)"
  Make: AOC
  Model: 4K27
  Position: 0,0
  Modes:
    3840x2160 px, 60.000000 Hz (preferred, current)
    1920x1080 px, 60.000000 Hz
  Transform: normal
HDMI-A-1 "Generic Display"
  Position: 3840,0
  Modes:
    2560x1440 px, 60.000000 Hz (preferred, current)
"""

_XRANDR_TWO_OUTPUTS = """\
Screen 0: minimum 320 x 200, current 6400 x 2160, maximum 16384 x 16384
DP-1 connected primary 3840x2160+0+0 (normal left inverted right x axis y axis) 600mm x 340mm
   3840x2160     60.00*+  30.00
HDMI-1 connected 2560x1440+3840+0 (normal left inverted right x axis y axis) 597mm x 336mm
   2560x1440     60.00*+
DP-2 disconnected (normal left inverted right x axis y axis)
"""


def test_enumerate_wlr_randr_parses_two_outputs() -> None:
    from crossdesk_host.display.multimonitor import enumerate_monitors

    runner = _ScriptedRunner({"wlr-randr": _WLR_TWO_OUTPUTS})
    monitors = enumerate_monitors(runner)

    assert [m.name for m in monitors] == ["DP-1", "HDMI-A-1"]
    assert monitors[0] == Monitor(name="DP-1", x=0, y=0, width=3840, height=2160)
    assert monitors[1] == Monitor(name="HDMI-A-1", x=3840, y=0, width=2560, height=1440)


def test_enumerate_falls_through_to_xrandr_when_wlr_missing() -> None:
    from crossdesk_host.display.multimonitor import enumerate_monitors

    runner = _ScriptedRunner({"wlr-randr": None, "xrandr": _XRANDR_TWO_OUTPUTS})
    monitors = enumerate_monitors(runner)

    assert [m.name for m in monitors] == ["DP-1", "HDMI-1"]
    assert monitors[0].width == 3840
    assert monitors[0].height == 2160
    assert monitors[1].x == 3840


def test_enumerate_xrandr_skips_disconnected_outputs() -> None:
    from crossdesk_host.display.multimonitor import enumerate_monitors

    runner = _ScriptedRunner({"wlr-randr": None, "xrandr": _XRANDR_TWO_OUTPUTS})
    monitors = enumerate_monitors(runner)
    assert "DP-2" not in [m.name for m in monitors]


def test_enumerate_returns_empty_when_neither_tool_available() -> None:
    from crossdesk_host.display.multimonitor import enumerate_monitors

    runner = _ScriptedRunner({})
    assert enumerate_monitors(runner) == []


def test_enumerate_wlr_randr_negative_position_is_preserved() -> None:
    from crossdesk_host.display.multimonitor import enumerate_monitors

    text = """\
DP-1 "Left"
  Position: -1920,0
  Modes:
    1920x1080 px, 60.000000 Hz (current)
DP-2 "Right"
  Position: 0,0
  Modes:
    1920x1080 px, 60.000000 Hz (current)
"""
    monitors = enumerate_monitors(_ScriptedRunner({"wlr-randr": text}))
    assert monitors[0].x == -1920
    assert monitors[1].x == 0


def test_enumerate_xrandr_parses_primary_flag() -> None:
    from crossdesk_host.display.multimonitor import enumerate_monitors

    text = """\
DP-1 connected primary 1920x1080+0+0 600mm x 340mm
"""
    monitors = enumerate_monitors(_ScriptedRunner({"wlr-randr": None, "xrandr": text}))
    assert monitors == [Monitor(name="DP-1", x=0, y=0, width=1920, height=1080)]


def test_enumerate_falls_through_when_wlr_unparseable() -> None:
    from crossdesk_host.display.multimonitor import enumerate_monitors

    runner = _ScriptedRunner({
        "wlr-randr": "this is not wlr-randr output\n",
        "xrandr": _XRANDR_TWO_OUTPUTS,
    })
    monitors = enumerate_monitors(runner)
    assert [m.name for m in monitors] == ["DP-1", "HDMI-1"]

