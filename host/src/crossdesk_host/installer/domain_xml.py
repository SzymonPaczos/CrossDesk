"""Generate the libvirt domain XML for the CrossDesk Windows guest.

Authored with libvirt-native elements (not by parsing
``infra/launch-vm.py``'s qemu argv) per DEC-0016: libvirt owns the swtpm
lifecycle, UEFI loader/nvram, the AF_VSOCK device, virtio-net and the
balloon, which is cleaner and less drift-prone than argv translation.

Disk bus is **SATA/AHCI**, not virtio-blk: Windows Setup has no in-box
virtio-blk driver, so a virtio boot disk leaves Setup with "no drives
found". SATA lets the stock Microsoft ISO install unattended with no
extra driver media (DEC-0016). Two read-only CD-ROMs carry the Windows
installer (boot source) and the CrossDesk tools ISO (autounattend +
agent + CA). A VNC graphics device on loopback lets the operator watch
the unattended install.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

# qemu's hard-coded host CID for AF_VSOCK is 2; the guest is assigned a
# distinct CID here (3 by convention, matching infra/launch-vm.py).
_DEFAULT_GUEST_CID = 3

# OVMF (UEFI) firmware descriptor paths differ by distro. The plain
# (non-Secure-Boot, non-.ms) split-firmware build is required: libvirt's
# `firmware='efi'` auto-select grabbed the Secure Boot / AMD-SEV variants and
# left a fresh install at UEFI "No bootable option" (A7-live 2026-07-01). The
# Debian/Ubuntu path is first (the box we validate on); Fedora/RHEL/Arch
# follow. PACKAGING.md targets rpm/AUR/NixOS, so a single hardcoded path would
# break `defineXML` on every non-Debian host. Mirrors infra/launch-vm.py.
_OVMF_CODE_CANDIDATES = (
    "/usr/share/OVMF/OVMF_CODE_4M.fd",  # Ubuntu/Debian
    "/usr/share/OVMF/OVMF_CODE.fd",
    "/usr/share/edk2/ovmf/OVMF_CODE.fd",  # Fedora/RHEL
    "/usr/share/edk2-ovmf/x64/OVMF_CODE.fd",  # Arch (edk2-ovmf)
    "/usr/share/ovmf/x64/OVMF_CODE.fd",  # Arch (ovmf)
)
_OVMF_VARS_CANDIDATES = (
    "/usr/share/OVMF/OVMF_VARS_4M.fd",
    "/usr/share/OVMF/OVMF_VARS.fd",
    "/usr/share/edk2/ovmf/OVMF_VARS.fd",
    "/usr/share/edk2-ovmf/x64/OVMF_VARS.fd",
    "/usr/share/ovmf/x64/OVMF_VARS.fd",
)
# build_domain_xml stays a pure formatter (no I/O); these are its fallback
# defaults when the caller doesn't resolve a real path. The install path calls
# resolve_ovmf() (below) to pick a host-correct pair and fail loudly if absent.
_DEFAULT_OVMF_CODE = _OVMF_CODE_CANDIDATES[0]
_DEFAULT_OVMF_VARS = _OVMF_VARS_CANDIDATES[0]


def resolve_ovmf() -> Tuple[str, str]:
    """Return ``(code_path, vars_template)`` for the plain OVMF firmware on this
    host: ``$CROSSDESK_OVMF_CODE`` / ``$CROSSDESK_OVMF_VARS`` if set, else the
    first existing distro candidate. Raises :class:`FileNotFoundError` naming
    the searched paths so a missing-firmware install fails with a fixable
    message instead of an opaque libvirt ``defineXML`` error.

    Does filesystem I/O — call it in the install path and pass the result into
    :class:`DomainSpec`, keeping :func:`build_domain_xml` pure.
    """

    def _pick(env: str, candidates: Tuple[str, ...], what: str) -> str:
        override = os.environ.get(env)
        if override:
            if Path(override).is_file():
                return override
            raise FileNotFoundError(f"{env}={override!r} does not exist")
        for c in candidates:
            if Path(c).is_file():
                return c
        raise FileNotFoundError(
            f"OVMF {what} not found — install the 'ovmf'/'edk2-ovmf' package or set "
            f"{env}. Searched: {', '.join(candidates)}"
        )

    return (
        _pick("CROSSDESK_OVMF_CODE", _OVMF_CODE_CANDIDATES, "firmware (CODE)"),
        _pick("CROSSDESK_OVMF_VARS", _OVMF_VARS_CANDIDATES, "vars template"),
    )

# libvirt's qemu-commandline passthrough namespace. Used for the user-net
# NIC + host→guest RDP hostfwd: libvirt's native <portForward> needs the
# passt backend, so we drive qemu's SLIRP hostfwd directly instead.
_QEMU_NS = "http://libvirt.org/schemas/domain/qemu/1.0"


@dataclass(frozen=True)
class DomainSpec:
    """Inputs for one CrossDesk guest domain."""

    name: str
    disk_path: Path
    windows_iso: Path
    tools_iso: Path
    ram_mib: int = 4096
    vcpus: int = 4
    vsock_cid: int = _DEFAULT_GUEST_CID
    emulator: str = "/usr/bin/qemu-system-x86_64"
    ovmf_code: str = ""
    """Plain OVMF CODE descriptor path. Empty → the Debian/Ubuntu default; the
    install path fills it via :func:`resolve_ovmf` so non-Debian hosts work."""
    ovmf_vars: str = ""
    """OVMF VARS template path. Empty → the Debian/Ubuntu default (see above)."""
    vsock_enabled: bool = True
    """Include the AF_VSOCK device. Disabled when ``/dev/vhost-vsock`` is
    not accessible to the qemu:///session process (a udev-rule / permission
    fix is required) — Windows installs fine without it; vsock only carries
    the post-install agent connection (DEC-0017)."""

    persistent_shares: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    """FS Stage B persistent virtio-fs mounts, as ``(target_tag, host_dir)``
    pairs present from domain start (not JIT). Each adds a
    ``<filesystem driver='virtiofs'>`` device; a non-empty list also enables
    shared ``memfd`` memory backing, which virtio-fs (vhost-user) requires.

    Empty by default so a no-share install emits byte-identical XML. The
    guest side (WinFSP + VirtioFsSvc) and live-mount verification are
    box-gated follow-ups; this is the host-side capability the install path
    consumes once the guest driver is confirmed."""


def build_domain_xml(spec: DomainSpec) -> str:
    """Return the libvirt domain XML string for *spec*.

    Pure formatting — no I/O. ``ElementTree`` guarantees well-formed,
    attribute-escaped output (paths with ``&`` / quotes are handled).

    Raises:
        ValueError: a ``persistent_shares`` entry has a relative ``host_dir``
            (libvirt rejects a relative ``<source dir>``) or a duplicate tag
            (virtio-fs target tags must be unique within a domain). Failing
            here gives a clear message instead of a cryptic libvirt error at
            ``define`` time.
    """
    seen_tags: set[str] = set()
    for tag, host_dir in spec.persistent_shares:
        if not Path(host_dir).is_absolute():
            raise ValueError(
                f"persistent_shares host_dir must be an absolute path, got {host_dir!r}"
            )
        if tag in seen_tags:
            raise ValueError(f"persistent_shares has a duplicate target tag {tag!r}")
        seen_tags.add(tag)

    domain = ET.Element("domain", {"type": "kvm", "xmlns:qemu": _QEMU_NS})
    ET.SubElement(domain, "name").text = spec.name
    ET.SubElement(domain, "memory", {"unit": "MiB"}).text = str(spec.ram_mib)
    ET.SubElement(domain, "currentMemory", {"unit": "MiB"}).text = str(spec.ram_mib)
    # virtio-fs (vhost-user) needs the guest RAM exposed as a shared mapping
    # so the virtiofsd helper can mmap it. Only emitted when there are shares,
    # so a no-share domain keeps its default (private) memory backing.
    if spec.persistent_shares:
        mem_backing = ET.SubElement(domain, "memoryBacking")
        ET.SubElement(mem_backing, "source", {"type": "memfd"})
        ET.SubElement(mem_backing, "access", {"mode": "shared"})
    ET.SubElement(domain, "vcpu").text = str(spec.vcpus)

    # firmware='efi' lets libvirt pick the OVMF descriptor and manage the
    # per-domain nvram copy. Win10 does not require Secure Boot, so plain
    # UEFI is enough (Win11 would need <loader secure='yes'> + smm).
    # Pin the plain (non-Secure-Boot) OVMF explicitly. Letting libvirt
    # auto-select via `firmware='efi'` picked the Secure Boot descriptor
    # (OVMF_CODE_4M.ms.fd, secure='yes'); a `<firmware><feature
    # secure-boot=no></firmware>` constraint instead matched the stateless
    # AMD-SEV build — both left a fresh install at UEFI "No bootable option"
    # (verified live 2026-07-01, A7-live). Win10 needs neither, so name the
    # plain OVMF directly; libvirt derives the per-domain nvram from the
    # template.
    os_el = ET.SubElement(domain, "os")
    ET.SubElement(os_el, "type", {"arch": "x86_64", "machine": "q35"}).text = "hvm"
    ET.SubElement(
        os_el, "loader", {"readonly": "yes", "type": "pflash"}
    ).text = spec.ovmf_code or _DEFAULT_OVMF_CODE
    ET.SubElement(
        os_el, "nvram", {"template": spec.ovmf_vars or _DEFAULT_OVMF_VARS}
    )
    # Boot order is set per-device below (<boot order=.../>), not here:
    # with UEFI + multiple SATA devices the global <os><boot> form left
    # OVMF with "no bootable option" — per-device order is reliable.

    features = ET.SubElement(domain, "features")
    ET.SubElement(features, "acpi")
    ET.SubElement(features, "apic")

    ET.SubElement(domain, "cpu", {"mode": "host-passthrough", "check": "none"})
    # Windows reads the RTC as local time; offset='utc' makes the clock skew.
    ET.SubElement(domain, "clock", {"offset": "localtime"})
    ET.SubElement(domain, "on_crash").text = "destroy"

    devices = ET.SubElement(domain, "devices")
    ET.SubElement(devices, "emulator").text = spec.emulator

    # Boot disk on SATA (DEC-0016: Windows Setup has no in-box virtio-blk).
    # boot order 2: the (empty) disk is only bootable after Setup installs.
    disk = ET.SubElement(devices, "disk", {"type": "file", "device": "disk"})
    ET.SubElement(disk, "driver", {"name": "qemu", "type": "qcow2", "discard": "unmap"})
    ET.SubElement(disk, "source", {"file": str(spec.disk_path)})
    ET.SubElement(disk, "target", {"dev": "sda", "bus": "sata"})
    ET.SubElement(disk, "boot", {"order": "2"})

    # sdb = Windows install media → C: source (boot order 1); sdc = tools
    # ISO → D:, which autounattend.xml's FirstLogonCommands read (not boot).
    for dev, iso, order in (
        ("sdb", spec.windows_iso, "1"),
        ("sdc", spec.tools_iso, None),
    ):
        cd = ET.SubElement(devices, "disk", {"type": "file", "device": "cdrom"})
        ET.SubElement(cd, "driver", {"name": "qemu", "type": "raw"})
        ET.SubElement(cd, "source", {"file": str(iso)})
        ET.SubElement(cd, "target", {"dev": dev, "bus": "sata"})
        if order is not None:
            ET.SubElement(cd, "boot", {"order": order})
        ET.SubElement(cd, "readonly")

    # NIC + host→guest RDP forward are added via <qemu:commandline> below.
    # libvirt's native <portForward> requires the passt backend; qemu's SLIRP
    # hostfwd works with no extra host package (DEC-0003: no root/bridge).

    # libvirt spawns + tears down swtpm itself (no manual socket daemon).
    tpm = ET.SubElement(devices, "tpm", {"model": "tpm-crb"})
    ET.SubElement(tpm, "backend", {"type": "emulator", "version": "2.0"})

    # AF_VSOCK control channel back to the host (guest CID fixed). Omitted
    # when /dev/vhost-vsock is not accessible — see DomainSpec.vsock_enabled.
    if spec.vsock_enabled:
        vsock = ET.SubElement(devices, "vsock", {"model": "virtio"})
        ET.SubElement(vsock, "cid", {"auto": "no", "address": str(spec.vsock_cid)})

    ET.SubElement(devices, "memballoon", {"model": "virtio"})

    # FS Stage B: persistent virtio-fs shares (host dir → guest), present from
    # domain start. accessmode='passthrough' maps host uid/gid through;
    # libvirt spawns the virtiofsd helper. <target dir='...'> is the virtio-fs
    # tag the guest mounts (WinFSP + VirtioFsSvc). Empty list → no devices.
    for tag, host_dir in spec.persistent_shares:
        fs = ET.SubElement(
            devices, "filesystem", {"type": "mount", "accessmode": "passthrough"}
        )
        ET.SubElement(fs, "driver", {"type": "virtiofs"})
        ET.SubElement(fs, "source", {"dir": host_dir})
        ET.SubElement(fs, "target", {"dir": tag})

    # Loopback VNC so the operator can watch the unattended install; plain
    # VGA so Windows Setup has a driver before any guest tools land.
    ET.SubElement(
        devices, "graphics", {"type": "vnc", "port": "-1", "listen": "127.0.0.1"}
    )
    video = ET.SubElement(devices, "video")
    ET.SubElement(video, "model", {"type": "vga"})
    ET.SubElement(devices, "input", {"type": "tablet", "bus": "usb"})

    # User-mode NIC with a host→guest RDP forward, via qemu's SLIRP hostfwd
    # (host 127.0.0.1:3389 → guest:3389). The literal "qemu:"-prefixed tags +
    # the xmlns:qemu on <domain> emit the libvirt qemu-commandline passthrough
    # without ElementTree's namespace machinery.
    cmd = ET.SubElement(domain, "qemu:commandline")
    for value in (
        "-netdev",
        "user,id=usernet0,hostfwd=tcp:127.0.0.1:3389-:3389",
        "-device",
        # e1000e, NOT virtio-net: Windows Setup/10 has no in-box virtio-net
        # driver (same reason the boot disk is SATA — DEC-0016), so a virtio
        # NIC leaves the guest with no network → no DHCP → RDP unreachable.
        # The Intel e1000e (82574) driver ships in-box. Explicit PCI slot:
        # qemu otherwise auto-picks 0x1, which libvirt gave to the VGA device.
        "e1000e,netdev=usernet0,bus=pcie.0,addr=0x0a",
    ):
        ET.SubElement(cmd, "qemu:arg", {"value": value})

    return ET.tostring(domain, encoding="unicode")
