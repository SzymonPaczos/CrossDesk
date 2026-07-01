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
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.doctor import has_failures, run_all
from crossdesk_host.doctor.checks import DEFAULT_CHECKS, Status
from crossdesk_host.i18n import _
from crossdesk_host.installer import credentials, pki, state, tools_iso
from crossdesk_host.installer.domain_xml import DomainSpec, build_domain_xml

# Domain name the daemon's LibvirtController also defaults to, so the
# domain `crossdesk install` defines is the one the daemon manages.
_DOMAIN_NAME = "windows-guest"
_DISK_GB = 64
# infra/autounattend.xml is authored in this locale; --locale substitutes it
# so the windowsPE language settings match a non-English ISO. A mismatch
# leaves Windows Setup stalled on the interactive language-selection screen
# (verified: an en-US answer file on a Polish ISO does not auto-skip it).
_DEFAULT_LOCALE = "en-US"

# Tests set this to a mock LibvirtController; production resolves the real
# one lazily (deferred libvirt import keeps the CLI importable on dev hosts).
_libvirt_ctl_override: Optional[LibvirtController] = None


def _resolve_libvirt_ctl() -> LibvirtController:
    if _libvirt_ctl_override is not None:
        return _libvirt_ctl_override
    from crossdesk_host.libvirt_ctl.real import RealLibvirtController

    return RealLibvirtController(domain_name=_DOMAIN_NAME)

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


def _packaged_data_dir() -> Path:
    """System data dir where distro packages place the tools-ISO inputs
    (``agent.exe`` + publisher CA + autounattend) — ``/usr/share/crossdesk``
    per ``docs/PACKAGING.md``. Overridable via ``CROSSDESK_DATA_DIR`` for
    relocatable installs and tests."""
    return Path(os.environ.get("CROSSDESK_DATA_DIR", "/usr/share/crossdesk"))


