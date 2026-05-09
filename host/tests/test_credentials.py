"""VM credential tests (Week 15)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from crossdesk_host.installer import credentials


def test_generate_produces_strong_password() -> None:
    c = credentials.generate()
    assert c.username == "crossdesk"
    assert len(c.password) == 20
    assert c.password != credentials.generate().password  # different each call


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "vm.toml"
    creds = credentials.VmCredentials(username="alice", password='p"a"s"s')
    credentials.save(creds, target)
    loaded = credentials.load(target)
    assert loaded == creds


def test_save_sets_0600_permissions(tmp_path: Path) -> None:
    target = tmp_path / "vm.toml"
    credentials.save(credentials.generate(), target)
    if os.name == "posix":
        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o600


def test_load_missing_file_returns_none(tmp_path: Path) -> None:
    assert credentials.load(tmp_path / "nope.toml") is None


def test_load_malformed_raises(tmp_path: Path) -> None:
    target = tmp_path / "vm.toml"
    target.write_text("garbage =")
    with pytest.raises(Exception):
        credentials.load(target)


def test_save_does_not_leave_tmp(tmp_path: Path) -> None:
    target = tmp_path / "vm.toml"
    credentials.save(credentials.generate(), target)
    leftover = list(tmp_path.glob("vm.toml.*.tmp"))
    assert leftover == []
