"""``crossdesk uninstall`` CLI wrapper."""

from __future__ import annotations

import argparse

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.i18n import _
from crossdesk_host.uninstall import uninstall

# Domain name the install defines (matches install_cmd._DOMAIN_NAME), so
# uninstall tears down the same domain the install created.
_DOMAIN_NAME = "windows-guest"


def _resolve_libvirt_ctl() -> LibvirtController:
    # Deferred import: RealLibvirtController pulls libvirt-python (Linux-only)
    # lazily on first use, so constructing it here is safe on any dev host and
    # the dry-run path never opens a connection.
    from crossdesk_host.libvirt_ctl.real import RealLibvirtController

    return RealLibvirtController(domain_name=_DOMAIN_NAME)


def add_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("uninstall", help="Remove CrossDesk")
    p.add_argument("--keep-config", action="store_true", help="Preserve vm.toml")
    p.add_argument("--dry-run", action="store_true")


def run(args: argparse.Namespace) -> int:
    report = uninstall(
        keep_config=args.keep_config,
        dry_run=args.dry_run,
        libvirt_ctl=_resolve_libvirt_ctl(),
    )
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
