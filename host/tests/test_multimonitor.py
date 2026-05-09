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
