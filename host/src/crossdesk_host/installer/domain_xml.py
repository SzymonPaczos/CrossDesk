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

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# qemu's hard-coded host CID for AF_VSOCK is 2; the guest is assigned a
# distinct CID here (3 by convention, matching infra/launch-vm.py).
_DEFAULT_GUEST_CID = 3


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
    vsock_enabled: bool = True
    """Include the AF_VSOCK device. Disabled when ``/dev/vhost-vsock`` is
    not accessible to the qemu:///session process (a udev-rule / permission
    fix is required) — Windows installs fine without it; vsock only carries
    the post-install agent connection (DEC-0017)."""


def build_domain_xml(spec: DomainSpec) -> str:
    """Return the libvirt domain XML string for *spec*.

    Pure formatting — no I/O. ``ElementTree`` guarantees well-formed,
    attribute-escaped output (paths with ``&`` / quotes are handled).
    """
    domain = ET.Element("domain", {"type": "kvm"})
    ET.SubElement(domain, "name").text = spec.name
    ET.SubElement(domain, "memory", {"unit": "MiB"}).text = str(spec.ram_mib)
    ET.SubElement(domain, "currentMemory", {"unit": "MiB"}).text = str(spec.ram_mib)
    ET.SubElement(domain, "vcpu").text = str(spec.vcpus)

    # firmware='efi' lets libvirt pick the OVMF descriptor and manage the
    # per-domain nvram copy. Win10 does not require Secure Boot, so plain
    # UEFI is enough (Win11 would need <loader secure='yes'> + smm).
    os_el = ET.SubElement(domain, "os", {"firmware": "efi"})
    ET.SubElement(os_el, "type", {"arch": "x86_64", "machine": "q35"}).text = "hvm"
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

    # User-mode (SLIRP) networking — no root, no bridge setup (DEC-0003).
    iface = ET.SubElement(devices, "interface", {"type": "user"})
    ET.SubElement(iface, "model", {"type": "virtio"})
    # Forward host 127.0.0.1:3389 → guest:3389 so the host's FreeRDP can reach
    # the guest's RDP server (RemoteApp/RAIL) over user-mode networking,
    # which otherwise only routes guest→host.
    pf = ET.SubElement(iface, "portForward", {"proto": "tcp", "address": "127.0.0.1"})
    ET.SubElement(pf, "range", {"start": "3389", "to": "3389"})

    # libvirt spawns + tears down swtpm itself (no manual socket daemon).
    tpm = ET.SubElement(devices, "tpm", {"model": "tpm-crb"})
    ET.SubElement(tpm, "backend", {"type": "emulator", "version": "2.0"})

    # AF_VSOCK control channel back to the host (guest CID fixed). Omitted
    # when /dev/vhost-vsock is not accessible — see DomainSpec.vsock_enabled.
    if spec.vsock_enabled:
        vsock = ET.SubElement(devices, "vsock", {"model": "virtio"})
        ET.SubElement(vsock, "cid", {"auto": "no", "address": str(spec.vsock_cid)})

    ET.SubElement(devices, "memballoon", {"model": "virtio"})

    # Loopback VNC so the operator can watch the unattended install; plain
    # VGA so Windows Setup has a driver before any guest tools land.
    ET.SubElement(
        devices, "graphics", {"type": "vnc", "port": "-1", "listen": "127.0.0.1"}
    )
    video = ET.SubElement(devices, "video")
    ET.SubElement(video, "model", {"type": "vga"})
    ET.SubElement(devices, "input", {"type": "tablet", "bus": "usb"})

    return ET.tostring(domain, encoding="unicode")
