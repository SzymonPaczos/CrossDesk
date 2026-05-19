"""HiDPI scale detection unit tests (Phase 4 / Week 10)."""

from __future__ import annotations

from typing import Dict, Optional

import pytest

from crossdesk_host.display.hidpi import (
    ProbeRunner,
    auto_scale,
    bucketize,
    detect_scaling,
)


class _ScriptedRunner(ProbeRunner):
    def __init__(self, scripted: Dict[str, str]) -> None:
        # Map binary name → stdout. Unmapped binaries return None.
        self.scripted = scripted

    def run(self, argv: list[str]) -> Optional[str]:
        if not argv:
            return None
        return self.scripted.get(argv[0])


# ---------------------------------------------------------------------------
# bucketize
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "factor,expected",
    [
        (1.0, 100),
        (1.1, 100),
        (1.2, 100),
        (1.3, 140),
        (1.4, 140),
        (1.5, 140),
        (1.7, 180),
        (1.8, 180),
        (2.0, 180),
        (3.0, 180),
    ],
)
def test_bucketize_snaps_to_freerdp_scale(factor: float, expected: int) -> None:
    assert bucketize(factor) == expected


def test_bucketize_rejects_zero() -> None:
    with pytest.raises(ValueError):
        bucketize(0.0)


def test_bucketize_rejects_negative() -> None:
    with pytest.raises(ValueError):
        bucketize(-1.0)


# ---------------------------------------------------------------------------
# detect_scaling ladder
# ---------------------------------------------------------------------------


_WLR_RANDR_SAMPLE = """\
DP-1 "Some Display Co LTD A123 (DP-1)"
  Make: Some Display Co LTD
  Model: A123
  Serial: 0xCAFE
  Physical size: 600x340 mm
  Enabled: yes
  Modes:
    3840x2160 px, 60.000000 Hz (preferred, current)
  Position: 0,0
  Transform: normal
  Scale: 1.500000
"""


def test_wlr_randr_takes_first_output_scale() -> None:
    runner = _ScriptedRunner({"wlr-randr": _WLR_RANDR_SAMPLE})
    result = detect_scaling(runner)
    assert result.source == "wlr-randr"
    assert result.scaling_factor == pytest.approx(1.5)


def test_wlr_randr_takes_precedence_over_gnome() -> None:
    runner = _ScriptedRunner(
        {"wlr-randr": _WLR_RANDR_SAMPLE, "gsettings": "1.0\n"}
    )
    result = detect_scaling(runner)
    assert result.source == "wlr-randr"


def test_wlr_randr_invalid_scale_falls_through() -> None:
    bad = _WLR_RANDR_SAMPLE.replace("1.500000", "not-a-number")
    runner = _ScriptedRunner({"wlr-randr": bad, "gsettings": "1.4\n"})
    result = detect_scaling(runner)
    assert result.source == "gnome"


def test_wlr_randr_no_scale_line_falls_through() -> None:
    no_scale = "\n".join(
        line for line in _WLR_RANDR_SAMPLE.splitlines() if "Scale:" not in line
    )
    runner = _ScriptedRunner({"wlr-randr": no_scale, "gsettings": "1.4\n"})
    result = detect_scaling(runner)
    assert result.source == "gnome"


def test_gnome_text_scaling_factor_returned_first() -> None:
    runner = _ScriptedRunner({"gsettings": "1.5\n"})
    result = detect_scaling(runner)
    assert result.source == "gnome"
    assert result.scaling_factor == pytest.approx(1.5)


def test_falls_through_to_kde_when_gsettings_missing() -> None:
    runner = _ScriptedRunner({"kreadconfig5": "DP-1=2.0;HDMI-A-1=1.0;\n"})
    result = detect_scaling(runner)
    assert result.source == "kde"
    assert result.scaling_factor == pytest.approx(2.0)


def test_falls_through_to_xrdb() -> None:
    runner = _ScriptedRunner({"xrdb": "Xft.dpi: 192\nfoo: bar\n"})
    result = detect_scaling(runner)
    assert result.source == "xrdb"
    assert result.scaling_factor == pytest.approx(2.0)  # 192/96


def test_default_when_nothing_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CROSSDESK_SCALE", raising=False)
    runner = _ScriptedRunner({})
    result = detect_scaling(runner)
    assert result.source == "default"
    assert result.scaling_factor == 1.0


def test_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROSSDESK_SCALE", "140")
    runner = _ScriptedRunner({})
    result = detect_scaling(runner)
    assert result.source == "env"
    assert result.scaling_factor == pytest.approx(1.4)


def test_invalid_gsettings_output_falls_through() -> None:
    runner = _ScriptedRunner(
        {"gsettings": "not-a-number\n", "kreadconfig5": "DP-1=1.4;\n"}
    )
    result = detect_scaling(runner)
    assert result.source == "kde"


def test_invalid_xrdb_dpi_returns_none() -> None:
    runner = _ScriptedRunner({"xrdb": "Xft.dpi: garbage\n"})
    result = detect_scaling(runner)
    assert result.source == "default"


# ---------------------------------------------------------------------------
# auto_scale (detect + bucketize convenience)
# ---------------------------------------------------------------------------


def test_auto_scale_wayland_15_buckets_to_140() -> None:
    runner = _ScriptedRunner({"wlr-randr": _WLR_RANDR_SAMPLE})
    assert auto_scale(runner) == 140


def test_auto_scale_default_returns_100(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CROSSDESK_SCALE", raising=False)
    assert auto_scale(_ScriptedRunner({})) == 100


def test_auto_scale_4k_2x_buckets_to_180() -> None:
    runner = _ScriptedRunner({"xrdb": "Xft.dpi: 192\n"})
    assert auto_scale(runner) == 180
