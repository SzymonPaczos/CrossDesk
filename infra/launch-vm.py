#!/usr/bin/env python3
"""
launch-vm.py — Bootstrap launcher for the CrossDesk Windows guest VM.

Usage:
    python3 infra/launch-vm.py <windows.iso> <tools.iso> [--gpu-pci BDF[,BDF...]]

    windows.iso  — Downloaded Windows 10/11 installation ISO.
    tools.iso    — ISO containing autounattend.xml + CrossDeskAgent.exe at root.
    --gpu-pci    — Optional: one or more PCI Bus:Device.Function addresses of the
                   GPU and companion audio device to pass through via VFIO
                   (e.g. --gpu-pci 01:00.0,01:00.1). The devices must already be
                   bound to vfio-pci (see docs/GPU_PASSTHROUGH.md). When omitted,
                   the VM uses software rendering (virtio-gpu / VNC debug).

GPU passthrough notes:
    Tier 1 GPUs (NVIDIA RTX 20/30/40, AMD RDNA2/3 multi-GPU): pass all BDF
    addresses for the GPU plus its audio function.

    Tier 2 (older NVIDIA): add kvm=off and hv_vendor_id=AuthenticAMD to the
    -cpu flag to hide the virtualisation from the driver (done automatically
    when --nvidia-hide-vm is also passed).

Requirements (install via distro package manager):
    qemu-system-x86_64, qemu-img, ovmf, swtpm
    vfio-pci module (for --gpu-pci; load: modprobe vfio-pci)

The script creates crossdesk-win.qcow2 and efivars.fd in the current directory
on first run; subsequent runs reuse them (install does not repeat).
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List

# ── Configuration ────────────────────────────────────────────────────────────

DISK_IMAGE: Path = Path("crossdesk-win.qcow2")
EFIVARS: Path = Path("efivars.fd")

DISK_GB: int = 64
RAM_MB: int = 4096
VCPUS: int = 4

# Guest CID for AF_VSOCK; 0=hypervisor, 1=loopback, 2=host, 3+ are free.
VSOCK_CID: int = 3

# OVMF paths differ by distro; list checked in order.
_OVMF_CODE_CANDIDATES: list[Path] = [
    Path("/usr/share/OVMF/OVMF_CODE_4M.fd"),           # Ubuntu/Debian
    Path("/usr/share/OVMF/OVMF_CODE.fd"),
    Path("/usr/share/edk2/ovmf/OVMF_CODE.fd"),          # Fedora/RHEL
    Path("/usr/share/ovmf/x64/OVMF_CODE.fd"),           # Arch
]
_OVMF_VARS_CANDIDATES: list[Path] = [
    Path("/usr/share/OVMF/OVMF_VARS_4M.fd"),
    Path("/usr/share/OVMF/OVMF_VARS.fd"),
    Path("/usr/share/edk2/ovmf/OVMF_VARS.fd"),
    Path("/usr/share/ovmf/x64/OVMF_VARS.fd"),
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def find_first(candidates: list[Path]) -> Path:
    for p in candidates:
        if p.exists():
            return p
    die(
        "OVMF firmware not found. Install the 'ovmf' package.\n"
        f"  Searched: {[str(c) for c in candidates]}"
    )
    raise SystemExit(1)  # unreachable; satisfies type-checker


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        die(f"required binary not in PATH: {name}")


def preflight(windows_iso: Path, tools_iso: Path) -> None:
    for iso, label in ((windows_iso, "Windows ISO"), (tools_iso, "tools ISO")):
        if not iso.exists():
            die(f"{label} not found: {iso}")
    for binary in ("qemu-system-x86_64", "qemu-img", "swtpm"):
        require_binary(binary)
    if not Path("/dev/kvm").exists():
        die("/dev/kvm not present — enable KVM (modprobe kvm_intel or kvm_amd)")


def create_disk_if_missing() -> None:
    if not DISK_IMAGE.exists():
        subprocess.run(
            ["qemu-img", "create", "-f", "qcow2", str(DISK_IMAGE), f"{DISK_GB}G"],
            check=True,
        )


def copy_efivars_if_missing(ovmf_vars: Path) -> None:
    if not EFIVARS.exists():
        shutil.copy2(ovmf_vars, EFIVARS)


def start_swtpm(state_dir: Path) -> tuple[subprocess.Popen[bytes], Path]:
    sock = state_dir / "swtpm.sock"
    proc = subprocess.Popen(
        [
            "swtpm", "socket",
            "--tpmstate", f"dir={state_dir}",
            "--ctrl",     f"type=unixio,path={sock}",
            "--log",      "level=0",
            "--tpm2",
        ],
        stderr=subprocess.PIPE,
    )
    _wait_for_unix_socket(proc, sock, timeout=5.0)
    return proc, sock


def _wait_for_unix_socket(proc: subprocess.Popen[bytes], path: Path, timeout: float) -> None:
    """Poll until the AF_UNIX socket accepts connections or timeout expires.

    If `proc` has already exited, surface its stderr so the caller doesn't have
    to guess between "swtpm crashed" and "swtpm is just slow."
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            die(f"swtpm exited with code {proc.returncode} before socket appeared:\n{stderr}")
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(str(path))
            return
        except OSError:
            time.sleep(0.05)

    proc.terminate()
    try:
        stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
    except Exception:
        stderr = ""
    die(
        f"swtpm socket {path} not ready within {timeout}s"
        + (f"; swtpm stderr:\n{stderr}" if stderr else "")
    )


