"""``crossdesk`` CLI entry point.

Subcommands:
- ``install``       — orchestrate VM bring-up
- ``launch <app>``  — launch a Windows app as a RAIL window
- ``vm credentials`` — show / rotate / set / repair VM password
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
import sys
from typing import List, Optional

from crossdesk_host.cli import (
    credentials_cmd,
    doctor_cmd,
    install_cmd,
    launch_cmd,
    logs_cmd,
    metrics_cmd,
    uninstall_cmd,
    version_cmd,
)
from crossdesk_host.i18n import _


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crossdesk",
        description="Run Windows applications as native Linux windows.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    install_cmd.add_subparser(sub)
    launch_cmd.add_subparser(sub)

    vm = sub.add_parser("vm", help="VM lifecycle commands")
    vm_sub = vm.add_subparsers(dest="vm_command", required=True)
    credentials_cmd.add_subparser(vm_sub)

    doctor_cmd.add_subparser(sub)
    logs_cmd.add_subparser(sub)
    metrics_cmd.add_subparser(sub)
    version_cmd.add_subparser(sub)
    uninstall_cmd.add_subparser(sub)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "install":
        return install_cmd.run(args)
    if args.command == "launch":
        return launch_cmd.run(args)
    if args.command == "vm":
        if args.vm_command == "credentials":
            return credentials_cmd.run(args)
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

    parser.error(f"unknown command {args.command!r}")
    return 2  # unreachable but keeps mypy happy


if __name__ == "__main__":
    sys.exit(main())
