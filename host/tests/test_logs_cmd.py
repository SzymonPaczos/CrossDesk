"""Tests for ``crossdesk logs`` CLI subcommand.

All tests are self-contained — no real systemd journal, libvirt daemon,
or FreeRDP installation is required.  External processes (journalctl) and
filesystem paths are patched away so the suite runs on Mac and Linux
developer workstations alike.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crossdesk_host.cli.logs_cmd import (
    _parse_duration,
)
from crossdesk_host.cli.main import main


# ---------------------------------------------------------------------------
# Duration parsing
# ---------------------------------------------------------------------------


def test_parse_duration_minutes() -> None:
    assert _parse_duration("5m") == timedelta(minutes=5)


def test_parse_duration_hours() -> None:
    assert _parse_duration("1h") == timedelta(hours=1)


def test_parse_duration_seconds() -> None:
    assert _parse_duration("30s") == timedelta(seconds=30)


def test_parse_duration_compound() -> None:
    assert _parse_duration("2h30m") == timedelta(hours=2, minutes=30)


def test_parse_duration_invalid() -> None:
    with pytest.raises(ValueError, match="invalid duration"):
        _parse_duration("xyz")


def test_parse_duration_empty() -> None:
    with pytest.raises(ValueError, match="invalid duration"):
        _parse_duration("")


# ---------------------------------------------------------------------------
# Helpers — journalctl mock
# ---------------------------------------------------------------------------


def _make_subprocess_mock(returncode: int = 1, stdout: str = "") -> object:
    """Return a callable that stands in for subprocess.run and returns a
    process-like object with the given exit code and stdout.
    """

    class _FakeResult:
        def __init__(self) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    def _run(*_args: object, **_kwargs: object) -> _FakeResult:
        return _FakeResult()

    return _run


# ---------------------------------------------------------------------------
# Test 1: host logs from file
# ---------------------------------------------------------------------------


def test_host_logs_from_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reads host logs from the JSONL fallback file when journalctl is absent."""
    log_file = tmp_path / "crossdesk-host.jsonl"

    # Use wall-clock time so the cutoff computed inside `run` (datetime.now - 5m)
    # includes the "recent" event and excludes the "old" one.
    now_utc = datetime.now(tz=timezone.utc)
    recent_ts = (now_utc - timedelta(minutes=1)).isoformat()
    old_ts = (now_utc - timedelta(hours=2)).isoformat()

    log_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": recent_ts,
                        "level": "info",
                        "component": "host.ipc.control",
                        "trace_id": "",
                        "span_id": "",
                        "event": "session opened",
                    }
                ),
                json.dumps(
                    {
                        "timestamp": old_ts,
                        "level": "warning",
                        "component": "host.watchdog",
                        "trace_id": "",
                        "span_id": "",
                        "event": "degraded state",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # Patch _host_log_path to return our temp file.
    monkeypatch.setattr(
        "crossdesk_host.cli.logs_cmd._host_log_path",
        lambda: log_file,
    )
    # Make journalctl unavailable so we fall back to the file.
    import subprocess

    monkeypatch.setattr(subprocess, "run", _make_subprocess_mock(returncode=1))

    rc = main(["logs", "--component", "host", "--since", "5m"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "session opened" in out
    # The old line (2 hours ago) should be filtered out by the default --since 5m.
    assert "degraded state" not in out


# ---------------------------------------------------------------------------
# Test 2: libvirt logs from file
# ---------------------------------------------------------------------------


def test_libvirt_logs_from_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reads libvirt plain-text log with leading timestamp prefix."""
    log_file = tmp_path / "crossdesk-vm.log"
    log_file.write_text(
        "2026-05-10 12:34:56.123+0000: VM crossdesk-vm started\n"
        "2026-05-10 12:34:57.456+0000: NBD disk attached\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "crossdesk_host.cli.logs_cmd._libvirt_log_path",
        lambda: log_file,
    )

    # Use a cutoff that includes both lines (well before 2026-05-10 12:34).
    rc = main(["logs", "--component", "libvirt", "--since", "1000h"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "VM crossdesk-vm started" in out
    assert "NBD disk attached" in out
    assert "[LIBVIRT]" in out


# ---------------------------------------------------------------------------
# Test 3: FreeRDP logs from file
# ---------------------------------------------------------------------------


def test_freerdp_logs_from_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reads FreeRDP log from the first discovered candidate path."""
    freerdp_log = tmp_path / "freerdp.log"
    freerdp_log.write_text(
        "[INFO][com.freerdp.client.x11] connected to crossdesk-vm\n"
        "[INFO][com.freerdp.core] negotiation complete\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "crossdesk_host.cli.logs_cmd._freerdp_log_paths",
        lambda: [freerdp_log],
    )

    rc = main(["logs", "--component", "freerdp", "--since", "1000h"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "connected to crossdesk-vm" in out
    assert "[FREERDP]" in out


# ---------------------------------------------------------------------------
# Test 4: --since filter
# ---------------------------------------------------------------------------


def test_since_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Lines older than --since are excluded; recent lines are kept."""
    log_file = tmp_path / "crossdesk-host.jsonl"

    now_utc = datetime.now(tz=timezone.utc)
    ts_recent = (now_utc - timedelta(minutes=2)).isoformat()
    ts_old = (now_utc - timedelta(hours=1)).isoformat()

    log_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": ts_recent,
                        "level": "info",
                        "component": "c",
                        "trace_id": "",
                        "span_id": "",
                        "event": "recent event",
                    }
                ),
                json.dumps(
                    {
                        "timestamp": ts_old,
                        "level": "info",
                        "component": "c",
                        "trace_id": "",
                        "span_id": "",
                        "event": "old event",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "crossdesk_host.cli.logs_cmd._host_log_path",
        lambda: log_file,
    )

    import subprocess

    monkeypatch.setattr(subprocess, "run", _make_subprocess_mock(returncode=1))

    rc = main(["logs", "--component", "host", "--since", "5m"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "recent event" in out
    assert "old event" not in out


# ---------------------------------------------------------------------------
# Test 5: all sources unavailable → exit 0 with warning
# ---------------------------------------------------------------------------


def test_no_sources_available_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When every log source is unavailable the command exits 0 and warns."""
    # Make host log path point to a nonexistent file.
    monkeypatch.setattr(
        "crossdesk_host.cli.logs_cmd._host_log_path",
        lambda: tmp_path / "nonexistent-host.jsonl",
    )
    # Make journalctl fail.
    import subprocess

    monkeypatch.setattr(subprocess, "run", _make_subprocess_mock(returncode=1))
    # Make libvirt log absent.
    monkeypatch.setattr(
        "crossdesk_host.cli.logs_cmd._libvirt_log_path",
        lambda: tmp_path / "nonexistent.log",
    )
    # Make freerdp paths empty.
    monkeypatch.setattr(
        "crossdesk_host.cli.logs_cmd._freerdp_log_paths",
        lambda: [],
    )

    rc = main(["logs", "--component", "all", "--since", "5m"])
    err = capsys.readouterr().err
    assert rc == 0
    # At least one warning about unavailability.
    assert "warning:" in err


# ---------------------------------------------------------------------------
# Test 6: --json output
# ---------------------------------------------------------------------------


def test_json_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--json mode outputs valid JSON per line with a _source field."""
    log_file = tmp_path / "crossdesk-host.jsonl"

    now_utc = datetime.now(tz=timezone.utc)
    ts = (now_utc - timedelta(seconds=30)).isoformat()
    log_file.write_text(
        json.dumps(
            {
                "timestamp": ts,
                "level": "info",
                "component": "c",
                "trace_id": "",
                "span_id": "",
                "event": "json test event",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "crossdesk_host.cli.logs_cmd._host_log_path",
        lambda: log_file,
    )
    import subprocess

    monkeypatch.setattr(subprocess, "run", _make_subprocess_mock(returncode=1))

    rc = main(["logs", "--component", "host", "--since", "5m", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines, "expected at least one JSON line"
    for ln in lines:
        obj = json.loads(ln)  # must be valid JSON
        assert "_source" in obj
        assert obj["_source"] == "host"
        assert obj["event"] == "json test event"


# ---------------------------------------------------------------------------
# Test 7: --component filter
# ---------------------------------------------------------------------------


def test_component_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--component host only shows host lines even when other sources have data."""
    log_file = tmp_path / "crossdesk-host.jsonl"

    now_utc = datetime.now(tz=timezone.utc)
    ts = (now_utc - timedelta(seconds=10)).isoformat()
    log_file.write_text(
        json.dumps(
            {
                "timestamp": ts,
                "level": "info",
                "component": "host.test",
                "trace_id": "",
                "span_id": "",
                "event": "host only event",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # A libvirt file that also exists — should NOT appear in output.
    libvirt_log = tmp_path / "crossdesk-vm.log"
    libvirt_log.write_text(
        "2026-05-10 12:34:56.000+0000: should not appear\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "crossdesk_host.cli.logs_cmd._libvirt_log_path",
        lambda: libvirt_log,
    )
    monkeypatch.setattr(
        "crossdesk_host.cli.logs_cmd._host_log_path",
        lambda: log_file,
    )

    import subprocess

    monkeypatch.setattr(subprocess, "run", _make_subprocess_mock(returncode=1))

    rc = main(["logs", "--component", "host", "--since", "5m"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "host only event" in out
    assert "should not appear" not in out


# ---------------------------------------------------------------------------
# Test 8: guest component exits 0 with not-implemented warning
# ---------------------------------------------------------------------------


def test_guest_component_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--component guest warns and exits 0 (P2 scope, not yet implemented)."""
    rc = main(["logs", "--component", "guest"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "not yet implemented" in err