def build_qemu_cmd(
    windows_iso: Path,
    tools_iso: Path,
    ovmf_code: Path,
    tpm_sock: Path,
    gpu_pci_ids: List[str] = [],
    nvidia_hide_vm: bool = False,
) -> List[str]:
    # kvm=off + hv_vendor_id spoof hides the hypervisor from older NVIDIA drivers
    cpu_flags = "host,kvm=off,hv_vendor_id=AuthenticAMD" if nvidia_hide_vm else "host"

    cmd = [
        "qemu-system-x86_64",
        "-name",    "CrossDesk-Win",
        # q35 chipset; smm=on required for OVMF Secure Boot / Win11 compatibility
        "-machine", "q35,accel=kvm,smm=on",
        "-cpu",     cpu_flags,
        "-smp",     str(VCPUS),
        "-m",       str(RAM_MB),
        # ── UEFI ──────────────────────────────────────────────────────────
        "-drive",   f"if=pflash,format=raw,readonly=on,file={ovmf_code}",
        "-drive",   f"if=pflash,format=raw,file={EFIVARS}",
        # ── TPM 2.0 ───────────────────────────────────────────────────────
        "-chardev", f"socket,id=chrtpm,path={tpm_sock}",
        "-tpmdev",  "emulator,id=tpm0,chardev=chrtpm",
        "-device",  "tpm-tis,tpmdev=tpm0",
        # ── Storage ───────────────────────────────────────────────────────
        "-drive",   f"file={DISK_IMAGE},if=virtio,format=qcow2,cache=writeback",
        # cdrom index=0 → C: (install source), index=1 → D: (tools ISO)
        "-drive",   f"file={windows_iso},media=cdrom,readonly=on,index=0",
        "-drive",   f"file={tools_iso},media=cdrom,readonly=on,index=1",
        # Boot from optical first (install); disk takes over on subsequent boots
        "-boot",    "order=dc,menu=off",
        # ── Network (user-mode, no root required) ─────────────────────────
        "-netdev",  "user,id=net0",
        "-device",  "virtio-net-pci,netdev=net0",
        # ── AF_VSOCK for Phase 2 gRPC transport ───────────────────────────
        # Requires: modprobe vhost_vsock (or CONFIG_VHOST_VSOCK=y in kernel)
        "-device",  f"vhost-vsock-pci,guest-cid={VSOCK_CID}",
    ]

    if gpu_pci_ids:
        # Pass through each BDF via VFIO; first function gets multifunction=on so
        # the guest sees the whole slot (GPU + audio companion) as one PCI device.
        for i, bdf in enumerate(gpu_pci_ids):
            extra = ",multifunction=on" if i == 0 else ""
            cmd += ["-device", f"vfio-pci,host={bdf}{extra}"]
        # With a real GPU, render directly to the display — no VNC overlay.
        cmd += ["-display", "none"]
    else:
        # Software rendering fallback; VNC on :0 (port 5900) for debugging.
        cmd += [
            "-display", "none",
            "-vnc",     "127.0.0.1:0",
        ]

    return cmd


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap launcher for the CrossDesk Windows guest VM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("windows_iso", type=Path, help="Windows 10/11 installation ISO")
    parser.add_argument("tools_iso", type=Path, help="ISO containing autounattend.xml + CrossDeskAgent.exe")
    parser.add_argument(
        "--gpu-pci",
        metavar="BDF[,BDF...]",
        help=(
            "Comma-separated PCI Bus:Device.Function addresses for GPU passthrough "
            "(e.g. 01:00.0,01:00.1). Devices must already be bound to vfio-pci."
        ),
    )
    parser.add_argument(
        "--nvidia-hide-vm",
        action="store_true",
        help="Add kvm=off + hv_vendor_id=AuthenticAMD to hide the VM from older NVIDIA drivers (Tier 2).",
    )
    args = parser.parse_args()

    gpu_pci_ids: List[str] = []
    if args.gpu_pci:
        gpu_pci_ids = [bdf.strip() for bdf in args.gpu_pci.split(",") if bdf.strip()]

    preflight(args.windows_iso, args.tools_iso)

    ovmf_code = find_first(_OVMF_CODE_CANDIDATES)
    ovmf_vars = find_first(_OVMF_VARS_CANDIDATES)

    create_disk_if_missing()
    copy_efivars_if_missing(ovmf_vars)

    tpm_state = Path(tempfile.mkdtemp(prefix="crossdesk-tpm-"))
    tpm_proc, tpm_sock = start_swtpm(tpm_state)

    try:
        cmd = build_qemu_cmd(
            args.windows_iso,
            args.tools_iso,
            ovmf_code,
            tpm_sock,
            gpu_pci_ids=gpu_pci_ids,
            nvidia_hide_vm=args.nvidia_hide_vm,
        )
        print("+ " + " ".join(cmd))
        subprocess.run(cmd, check=True)
    finally:
        tpm_proc.terminate()
        tpm_proc.wait()


if __name__ == "__main__":
    main()
