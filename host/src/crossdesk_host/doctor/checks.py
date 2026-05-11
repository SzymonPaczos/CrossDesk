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
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional


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


@dataclass(frozen=True)
class GpuInfo:
    """Parsed entry from ``lspci -nnk`` for a VGA-class device."""

    pci_id: str           # e.g. "01:00.0"
    vendor_id: str        # 4-hex, e.g. "10de" (NVIDIA) or "1002" (AMD)
    device_id: str        # 4-hex
    name: str             # human-readable from lspci
    iommu_group: Optional[str] = None   # path leaf under /sys/kernel/iommu_groups/
    kernel_driver: str = ""


@dataclass
class GpuPassthroughResult:
    """Structured result of the GPU passthrough pre-flight check."""

    tier: int = 3                       # 1 = supported, 2 = possible with caveats, 3 = unsupported
    host_gpus: List[GpuInfo] = field(default_factory=list)
    passthrough_candidates: List[GpuInfo] = field(default_factory=list)
    iommu_enabled: bool = False
    warnings: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)


_NVIDIA_VENDOR = "10de"
_AMD_VENDOR = "1002"
_INTEL_VENDOR = "8086"

# RTX 20/30/40 series: device IDs start with 1e/1f/2x/24/25 (TU10x, GA10x, AD10x)
_NVIDIA_TIER1_DEVICE_PREFIX = ("1e", "1f", "20", "21", "22", "23", "24", "25", "26", "27")
# RDNA2 = Navi 21/22/23/24 (0x73*), RDNA3 = Navi 31/32/33 (0x74*)
_AMD_TIER1_DEVICE_PREFIX = ("73", "74")

_VGA_CLASS_PATTERN = re.compile(  # noqa: E501
    r"^([0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f])\s.*?\[0[23][0-9a-f]{2}\].*?\[([0-9a-f]{4}):([0-9a-f]{4})\]",
    re.IGNORECASE,
)
_KERNEL_DRIVER_PATTERN = re.compile(r"^\s+Kernel driver in use:\s+(.+)$", re.MULTILINE)


def _parse_lspci_output(output: str) -> List[GpuInfo]:
    gpus: List[GpuInfo] = []
    for line in output.splitlines():
        m = _VGA_CLASS_PATTERN.match(line)
        if not m:
            continue
        pci_id, vendor_id, device_id = m.group(1), m.group(2).lower(), m.group(3).lower()
        name = line.split("] ", 1)[-1] if "] " in line else line
        gpus.append(GpuInfo(pci_id=pci_id, vendor_id=vendor_id, device_id=device_id, name=name.strip()))
    return gpus


def _lspci_verbose(pci_id: str) -> str:
    try:
        result = subprocess.run(
            ["lspci", "-nnk", "-s", pci_id],
            capture_output=True, text=True, timeout=5.0,
        )
        return result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def _iommu_enabled(sys_root: Path = Path("/sys")) -> bool:
    return any((sys_root / "class" / "iommu").iterdir()) if (sys_root / "class" / "iommu").exists() else False


def _iommu_group_for(pci_id: str, sys_root: Path = Path("/sys")) -> Optional[str]:
    # /sys/bus/pci/devices/0000:01:00.0/iommu_group -> symlink to /sys/kernel/iommu_groups/N
    pci_addr = f"0000:{pci_id}" if ":" in pci_id else pci_id
    link = sys_root / "bus" / "pci" / "devices" / pci_addr / "iommu_group"
    if link.exists():
        try:
            return link.resolve().name  # the group number
        except OSError:
            pass
    return None


def _iommu_group_devices(group: str, sys_root: Path = Path("/sys")) -> List[str]:
    group_dir = sys_root / "kernel" / "iommu_groups" / group / "devices"
    if not group_dir.exists():
        return []
    return [p.name for p in group_dir.iterdir()]


def _classify_gpu(gpu: GpuInfo) -> int:
    """Return 1, 2, or 3 for Tier 1/2/3 passthrough support."""
    if gpu.vendor_id == _NVIDIA_VENDOR:
        dev = gpu.device_id[:2]
        if dev in _NVIDIA_TIER1_DEVICE_PREFIX:
            return 1
        return 2
    if gpu.vendor_id == _AMD_VENDOR:
        dev = gpu.device_id[:2]
        if dev in _AMD_TIER1_DEVICE_PREFIX:
            return 1
        return 2
    # Intel and others are Tier 3
    return 3


