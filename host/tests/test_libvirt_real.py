"""Pure helpers in the real libvirt controller.

``RealLibvirtController`` itself needs libvirt + a live ``qemu:///session``
(box-gated), but ``_with_domain_uuid`` is pure string→string and is the load-
bearing piece of ``redefine_steady_state``: it preserves the running domain's
UUID so ``defineXML`` updates the persistent config in place (not a new domain).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from crossdesk_host.libvirt_ctl.real import (
    _checked_share_id,
    _virtiofs_attach_xml,
    _virtiofs_detach_xml,
    _with_domain_uuid,
)

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


# ---------------------------------------------------------------------------
# virtiofs device XML — the share_id boundary check
#
# attach/detach build a <filesystem> device by string interpolation and hand it
# to libvirt. The detach side is reached from a guest-supplied frame, so the
# tag is validated rather than trusted, and both attribute values are quoted.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "s1' /><disk type='file'><source file='/etc/shadow'/></disk><x a='",
        "not-a-uuid",
        "",
        "urn:uuid:12345678-1234-1234-1234-1234567890ab",
        "{12345678-1234-1234-1234-1234567890ab}",
        "123456781234123412341234567890ab",
    ],
)
def test_share_id_that_is_not_a_canonical_uuid_is_rejected(bad: str) -> None:
    """Both device builders refuse it, so neither libvirt call can be reached
    with a tag the host did not mint."""
    with pytest.raises(ValueError):
        _checked_share_id(bad)
    with pytest.raises(ValueError):
        _virtiofs_attach_xml(bad, "/home/u/docs")
    with pytest.raises(ValueError):
        _virtiofs_detach_xml(bad)


def test_a_canonical_uuid_passes_unchanged() -> None:
    assert _checked_share_id(_UUID) == _UUID
    assert ET.fromstring(_virtiofs_detach_xml(_UUID)).find("target").get("dir") == _UUID  # type: ignore[union-attr]


def test_a_quote_in_a_shared_directory_name_cannot_close_the_attribute() -> None:
    """A directory may legally contain a quote; raw interpolation would let it
    terminate the source attribute and append device XML of the caller's
    choosing. Parsed back rather than string-matched, so the assertion is
    'this is one <filesystem> element with that literal dir', not 'the escape
    looks how I expected'."""
    hostile = "/home/u/we're '/><disk type='file'><source file='/etc/shadow'/><x y='"
    root = ET.fromstring(_virtiofs_attach_xml(_UUID, hostile))
    assert root.tag == "filesystem"
    assert root.find("source") is not None
    assert root.find("source").get("dir") == hostile  # type: ignore[union-attr]
    # No smuggled sibling survived the quoting.
    assert [child.tag for child in root] == ["driver", "source", "target"]
