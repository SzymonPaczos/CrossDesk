"""Pure helpers in the real libvirt controller.

``RealLibvirtController`` itself needs libvirt + a live ``qemu:///session``
(box-gated), but ``_with_domain_uuid`` is pure string→string and is the load-
bearing piece of ``redefine_steady_state``: it preserves the running domain's
UUID so ``defineXML`` updates the persistent config in place (not a new domain).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from crossdesk_host.libvirt_ctl.real import _with_domain_uuid

_UUID = "12345678-1234-1234-1234-1234567890ab"


def test_injects_uuid_after_name_when_absent() -> None:
    xml = "<domain type='kvm'><name>windows-guest</name><vcpu>4</vcpu></domain>"
    root = ET.fromstring(_with_domain_uuid(xml, _UUID))
    children = [c.tag for c in root]
    # <uuid> lands directly after <name> (libvirt's canonical ordering).
    assert children == ["name", "uuid", "vcpu"]
    assert root.findtext("uuid") == _UUID


def test_replaces_existing_uuid() -> None:
    xml = (
        "<domain type='kvm'><name>windows-guest</name>"
        "<uuid>old-uuid</uuid><vcpu>4</vcpu></domain>"
    )
    root = ET.fromstring(_with_domain_uuid(xml, _UUID))
    # Exactly one <uuid>, updated in place (no duplicate inserted).
    uuids = root.findall("uuid")
    assert len(uuids) == 1
    assert uuids[0].text == _UUID


def test_preserves_the_rest_of_the_domain() -> None:
    xml = (
        "<domain type='kvm'><name>windows-guest</name>"
        "<memory unit='MiB'>4096</memory></domain>"
    )
    root = ET.fromstring(_with_domain_uuid(xml, _UUID))
    assert root.get("type") == "kvm"
    assert root.findtext("name") == "windows-guest"
    assert root.findtext("memory") == "4096"
