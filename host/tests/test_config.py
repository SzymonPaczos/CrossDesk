"""Unit coverage for the typed config schema (``crossdesk_host.config``).

Covers the four boundaries an operator can hit:

- happy path: empty TOML → all defaults.
- partial overrides via TOML: one section replaced, others default.
- env-var overrides via ``CROSSDESK_CONFIG__SECTION__FIELD``.
- validation errors: bad enum value, out-of-range port, malformed TOML.

Path-handling defaults (``vm_credentials_file``, etc.) are derived
properties; covered in the happy-path test rather than per-property
because they're pure path concatenation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from crossdesk_host.config import (
    CrossdeskConfig,
    HeartbeatConfig,
    PathsConfig,
    PeripheralsConfig,
    TransportConfig,
    default_config_path,
    load_from_toml,
)


def test_defaults_all_sensible() -> None:
    cfg = CrossdeskConfig()
    assert cfg.transport.vsock_port == 50051
    assert cfg.transport.connect_timeout_seconds == 5.0
    assert cfg.heartbeat.ewma_alpha == 0.125
    assert cfg.heartbeat.miss_threshold == 3
    assert cfg.peripherals.audio_mode == "playback"
    assert cfg.peripherals.clipboard_mode == "text"
    assert cfg.peripherals.smartcard_enabled is False
    assert cfg.daemon.host_version == "0.1.0"
    assert "adaptive-heartbeat" in cfg.daemon.supported_features


def test_paths_derived_properties_compose_correctly(tmp_path: Path) -> None:
    paths = PathsConfig(
        config_dir=tmp_path / "cfg",
        state_dir=tmp_path / "state",
        data_dir=tmp_path / "data",
        pki_dir=tmp_path / "pki",
    )
    assert paths.vm_credentials_file == tmp_path / "cfg" / "vm.toml"
    assert paths.settings_file == tmp_path / "cfg" / "settings.toml"
    assert paths.install_state_file == tmp_path / "state" / "install.state.json"
    assert paths.ca_cert == tmp_path / "pki" / "ca.crt"
    assert paths.host_cert == tmp_path / "pki" / "host.crt"
    assert paths.host_key == tmp_path / "pki" / "host.key"


def test_load_from_toml_missing_file_returns_defaults(tmp_path: Path) -> None:
    cfg = load_from_toml(tmp_path / "nonexistent.toml", env={})
    assert cfg == CrossdeskConfig()


def test_load_from_toml_partial_override_keeps_other_defaults(
    tmp_path: Path,
) -> None:
    toml = tmp_path / "config.toml"
    toml.write_text(
        "[transport]\n"
        "vsock_port = 60001\n"
        "[peripherals]\n"
        'clipboard_mode = "rich"\n'
    )
    cfg = load_from_toml(toml, env={})
    assert cfg.transport.vsock_port == 60001
    # Defaults preserved on untouched fields.
    assert cfg.transport.connect_timeout_seconds == 5.0
    assert cfg.peripherals.clipboard_mode == "rich"
    assert cfg.peripherals.audio_mode == "playback"
    assert cfg.heartbeat.ewma_alpha == 0.125


def test_env_overrides_apply_on_top_of_toml(tmp_path: Path) -> None:
    toml = tmp_path / "config.toml"
    toml.write_text("[transport]\nvsock_port = 60001\n")
    env: Dict[str, str] = {
        "CROSSDESK_CONFIG__TRANSPORT__VSOCK_PORT": "60002",
        "CROSSDESK_CONFIG__HEARTBEAT__MISS_THRESHOLD": "7",
        "CROSSDESK_CONFIG__PERIPHERALS__SMARTCARD_ENABLED": "true",
        "UNRELATED_VAR": "ignored",
    }
    cfg = load_from_toml(toml, env=env)
    assert cfg.transport.vsock_port == 60002  # env wins over TOML
    assert cfg.heartbeat.miss_threshold == 7
    assert cfg.peripherals.smartcard_enabled is True


def test_env_override_coerces_float_and_bool() -> None:
    env: Dict[str, str] = {
        "CROSSDESK_CONFIG__HEARTBEAT__EWMA_ALPHA": "0.25",
        "CROSSDESK_CONFIG__PERIPHERALS__DRAG_AND_DROP_ENABLED": "FALSE",
    }
    cfg = load_from_toml(Path("/nonexistent"), env=env)
    assert cfg.heartbeat.ewma_alpha == 0.25
    assert cfg.peripherals.drag_and_drop_enabled is False


def test_invalid_audio_mode_raises() -> None:
    with pytest.raises(ValueError, match="audio_mode"):
        PeripheralsConfig(audio_mode="banana")


def test_invalid_clipboard_mode_raises() -> None:
    with pytest.raises(ValueError, match="clipboard_mode"):
        PeripheralsConfig(clipboard_mode="binary")


def test_printer_named_form_accepted() -> None:
    cfg = PeripheralsConfig(printer_mode="named:Brother-HL")
    assert cfg.printer_mode == "named:Brother-HL"


def test_printer_invalid_form_rejected() -> None:
    with pytest.raises(ValueError, match="printer_mode"):
        PeripheralsConfig(printer_mode="random-string")


def test_port_out_of_range_rejected() -> None:
    with pytest.raises(ValueError, match="vsock_port"):
        TransportConfig(vsock_port=0)
    with pytest.raises(ValueError, match="vsock_port"):
        TransportConfig(vsock_port=70000)


def test_negative_timeout_rejected() -> None:
    with pytest.raises(ValueError, match="timeouts"):
        TransportConfig(rpc_timeout_seconds=-1.0)


def test_ewma_alpha_outside_unit_interval_rejected() -> None:
    with pytest.raises(ValueError, match="ewma_alpha"):
        HeartbeatConfig(ewma_alpha=1.0)
    with pytest.raises(ValueError, match="ewma_alpha"):
        HeartbeatConfig(ewma_alpha=0.0)


def test_miss_threshold_zero_rejected() -> None:
    with pytest.raises(ValueError, match="counts"):
        HeartbeatConfig(miss_threshold=0)


def test_baseline_multiplier_must_exceed_one() -> None:
    with pytest.raises(ValueError, match="baseline_multiplier_k1"):
        HeartbeatConfig(baseline_multiplier_k1=1.0)


def test_unknown_field_in_toml_rejected(tmp_path: Path) -> None:
    toml = tmp_path / "config.toml"
    toml.write_text("[transport]\nbogus_field = 42\n")
    with pytest.raises(ValueError):
        load_from_toml(toml, env={})


def test_frozen_config_blocks_mutation() -> None:
    cfg = CrossdeskConfig()
    with pytest.raises(Exception):  # pydantic raises ValidationError on frozen-set
        cfg.transport.vsock_port = 60001  # type: ignore[misc]


def test_supported_features_duplicate_rejected() -> None:
    from crossdesk_host.config import DaemonConfig

    with pytest.raises(ValueError, match="duplicates"):
        DaemonConfig(supported_features=("a", "b", "a"))


def test_supported_features_normalised_to_sorted_tuple() -> None:
    from crossdesk_host.config import DaemonConfig

    cfg = DaemonConfig(supported_features=("z", "a", "m"))
    assert cfg.supported_features == ("a", "m", "z")


def test_default_config_path_under_user_home(monkeypatch: Any) -> None:
    monkeypatch.setenv("HOME", "/tmp/fake-home")
    assert default_config_path() == Path("/tmp/fake-home/.config/crossdesk/config.toml")


def test_load_uses_default_path_when_omitted(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    # File doesn't exist → defaults; verifies the discovery branch runs.
    cfg = load_from_toml(env={})
    assert cfg == CrossdeskConfig()


def test_partial_env_only_no_toml(tmp_path: Path) -> None:
    env: Dict[str, str] = {"CROSSDESK_CONFIG__TRANSPORT__VSOCK_PORT": "12345"}
    cfg = load_from_toml(tmp_path / "missing.toml", env=env)
    assert cfg.transport.vsock_port == 12345
