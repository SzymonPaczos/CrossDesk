"""``crossdesk install`` subcommand.

Orchestrates the install pipeline; persists progress through the
:mod:`installer.state` machine so a partial install can resume. The
real work (ISO download, libvirt domain create, autounattend run) is
hardware-gated; this skeleton wires the steps and prints status so
the operator can follow along.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from crossdesk_host.i18n import _
from crossdesk_host.installer import credentials, state

_STEPS: List[str] = [
    "doctor",
    "download_iso",
    "generate_credentials",
    "create_libvirt_domain",
    "run_autounattend",
    "install_agent_service",
    "post_install_tweaks",
    "first_launch_notification",
]


def add_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("install", help="Install CrossDesk (Windows VM + agent)")
    p.add_argument("--iso-path", type=Path, help="Skip Fido download; use this ISO")
    p.add_argument("--lean", action="store_true", help="Slim Windows image")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print steps without invoking libvirt / network",
    )


def _ensure_steps(s: state.InstallState) -> None:
    for step in _STEPS:
        s.steps.setdefault(step, "pending")


def run(args: argparse.Namespace) -> int:
    state_path = state.default_state_file()
    s = state.load(state_path)
    _ensure_steps(s)

    print(_("crossdesk install (state at {path})").format(path=state_path))
    if args.dry_run:
        print(_("dry-run mode: no libvirt or network calls"))

    next_step = s.first_unfinished()
    if next_step is None:
        print(_("all steps already done; nothing to do"))
        return 0

    for step in _STEPS:
        if s.is_done(step):
            print(_("  ✓ {step} (already done)").format(step=step))
            continue
        print(_("  → {step}").format(step=step))
        if args.dry_run:
            s.mark(step, "done")
            state.save(s, state_path)
            continue
        # Real implementations land per-step; for now the only step
        # that runs end-to-end without hardware is generate_credentials
        # (host-side only, no libvirt touch).
        if step == "generate_credentials":
            creds = credentials.generate()
            credentials.save(creds)
            s.mark(step, "done")
            state.save(s, state_path)
            print(_("    saved credentials for user {user!r}").format(user=creds.username))
            continue
        print(_("    {step}: hardware-gated; not implemented in --no-hardware mode").format(step=step))
        s.mark(step, "pending")
        state.save(s, state_path)
        return 1

    print(_("install complete"))
    return 0
