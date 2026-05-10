"""Pre-flight checks for ``crossdesk doctor``.

Each check is a small function returning ``CheckResult``: status
(``ok`` / ``warn`` / ``fail``) plus a short remediation message
when relevant. ``run_all`` returns ``0`` when no checks failed (warns
are tolerated), ``1`` otherwise — that's what the CLI exits with.

Most checks are subprocess- or filesystem-based; on Mac the daemon
package isn't fully wired but doctor still works for the parts we
can probe (FreeRDP version, KVM module file existence is Linux-only
and reported as ``warn`` when /dev/kvm is missing on a non-Linux host).
"""

from __future__ import annotations

import enum
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List


class Status(enum.Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    message: str = ""


CheckFn = Callable[[], CheckResult]


def _is_linux() -> bool:
    return platform.system() == "Linux"


def check_kvm_device() -> CheckResult:
    if not _is_linux():
        return CheckResult(
            "kvm_device",
            Status.WARN,
            "non-Linux host — /dev/kvm probe skipped",
        )
    if Path("/dev/kvm").exists():
        return CheckResult("kvm_device", Status.OK)
    return CheckResult(
        "kvm_device",
        Status.FAIL,
        "/dev/kvm missing. Load the kvm-intel or kvm-amd module and "
        "ensure your user is in the 'kvm' group.",
    )


def check_freerdp_available() -> CheckResult:
    candidates = ("xfreerdp", "xfreerdp3", "sdl-freerdp3", "sdl3-freerdp")
    for binary in candidates:
        if shutil.which(binary) is not None:
            return CheckResult(
                "freerdp",
                Status.OK,
                f"found {binary}",
            )
    if shutil.which("flatpak") is not None:
        return CheckResult(
            "freerdp",
            Status.WARN,
            "no system FreeRDP found; flatpak fallback "
            "'com.freerdp.FreeRDP' will be tried at runtime.",
        )
    return CheckResult(
        "freerdp",
        Status.FAIL,
        "no FreeRDP binary on PATH and no flatpak. "
        "Install xfreerdp >= 2.x or 'flatpak install com.freerdp.FreeRDP'.",
    )


def check_libvirt_session() -> CheckResult:
    if not _is_linux():
        return CheckResult(
            "libvirt",
            Status.WARN,
            "non-Linux host — libvirt session skipped",
        )
    if shutil.which("virsh") is None:
        return CheckResult(
            "libvirt",
            Status.FAIL,
            "virsh not on PATH. Install libvirt-clients (deb) / "
            "libvirt-client (rpm) / libvirt (Arch).",
        )
    try:
        result = subprocess.run(
            ["virsh", "-c", "qemu:///session", "list"],
            check=False,
            capture_output=True,
            timeout=5.0,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return CheckResult(
            "libvirt",
            Status.FAIL,
            f"virsh probe failed: {exc}",
        )
    if result.returncode != 0:
        return CheckResult(
            "libvirt",
            Status.FAIL,
            "virsh -c qemu:///session list returned non-zero. "
            "Start libvirtd / libvirt-session as user.",
        )
    return CheckResult("libvirt", Status.OK)


def check_disk_space(min_gb: float = 60.0) -> CheckResult:
    """Windows install + working set + virtiofs surface needs ~60 GB.
    The check looks at the home filesystem because that's where the
    libvirt session storage pool lives."""
    home = str(Path.home())
    try:
        usage = shutil.disk_usage(home)
    except OSError as exc:
        return CheckResult(
            "disk_space",
            Status.WARN,
            f"could not stat {home}: {exc}",
        )
    free_gb = usage.free / (1 << 30)
    if free_gb < min_gb:
        return CheckResult(
            "disk_space",
            Status.FAIL,
            f"{free_gb:.1f} GB free in {home}; need at least {min_gb:.0f} GB.",
        )
    return CheckResult(
        "disk_space",
        Status.OK,
        f"{free_gb:.1f} GB free",
    )


def check_vm_credentials() -> CheckResult:
    """vm.toml health: present, parsable, file mode 0600.

    Does NOT contact the guest — that requires a running daemon and is
    wired through ``display.session_starter`` before each RAIL spawn.
    Doctor stays a fast pre-flight: it tells the user whether the
    credential file is sane on disk.
    """
    from crossdesk_host.installer.credentials import health_check

    health = health_check()
    if health.ok:
        return CheckResult("vm_credentials", Status.OK, f"{health.path}")
    if not health.present:
        return CheckResult(
            "vm_credentials",
            Status.WARN,
            health.remediation() or f"{health.path} missing",
        )
    return CheckResult(
        "vm_credentials",
        Status.FAIL,
        health.remediation() or f"{health.path} unhealthy",
    )


DEFAULT_CHECKS: List[CheckFn] = [
    check_kvm_device,
    check_freerdp_available,
    check_libvirt_session,
    check_disk_space,
    check_vm_credentials,
]


def run_all(checks: List[CheckFn] = DEFAULT_CHECKS) -> List[CheckResult]:
    return [c() for c in checks]


def has_failures(results: List[CheckResult]) -> bool:
    return any(r.status == Status.FAIL for r in results)
