"""``crossdesk uninstall`` CLI wrapper."""

from __future__ import annotations

import argparse

from crossdesk_host.i18n import _
from crossdesk_host.uninstall import uninstall


def add_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("uninstall", help="Remove CrossDesk")
    p.add_argument("--keep-config", action="store_true", help="Preserve vm.toml")
    p.add_argument("--dry-run", action="store_true")


def run(args: argparse.Namespace) -> int:
    report = uninstall(keep_config=args.keep_config, dry_run=args.dry_run)
    if report.removed:
        print(_("removed:"))
        for line in report.removed:
            print(f"  - {line}")
    if report.skipped:
        print(_("skipped:"))
        for line in report.skipped:
            print(f"  - {line}")
    if report.failed:
        print(_("failed:"))
        for line in report.failed:
            print(f"  - {line}")
    return 1 if report.failed else 0
