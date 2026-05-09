"""Keyring abstraction tests (Phase 7 / Week 29)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from crossdesk_host.integrations.keyring import (
    FileKeyring,
    GnomeKeyring,
    KwalletKeyring,
    MockKeyring,
    detect_backend,
)

# ---------------------------------------------------------------------------
# Mock backend
# ---------------------------------------------------------------------------


def test_mock_set_get_round_trip() -> None:
    k = MockKeyring()
    k.set("vm.password", "hunter2")
    assert k.get("vm.password") == "hunter2"


def test_mock_get_missing_returns_none() -> None:
    k = MockKeyring()
    assert k.get("nope") is None


def test_mock_delete_removes() -> None:
    k = MockKeyring()
    k.set("a", "1")
    k.delete("a")
    assert k.get("a") is None


def test_mock_delete_missing_is_noop() -> None:
    MockKeyring().delete("doesnt-exist")


def test_mock_is_available() -> None:
    assert MockKeyring().is_available()


# ---------------------------------------------------------------------------
# File backend
# ---------------------------------------------------------------------------


def test_file_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "keyring.toml"
    k = FileKeyring(target)
    k.set("a", "alpha")
    k.set("b", "beta")
    assert k.get("a") == "alpha"
    assert k.get("b") == "beta"


def test_file_get_missing(tmp_path: Path) -> None:
    k = FileKeyring(tmp_path / "absent.toml")
    assert k.get("anything") is None


def test_file_delete_persists(tmp_path: Path) -> None:
    target = tmp_path / "keyring.toml"
    k = FileKeyring(target)
    k.set("k", "v")
    k.delete("k")
    # Re-open fresh handle to verify the file was rewritten.
    k2 = FileKeyring(target)
    assert k2.get("k") is None


def test_file_set_chmods_0600(tmp_path: Path) -> None:
    target = tmp_path / "keyring.toml"
    FileKeyring(target).set("k", "v")
    if os.name == "posix":
        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o600


def test_file_special_chars_escape(tmp_path: Path) -> None:
    """Quotes + backslashes must round-trip through the TOML serialiser."""
    target = tmp_path / "keyring.toml"
    k = FileKeyring(target)
    raw = 'pass with " quote and \\ slash'
    k.set("tricky", raw)
    assert FileKeyring(target).get("tricky") == raw


def test_file_is_available_always_true(tmp_path: Path) -> None:
    assert FileKeyring(tmp_path / "wherever").is_available()


def test_file_no_tmp_leak_on_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "keyring.toml"
    k = FileKeyring(target)
    for _ in range(10):
        k.set("k", "v")
    leftover = list(tmp_path.glob("keyring.toml.*.tmp"))
    assert leftover == []


# ---------------------------------------------------------------------------
# KWallet / GnomeKeyring smoke (Mac dev: is_available False)
# ---------------------------------------------------------------------------


def test_kwallet_not_available_on_mac() -> None:
    """We're running tests on Mac dev. KWallet binary is absent;
    backend reports unavailable rather than crashing."""
    assert not KwalletKeyring().is_available()


def test_gnome_not_available_on_mac() -> None:
    """secretstorage may be importable but session bus isn't reachable
    from Mac; the backend falls into ``False`` cleanly."""
    assert not GnomeKeyring().is_available()


# ---------------------------------------------------------------------------
# Picker
# ---------------------------------------------------------------------------


def test_detect_backend_returns_file_on_mac(monkeypatch: pytest.MonkeyPatch) -> None:
    """No KDE/GNOME on Mac → picker chooses FileKeyring."""
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    monkeypatch.delenv("DESKTOP_SESSION", raising=False)
    backend = detect_backend()
    assert backend.name == "file"


def test_detect_backend_skips_keyring_when_disabled() -> None:
    backend = detect_backend(prefer_keyring=False)
    assert backend.name == "file"
