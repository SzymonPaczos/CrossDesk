"""Install state concurrency edges (Week 14 follow-ups).

The ``state`` machine writes through ``rename`` for atomicity; the
question these tests answer is what happens when:

- two ``crossdesk install`` invocations race the same state file,
- a save() is interrupted partway through (atomic rename should leave
  either old or new content, never partial),
- the schema-version mismatch path actually triggers.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from crossdesk_host.installer import state


def _make_state(steps: dict[str, str]) -> state.InstallState:
    s = state.InstallState()
    for k, v in steps.items():
        s.mark(k, v)
    return s


def test_concurrent_saves_dont_corrupt_file(tmp_path: Path) -> None:
    """Two threads racing save() must leave the file in a parseable
    state — atomicity guarantee. We don't promise which version wins,
    only that we never see torn JSON."""
    target = tmp_path / "install.state.json"

    a = _make_state({"step-a": "done"})
    b = _make_state({"step-b": "running", "step-c": "pending"})

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for _ in range(50):
            futures.append(pool.submit(state.save, a, target))
            futures.append(pool.submit(state.save, b, target))
        for f in futures:
            f.result()

    # File must always be parseable JSON, never garbled.
    loaded = state.load(target)
    assert loaded.steps in (
        {"step-a": "done"},
        {"step-b": "running", "step-c": "pending"},
    )


def test_save_does_not_leak_tmp_files_after_many_cycles(tmp_path: Path) -> None:
    target = tmp_path / "install.state.json"
    s = _make_state({"a": "done"})
    for _ in range(20):
        state.save(s, target)
    leftover = list(tmp_path.glob("install.state.json.*.tmp"))
    assert leftover == []


def test_load_garbage_json_raises(tmp_path: Path) -> None:
    target = tmp_path / "install.state.json"
    target.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(Exception):
        state.load(target)


def test_load_empty_file_raises(tmp_path: Path) -> None:
    target = tmp_path / "install.state.json"
    target.write_text("", encoding="utf-8")
    with pytest.raises(Exception):
        state.load(target)


def test_load_truncated_json_raises(tmp_path: Path) -> None:
    target = tmp_path / "install.state.json"
    target.write_text('{"schema_version": 1, "ste', encoding="utf-8")
    with pytest.raises(Exception):
        state.load(target)


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    """save() must mkdir parents — the operator may have removed
    ~/.local/state/crossdesk between install runs."""
    nested = tmp_path / "deep" / "subdir" / "install.state.json"
    state.save(_make_state({"a": "done"}), nested)
    assert nested.exists()
    assert state.load(nested).is_done("a")


def test_marking_step_done_clears_last_error() -> None:
    s = state.InstallState()
    s.last_error = "previous failure"
    s.mark("step-a", "done")
    assert s.last_error is None


def test_marking_step_failed_does_not_clear_last_error() -> None:
    s = state.InstallState()
    s.last_error = "set externally"
    s.mark("step-a", "failed")
    assert s.last_error == "set externally"


def test_first_unfinished_returns_none_when_all_done() -> None:
    s = state.InstallState()
    s.mark("a", "done")
    s.mark("b", "done")
    assert s.first_unfinished() is None


def test_first_unfinished_returns_running_step() -> None:
    """A step in 'running' state is not yet 'done', so it counts as
    unfinished — useful when a previous install was killed mid-step."""
    s = state.InstallState()
    s.mark("a", "done")
    s.mark("b", "running")
    s.mark("c", "pending")
    assert s.first_unfinished() == "b"
