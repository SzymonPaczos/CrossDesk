"""Tests for the CLI last-resort exception handler (``cli/main.py``)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from crossdesk_host.cli import main as cli_main


def _raise_runtime(_args: argparse.Namespace) -> int:
    raise RuntimeError("simulated failure")


def _raise_interrupt(_args: argparse.Namespace) -> int:
    raise KeyboardInterrupt


def test_unhandled_exception_returns_2_and_friendly_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CROSSDESK_DEBUG", raising=False)
    monkeypatch.setattr(cli_main.version_cmd, "run", _raise_runtime)

    rc = cli_main.main(["version"])

    assert rc == 2
    err = capsys.readouterr().err
    assert "unexpected error" in err
    assert "RuntimeError: simulated failure" in err
    # The whole point: no raw Python traceback reaches the user.
    assert "Traceback (most recent call last)" not in err


def test_crash_report_written_when_enabled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CROSSDESK_CONFIG__OBSERVABILITY__CRASH_REPORT_ENABLED", "true")
    monkeypatch.delenv("CROSSDESK_DEBUG", raising=False)
    monkeypatch.setattr(cli_main.version_cmd, "run", _raise_runtime)

    rc = cli_main.main(["version"])

    assert rc == 2
    reports = list(
        (tmp_path / ".local/state/crossdesk/crash-reports").glob("crash-*.json")
    )
    assert len(reports) == 1
    payload = json.loads(reports[0].read_text())
    assert payload["exception_type"] == "RuntimeError"
    assert payload["component"] == "host.cli"
    assert "crash report written" in capsys.readouterr().err


def test_no_crash_report_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CROSSDESK_CONFIG__OBSERVABILITY__CRASH_REPORT_ENABLED", raising=False)
    monkeypatch.delenv("CROSSDESK_DEBUG", raising=False)
    monkeypatch.setattr(cli_main.version_cmd, "run", _raise_runtime)

    rc = cli_main.main(["version"])

    assert rc == 2
    assert not (tmp_path / ".local/state/crossdesk/crash-reports").exists()
    # Default OFF surfaces the opt-in tip instead of a report path.
    assert "CRASH_REPORT_ENABLED" in capsys.readouterr().err


def test_debug_env_reraises_for_developers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CROSSDESK_DEBUG", "1")
    monkeypatch.setattr(cli_main.version_cmd, "run", _raise_runtime)

    with pytest.raises(RuntimeError, match="simulated failure"):
        cli_main.main(["version"])


def test_exception_message_sanitized_for_terminal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CROSSDESK_DEBUG", raising=False)

    def _boom(_args: argparse.Namespace) -> int:
        raise RuntimeError("line one\nline two\x1b[31mred\x1b[0m")

    monkeypatch.setattr(cli_main.version_cmd, "run", _boom)
    rc = cli_main.main(["version"])

    assert rc == 2
    err = capsys.readouterr().err
    # No raw ESC reaches the terminal, and the newline is collapsed so the
    # crafted message can't reflow or escape-sequence the error output.
    assert "\x1b" not in err
    what_lines = [ln for ln in err.splitlines() if ln.startswith("  what:")]
    assert len(what_lines) == 1
    assert "line one | line two" in what_lines[0]


def test_keyboard_interrupt_returns_130(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(cli_main.version_cmd, "run", _raise_interrupt)

    rc = cli_main.main(["version"])

    assert rc == 130
    assert "interrupted" in capsys.readouterr().err