def _resolve_input(env_var: str, repo_path: Path, packaged_name: str) -> Optional[Path]:
    """Resolve one tools-ISO input by precedence:

    1. ``$env_var`` — when set, the *only* candidate (an explicit pin that
       doesn't exist is an error, not a silent fallthrough).
    2. the in-repo dev build/layout path.
    3. the packaged ``/usr/share/crossdesk/<packaged_name>`` so deb/rpm/AUR/
       Nix installs find inputs the package placed there.

    Returns the first existing path, or ``None`` if none exist.
    """
    override = os.environ.get(env_var)
    candidates = (
        [Path(override)]
        if override
        else [repo_path, _packaged_data_dir() / packaged_name]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _resolve_tools_inputs() -> tuple[Path, Path, Path]:
    """Locate the three tools-ISO inputs via env override → in-repo dev path
    → packaged ``/usr/share/crossdesk``. Raises :class:`_StepFailed` naming
    the missing input plus how to produce it."""
    root = _repo_root()
    pkg = _packaged_data_dir()
    agent = _resolve_input(
        "CROSSDESK_AGENT_EXE",
        root / "guest/target/x86_64-pc-windows-gnu/release/agent.exe",
        "agent.exe",
    )
    if agent is None:
        raise _StepFailed(
            _(
                "agent.exe not found (looked in $CROSSDESK_AGENT_EXE, the in-repo "
                "build dir, and {pkg}) — build it (`cd guest && cargo build "
                "--release --target x86_64-pc-windows-gnu`), install the crossdesk "
                "package, or set CROSSDESK_AGENT_EXE"
            ).format(pkg=pkg)
        )
    ca = _resolve_input(
        "CROSSDESK_PUBLISHER_CA",
        root / "infra/code-signing/pki/publisher-root-ca.crt",
        "publisher-root-ca.crt",
    )
    if ca is None:
        raise _StepFailed(_("publisher CA not found (in-repo or {pkg})").format(pkg=pkg))
    autounattend = _resolve_input(
        "CROSSDESK_AUTOUNATTEND", root / "infra/autounattend.xml", "autounattend.xml"
    )
    if autounattend is None:
        raise _StepFailed(
            _("autounattend.xml not found (in-repo or {pkg})").format(pkg=pkg)
        )
    return agent, ca, autounattend


def _install_pki_dir() -> Path:
    """Per-install mTLS PKI home: ``$CROSSDESK_PKI_DIR`` or
    ``~/.config/crossdesk/pki``."""
    env = os.environ.get("CROSSDESK_PKI_DIR")
    return Path(env) if env else Path.home() / ".config" / "crossdesk" / "pki"


def _resolve_mtls_pki() -> tuple[Path, Path, Path]:
    """Return the guest mTLS trio (``ca.crt`` / ``guest.crt`` / ``guest.key``)
    the tools ISO ships to ``C:\\CrossDesk\\pki\\``.

    Prefers a pre-provisioned dir (``CROSSDESK_MTLS_PKI_DIR`` env override, or
    the in-repo dev ``infra/certs/pki`` from ``generate_mtls.sh``). When
    absent, mints a **unique per-install** PKI — its own CA + host + guest
    leaf — under :func:`_install_pki_dir`, so this install never shares a CA
    or identity with any other and a leaked ``guest.key`` can't impersonate
    the guest on a different machine. Generated once; reused on re-runs.
    """
    provisioned = Path(
        os.environ.get("CROSSDESK_MTLS_PKI_DIR", _repo_root() / "infra/certs/pki")
    )
    ca = provisioned / "ca.crt"
    cert = provisioned / "guest.crt"
    key = provisioned / "guest.key"
    if ca.is_file() and cert.is_file() and key.is_file():
        return ca, cert, key
    minted = pki.ensure_install_pki(_install_pki_dir())
    print(
        _("    minted a unique per-install mTLS PKI under {dir}").format(
            dir=_install_pki_dir()
        )
    )
    return minted.ca_cert, minted.guest_cert, minted.guest_key


def _prepare_autounattend(src: Path, locale: str, password: str, dest_dir: Path) -> Path:
    """Return a per-install autounattend with the windowsPE locale set to
    *locale* and the account-password placeholder filled with *password*.

    The bundled file is the en-US template carrying a ``__CROSSDESK_PASSWORD__``
    placeholder; substituting both means (a) the language screen is skipped on
    a matching-locale ISO and (b) the guest account password equals the stored
    vm.toml credential, so the host can log in over RDP. Always writes a fresh
    copy — the password must never be baked into the repo template.
    """
    from xml.sax.saxutils import escape

    text = src.read_text(encoding="utf-8")
    if locale != _DEFAULT_LOCALE:
        text = text.replace(_DEFAULT_LOCALE, locale)
    text = text.replace("__CROSSDESK_PASSWORD__", escape(password))
    out = dest_dir / "autounattend.prepared.xml"
    out.write_text(text, encoding="utf-8")
    return out


def _step_build_tools_iso(args: argparse.Namespace) -> None:
    agent, ca, autounattend = _resolve_tools_inputs()
    state_dir = state.default_state_file().parent
    locale = getattr(args, "locale", _DEFAULT_LOCALE)
    creds = credentials.load()
    password = creds.password if creds is not None else ""
    autounattend = _prepare_autounattend(autounattend, locale, password, state_dir)
    output = state_dir / "tools.iso"
    mtls_ca, mtls_cert, mtls_key = _resolve_mtls_pki()
    try:
        tools_iso.build_tools_iso(
            agent_exe=agent,
            ca_cert=ca,
            autounattend=autounattend,
            output_iso=output,
            mtls_ca=mtls_ca,
            mtls_guest_cert=mtls_cert,
            mtls_guest_key=mtls_key,
        )
    except tools_iso.ToolsIsoError as exc:
        raise _StepFailed(str(exc)) from exc
    print(_("    built tools ISO at {path} (locale {loc})").format(path=output, loc=locale))


# Linux keycode for ENTER + boot-assist burst tuning (see _boot_from_cd).
_KEY_ENTER = 28
_BOOT_KEY_PRESSES = 12
_BOOT_KEY_INTERVAL_S = 1.25


def _boot_from_cd(ctl: LibvirtController) -> None:
    """Satisfy the Windows installer's "Press any key to boot from CD or
    DVD" prompt on the first boot of a fresh install.

    That prompt shows for a few seconds once the firmware POSTs and is the
    only keystroke a fresh unattended install needs — every later reboot
    falls through to the (now-bootable) disk by itself. Send ENTER a bounded
    number of times across the prompt window (a one-shot boot assist — a
    fixed-count ``for``, not a ``while True`` poll). The burst finishes long
    before Windows Setup's first reboot, so it never re-triggers the prompt
    and restarts Setup. Verified live 2026-07-01 (A7-live).
    """
    print(_("    clearing the installer's 'press any key to boot' prompt"))
    for _i in range(_BOOT_KEY_PRESSES):
        ctl.send_key([_KEY_ENTER])
        time.sleep(_BOOT_KEY_INTERVAL_S)


def _step_create_libvirt_domain(args: argparse.Namespace) -> None:
    iso: Path | None = args.iso_path
    if iso is None or not iso.is_file():
        raise _StepFailed(_("Windows ISO missing — pass --iso-path"))
    state_dir = state.default_state_file().parent
    disk = state_dir / "crossdesk-win.qcow2"
    tools = state_dir / "tools.iso"
    if not tools.is_file():
        raise _StepFailed(_("tools ISO not found at {p} (build_tools_iso first)").format(p=tools))

    if not disk.exists():
        try:
            subprocess.run(
                ["qemu-img", "create", "-f", "qcow2", str(disk), f"{_DISK_GB}G"],
                check=True,
                capture_output=True,
                text=True,
                timeout=120.0,
            )
        except FileNotFoundError as exc:
            raise _StepFailed(_("qemu-img not found — install qemu-utils")) from exc
        except subprocess.CalledProcessError as exc:
            raise _StepFailed(
                _("qemu-img create failed: {err}").format(err=exc.stderr.strip())
            ) from exc
        print(_("    created {gb} GB disk at {p}").format(gb=_DISK_GB, p=disk))

    # /dev/vhost-vsock must be openable by the qemu:///session process for
    # the AF_VSOCK device; if it isn't (default perms are root-only), drop
    # the device so the install still boots — vsock only carries the
    # post-install agent connection (DEC-0017). Fix later with a udev rule.
    vsock_ok = os.access("/dev/vhost-vsock", os.R_OK | os.W_OK)
    if not vsock_ok:
        print(
            _("    note: /dev/vhost-vsock not accessible — omitting vsock device")
        )
        print(
            _("    (Windows installs fine; the agent's vsock link needs a udev")
        )
        print(_("    rule granting access — see DEC-0017. Install proceeds.)"))

    spec = DomainSpec(
        name=_DOMAIN_NAME,
        disk_path=disk,
        windows_iso=iso,
        tools_iso=tools,
        vsock_enabled=vsock_ok,
    )
    ctl = _resolve_libvirt_ctl()
    try:
        ctl.define_and_start(build_domain_xml(spec))
    except RuntimeError as exc:
        raise _StepFailed(str(exc)) from exc
    print(_("    defined + started libvirt domain {name}").format(name=_DOMAIN_NAME))
    _boot_from_cd(ctl)


def _step_run_autounattend(args: argparse.Namespace) -> None:
    try:
        running = _resolve_libvirt_ctl().is_running()
    except RuntimeError as exc:
        raise _StepFailed(str(exc)) from exc
    if not running:
        raise _StepFailed(_("domain is not running after start"))
    # The unattended install is driven by autounattend.xml inside the
    # guest; the host's role from here is to inform + let it proceed.
    print(_("    Windows is installing unattended (~20-40 min)."))
    print(_("    Watch it: virt-viewer / a VNC client to the domain's VNC port."))
    print(_("    Setup + agent install run from autounattend.xml; the agent"))
    print(_("    registers itself with the host when setup completes."))


def _step_delegated_to_guest(args: argparse.Namespace) -> None:
    # Agent-service install + post-install tweaks are performed inside the
    # guest by autounattend.xml's FirstLogonCommands; the host has no
    # synchronous action and verifies readiness later via the daemon.
    print(_("    delegated to in-guest autounattend"))


def _step_first_launch_notification(args: argparse.Namespace) -> None:
    print(_("    install initiated. When Windows finishes and the agent"))
    print(_("    connects, launch an app: crossdesk launch notepad"))


def _gated(step: str) -> Callable[[argparse.Namespace], None]:
    def handler(args: argparse.Namespace) -> None:
        raise _HardwareGated(step)

    return handler


_HANDLERS: Dict[str, Callable[[argparse.Namespace], None]] = {
    "doctor": _step_doctor,
    "download_iso": _step_download_iso,
    "generate_credentials": _step_generate_credentials,
    "build_tools_iso": _step_build_tools_iso,
    "create_libvirt_domain": _step_create_libvirt_domain,
    "run_autounattend": _step_run_autounattend,
    "install_agent_service": _step_delegated_to_guest,
    "post_install_tweaks": _step_delegated_to_guest,
    "first_launch_notification": _step_first_launch_notification,
}


def add_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("install", help="Install CrossDesk (Windows VM + agent)")
    p.add_argument("--iso-path", type=Path, help="Skip Fido download; use this ISO")
    p.add_argument(
        "--locale",
        default=_DEFAULT_LOCALE,
        help=(
            "Install locale matching the ISO's language (e.g. en-US, pl-PL). "
            "Must match or Windows Setup stalls on the language screen."
        ),
    )
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

    if s.last_error:
        print(_("  last attempt stopped: {err}").format(err=s.last_error))

    # Pre-flight re-validation: when there's still install work to resume,
    # re-run `doctor` even if it passed before, so an environment regression
    # since the last attempt (libvirt removed, /dev/kvm perms changed) is
    # caught before we touch hardware. A fully-completed install stays a no-op.
    if not args.dry_run and s.is_done("doctor") and s.first_unfinished() is not None:
        s.mark("doctor", "pending")

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
            s.record_failure(
                step,
                _("{step}: hardware-gated (needs a booted Windows VM)").format(step=step),
            )
            state.save(s, state_path)
            return 1
        except _StepFailed as exc:
            print(_("    {step}: {err}").format(step=step, err=exc))
            s.record_failure(step, _("{step}: {err}").format(step=step, err=exc))
            state.save(s, state_path)
            return 1
        s.mark(step, "done")
        state.save(s, state_path)

    print(_("install pipeline complete (Windows continues installing in the guest)"))
    return 0