def check_gpu_passthrough(
    *,
    sys_root: Path = Path("/sys"),
    lspci_output: Optional[str] = None,
) -> CheckResult:
    """Detect whether the host GPU(s) support VFIO passthrough.

    Checks: IOMMU enabled, at least one Tier 1 or Tier 2 candidate GPU,
    candidate is in its own IOMMU group (not sharing with other devices).
    Non-Linux hosts get a WARN (skipped).

    The ``lspci_output`` and ``sys_root`` parameters allow injection in
    tests without requiring physical hardware.
    """
    if not _is_linux():
        return CheckResult(
            "gpu_passthrough",
            Status.WARN,
            "non-Linux host — GPU passthrough check skipped",
        )

    if lspci_output is None:
        if shutil.which("lspci") is None:
            return CheckResult(
                "gpu_passthrough",
                Status.WARN,
                "lspci not on PATH (install pciutils); GPU tier detection skipped",
            )
        try:
            proc = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True, text=True, timeout=10.0,
            )
            lspci_output = proc.stdout
        except (subprocess.SubprocessError, OSError) as exc:
            return CheckResult("gpu_passthrough", Status.WARN, f"lspci failed: {exc}")

    gpus = _parse_lspci_output(lspci_output)
    if not gpus:
        return CheckResult(
            "gpu_passthrough",
            Status.WARN,
            "no VGA-class devices found by lspci — GPU detection inconclusive",
        )

    iommu_ok = _iommu_enabled(sys_root)
    result = GpuPassthroughResult(iommu_enabled=iommu_ok, host_gpus=list(gpus))

    if not iommu_ok:
        result.blockers.append(
            "IOMMU not enabled. Add intel_iommu=on (Intel) or amd_iommu=on (AMD) "
            "to kernel cmdline and reboot."
        )

    for gpu in gpus:
        tier = _classify_gpu(gpu)
        group = _iommu_group_for(gpu.pci_id, sys_root)
        gpu_info = GpuInfo(
            pci_id=gpu.pci_id,
            vendor_id=gpu.vendor_id,
            device_id=gpu.device_id,
            name=gpu.name,
            iommu_group=group,
            kernel_driver=gpu.kernel_driver,
        )
        if tier == 3:
            result.warnings.append(
                f"{gpu.name} ({gpu.pci_id}): Tier 3 (Intel Arc / single-GPU) — "
                "passthrough not supported for CrossDesk; use software rendering."
            )
            continue
        if tier == 1:
            result.passthrough_candidates.append(gpu_info)
        else:
            result.passthrough_candidates.append(gpu_info)
            result.warnings.append(
                f"{gpu.name} ({gpu.pci_id}): Tier 2 — requires vendor-reset "
                "or hide-the-VM workaround; see docs/GPU_PASSTHROUGH.md."
            )
        if group is not None:
            siblings = _iommu_group_devices(group, sys_root)
            non_audio = [s for s in siblings if not s.endswith(".1")]
            if len(non_audio) > 1:
                result.warnings.append(
                    f"{gpu.name}: IOMMU group {group} contains other devices "
                    f"({', '.join(non_audio)}) — ACS patch may be required."
                )

    if not result.passthrough_candidates:
        result.tier = 3
        tier_str = "Tier 3 (Intel / single-GPU)"
        detail = "; ".join(result.warnings) if result.warnings else tier_str
        return CheckResult(
            "gpu_passthrough",
            Status.WARN,
            f"no passthrough-capable GPU found ({detail})",
        )

    result.tier = min(_classify_gpu(g) for g in result.passthrough_candidates)

    if result.blockers:
        return CheckResult(
            "gpu_passthrough",
            Status.FAIL,
            "; ".join(result.blockers),
        )

    if result.warnings:
        candidates_str = ", ".join(f"{g.name} ({g.pci_id})" for g in result.passthrough_candidates)
        return CheckResult(
            "gpu_passthrough",
            Status.WARN,
            f"Tier {result.tier} GPU candidate(s): {candidates_str}. "
            + "; ".join(result.warnings),
        )

    candidates_str = ", ".join(f"{g.name} ({g.pci_id})" for g in result.passthrough_candidates)
    return CheckResult(
        "gpu_passthrough",
        Status.OK,
        f"Tier {result.tier} passthrough-ready: {candidates_str}",
    )


DEFAULT_CHECKS: List[CheckFn] = [
    check_kvm_device,
    check_freerdp_available,
    check_libvirt_session,
    check_disk_space,
    check_vm_credentials,
]

GPU_CHECKS: List[CheckFn] = [
    check_gpu_passthrough,
]


def run_all(checks: List[CheckFn] = DEFAULT_CHECKS) -> List[CheckResult]:
    return [c() for c in checks]


def has_failures(results: List[CheckResult]) -> bool:
    return any(r.status == Status.FAIL for r in results)
