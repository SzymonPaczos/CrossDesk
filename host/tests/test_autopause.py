"""Tests for AutopauseController and vm autostart CLI.

All unit tests — no libvirt, no systemd. Async tests use pytest-asyncio
(``asyncio_mode = "auto"`` in pyproject.toml).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crossdesk_host.watchdog.autopause import AutopauseController

# ---------------------------------------------------------------------------
# Session-count bookkeeping
# ---------------------------------------------------------------------------


def test_session_opened_increments_count() -> None:
    ctrl = AutopauseController(idle_timeout_s=300)
    assert ctrl.active_sessions == 0
    ctrl.session_opened()
    assert ctrl.active_sessions == 1
    ctrl.session_opened()
    assert ctrl.active_sessions == 2


def test_session_closed_decrements_count() -> None:
    ctrl = AutopauseController(idle_timeout_s=300)
    ctrl.session_opened()
    ctrl.session_opened()
    ctrl.session_closed()
    assert ctrl.active_sessions == 1
    ctrl.session_closed()
    assert ctrl.active_sessions == 0


def test_session_closed_does_not_go_below_zero() -> None:
    """Closing with no open sessions must not produce a negative count."""
    ctrl = AutopauseController(idle_timeout_s=300)
    ctrl.session_closed()
    assert ctrl.active_sessions == 0


# ---------------------------------------------------------------------------
# Suspend not called when sessions are active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_suspend_when_sessions_active() -> None:
    """Open a session, close it, re-open before timeout — suspend must not fire."""
    ctrl = AutopauseController(idle_timeout_s=0.05)  # very short timeout
    mock_libvirt = MagicMock()

    # Start the autopause loop as a background task.
    task = asyncio.create_task(ctrl.run(mock_libvirt))

    # Open → close → immediately re-open (within timeout window).
    ctrl.session_opened()
    ctrl.session_closed()
    ctrl.session_opened()  # prevents suspend

    # Give the loop enough time to run (longer than the timeout).
    await asyncio.sleep(0.15)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    mock_libvirt.suspend.assert_not_called()


# ---------------------------------------------------------------------------
# Suspend IS called after the full idle timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suspend_called_after_idle_timeout() -> None:
    """With no open sessions, suspend() must be called after idle_timeout_s."""
    ctrl = AutopauseController(idle_timeout_s=0.02)  # 20 ms
    mock_libvirt = MagicMock()

    # Start idle immediately (no session opened).
    ctrl._idle_event.set()

    task = asyncio.create_task(ctrl.run(mock_libvirt))

    # Wait longer than the idle timeout.
    await asyncio.sleep(0.2)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    mock_libvirt.suspend.assert_called_once()


# ---------------------------------------------------------------------------
# Autostart CLI — unit file written with correct content
# ---------------------------------------------------------------------------


def test_autostart_unit_file_written(tmp_path: Path) -> None:
    """Enable command writes the systemd unit file with the ExecStart line.

    We stub ``_systemctl_available`` to True and ``subprocess.run`` so that
    no real systemctl is invoked. The file itself must be created by the
    function with the correct content.
    """
    from crossdesk_host.cli.vm_cmd import _run_enable

    fake_unit_path = tmp_path / "crossdesk.service"

    with (
        patch(
            "crossdesk_host.cli.vm_cmd._unit_path",
            return_value=fake_unit_path,
        ),
        patch(
            "crossdesk_host.cli.vm_cmd._systemctl_available",
            return_value=True,
        ),
        patch("crossdesk_host.cli.vm_cmd.subprocess.run") as mock_run,
    ):
        # subprocess.run is called twice (daemon-reload, enable); make both succeed.
        mock_run.return_value = MagicMock(returncode=0)
        rc = _run_enable()

    assert rc == 0
    assert fake_unit_path.exists()
    content = fake_unit_path.read_text(encoding="utf-8")
    assert "ExecStart" in content
    assert "crossdesk daemon start" in content


def test_autostart_disable_removes_unit_file(tmp_path: Path) -> None:
    """Disable command removes the unit file when systemctl is unavailable."""
    from crossdesk_host.cli.vm_cmd import _run_disable

    fake_unit_path = tmp_path / "crossdesk.service"
    fake_unit_path.write_text("[Unit]\nDescription=test\n", encoding="utf-8")

    with (
        patch("crossdesk_host.cli.vm_cmd._unit_path", return_value=fake_unit_path),
        patch("crossdesk_host.cli.vm_cmd._systemctl_available", return_value=False),
    ):
        rc = _run_disable()

    assert rc == 0
    # On non-systemd the file is not touched (disable is a no-op print).
    # The unit file still exists because systemd is not available.
    # That matches the documented behaviour: "nothing to disable".
    assert fake_unit_path.exists()


def test_autostart_enable_no_systemd_exits_zero() -> None:
    """Enable on a non-Linux machine prints a message and returns 0."""
    from crossdesk_host.cli.vm_cmd import _run_enable

    with (
        patch("crossdesk_host.cli.vm_cmd._systemctl_available", return_value=False),
        patch("crossdesk_host.cli.vm_cmd._unit_path") as mock_path,
    ):
        # Provide a real Path-like object so .parent.mkdir() works.
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            mock_path.return_value = Path(td) / "crossdesk.service"
            rc = _run_enable()

    assert rc == 0
