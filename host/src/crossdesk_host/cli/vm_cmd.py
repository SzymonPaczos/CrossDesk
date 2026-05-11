"""``crossdesk vm autostart`` subcommands.

Manages a systemd user unit so the CrossDesk daemon starts automatically
on login. The unit file is written to ``~/.config/systemd/user/crossdesk.service``
and enabled via ``systemctl --user``.

On macOS (and other non-systemd systems) the commands print a clear message
and exit 0 — the autostart feature is Linux-only but the CLI should not
crash on development machines.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from crossdesk_host.i18n import _

_UNIT_NAME = "crossdesk.service"
_UNIT_CONTENT = """\
[Unit]
Description=CrossDesk Windows VM daemon
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/env crossdesk daemon start
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def _unit_path() -> Path:
    """``~/.config/systemd/user/crossdesk.service`` — resolved at call time
    so tests that monkey-patch ``HOME`` see the redirected path."""
    return Path.home() / ".config" / "systemd" / "user" / _UNIT_NAME


def _systemctl_available() -> bool:
    return shutil.which("systemctl") is not None


def add_autostart_subparser(
    sub: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    """Register ``autostart enable`` and ``autostart disable`` under ``sub``."""
    p = sub.add_parser("autostart", help="Manage VM daemon autostart on login")
    asp = p.add_subparsers(dest="autostart_action", required=True)
    asp.add_parser("enable", help="Install and enable the systemd user unit")
    asp.add_parser("disable", help="Disable and remove the systemd user unit")


def run_autostart(args: argparse.Namespace) -> int:
    action: str = args.autostart_action
    if action == "enable":
        return _run_enable()
    if action == "disable":
        return _run_disable()
    print(_("unknown autostart action: {action!r}").format(action=action))
    return 2


def _run_enable() -> int:
    if not _systemctl_available():
        print(
            _(
                "systemd not available — autostart is Linux-only; "
                "no unit file written"
            )
        )
        return 0

    unit_path = _unit_path()
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(_UNIT_CONTENT, encoding="utf-8")
    print(_("unit file written to {path}").format(path=unit_path))

    try:
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            timeout=10,
        )
        subprocess.run(
            ["systemctl", "--user", "enable", _UNIT_NAME],
            check=True,
            timeout=10,
        )
        print(_("crossdesk.service enabled — will start on next login"))
    except subprocess.CalledProcessError as exc:
        print(
            _("systemctl failed (exit {code}): {err}").format(
                code=exc.returncode, err=exc.stderr or ""
            )
        )
        return 1

    return 0


def _run_disable() -> int:
    if not _systemctl_available():
        print(
            _(
                "systemd not available — autostart is Linux-only; "
                "nothing to disable"
            )
        )
        return 0

    try:
        subprocess.run(
            ["systemctl", "--user", "disable", _UNIT_NAME],
            check=True,
            timeout=10,
        )
        print(_("crossdesk.service disabled"))
    except subprocess.CalledProcessError as exc:
        # Unit may not be enabled — that's fine; still remove the file.
        print(
            _("systemctl disable exited {code} — removing unit file anyway").format(
                code=exc.returncode
            )
        )

    unit_path = _unit_path()
    if unit_path.exists():
        unit_path.unlink()
        print(_("unit file removed from {path}").format(path=unit_path))
    else:
        print(_("unit file not present at {path}").format(path=unit_path))

    return 0
