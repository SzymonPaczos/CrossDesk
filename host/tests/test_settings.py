"""Settings TOML round-trip + clamping tests."""

from __future__ import annotations

from pathlib import Path

from crossdesk_host.installer import settings


def test_load_missing_returns_defaults(tmp_path: Path) -> None:
    s = settings.load(tmp_path / "nope.toml")
    assert s == settings.Settings()


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "settings.toml"
    s = settings.Settings(
        language="pl", theme="dark", telemetry_enabled=True, hidpi_scale=140
    )
    settings.save(s, target)
    loaded = settings.load(target)
    assert loaded == s


def test_clamp_normalises_invalid_hidpi() -> None:
    s = settings.Settings(hidpi_scale=125)
    settings.clamp(s)
    assert s.hidpi_scale == 0


def test_clamp_normalises_invalid_theme() -> None:
    s = settings.Settings(theme="solarized")
    settings.clamp(s)
    assert s.theme == "system"


def test_clamp_normalises_invalid_network() -> None:
    s = settings.Settings(network_mode="hyperloop")
    settings.clamp(s)
    assert s.network_mode == "nat"


def test_clamp_floors_fsm_thresholds() -> None:
    s = settings.Settings(
        miss_threshold=0,
        recovery_ticks=0,
        max_soft_attempts=0,
        backoff_initial_seconds=0.01,
        auto_suspend_after_seconds=10,
    )
    settings.clamp(s)
    assert s.miss_threshold == 1
    assert s.recovery_ticks == 1
    assert s.max_soft_attempts == 1
    assert s.backoff_initial_seconds >= 0.1
    assert s.auto_suspend_after_seconds >= 60


def test_save_atomic_no_tmp_leak(tmp_path: Path) -> None:
    target = tmp_path / "settings.toml"
    settings.save(settings.Settings(), target)
    leftover = list(tmp_path.glob("settings.toml.*.tmp"))
    assert leftover == []


def test_load_ignores_unknown_keys(tmp_path: Path) -> None:
    """Forward compat: a future field on disk must not crash older
    binaries reading the file."""
    target = tmp_path / "settings.toml"
    target.write_text(
        'language = "pl"\nfuture_field = "some-future-feature"\n', encoding="utf-8"
    )
    loaded = settings.load(target)
    assert loaded.language == "pl"
