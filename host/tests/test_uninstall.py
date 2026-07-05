"""crossdesk uninstall tests (Week 17)."""

from __future__ import annotations

from pathlib import Path

from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
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


def test_uninstall_tears_down_libvirt_domain(tmp_path: Path) -> None:
    _seed(tmp_path)
    ctl = LibvirtControllerMock()
    report = uninstall(home=tmp_path, libvirt_ctl=ctl)
    assert ctl.hooks.undefine_count == 1
    assert ctl.hooks.undefined is True
    assert any("libvirt_domain" in line for line in report.removed)
    assert not report.failed


def test_dry_run_does_not_touch_the_domain(tmp_path: Path) -> None:
    _seed(tmp_path)
    ctl = LibvirtControllerMock()
    report = uninstall(home=tmp_path, dry_run=True, libvirt_ctl=ctl)
    assert ctl.hooks.undefine_count == 0
    assert any("libvirt_domain: would" in line for line in report.removed)


def test_domain_failure_recorded_but_files_still_removed(tmp_path: Path) -> None:
    # A libvirt error on undefine must not abort the file cleanup — uninstall
    # has to make progress even when the domain teardown fails.
    _seed(tmp_path)
    ctl = LibvirtControllerMock()
    ctl.hooks.fail_next_undefine = True
    report = uninstall(home=tmp_path, libvirt_ctl=ctl)
    assert any("libvirt_domain" in line for line in report.failed)
    assert not (tmp_path / ".local" / "state" / "crossdesk").exists()
    assert not (tmp_path / ".cache" / "crossdesk").exists()


def test_no_controller_skips_domain_silently(tmp_path: Path) -> None:
    # File-only callers (older API) pass no controller: no domain entry, no noise.
    _seed(tmp_path)
    report = uninstall(home=tmp_path)
    assert not any("libvirt_domain" in line for line in report.removed)
    assert not any("libvirt_domain" in line for line in report.skipped)
