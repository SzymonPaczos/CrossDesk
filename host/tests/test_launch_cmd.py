"""Unit tests for ``crossdesk launch <app-id>``.

All tests run in-process: no D-Bus, no notify-send subprocess, no
daemon socket. External dependencies are replaced by monkeypatching or
by wiring a :class:`RecordingNotifier` directly into ``_launch()``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from crossdesk_host.cli.launch_cmd import _launch, _resolve_display_name
from crossdesk_host.lifecycle.notifications import RecordingNotifier


# ---------------------------------------------------------------------------
# _resolve_display_name
# ---------------------------------------------------------------------------


def test_launch_known_app_returns_friendly_name() -> None:
    """Known app IDs map to their branded display names."""
    assert _resolve_display_name("word") == "Microsoft Word"
    assert _resolve_display_name("excel") == "Microsoft Excel"
    assert _resolve_display_name("notepad") == "Notepad"


def test_launch_unknown_app_fallbacks_to_title_case() -> None:
    """An unrecognised app_id is title-cased as a last resort."""
    assert _resolve_display_name("myapp") == "Myapp"
    assert _resolve_display_name("some-tool") == "Some-Tool"


# ---------------------------------------------------------------------------
# _launch — notification
# ---------------------------------------------------------------------------


def test_launch_sends_notification(tmp_path: Path) -> None:
    """A desktop notification is sent with the correct body before the
    RAIL stub log when the daemon socket exists."""
    sock = tmp_path / "crossdesk-host.sock"
    sock.touch()  # simulate running daemon

    notifier = RecordingNotifier()
    rc = _launch("word", notifier=notifier, _socket_path_override=str(sock))  # type: ignore[arg-type]

    assert rc == 0
    assert len(notifier.calls) == 1
    call = notifier.calls[0]
    assert call.summary == "CrossDesk"
    assert "Microsoft Word" in call.body
    assert "Starting" in call.body


def test_launch_notification_uses_title_case_for_unknown_app(tmp_path: Path) -> None:
    """Unknown app IDs fall back to title-case in the notification body."""
    sock = tmp_path / "crossdesk-host.sock"
    sock.touch()

    notifier = RecordingNotifier()
    rc = _launch("mycoolapp", notifier=notifier, _socket_path_override=str(sock))  # type: ignore[arg-type]

    assert rc == 0
    assert len(notifier.calls) == 1
    assert "Mycoolapp" in notifier.calls[0].body


# ---------------------------------------------------------------------------
# _launch — daemon not running
# ---------------------------------------------------------------------------


def test_launch_daemon_not_running_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When the management socket does not exist, the command exits 1
    and prints an actionable error message to stderr."""
    missing_sock = str(tmp_path / "crossdesk-host.sock")
    notifier = RecordingNotifier()

    rc = _launch("notepad", notifier=notifier, _socket_path_override=missing_sock)  # type: ignore[arg-type]

    assert rc == 1
    # No notification should be sent when the daemon is absent.
    assert notifier.calls == []
    captured = capsys.readouterr()
    assert "crossdesk vm start" in captured.err


def test_launch_daemon_not_running_no_notification(tmp_path: Path) -> None:
    """Absence of the socket suppresses the notification entirely."""
    notifier = RecordingNotifier()
    _launch(
        "excel",
        notifier=notifier,  # type: ignore[arg-type]
        _socket_path_override=str(tmp_path / "missing.sock"),
    )
    assert notifier.calls == []


# ---------------------------------------------------------------------------
# _launch — RAIL stub log
# ---------------------------------------------------------------------------


def test_launch_logs_stub_message(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The Phase 4 RAIL stub produces an INFO log mentioning the app_id."""
    sock = tmp_path / "crossdesk-host.sock"
    sock.touch()

    notifier = RecordingNotifier()
    with caplog.at_level(logging.INFO, logger="crossdesk_host.cli.launch_cmd"):
        _launch("excel", notifier=notifier, _socket_path_override=str(sock))  # type: ignore[arg-type]

    stub_messages = [r.message for r in caplog.records]
    assert any("Phase 4" in msg and "excel" in msg for msg in stub_messages), (
        f"Expected Phase 4 stub log with app_id, got: {stub_messages}"
    )


# ---------------------------------------------------------------------------
# CLI wiring via main()
# ---------------------------------------------------------------------------


def test_launch_subcommand_wired_in_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``crossdesk launch notepad`` reaches ``launch_cmd.run()`` via main.

    With no daemon socket present, exit code is 1 and the actionable
    message appears — proves the subcommand is wired, not silently
    swallowed.
    """
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    # No socket file created → daemon not running path.
    from crossdesk_host.cli.main import main

    rc = main(["launch", "notepad"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "crossdesk vm start" in captured.err
