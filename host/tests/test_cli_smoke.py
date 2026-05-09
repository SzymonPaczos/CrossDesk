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
