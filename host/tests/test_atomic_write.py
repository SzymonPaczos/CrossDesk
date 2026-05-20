"""Unit tests for crossdesk_host.utils.atomic_write."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from crossdesk_host.utils.atomic_write import atomic_write


def test_writes_payload(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "dir" / "file.txt"
    atomic_write(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "dir" / "x.json"
    atomic_write(target, "{}")
    assert target.parent.is_dir()


def test_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("old", encoding="utf-8")
    atomic_write(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_unicode_round_trip(tmp_path: Path) -> None:
    payload = 'name = "Zażółć gęślą jaźń"\n'
    target = tmp_path / "polish.toml"
    atomic_write(target, payload)
    assert target.read_text(encoding="utf-8") == payload


def test_temp_file_cleaned_up_on_write_failure(tmp_path: Path) -> None:
    target = tmp_path / "doomed.txt"
    # Force os.rename to fail mid-write; atomic_write must clean up
    # the temp file and re-raise.
    real_rename = os.rename

    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("simulated rename failure")

    with patch("crossdesk_host.utils.atomic_write.os.rename", side_effect=boom):
        with pytest.raises(OSError, match="simulated rename failure"):
            atomic_write(target, "anything")

    # The target was never created, and no stray .tmp file remains in
    # the parent directory.
    assert not target.exists()
    leftovers = list(target.parent.glob(f"{target.name}.*.tmp"))
    assert leftovers == [], f"orphan temp file(s): {leftovers}"

    # Restore in case other tests look at os.rename — patch.context above
    # already restored it, this is belt-and-braces.
    assert os.rename is real_rename


def test_atomic_swap_does_not_leak_partial(tmp_path: Path) -> None:
    """Sanity: between rename atomicity and fsync, an interrupted writer
    leaves either the original file or the full new payload — never a
    partial. We can't easily simulate a power loss, but we can verify
    that after a successful write, only the target file exists (no
    stray tmp)."""
    target = tmp_path / "config.json"
    atomic_write(target, '{"k": "v"}')
    siblings = sorted(p.name for p in tmp_path.iterdir())
    assert siblings == ["config.json"], f"unexpected leftovers: {siblings}"
