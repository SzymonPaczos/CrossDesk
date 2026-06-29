"""Tests for the opt-in crash reporter (``observability/crash_reporter``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from crossdesk_host.observability import crash_reporter
from crossdesk_host.observability.crash_reporter import (
    build_crash_report,
    report_exception,
    write_crash_report,
)

_TS = "2026-06-29T10:00:00+00:00"


def _captured(exc: BaseException) -> BaseException:
    """Return ``exc`` with a real ``__traceback__`` attached."""
    try:
        raise exc
    except BaseException as caught:  # noqa: BLE001 - we want the live traceback
        return caught


def test_build_crash_report_captures_type_message_and_traceback() -> None:
    report = build_crash_report(
        _captured(ValueError("boom happened")),
        component="host.cli",
        command=["crossdesk", "launch", "notepad"],
        host_version="0.1.0",
        timestamp=_TS,
    )
    assert report.exception_type == "ValueError"
    assert "boom happened" in report.exception_message
    assert report.command == "crossdesk launch notepad"
    assert report.host_version == "0.1.0"
    assert any("ValueError" in line for line in report.traceback)
    assert json.loads(report.to_json())["exception_type"] == "ValueError"


def test_build_crash_report_redacts_sensitive_message() -> None:
    report = build_crash_report(
        _captured(RuntimeError("login failed: password=hunter2")),
        component="host.cli",
        command=["crossdesk"],
        host_version="0.1.0",
        timestamp=_TS,
    )
    assert "hunter2" not in report.exception_message
    assert "redacted" in report.exception_message
    assert all("hunter2" not in line for line in report.traceback)


def test_report_exception_disabled_returns_none(tmp_path: Path) -> None:
    out = report_exception(
        _captured(ValueError("x")),
        component="host.cli",
        command=["crossdesk"],
        host_version="0.1.0",
        enabled=False,
        report_dir=tmp_path / "crash-reports",
    )
    assert out is None
    assert not (tmp_path / "crash-reports").exists()


def test_report_exception_enabled_writes_file(tmp_path: Path) -> None:
    report_dir = tmp_path / "crash-reports"
    out = report_exception(
        _captured(ValueError("kaboom")),
        component="host.cli",
        command=["crossdesk", "doctor"],
        host_version="0.1.0",
        enabled=True,
        report_dir=report_dir,
        timestamp=_TS,
    )
    assert out is not None
    assert out.exists()
    assert out.parent == report_dir
    payload = json.loads(out.read_text())
    assert payload["exception_type"] == "ValueError"
    assert "kaboom" in payload["exception_message"]
    assert payload["command"] == "crossdesk doctor"


def test_report_exception_swallows_write_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_a: Any, **_k: Any) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(crash_reporter, "write_crash_report", _boom)
    out = report_exception(
        _captured(ValueError("x")),
        component="host.cli",
        command=["crossdesk"],
        host_version="0.1.0",
        enabled=True,
        report_dir=tmp_path / "crash-reports",
    )
    assert out is None  # swallowed, not raised


def test_write_crash_report_unique_filenames(tmp_path: Path) -> None:
    report = build_crash_report(
        _captured(ValueError("x")),
        component="host.cli",
        command=["crossdesk"],
        host_version="0.1.0",
        timestamp=_TS,
    )
    p1 = write_crash_report(report, tmp_path)
    p2 = write_crash_report(report, tmp_path)
    assert p1 != p2  # the random suffix prevents same-second collisions
    assert p1.exists() and p2.exists()
