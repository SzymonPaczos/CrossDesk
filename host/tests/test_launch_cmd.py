"""Unit tests for ``crossdesk launch <app-id>``.

All tests run in-process: no D-Bus, no notify-send subprocess, no
daemon socket. External dependencies are replaced by monkeypatching or
by wiring a :class:`RecordingNotifier` directly into ``_launch()``.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, List

import pytest

from crossdesk_host.cli import launch_cmd
from crossdesk_host.cli.launch_cmd import _launch, _resolve_display_name
from crossdesk_host.lifecycle.notifications import RecordingNotifier


def _patch_gui_helpers(
    monkeypatch: pytest.MonkeyPatch,
    *,
    already_running: bool,
    spawn_succeeds: bool = True,
) -> List[List[str]]:
    """Stub the two helpers used on the daemon-down branch.

    Returns a list that gets appended to every time _spawn_gui would
    have launched a subprocess. Lets tests assert "no spawn" by
    checking the list is empty.
    """
    spawns: List[List[str]] = []
    monkeypatch.setattr(launch_cmd, "_gui_is_running", lambda: already_running)

    def fake_spawn() -> bool:
        if spawn_succeeds:
            spawns.append(["crossdesk-gui"])
            return True
        return False

    monkeypatch.setattr(launch_cmd, "_spawn_gui", fake_spawn)
    return spawns

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


def test_launch_daemon_not_running_exits_1_and_prints_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the management socket does not exist, the command exits 1
    and prints an actionable error message to stderr.

    Behavior changed 2026-05-20: previously fired notify_vm_failed_to_start
    which spammed Dolphin / ms-word:// invocations. Now it opens the
    GUI instead (one window > N notifications)."""
    spawns = _patch_gui_helpers(monkeypatch, already_running=False)
    missing_sock = str(tmp_path / "crossdesk-host.sock")
    notifier = RecordingNotifier()

    rc = _launch("notepad", notifier=notifier, _socket_path_override=missing_sock)  # type: ignore[arg-type]

    assert rc == 1
    captured = capsys.readouterr()
    assert "crossdesk vm start" in captured.err
    # No desktop notification — the GUI window IS the user-visible signal.
    assert notifier.calls == []
    # GUI was spawned (no instance running).
    assert spawns == [["crossdesk-gui"]]


def test_launch_daemon_not_running_does_not_spawn_when_gui_already_running(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Idempotence: repeated Dolphin / URL-handler invocations must not
    pile up duplicate GUI windows. pgrep finds the existing instance →
    we do nothing extra."""
    spawns = _patch_gui_helpers(monkeypatch, already_running=True)
    notifier = RecordingNotifier()

    rc = _launch(
        "excel",
        notifier=notifier,  # type: ignore[arg-type]
        _socket_path_override=str(tmp_path / "missing.sock"),
    )

    assert rc == 1
    assert notifier.calls == []
    assert spawns == []  # GUI already up → no second spawn
    # Stderr message still goes out so terminal users get a hint.
    assert "crossdesk vm start" in capsys.readouterr().err


def test_launch_daemon_not_running_handles_missing_gui_binary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """If crossdesk-gui isn't installed, the spawn helper silently
    returns False and the CLI still exits 1 cleanly. Users still see
    the stderr hint, just no GUI fallback."""
    spawns = _patch_gui_helpers(
        monkeypatch, already_running=False, spawn_succeeds=False
    )
    notifier = RecordingNotifier()

    rc = _launch(
        "word",
        notifier=notifier,  # type: ignore[arg-type]
        _socket_path_override=str(tmp_path / "missing.sock"),
    )

    assert rc == 1
    assert notifier.calls == []
    assert spawns == []  # spawn was attempted but returned False
    assert "crossdesk vm start" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# _gui_is_running / _spawn_gui — direct coverage of the helpers
# ---------------------------------------------------------------------------


def test_gui_is_running_returns_false_when_pgrep_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No pgrep on PATH → return False so the caller still spawns the GUI."""
    monkeypatch.setattr(launch_cmd.shutil, "which", lambda name: None)
    assert launch_cmd._gui_is_running() is False


def test_gui_is_running_true_when_pgrep_exit_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pgrep exit 0 = match found = GUI already running."""
    monkeypatch.setattr(launch_cmd.shutil, "which", lambda name: "/usr/bin/pgrep")

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=b"123\n")

    monkeypatch.setattr(launch_cmd.subprocess, "run", fake_run)
    assert launch_cmd._gui_is_running() is True


def test_gui_is_running_false_when_pgrep_exit_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pgrep exit 1 = no match = caller should spawn."""
    monkeypatch.setattr(launch_cmd.shutil, "which", lambda name: "/usr/bin/pgrep")

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout=b"")

    monkeypatch.setattr(launch_cmd.subprocess, "run", fake_run)
    assert launch_cmd._gui_is_running() is False


def test_spawn_gui_returns_false_when_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """shutil.which returns None → no Popen attempt, return False."""
    monkeypatch.setattr(launch_cmd.shutil, "which", lambda name: None)
    popen_calls: List[Any] = []
    monkeypatch.setattr(
        launch_cmd.subprocess, "Popen", lambda *a, **kw: popen_calls.append((a, kw))
    )
    assert launch_cmd._spawn_gui() is False
    assert popen_calls == []


def test_spawn_gui_returns_true_when_binary_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Binary present → Popen invoked with detached session."""
    monkeypatch.setattr(launch_cmd.shutil, "which", lambda name: "/usr/bin/crossdesk-gui")
    popen_calls: List[Any] = []

    def fake_popen(*args: Any, **kwargs: Any) -> object:
        popen_calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(launch_cmd.subprocess, "Popen", fake_popen)
    assert launch_cmd._spawn_gui() is True
    assert len(popen_calls) == 1
    # Detached: start_new_session=True so child outlives the CLI process.
    assert popen_calls[0][1].get("start_new_session") is True


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
    # Stub GUI-spawn helpers so this test doesn't fork a real
    # crossdesk-gui process (or attempt to).
    _patch_gui_helpers(monkeypatch, already_running=True)
    # No socket file created → daemon not running path.
    from crossdesk_host.cli.main import main

    rc = main(["launch", "notepad"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "crossdesk vm start" in captured.err
