"""crossdesk CLI smoke tests.

argparse plumbing only; per-subcommand business logic is covered in
its own test module. These tests guard against regressions where a
subcommand goes silent because its parser was forgotten.
"""

from __future__ import annotations

import pytest

from crossdesk_host.cli.main import main


def test_no_args_errors() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "install" in out and "doctor" in out and "uninstall" in out


def test_doctor_subcommand_runs(capsys: pytest.CaptureFixture[str]) -> None:
    # doctor will return 0 or 1 depending on host; we just want
    # to verify the subcommand wiring is sound.
    rc = main(["doctor"])
    assert rc in (0, 1)
    out = capsys.readouterr().out
    assert "[" in out  # bracketed status glyphs


def test_uninstall_dry_run_runs(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = main(["uninstall", "--dry-run"])
    assert rc == 0


def test_vm_credentials_check_with_missing_file(
    tmp_path, monkeypatch, capsys
) -> None:
    """`vm credentials check` exits 1 when vm.toml is absent and prints
    a remediation hint pointing at install."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "pathlib.Path.home", lambda: tmp_path
    )
    rc = main(["vm", "credentials", "check"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "present:      no" in out
    assert "install" in out


def test_vm_credentials_check_with_healthy_file(
    tmp_path, monkeypatch, capsys
) -> None:
    """Happy path: vm.toml present, parsable, 0600 → check exits 0."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    from crossdesk_host.installer import credentials

    cred_dir = tmp_path / ".config" / "crossdesk"
    cred_dir.mkdir(parents=True)
    credentials.save(credentials.generate(), cred_dir / "vm.toml")

    rc = main(["vm", "credentials", "check"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "status:       OK" in out


def test_doctor_includes_vm_credentials_check(
    tmp_path, monkeypatch, capsys
) -> None:
    """The new check_vm_credentials probe shows up in `crossdesk doctor`
    output (regression guard for the DEFAULT_CHECKS wiring)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    rc = main(["doctor"])
    assert rc in (0, 1)
    out = capsys.readouterr().out
    assert "vm_credentials" in out
