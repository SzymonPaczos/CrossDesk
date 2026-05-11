"""Unit coverage for ``crossdesk_host.config.peripherals``.

Tests follow the project convention: validate at boundaries, unit-test the
boundary module directly without mocking internals.

The twelve required cases cover:

1.  ``test_defaults_all_safe`` — defaults are safe (playback audio, text-only
    clipboard, everything else off, empty USB list).
2.  ``test_freerdp_flags_audio_playback`` — enabled playback → ``/sound``.
3.  ``test_freerdp_flags_audio_bidirectional`` — bidirectional → both
    ``/sound`` and ``/microphone``.
4.  ``test_freerdp_flags_clipboard_off`` — off mode → no clipboard flag.
5.  ``test_freerdp_flags_clipboard_rich`` — rich mode → ``+clipboard``
    without the text restriction flag.
6.  ``test_freerdp_flags_printer_auto`` — auto → ``/printer``.
7.  ``test_freerdp_flags_printer_named`` — named → ``/printer:<name>``.
8.  ``test_freerdp_flags_smartcard`` — enabled → ``/smartcard``.
9.  ``test_usb_validation_rejects_invalid`` — bad ID → ValidationError.
10. ``test_usb_validation_accepts_valid`` — well-formed ID → no error.
11. ``test_libvirt_xml_usb_fragment`` — one device → XML with vendor+product.
12. ``test_load_missing_file_returns_defaults`` — absent path → defaults.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from crossdesk_host.config.peripherals import PeripheralsConfig, load_peripherals_config


# ---------------------------------------------------------------------------
# 1. Defaults
# ---------------------------------------------------------------------------


def test_defaults_all_safe() -> None:
    cfg = PeripheralsConfig()
    assert cfg.audio_enabled is True
    assert cfg.audio_mode == "playback"
    assert cfg.clipboard_mode == "text-only"
    assert cfg.microphone_enabled is False
    assert cfg.printer_mode == "off"
    assert cfg.printer_name == ""
    assert cfg.smartcard_enabled is False
    assert cfg.usb_devices == []


# ---------------------------------------------------------------------------
# 2. FreeRDP — audio playback
# ---------------------------------------------------------------------------


def test_freerdp_flags_audio_playback() -> None:
    cfg = PeripheralsConfig(audio_enabled=True, audio_mode="playback", clipboard_mode="off")
    flags = cfg.to_freerdp_flags()
    assert "/sound:sys:pipewire" in flags
    # No microphone in playback-only mode.
    assert not any("microphone" in f for f in flags)


# ---------------------------------------------------------------------------
# 3. FreeRDP — audio bidirectional
# ---------------------------------------------------------------------------


def test_freerdp_flags_audio_bidirectional() -> None:
    cfg = PeripheralsConfig(audio_enabled=True, audio_mode="bidirectional", clipboard_mode="off")
    flags = cfg.to_freerdp_flags()
    assert "/sound:sys:pipewire" in flags
    assert "/microphone:sys:pulse" in flags


# ---------------------------------------------------------------------------
# 4. FreeRDP — clipboard off
# ---------------------------------------------------------------------------


def test_freerdp_flags_clipboard_off() -> None:
    cfg = PeripheralsConfig(clipboard_mode="off")
    flags = cfg.to_freerdp_flags()
    assert "+clipboard" not in flags
    assert not any("clipboard" in f for f in flags)


# ---------------------------------------------------------------------------
# 5. FreeRDP — clipboard rich
# ---------------------------------------------------------------------------


def test_freerdp_flags_clipboard_rich() -> None:
    cfg = PeripheralsConfig(clipboard_mode="rich")
    flags = cfg.to_freerdp_flags()
    assert "+clipboard" in flags
    # Rich mode does NOT add the text-restriction flag.
    assert "/clipboard-redirect-type:text" not in flags


# ---------------------------------------------------------------------------
# 6. FreeRDP — printer auto
# ---------------------------------------------------------------------------


def test_freerdp_flags_printer_auto() -> None:
    cfg = PeripheralsConfig(printer_mode="auto", clipboard_mode="off")
    flags = cfg.to_freerdp_flags()
    assert "/printer" in flags


# ---------------------------------------------------------------------------
# 7. FreeRDP — printer named
# ---------------------------------------------------------------------------


def test_freerdp_flags_printer_named() -> None:
    cfg = PeripheralsConfig(printer_mode="named", printer_name="HP_LaserJet", clipboard_mode="off")
    flags = cfg.to_freerdp_flags()
    assert "/printer:HP_LaserJet" in flags
    # Generic /printer must not appear — only the named variant.
    assert "/printer" not in flags


# ---------------------------------------------------------------------------
# 8. FreeRDP — smart card
# ---------------------------------------------------------------------------


def test_freerdp_flags_smartcard() -> None:
    cfg = PeripheralsConfig(smartcard_enabled=True, clipboard_mode="off")
    flags = cfg.to_freerdp_flags()
    assert "/smartcard" in flags


# ---------------------------------------------------------------------------
# 9. USB — validation rejects invalid
# ---------------------------------------------------------------------------


def test_usb_validation_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        PeripheralsConfig(usb_devices=["badvalue"])


def test_usb_validation_rejects_too_short() -> None:
    with pytest.raises(ValidationError):
        PeripheralsConfig(usb_devices=["403:6001"])  # vendor only 3 digits


def test_usb_validation_rejects_non_hex() -> None:
    with pytest.raises(ValidationError):
        PeripheralsConfig(usb_devices=["040g:6001"])  # 'g' is not hex


# ---------------------------------------------------------------------------
# 10. USB — validation accepts valid
# ---------------------------------------------------------------------------


def test_usb_validation_accepts_valid() -> None:
    cfg = PeripheralsConfig(usb_devices=["0403:6001"])
    assert cfg.usb_devices == ["0403:6001"]


def test_usb_validation_accepts_multiple_devices() -> None:
    cfg = PeripheralsConfig(usb_devices=["0403:6001", "046d:c534"])
    assert len(cfg.usb_devices) == 2


def test_usb_validation_accepts_uppercase_hex() -> None:
    cfg = PeripheralsConfig(usb_devices=["04D8:000A"])
    assert cfg.usb_devices == ["04D8:000A"]


# ---------------------------------------------------------------------------
# 11. libvirt XML — USB fragment
# ---------------------------------------------------------------------------


def test_libvirt_xml_usb_fragment() -> None:
    cfg = PeripheralsConfig(usb_devices=["0403:6001"])
    fragments = cfg.to_libvirt_xml_fragments()
    assert len(fragments) == 1
    xml = fragments[0]
    assert "0x0403" in xml
    assert "0x6001" in xml
    assert 'type="usb"' in xml
    assert 'managed="yes"' in xml
    assert "<vendor" in xml
    assert "<product" in xml


def test_libvirt_xml_no_devices_returns_empty() -> None:
    cfg = PeripheralsConfig()
    assert cfg.to_libvirt_xml_fragments() == []


def test_libvirt_xml_multiple_devices_returns_multiple_fragments() -> None:
    cfg = PeripheralsConfig(usb_devices=["0403:6001", "046d:c534"])
    fragments = cfg.to_libvirt_xml_fragments()
    assert len(fragments) == 2
    assert "0x0403" in fragments[0]
    assert "0x046d" in fragments[1]


# ---------------------------------------------------------------------------
# 12. Loader — missing file returns defaults
# ---------------------------------------------------------------------------


def test_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    cfg = load_peripherals_config(tmp_path / "nonexistent.toml")
    assert cfg == PeripheralsConfig()


def test_load_existing_file_overrides_defaults(tmp_path: Path) -> None:
    toml = tmp_path / "peripherals.toml"
    toml.write_text(
        "audio_enabled = false\n"
        'clipboard_mode = "rich"\n'
        "smartcard_enabled = true\n"
    )
    cfg = load_peripherals_config(toml)
    assert cfg.audio_enabled is False
    assert cfg.clipboard_mode == "rich"
    assert cfg.smartcard_enabled is True
    # Untouched fields keep defaults.
    assert cfg.audio_mode == "playback"
    assert cfg.usb_devices == []


def test_load_usb_devices_from_toml(tmp_path: Path) -> None:
    toml = tmp_path / "peripherals.toml"
    toml.write_text('usb_devices = ["0403:6001", "046d:c534"]\n')
    cfg = load_peripherals_config(toml)
    assert cfg.usb_devices == ["0403:6001", "046d:c534"]


# ---------------------------------------------------------------------------
# Extra validation edge cases
# ---------------------------------------------------------------------------


def test_printer_named_requires_nonempty_name() -> None:
    with pytest.raises(ValidationError):
        PeripheralsConfig(printer_mode="named", printer_name="")


def test_printer_named_with_name_accepted() -> None:
    cfg = PeripheralsConfig(printer_mode="named", printer_name="Brother-HL")
    assert cfg.printer_name == "Brother-HL"


def test_audio_disabled_no_sound_flag() -> None:
    cfg = PeripheralsConfig(audio_enabled=False, clipboard_mode="off")
    flags = cfg.to_freerdp_flags()
    assert not any("sound" in f for f in flags)


def test_microphone_enabled_without_audio() -> None:
    """Explicit microphone_enabled=True should add /microphone even if audio off."""
    cfg = PeripheralsConfig(audio_enabled=False, microphone_enabled=True, clipboard_mode="off")
    flags = cfg.to_freerdp_flags()
    assert "/microphone:sys:pulse" in flags
    assert not any("sound" in f for f in flags)


def test_freerdp_flags_text_clipboard_includes_restriction() -> None:
    cfg = PeripheralsConfig(clipboard_mode="text-only")
    flags = cfg.to_freerdp_flags()
    assert "+clipboard" in flags
    assert "/clipboard-redirect-type:text" in flags


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        PeripheralsConfig(**{"bogus_field": True})  # type: ignore[arg-type]


def test_frozen_blocks_mutation() -> None:
    cfg = PeripheralsConfig()
    with pytest.raises(Exception):
        cfg.audio_enabled = False  # type: ignore[misc]
