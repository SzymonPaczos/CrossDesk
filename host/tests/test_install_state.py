"""Install state machine tests (Week 14)."""

from __future__ import annotations

from pathlib import Path

import pytest

from crossdesk_host.installer import state


def test_default_state_has_no_steps() -> None:
    s = state.InstallState()
    assert s.steps == {}
    assert s.first_unfinished() is None


def test_mark_invalid_status_rejected() -> None:
    s = state.InstallState()
    with pytest.raises(ValueError):
        s.mark("step-a", "garbage")


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    s = state.InstallState()
    s.mark("download", "running")
    s.mark("download", "done")
    s.mark("create_domain", "pending")
    s.last_error = "test"

    target = tmp_path / "install.state.json"
    state.save(s, target)
    loaded = state.load(target)
    assert loaded.steps == {"download": "done", "create_domain": "pending"}
    assert loaded.last_error == "test"


def test_load_missing_file_returns_default(tmp_path: Path) -> None:
    s = state.load(tmp_path / "nope.json")
    assert s.steps == {}


def test_first_unfinished_returns_first_pending(tmp_path: Path) -> None:
    s = state.InstallState()
    s.mark("a", "done")
    s.mark("b", "done")
    s.mark("c", "pending")
    s.mark("d", "pending")
    assert s.first_unfinished() == "c"


def test_atomic_write_does_not_leave_tmp_files(tmp_path: Path) -> None:
    target = tmp_path / "install.state.json"
    s = state.InstallState()
    s.mark("a", "done")
    state.save(s, target)
    leftover = list(tmp_path.glob("install.state.json.*.tmp"))
    assert leftover == []


def test_schema_version_mismatch_raises(tmp_path: Path) -> None:
    target = tmp_path / "install.state.json"
    target.write_text('{"schema_version": 999, "steps": {}}', encoding="utf-8")
    with pytest.raises(ValueError):
        state.load(target)
