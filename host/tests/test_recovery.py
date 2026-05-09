"""Recovery snapshot + diagnostic bundle tests (Phase 9 / Week 37)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from crossdesk_host.recovery import (
    capture_snapshot,
    export_bundle,
    list_snapshots,
    suggest_cause,
)

# ---------------------------------------------------------------------------
# Snapshot capture
# ---------------------------------------------------------------------------


def test_capture_snapshot_writes_json_and_log(tmp_path: Path) -> None:
    target = capture_snapshot(
        fsm_transitions=["HEALTHY→DEGRADED", "DEGRADED→PROBING"],
        rail_apps=["Notepad", "Word"],
        active_mounts=["~/Documents/spec.docx"],
        log_tail=[f"line {i}" for i in range(50)],
        soft_attempts=3,
        final_miss_count=11,
        root=tmp_path,
    )
    assert (target / "snapshot.json").exists()
    assert (target / "log_tail.txt").exists()

    payload = json.loads((target / "snapshot.json").read_text(encoding="utf-8"))
    assert "HEALTHY→DEGRADED" in payload["fsm_transitions"]
    assert "Word" in payload["rail_apps_at_destroy"]
    assert payload["soft_attempts_before_destroy"] == 3
    assert payload["final_miss_count"] == 11


def test_capture_snapshot_truncates_log_tail(tmp_path: Path) -> None:
    capture_snapshot(
        fsm_transitions=[],
        rail_apps=[],
        active_mounts=[],
        log_tail=[f"line {i}" for i in range(5000)],
        soft_attempts=0,
        final_miss_count=0,
        root=tmp_path,
    )
    snapshots = list_snapshots(tmp_path)
    payload = json.loads((snapshots[0] / "snapshot.json").read_text())
    assert len(payload["log_tail"]) == 200  # capped at 200 lines


def test_capture_snapshot_no_tmp_leak(tmp_path: Path) -> None:
    capture_snapshot(
        fsm_transitions=["A"],
        rail_apps=[],
        active_mounts=[],
        log_tail=[],
        soft_attempts=0,
        final_miss_count=0,
        root=tmp_path,
    )
    leftover = list(tmp_path.rglob("*.tmp"))
    assert leftover == []


def test_list_snapshots_returns_newest_first(tmp_path: Path) -> None:
    """Each capture creates a new directory whose name encodes the
    timestamp; sort order should descend by name (== chronologically)."""
    import time

    for _ in range(2):
        capture_snapshot(
            fsm_transitions=[],
            rail_apps=[],
            active_mounts=[],
            log_tail=[],
            soft_attempts=0,
            final_miss_count=0,
            root=tmp_path,
        )
        time.sleep(1.1)  # crude — UTC seconds in filename

    snaps = list_snapshots(tmp_path)
    assert len(snaps) == 2
    assert snaps[0].name > snaps[1].name


def test_list_snapshots_empty_dir(tmp_path: Path) -> None:
    assert list_snapshots(tmp_path / "absent") == []


# ---------------------------------------------------------------------------
# Suggestion heuristic
# ---------------------------------------------------------------------------


def test_suggest_cause_flags_sustained_silence() -> None:
    suggestions = suggest_cause([], soft_attempts=3, final_miss_count=11)
    titles = [s.title for s in suggestions]
    assert any("Sustained heartbeat silence" in t for t in titles)


def test_suggest_cause_flags_gpu_heavy_app() -> None:
    suggestions = suggest_cause(["Photoshop"], soft_attempts=3, final_miss_count=11)
    titles = [s.title for s in suggestions]
    assert any("GPU-heavy" in t for t in titles)


def test_suggest_cause_falls_through_to_inspect_trail() -> None:
    suggestions = suggest_cause(["Notepad"], soft_attempts=0, final_miss_count=0)
    assert any("transition" in s.title.lower() for s in suggestions)


# ---------------------------------------------------------------------------
# Diagnostic bundle export
# ---------------------------------------------------------------------------


def test_export_bundle_creates_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    snap_root = tmp_path / "snap"
    capture_snapshot(
        fsm_transitions=["X→Y"],
        rail_apps=["Notepad"],
        active_mounts=[],
        log_tail=["one", "two"],
        soft_attempts=1,
        final_miss_count=4,
        root=snap_root,
    )

    output = tmp_path / "out"
    bundle_path = export_bundle(snapshot_root=snap_root, output_dir=output)
    assert bundle_path.exists()
    assert zipfile.is_zipfile(bundle_path)

    with zipfile.ZipFile(bundle_path) as zf:
        names = zf.namelist()
        assert any(n.endswith("snapshot.json") for n in names)
        assert "README.txt" in names


def test_export_bundle_redacts_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    from crossdesk_host.installer import credentials

    credentials.save(credentials.VmCredentials("alice", "supersecret"))

    output = tmp_path / "out"
    bundle_path = export_bundle(output_dir=output)

    with zipfile.ZipFile(bundle_path) as zf:
        members = zf.namelist()
        assert "install/vm.toml.redacted" in members
        contents = zf.read("install/vm.toml.redacted").decode("utf-8")
        assert "alice" in contents
        assert "supersecret" not in contents
        assert "REDACTED" in contents


def test_export_bundle_handles_no_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A user who never had HARD_DESTROY can still export a bundle —
    it just skips the recovery/ section."""
    monkeypatch.setenv("HOME", str(tmp_path))
    bundle_path = export_bundle(
        snapshot_root=tmp_path / "absent",
        output_dir=tmp_path / "out",
    )
    assert bundle_path.exists()
    with zipfile.ZipFile(bundle_path) as zf:
        assert "README.txt" in zf.namelist()
