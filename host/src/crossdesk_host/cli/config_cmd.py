"""``crossdesk config`` subcommands.

``config migrate`` reads vm.toml, applies any pending schema migrations
(in-memory), and writes it back at the current ``SCHEMA_VERSION``.
This is safe to run at any time — it is idempotent and uses the same
atomic-rename write path as the regular credential save.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from crossdesk_host.i18n import _
from crossdesk_host.installer import credentials


def add_subparser(
    sub: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    p = sub.add_parser("config", help="Manage CrossDesk configuration files")
    sp = p.add_subparsers(dest="config_command", required=True)
    sp.add_parser(
        "migrate",
        help=(
            "Migrate vm.toml to the current schema version "
            "(safe to run repeatedly; no-op when already current)"
        ),
    )


def run(args: argparse.Namespace) -> int:
    if args.config_command == "migrate":
        return _run_migrate()
    print(_("unknown config command: {cmd!r}").format(cmd=args.config_command))
    return 2


def _run_migrate(path: Optional[Path] = None) -> int:
    """Migrate vm.toml to the current schema.

    Exposed as a separate function so tests can inject a custom path
    without going through argparse.
    """
    if path is None:
        path = credentials.default_path()

    if not path.exists():
        print(
            _("no vm.toml at {path} — run `crossdesk install` first").format(
                path=path
            )
        )
        return 1

    # Read the raw schema_version without full parse so we can report
    # the version even when the file is from a future schema we can't read.
    if sys.version_info >= (3, 11):
        import tomllib as _tomllib  # type: ignore[import-not-found,unused-ignore]
    else:  # pragma: no cover
        import tomli as _tomllib  # type: ignore[import-not-found]

    with path.open("rb") as f:
        raw = _tomllib.load(f)

    file_version = raw.get("schema_version", 1)
    current = credentials.SCHEMA_VERSION

    if not isinstance(file_version, int):
        print(
            _(
                "vm.toml at {path}: schema_version is not an integer ({val!r})"
            ).format(path=path, val=file_version)
        )
        return 1

    if file_version > current:
        print(
            _(
                "vm.toml is at schema version {file} which is newer than this "
                "build supports (max={current}). Upgrade crossdesk-host or "
                "back up the file and run `crossdesk vm credentials repair` "
                "to regenerate."
            ).format(file=file_version, current=current)
        )
        return 1

    if file_version == current:
        print(
            _("vm.toml is already at schema version {v} — nothing to do").format(
                v=current
            )
        )
        return 0

    # file_version < current: load() applies migrations and we re-save.
    try:
        creds = credentials.load(path)
    except ValueError as exc:
        print(_("cannot load vm.toml: {err}").format(err=exc))
        return 1

    if creds is None:
        print(_("vm.toml at {path} is empty or missing credentials").format(path=path))
        return 1

    print(
        _("migrating vm.toml from schema {old} → {new}").format(
            old=file_version, new=current
        )
    )
    credentials.save(creds, path)
    print(_("done — vm.toml is now at schema version {v}").format(v=current))
    return 0
