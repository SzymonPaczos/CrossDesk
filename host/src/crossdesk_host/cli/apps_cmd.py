"""``crossdesk apps`` subcommand group.

Two sub-subcommands:

- ``crossdesk apps list``              — table of all catalog entries
- ``crossdesk apps install <app-id>``  — write a .desktop file for an app

Catalog entries come from the bundled ``catalog/apps.toml``; the
.desktop file is written via :func:`~crossdesk_host.integrations.mime.install_app`.
"""

from __future__ import annotations

import argparse
import sys

from crossdesk_host.catalog.loader import find_app, load_catalog
from crossdesk_host.i18n import _
from crossdesk_host.integrations.mime import install_app, update_mime_database


def add_subparser(
    sub: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    p = sub.add_parser("apps", help="Manage the app catalog")
    apps_sub = p.add_subparsers(dest="apps_command", required=True)

    # ``crossdesk apps list``
    apps_sub.add_parser("list", help="List all apps in the catalog")

    # ``crossdesk apps install <app-id>``
    install_p = apps_sub.add_parser("install", help="Install a .desktop entry for an app")
    install_p.add_argument("app_id", metavar="app-id", help="App slug from 'crossdesk apps list'")


def run(args: argparse.Namespace) -> int:
    if args.apps_command == "list":
        return _run_list()
    if args.apps_command == "install":
        return _run_install(args.app_id)
    # argparse `required=True` on subparsers prevents reaching here, but
    # mypy cannot model that invariant, so we keep the guard.
    args_parser_error(f"unknown apps subcommand {args.apps_command!r}")
    return 2


def args_parser_error(message: str) -> None:
    print(message, file=sys.stderr)


def _run_list() -> int:
    apps = load_catalog()
    if not apps:
        print(_("No apps in catalog."))
        return 0

    id_w = max(len(a.app_id) for a in apps)
    name_w = max(len(a.name) for a in apps)
    header = f"{'ID':<{id_w}}  {'Name':<{name_w}}  Executable"
    print(header)
    print("-" * len(header))
    for a in apps:
        print(f"{a.app_id:<{id_w}}  {a.name:<{name_w}}  {a.win_executable}")
    return 0


def _run_install(app_id: str) -> int:
    entry = find_app(app_id)
    if entry is None:
        print(
            _("app {app_id!r} not found in catalog; run 'crossdesk apps list' to see available apps.").format(
                app_id=app_id
            ),
            file=sys.stderr,
        )
        return 1

    dest = install_app(
        app_id=entry.app_id,
        display_name=entry.name,
        categories=entry.categories if entry.categories else ["Utility"],
        mime_types=entry.mime_types,
        icon=entry.icon if entry.icon else None,
    )
    update_mime_database()
    print(_("installed {name} → {path}").format(name=entry.name, path=dest))
    return 0
