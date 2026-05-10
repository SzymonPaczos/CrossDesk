"""``crossdesk vm credentials`` subcommands.

Operates on ``~/.config/crossdesk/vm.toml``. The ``rotate`` and
``repair`` subcommands need to talk to the guest (to push the new
password); without hardware we only print what would happen. ``show``
and ``set`` are pure host-side actions and work everywhere.
"""

from __future__ import annotations

import argparse
import getpass
from typing import Optional

from crossdesk_host.i18n import _
from crossdesk_host.installer import credentials


def add_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("credentials", help="Manage VM login credentials")
    sp = p.add_subparsers(dest="cred_action", required=True)
    sp.add_parser("show", help="Print current username (and password to stdout)")
    sp.add_parser("rotate", help="Generate a new password and apply to guest")
    set_p = sp.add_parser("set", help="Set username/password from stdin or args")
    set_p.add_argument("--username", required=True)
    set_p.add_argument("--password", default=None, help="Read from prompt if omitted")
    sp.add_parser(
        "check",
        help="Inspect vm.toml health (presence, parse, file mode); no guest contact",
    )
    sp.add_parser(
        "repair",
        help="Fix vm.toml file mode to 0600; re-applying password to guest needs a running daemon",
    )


def run(args: argparse.Namespace) -> int:
    action: Optional[str] = getattr(args, "cred_action", None)
    if action == "show":
        return _run_show()
    if action == "rotate":
        return _run_rotate()
    if action == "set":
        return _run_set(args.username, args.password)
    if action == "check":
        return _run_check()
    if action == "repair":
        return _run_repair()
    # The action!r value is a CLI-reachable identifier (English literal
    # passed by the user via argparse) — not translated. The framing is.
    print(_("unknown credentials action: {action!r}").format(action=action))
    return 2


def _run_show() -> int:
    creds = credentials.load()
    if creds is None:
        print(_("no credentials at {path}").format(path=credentials.default_path()))
        return 1
    print(_("username = {username}").format(username=creds.username))
    print(_("password = {password}").format(password=creds.password))
    return 0


def _run_rotate() -> int:
    existing = credentials.load()
    if existing is None:
        print(_("no existing credentials; run `crossdesk install` first"))
        return 1
    new_creds = credentials.generate(existing.username)
    credentials.save(new_creds)
    print(_("host updated for {username!r}").format(username=new_creds.username))
    print(
        _(
            "(guest password change is hardware-gated; "
            "run `crossdesk vm credentials repair` once VM is reachable)"
        )
    )
    return 0


def _run_set(username: str, password: Optional[str]) -> int:
    if password is None:
        password = getpass.getpass(_("password: "))
    credentials.save(credentials.VmCredentials(username=username, password=password))
    print(_("saved credentials for {username!r}").format(username=username))
    return 0


def _run_check() -> int:
    health = credentials.health_check()
    # Field labels are user-facing column headers for a human-readable
    # report, so they get translated. The values "yes" / "no" /
    # "0600" / "NEEDS REPAIR" are also surfaced to the operator,
    # not parsed by anything machine-readable.
    print(_("path:         {value}").format(value=health.path))
    print(
        _("present:      {value}").format(value=_("yes") if health.present else _("no"))
    )
    print(
        _("parsable:     {value}").format(
            value=_("yes") if health.parsable else _("no")
        )
    )
    print(
        _("permissions:  {value}").format(
            value="0600" if health.permissions_ok else _("NEEDS REPAIR")
        )
    )
    if health.ok:
        print(_("status:       OK"))
        return 0
    hint = health.remediation()
    print(_("status:       FAIL — {hint}").format(hint=hint))
    return 1


def _run_repair() -> int:
    creds = credentials.load()
    if creds is None:
        print(
            _("no credentials at {path}; nothing to repair").format(
                path=credentials.default_path()
            )
        )
        return 1
    changed = credentials.repair_permissions()
    if changed:
        print(
            _("vm.toml permissions tightened to 0600 at {path}").format(
                path=credentials.default_path()
            )
        )
    else:
        print(
            _("vm.toml permissions already 0600 at {path}").format(
                path=credentials.default_path()
            )
        )
    print(
        _(
            "note: full guest password re-apply for {username!r} requires a "
            "running daemon and is wired through `display.session_starter` "
            "before the next RAIL spawn."
        ).format(username=creds.username)
    )
    return 0
