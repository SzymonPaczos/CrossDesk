"""Tests for the libvirt domain XML generator (DEC-0016)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from crossdesk_host.installer.domain_xml import DomainSpec, build_domain_xml


def _xml(**kw: object) -> ET.Element:
    spec = DomainSpec(
        name=kw.get("name", "windows-guest"),  # type: ignore[arg-type]
        disk_path=Path(kw.get("disk", "/var/lib/crossdesk/win.qcow2")),  # type: ignore[arg-type]
        windows_iso=Path(kw.get("iso", "/iso/Win10.iso")),  # type: ignore[arg-type]
        tools_iso=Path(kw.get("tools", "/iso/tools.iso")),  # type: ignore[arg-type]
        ram_mib=kw.get("ram", 4096),  # type: ignore[arg-type]
        vcpus=kw.get("vcpus", 4),  # type: ignore[arg-type]
        vsock_cid=kw.get("cid", 3),  # type: ignore[arg-type]
    )
    return ET.fromstring(build_domain_xml(spec))


def test_well_formed_kvm_domain() -> None:
    root = _xml()
    assert root.tag == "domain"
    assert root.get("type") == "kvm"
    assert root.findtext("name") == "windows-guest"
    assert root.findtext("memory") == "4096"
    assert root.findtext("vcpu") == "4"


def test_uefi_and_per_device_boot_order() -> None:
    root = _xml()
    os_el = root.find("os")
    assert os_el is not None and os_el.get("firmware") == "efi"
    assert os_el.findtext("type") == "hvm"
    # Boot order is per-device (UEFI + multi-SATA): Windows ISO first, disk
    # second, tools ISO not bootable. The global <os><boot> form is gone.
    assert os_el.findall("boot") == []
    disks = root.findall("devices/disk")
    boot_orders = {
        d.find("source").get("file"): (  # type: ignore[union-attr]
            d.find("boot").get("order") if d.find("boot") is not None else None  # type: ignore[union-attr]
        )
        for d in disks
    }
    assert boot_orders["/iso/Win10.iso"] == "1"
    assert boot_orders["/var/lib/crossdesk/win.qcow2"] == "2"
    assert boot_orders["/iso/tools.iso"] is None


def test_disk_is_sata_with_two_cdroms() -> None:
    # DEC-0016: SATA boot disk so Windows Setup sees it without virtio-win.
    root = _xml()
    disks = root.findall("devices/disk")
    assert len(disks) == 3  # 1 boot disk + Windows ISO + tools ISO
    buses = [d.find("target").get("bus") for d in disks]  # type: ignore[union-attr]
    assert buses == ["sata", "sata", "sata"]
    devices = [d.get("device") for d in disks]
    assert devices == ["disk", "cdrom", "cdrom"]
    sources = [d.find("source").get("file") for d in disks]  # type: ignore[union-attr]
    assert sources == ["/var/lib/crossdesk/win.qcow2", "/iso/Win10.iso", "/iso/tools.iso"]


def test_vsock_tpm_balloon_present() -> None:
    root = _xml(cid=7)
    assert root.find("devices/vsock/cid").get("address") == "7"  # type: ignore[union-attr]
    assert root.find("devices/tpm").get("model") == "tpm-crb"  # type: ignore[union-attr]
    assert root.find("devices/tpm/backend").get("type") == "emulator"  # type: ignore[union-attr]
    assert root.find("devices/memballoon").get("model") == "virtio"  # type: ignore[union-attr]
    # localtime clock or Windows skews.
    assert root.find("clock").get("offset") == "localtime"  # type: ignore[union-attr]


def test_rdp_port_forward_present() -> None:
    # Host 127.0.0.1:3389 → guest:3389 so the host's FreeRDP reaches the
    # guest RDP server over user-mode networking.
    root = _xml()
    pf = root.find("devices/interface/portForward")
    assert pf is not None and pf.get("proto") == "tcp"
    assert pf.get("address") == "127.0.0.1"
    rng = pf.find("range")
    assert rng.get("start") == "3389" and rng.get("to") == "3389"  # type: ignore[union-attr]


def test_vsock_omitted_when_disabled() -> None:
    # When /dev/vhost-vsock is inaccessible the install drops the device so
    # the VM still boots (DEC-0017); the XML must then carry no <vsock>.
    spec = DomainSpec(
        name="windows-guest",
        disk_path=Path("/d.qcow2"),
        windows_iso=Path("/w.iso"),
        tools_iso=Path("/t.iso"),
        vsock_enabled=False,
    )
    root = ET.fromstring(build_domain_xml(spec))
    assert root.find("devices/vsock") is None
    # The rest of the device set is intact.
    assert root.find("devices/tpm") is not None
    assert len(root.findall("devices/disk")) == 3


def test_paths_with_special_chars_are_escaped() -> None:
    # A path containing & must not break the XML (ElementTree escapes it).
    root = _xml(disk="/data/A & B/win.qcow2")
    src = root.find("devices/disk/source").get("file")  # type: ignore[union-attr]
    assert src == "/data/A & B/win.qcow2"
