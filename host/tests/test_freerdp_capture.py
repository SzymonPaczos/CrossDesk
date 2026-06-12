"""Real RealFreeRDPInvocation capture + reap behaviour.

Pins ``CROSSDESK_FREERDP_BIN`` at a tiny shell script standing in for
xfreerdp, so we exercise the real ``subprocess.Popen`` path: output is
captured to the per-app log, ``wait`` returns the exit code and reaps the
child, and ``read_log_tail`` surfaces the captured error banner.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crossdesk_host.abstractions.freerdp import RailSession
from crossdesk_host.freerdp.real import (
    RealFreeRDPInvocation,
    freerdp_app_log_path,
)


def _fake_freerdp(tmp_path: Path, *, exit_code: int, message: str) -> Path:
    script = tmp_path / "fake-freerdp.sh"
    script.write_text(
        "#!/bin/sh\n"
        f'echo "{message}" 1>&2\n'
        f"exit {exit_code}\n"
    )
    script.chmod(0o755)
    return script


def test_app_log_path_sanitises_label() -> None:
    # A launch-by-path app_id can't escape the logs dir: the safety property
    # is no path separator survives, so the result is one filename in the
    # logs dir (dots are fine inside a filename — they can't traverse).
    p = freerdp_app_log_path("../../etc/passwd")
    assert "/" not in p.name and "\\" not in p.name
    assert p.parent.name == "logs"
    assert p.name.startswith("freerdp-") and p.name.endswith(".log")


def test_empty_label_falls_back() -> None:
    assert freerdp_app_log_path("").name == "freerdp-app.log"


async def test_capture_wait_and_reap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))  # redirect the XDG logs dir
    fake = _fake_freerdp(tmp_path, exit_code=7, message="ERRCONNECT_BOOM")
    monkeypatch.setenv("CROSSDESK_FREERDP_BIN", str(fake))

    inv = RealFreeRDPInvocation()
    session = inv.spawn_rail(["/v:localhost"], log_label="notepad")
    assert session.pid > 0

    returncode = await inv.wait(session)
    assert returncode == 7
    # Reaped: the tracked process is gone, so is_alive is False.
    assert inv.is_alive(session) is False

    # The captured stderr is readable for the exit log line.
    tail = inv.read_log_tail(session)
    assert "ERRCONNECT_BOOM" in tail
    # The capture file lives under the XDG state logs dir.
    assert freerdp_app_log_path("notepad").exists()


async def test_wait_on_unknown_session_returns_zero() -> None:
    inv = RealFreeRDPInvocation()
    assert await inv.wait(RailSession(pid=999999)) == 0


def test_spawn_without_label_does_not_create_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    fake = _fake_freerdp(tmp_path, exit_code=0, message="ok")
    monkeypatch.setenv("CROSSDESK_FREERDP_BIN", str(fake))
    inv = RealFreeRDPInvocation()
    session = inv.spawn_rail(["/v:localhost"])  # no log_label
    inv.terminate(session)  # reap so we don't leak the child
    logs_dir = tmp_path / ".local" / "state" / "crossdesk" / "logs"
    assert not logs_dir.exists() or not any(logs_dir.iterdir())
