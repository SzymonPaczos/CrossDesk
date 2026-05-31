"""``crossdesk install`` subcommand.

Orchestrates the install pipeline and persists progress through the
:mod:`installer.state` machine so a partial install can resume. Steps are
dispatched through a handler table: the host-side steps (``doctor``,
``download_iso`` when an ISO is supplied, ``generate_credentials``,
``build_tools_iso``) run for real; the steps that require a booted Windows
VM (``create_libvirt_domain`` onward) raise :class:`_HardwareGated` until
their hardware wiring lands.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Callable, Dict, List

from crossdesk_host.doctor import has_failures, run_all
from crossdesk_host.doctor.checks import DEFAULT_CHECKS, Status
from crossdesk_host.i18n import _
from crossdesk_host.installer import credentials, state, tools_iso

_STEPS: List[str] = [
    "doctor",
    "download_iso",
    "generate_credentials",
    "build_tools_iso",
    "create_libvirt_domain",
    "run_autounattend",
    "install_agent_service",
    "post_install_tweaks",
    "first_launch_notification",
]

_GLYPH = {Status.OK: "✓", Status.WARN: "!", Status.FAIL: "✗"}


class _HardwareGated(Exception):
    """A step that needs a booted Windows VM and is not wired yet."""


class _StepFailed(Exception):
    """A host-side step ran but could not complete (bad input, failed check)."""


# --------------------------------------------------------------------------
# Step handlers — each does the work or raises _HardwareGated / _StepFailed.
# The run loop owns state marking; handlers never mark steps themselves.
# --------------------------------------------------------------------------


def _step_doctor(args: argparse.Namespace) -> None:
    results = run_all(DEFAULT_CHECKS)
    for r in results:
        print(f"    {_GLYPH[r.status]} {r.name}" + (f" — {r.message}" if r.message else ""))
    if has_failures(results):
        failed = ", ".join(r.name for r in results if r.status is Status.FAIL)
        raise _StepFailed(_("doctor found blocking issues: {names}").format(names=failed))


def _step_download_iso(args: argparse.Namespace) -> None:
    iso: Path | None = args.iso_path
    if iso is None:
        # Fido-style auto-download is not wired yet; --iso-path is the
        # supported path until installer.iso_downloader grows a backend.
        raise _HardwareGated("download_iso")
    if not iso.is_file():
        raise _StepFailed(_("--iso-path is not a file: {path}").format(path=iso))
    print(_("    using ISO {path}").format(path=iso))


def _step_generate_credentials(args: argparse.Namespace) -> None:
    creds = credentials.generate()
    credentials.save(creds)
    print(_("    saved credentials for user {user!r}").format(user=creds.username))


def _repo_root() -> Path:
    # host/src/crossdesk_host/cli/install_cmd.py → parents[4] == repo root.
    return Path(__file__).resolve().parents[4]


def _resolve_tools_inputs() -> tuple[Path, Path, Path]:
    """Locate the three tools-ISO inputs via env overrides, falling back to
    the in-repo dev layout. Raises :class:`_StepFailed` naming the first
    missing input plus how to produce it."""
    root = _repo_root()
    agent = Path(
        os.environ.get(
            "CROSSDESK_AGENT_EXE",
            root / "guest/target/x86_64-pc-windows-gnu/release/agent.exe",
        )
    )
    ca = Path(
        os.environ.get(
            "CROSSDESK_PUBLISHER_CA",
            root / "infra/code-signing/pki/publisher-root-ca.crt",
        )
    )
    autounattend = Path(
        os.environ.get("CROSSDESK_AUTOUNATTEND", root / "infra/autounattend.xml")
    )
    if not agent.is_file():
        raise _StepFailed(
            _(
                "agent.exe not found at {p} — build it "
                "(`cd guest && cargo build --release "
                "--target x86_64-pc-windows-gnu`) or set CROSSDESK_AGENT_EXE"
            ).format(p=agent)
        )
    if not ca.is_file():
        raise _StepFailed(_("publisher CA not found at {p}").format(p=ca))
    if not autounattend.is_file():
        raise _StepFailed(_("autounattend.xml not found at {p}").format(p=autounattend))
    return agent, ca, autounattend


def _step_build_tools_iso(args: argparse.Namespace) -> None:
    agent, ca, autounattend = _resolve_tools_inputs()
    output = state.default_state_file().parent / "tools.iso"
    try:
        tools_iso.build_tools_iso(
            agent_exe=agent, ca_cert=ca, autounattend=autounattend, output_iso=output
        )
    except tools_iso.ToolsIsoError as exc:
        raise _StepFailed(str(exc)) from exc
    print(_("    built tools ISO at {path}").format(path=output))


def _gated(step: str) -> Callable[[argparse.Namespace], None]:
    def handler(args: argparse.Namespace) -> None:
        raise _HardwareGated(step)

    return handler


_HANDLERS: Dict[str, Callable[[argparse.Namespace], None]] = {
    "doctor": _step_doctor,
    "download_iso": _step_download_iso,
    "generate_credentials": _step_generate_credentials,
    "build_tools_iso": _step_build_tools_iso,
    "create_libvirt_domain": _gated("create_libvirt_domain"),
    "run_autounattend": _gated("run_autounattend"),
    "install_agent_service": _gated("install_agent_service"),
    "post_install_tweaks": _gated("post_install_tweaks"),
    "first_launch_notification": _gated("first_launch_notification"),
}


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

    if s.first_unfinished() is None:
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
        try:
            _HANDLERS[step](args)
        except _HardwareGated:
            print(
                _("    {step}: hardware-gated; not implemented in --no-hardware mode").format(
                    step=step
                )
            )
            s.mark(step, "pending")
            state.save(s, state_path)
            return 1
        except _StepFailed as exc:
            print(_("    {step}: {err}").format(step=step, err=exc))
            s.mark(step, "pending")
            state.save(s, state_path)
            return 1
        s.mark(step, "done")
        state.save(s, state_path)

    print(_("install complete"))
    return 0
