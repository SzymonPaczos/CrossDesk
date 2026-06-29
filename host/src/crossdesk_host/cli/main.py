"""``crossdesk`` CLI entry point.

Subcommands:
- ``install``       — orchestrate VM bring-up
- ``apps``          — list catalog apps or install a .desktop entry
- ``launch <app>``  — launch a Windows app as a RAIL window
- ``vm credentials`` — show / rotate / set / repair VM password
- ``vm autostart``   — enable/disable systemd user unit for autostart
- ``vm shutdown``    — ACPI shutdown with hard-destroy fallback
- ``doctor``        — pre-flight checks
- ``metrics``       — print daemon metrics snapshot
- ``logs``          — aggregate and display log streams
- ``version``       — show host, agent, and protocol version
- ``uninstall``     — clean removal

The daemon (``crossdesk-host``) is a separate binary; this CLI is for
imperative one-shot operations. Subcommand handlers live in sibling
modules to keep ``main.py`` thin.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import List, Optional

from crossdesk_host.cli import (
    apps_cmd,
    config_cmd,
    credentials_cmd,
    doctor_cmd,
    install_cmd,
    launch_cmd,
    logs_cmd,
    metrics_cmd,
    uninstall_cmd,
    version_cmd,
    vm_cmd,
)
from crossdesk_host.i18n import _


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crossdesk",
        description="Run Windows applications as native Linux windows.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    install_cmd.add_subparser(sub)
    apps_cmd.add_subparser(sub)
    launch_cmd.add_subparser(sub)
    config_cmd.add_subparser(sub)

    vm = sub.add_parser("vm", help="VM lifecycle commands")
    vm_sub = vm.add_subparsers(dest="vm_command", required=True)
    credentials_cmd.add_subparser(vm_sub)
    vm_cmd.add_autostart_subparser(vm_sub)
    vm_cmd.add_shutdown_subparser(vm_sub)

    doctor_cmd.add_subparser(sub)
    logs_cmd.add_subparser(sub)
    metrics_cmd.add_subparser(sub)
    version_cmd.add_subparser(sub)
    uninstall_cmd.add_subparser(sub)

    return parser


def _dispatch(args: argparse.Namespace) -> int:
    """Route parsed ``args`` to the owning subcommand handler.

    Subparsers are ``required=True`` so an unknown top-level command
    can't reach the trailing ``return`` — it's there to keep mypy happy.
    """
    if args.command == "install":
        return install_cmd.run(args)
    if args.command == "apps":
        return apps_cmd.run(args)
    if args.command == "launch":
        return launch_cmd.run(args)
    if args.command == "config":
        return config_cmd.run(args)
    if args.command == "vm":
        if args.vm_command == "credentials":
            return credentials_cmd.run(args)
        if args.vm_command == "autostart":
            return vm_cmd.run_autostart(args)
        if args.vm_command == "shutdown":
            return vm_cmd.run_shutdown(args)
    if args.command == "doctor":
        return doctor_cmd.run(args)
    if args.command == "logs":
        return logs_cmd.run(args)
    if args.command == "metrics":
        return metrics_cmd.run(args)
    if args.command == "version":
        return version_cmd.run(args)
    if args.command == "uninstall":
        return uninstall_cmd.run(args)

    return 2  # unreachable (subparsers are required)


# Control characters (ANSI escapes, raw newlines) in an exception message
# must never reach the terminal verbatim: a crafted message could reflow the
# error output or inject escape sequences. Collapse newlines to a visible
# separator and drop the rest before printing the summary.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_for_terminal(text: str) -> str:
    return _CONTROL_CHARS.sub(" ", text.replace("\n", " | "))


def _handle_unexpected(exc: Exception, argv: Optional[List[str]]) -> int:
    """Last-resort handler: turn an unhandled exception into a friendly,
    actionable message (never a raw traceback) and exit 2.

    Opt-in (default OFF), it also writes a redacted crash-report file the
    user can attach to a bug report. ``CROSSDESK_DEBUG=1`` re-raises the
    original so a developer still gets the full traceback.
    """
    if os.environ.get("CROSSDESK_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
        raise exc

    # Lazy imports keep the happy path's import cost unchanged.
    from crossdesk_host.observability import mask_sensitive, report_exception

    report_path = None
    enabled = False
    try:
        from crossdesk_host.config import load_from_toml

        cfg = load_from_toml()
        enabled = cfg.observability.crash_report_enabled
        report_path = report_exception(
            exc,
            component="host.cli",
            command=["crossdesk", *(argv if argv is not None else sys.argv[1:])],
            host_version=cfg.daemon.host_version,
            enabled=enabled,
            report_dir=cfg.paths.state_dir / "crash-reports",
        )
    except Exception:  # noqa: BLE001 - reporting must never mask the real error
        pass

    summary = _sanitize_for_terminal(mask_sensitive(f"{type(exc).__name__}: {exc}"))
    print(_("crossdesk hit an unexpected error and stopped."), file=sys.stderr)
    print(_("  what: {summary}").format(summary=summary), file=sys.stderr)
    print(
        _("  re-run with CROSSDESK_DEBUG=1 for the full traceback."),
        file=sys.stderr,
    )
    if report_path is not None:
        print(
            _("  crash report written to {path} — attach it to a bug report.").format(
                path=report_path
            ),
            file=sys.stderr,
        )
    elif not enabled:
        print(
            _(
                "  tip: set CROSSDESK_CONFIG__OBSERVABILITY__CRASH_REPORT_ENABLED=true "
                "to capture a shareable crash report."
            ),
            file=sys.stderr,
        )
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except KeyboardInterrupt:
        print(_("interrupted."), file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - last-resort friendly handler
        return _handle_unexpected(exc, argv)


if __name__ == "__main__":
    sys.exit(main())
