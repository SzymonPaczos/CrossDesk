"""crossdesk uninstall tests (Week 17)."""

from __future__ import annotations

from pathlib import Path

from crossdesk_host.uninstall import uninstall


def _seed(home: Path) -> None:
    (home / ".local" / "share" / "applications").mkdir(parents=True)
    (
        home / ".local" / "share" / "applications" / "crossdesk-notepad.desktop"
    ).write_text("[Desktop Entry]\nName=Notepad\n")
    (home / ".local" / "share" / "applications" / "crossdesk-cmd.desktop").write_text(
        "[Desktop Entry]\nName=cmd\n"
    )
    (home / ".local" / "share" / "applications" / "other.desktop").write_text(
        "[Desktop Entry]\nName=Other\n"
    )
    (home / ".cache" / "crossdesk" / "iso").mkdir(parents=True)
    (home / ".cache" / "crossdesk" / "iso" / "win11.iso").write_text("dummy")
    (home / ".local" / "state" / "crossdesk").mkdir(parents=True)
    (home / ".local" / "state" / "crossdesk" / "install.state.json").write_text("{}")
    (home / ".config" / "crossdesk").mkdir(parents=True)
    (home / ".config" / "crossdesk" / "vm.toml").write_text(
        'username = "x"\npassword = "y"\n'
    )


def test_dry_run_removes_nothing(tmp_path: Path) -> None:
    _seed(tmp_path)
    report = uninstall(home=tmp_path, dry_run=True)
    assert (
        tmp_path / ".local" / "share" / "applications" / "crossdesk-notepad.desktop"
    ).exists()
    assert any("would remove" in line for line in report.removed)


def test_full_uninstall(tmp_path: Path) -> None:
    _seed(tmp_path)
    report = uninstall(home=tmp_path, keep_config=False)
    assert not (tmp_path / ".cache" / "crossdesk").exists()
    assert not (tmp_path / ".local" / "state" / "crossdesk").exists()
    assert not (tmp_path / ".config" / "crossdesk").exists()
    # Other unrelated .desktop file should NOT be removed.
    assert (tmp_path / ".local" / "share" / "applications" / "other.desktop").exists()
    # crossdesk-* are removed.
    assert not (
        tmp_path / ".local" / "share" / "applications" / "crossdesk-notepad.desktop"
    ).exists()
    assert not (
        tmp_path / ".local" / "share" / "applications" / "crossdesk-cmd.desktop"
    ).exists()
    assert not report.failed


def test_keep_config_preserves_vm_toml(tmp_path: Path) -> None:
    _seed(tmp_path)
    uninstall(home=tmp_path, keep_config=True)
    assert (tmp_path / ".config" / "crossdesk" / "vm.toml").exists()


def test_uninstall_without_anything_present_succeeds(tmp_path: Path) -> None:
    """Idempotent: uninstall on a clean tree returns success."""
    report = uninstall(home=tmp_path)
    assert report.failed == []
    # Every step is a "skipped, not present"
    assert all(
        "not present" in entry or entry.startswith("config:")
        for entry in report.skipped
    )
