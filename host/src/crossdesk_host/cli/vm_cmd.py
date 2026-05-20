"""``crossdesk vm`` subcommands — ``autostart`` and ``shutdown``.

``autostart`` manages a systemd user unit so the CrossDesk daemon starts
automatically on login. The unit file is written to
``~/.config/systemd/user/crossdesk.service`` and enabled via
``systemctl --user``. On macOS (and other non-systemd systems) the
commands print a clear message and exit 0 — the autostart feature is
Linux-only but the CLI should not crash on development machines.

``shutdown`` performs an ACPI graceful shutdown of the Windows guest,
falling back to a hard destroy on timeout. ``--force`` skips ACPI
entirely. Exit codes: 0 clean shutdown, 2 fell back to hard destroy,
1 libvirt unreachable / other error.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.i18n import _

logger = logging.getLogger(__name__)

_SHUTDOWN_DEFAULT_TIMEOUT_SECONDS = 60
_SHUTDOWN_POLL_INTERVAL_SECONDS = 1.0

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


# ---------------------------------------------------------------------------
# ``crossdesk vm shutdown``
# ---------------------------------------------------------------------------


def add_shutdown_subparser(
    sub: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    """Register ``shutdown`` under ``sub`` (the ``vm`` sub-subparser)."""
    p = sub.add_parser(
        "shutdown",
        help="Gracefully shut down the VM (ACPI, falls back to hard destroy)",
        description=(
            "Send an ACPI shutdown signal to the Windows guest and wait up "
            "to --timeout seconds. If the guest is still running when the "
            "timeout expires, fall back to a forced destroy (exit 2). With "
            "--force, skip ACPI and go straight to destroy."
        ),
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=_SHUTDOWN_DEFAULT_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help=(
            "Seconds to wait for ACPI shutdown before falling back to a "
            f"forced destroy (default {_SHUTDOWN_DEFAULT_TIMEOUT_SECONDS})."
        ),
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Skip ACPI shutdown and immediately destroy the VM.",
    )
    p.add_argument(
        "--domain",
        default="windows-guest",
        metavar="NAME",
        help="Libvirt domain name (default: windows-guest).",
    )


def run_shutdown(
    args: argparse.Namespace,
    *,
    _libvirt_ctl_override: Optional[LibvirtController] = None,
) -> int:
    """Entry point for ``crossdesk vm shutdown``.

    ``_libvirt_ctl_override`` lets tests inject a mock controller without
    going through ``RealLibvirtController`` (which is Linux-only).
    """
    timeout = int(args.timeout)
    if timeout <= 0:
        print(
            _("--timeout must be a positive integer, got {value}").format(
                value=timeout
            )
        )
        return 2

    force = bool(args.force)
    domain_name: str = args.domain

    libvirt_ctl: LibvirtController
    if _libvirt_ctl_override is not None:
        libvirt_ctl = _libvirt_ctl_override
    else:
        # Defer the import so non-Linux dev hosts can still run the CLI's
        # ``--help`` and the tests, which always pass an override.
        try:
            from crossdesk_host.libvirt_ctl.real import RealLibvirtController
        except ImportError as exc:
            print(
                _("libvirt is not available on this host: {err}").format(err=exc)
            )
            return 1
        libvirt_ctl = RealLibvirtController(domain_name=domain_name)

    return asyncio.run(
        _shutdown(libvirt_ctl, timeout=timeout, force=force, domain_name=domain_name)
    )


async def _shutdown(
    libvirt_ctl: LibvirtController,
    *,
    timeout: int,
    force: bool,
    domain_name: str,
) -> int:
    """Drive the shutdown sequence. Returns the process exit code."""
    if force:
        print(
            _(
                "--force: skipping ACPI and destroying {domain}…"
            ).format(domain=domain_name)
        )
        try:
            libvirt_ctl.hard_destroy()
        except RuntimeError as exc:
            print(_("hard destroy failed: {err}").format(err=exc))
            return 1
        return 2

    print(
        _("sending ACPI shutdown to {domain} (timeout {sec}s)…").format(
            domain=domain_name, sec=timeout
        )
    )
    try:
        libvirt_ctl.graceful_shutdown()
    except RuntimeError as exc:
        print(_("graceful shutdown failed: {err}").format(err=exc))
        return 1

    elapsed = 0
    while elapsed < timeout:
        try:
            running = libvirt_ctl.is_running()
        except RuntimeError as exc:
            print(_("status probe failed: {err}").format(err=exc))
            return 1
        if not running:
            print(_("{domain} stopped cleanly").format(domain=domain_name))
            return 0
        await asyncio.sleep(_SHUTDOWN_POLL_INTERVAL_SECONDS)
        elapsed += 1

    logger.warning(
        "graceful shutdown timed out after %ds — falling back to hard destroy",
        timeout,
    )
    print(
        _(
            "{domain} did not stop within {sec}s — falling back to hard destroy"
        ).format(domain=domain_name, sec=timeout)
    )
    try:
        libvirt_ctl.hard_destroy()
    except RuntimeError as exc:
        print(_("hard destroy failed: {err}").format(err=exc))
        return 1
    return 2
