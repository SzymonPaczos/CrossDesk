"""crossdesk CLI error-path tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from crossdesk_host.cli.main import main


def test_no_subcommand_errors() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code != 0


def test_unknown_subcommand_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["nonexistent-subcommand"])


def test_vm_without_action_errors() -> None:
    with pytest.raises(SystemExit):
        main(["vm"])


def test_credentials_without_action_errors() -> None:
    with pytest.raises(SystemExit):
        main(["vm", "credentials"])


def test_credentials_show_with_no_file_returns_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Credentials show on a fresh system (no vm.toml) must exit 1
    with a clear message rather than crashing."""
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = main(["vm", "credentials", "show"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "no credentials" in out


def test_credentials_rotate_without_existing_file_returns_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rotate before install — must surface 'run install first' rather
    than silently generating a new credential out of thin air."""
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = main(["vm", "credentials", "rotate"])
    assert rc == 1


def test_credentials_set_writes_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = main(
        ["vm", "credentials", "set", "--username", "alice", "--password", "secret"]
    )
    assert rc == 0
    assert (tmp_path / ".config" / "crossdesk" / "vm.toml").exists()


def test_credentials_show_after_set_prints_username(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    main(["vm", "credentials", "set", "--username", "bob", "--password", "p1"])
    capsys.readouterr()  # drain
    rc = main(["vm", "credentials", "show"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "bob" in out
    assert "p1" in out


def test_credentials_repair_without_file_returns_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = main(["vm", "credentials", "repair"])
    assert rc == 1


def test_install_dry_run_completes_clean_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = main(["install", "--dry-run"])
    assert rc == 0
    assert (tmp_path / ".local" / "state" / "crossdesk" / "install.state.json").exists()


def test_install_dry_run_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Second --dry-run on the same state should report 'already done'
    rather than re-doing the work."""
    monkeypatch.setenv("HOME", str(tmp_path))
    main(["install", "--dry-run"])
    capsys.readouterr()
    rc = main(["install", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "already done" in out or "nothing to do" in out


def test_install_resumes_from_first_unfinished_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mark a few steps as done in advance; install should skip them
    and only attempt the remaining ones."""
    from crossdesk_host.installer import state as state_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    state_path = tmp_path / ".local" / "state" / "crossdesk" / "install.state.json"
    s = state_mod.InstallState()
    s.mark("doctor", "done")
    s.mark("download_iso", "done")
    state_mod.save(s, state_path)

    rc = main(["install", "--dry-run"])
    assert rc == 0
    loaded = state_mod.load(state_path)
    assert loaded.is_done("doctor")
    assert loaded.is_done("download_iso")


def test_uninstall_dry_run_returns_zero_on_clean_system(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = main(["uninstall", "--dry-run"])
    assert rc == 0


def test_uninstall_keep_config_preserves_vm_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    main(["vm", "credentials", "set", "--username", "u", "--password", "p"])
    rc = main(["uninstall", "--keep-config"])
    assert rc == 0
    assert (tmp_path / ".config" / "crossdesk" / "vm.toml").exists()


def test_doctor_does_not_crash_on_missing_kvm(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """On macOS the kvm_device check returns warn rather than crashing
    on the missing /dev/kvm. The whole doctor run must always return
    a clean exit code (0 or 1) and stable output."""
    rc = main(["doctor"])
    assert rc in (0, 1)
    out = capsys.readouterr().out
    assert "kvm_device" in out
