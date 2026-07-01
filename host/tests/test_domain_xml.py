"""Tests for the libvirt domain XML generator (DEC-0016)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

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
    assert os_el is not None
    assert os_el.findtext("type") == "hvm"
    # Plain (non-Secure-Boot) OVMF pinned explicitly: libvirt's `firmware='efi'`
    # auto-selection picked Secure Boot / AMD-SEV builds that left a fresh
    # install at UEFI "No bootable option" (verified live 2026-07-01).
    loader = os_el.find("loader")
    assert loader is not None and loader.text == "/usr/share/OVMF/OVMF_CODE_4M.fd"
    assert loader.get("secure") != "yes"
    nvram = os_el.find("nvram")
    assert nvram is not None and nvram.get("template") == "/usr/share/OVMF/OVMF_VARS_4M.fd"
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


def test_rdp_host_forward_via_qemu_cmdline() -> None:
    # Host 127.0.0.1:3389 → guest:3389 via qemu SLIRP hostfwd (libvirt
    # <portForward> needs passt, which we don't require). NIC is the
    # qemu-commandline one, so no libvirt <interface> remains.
    xml = build_domain_xml(
        DomainSpec(
            name="windows-guest",
            disk_path=Path("/d.qcow2"),
            windows_iso=Path("/w.iso"),
            tools_iso=Path("/t.iso"),
        )
    )
    assert "xmlns:qemu=" in xml
    assert "hostfwd=tcp:127.0.0.1:3389-:3389" in xml
    # e1000e (in-box Win10 driver), not virtio-net (no in-box driver).
    assert "e1000e,netdev=usernet0" in xml
    assert "<interface" not in xml


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


def _spec_with_shares(shares: tuple[tuple[str, str], ...]) -> ET.Element:
    spec = DomainSpec(
        name="windows-guest",
        disk_path=Path("/d.qcow2"),
        windows_iso=Path("/w.iso"),
        tools_iso=Path("/t.iso"),
        persistent_shares=shares,
    )
    return ET.fromstring(build_domain_xml(spec))


def test_no_filesystem_or_memfd_without_shares() -> None:
    # FS Stage B is opt-in: a no-share domain keeps byte-identical XML — no
    # <memoryBacking> and no <filesystem>.
    root = _xml()
    assert root.find("memoryBacking") is None
    assert root.find("devices/filesystem") is None


def test_persistent_share_emits_virtiofs_filesystem() -> None:
    root = _spec_with_shares((("crossdesk-home", "/home/u"),))
    fs = root.find("devices/filesystem")
    assert fs is not None
    assert fs.get("type") == "mount"
    assert fs.get("accessmode") == "passthrough"
    assert fs.find("driver").get("type") == "virtiofs"  # type: ignore[union-attr]
    assert fs.find("source").get("dir") == "/home/u"  # type: ignore[union-attr]
    assert fs.find("target").get("dir") == "crossdesk-home"  # type: ignore[union-attr]


def test_persistent_shares_enable_shared_memfd_backing() -> None:
    # virtio-fs (vhost-user) requires shared guest memory.
    root = _spec_with_shares((("crossdesk-home", "/home/u"),))
    mb = root.find("memoryBacking")
    assert mb is not None
    assert mb.find("source").get("type") == "memfd"  # type: ignore[union-attr]
    assert mb.find("access").get("mode") == "shared"  # type: ignore[union-attr]


def test_multiple_persistent_shares_in_order() -> None:
    root = _spec_with_shares(
        (("share-a", "/home/u/a"), ("share-b", "/home/u/b"))
    )
    targets = [fs.find("target").get("dir") for fs in root.findall("devices/filesystem")]  # type: ignore[union-attr]
    assert targets == ["share-a", "share-b"]


def test_persistent_share_relative_path_rejected() -> None:
    # libvirt rejects a relative <source dir>; fail loudly at build time.
    with pytest.raises(ValueError, match="absolute path"):
        build_domain_xml(
            DomainSpec(
                name="windows-guest",
                disk_path=Path("/d.qcow2"),
                windows_iso=Path("/w.iso"),
                tools_iso=Path("/t.iso"),
                persistent_shares=(("tag", "relative/dir"),),
            )
        )


def test_persistent_share_duplicate_tag_rejected() -> None:
    # virtio-fs target tags must be unique within a domain.
    with pytest.raises(ValueError, match="duplicate target tag"):
        build_domain_xml(
            DomainSpec(
                name="windows-guest",
                disk_path=Path("/d.qcow2"),
                windows_iso=Path("/w.iso"),
                tools_iso=Path("/t.iso"),
                persistent_shares=(("dup", "/home/u/a"), ("dup", "/home/u/b")),
            )
        )
