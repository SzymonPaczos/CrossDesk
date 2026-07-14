"""Live, DESTRUCTIVE integration test for the steady-state recovery path.

This is the regression guard for MVP criterion #6, and it exists because that
criterion is otherwise only ever proven by a one-off manual run.

The bug it guards: the install XML keeps the Windows ISO on ``<boot order='1'>``
for the domain's whole life. Heartbeat-FSM recovery calls ``hard_destroy`` —
``destroy`` + ``create`` against the *persistent* config — so on a domain that was
never finalized, recovery re-boots the installer and ``autounattend.xml``
reinstalls Windows over the disk. Silent data loss, no human in the loop. The fix
is ``redefine_steady_state``: after the first agent Hello, rewrite the persistent
config so the disk boots first and both CD-ROMs are ejected.

Everything here runs against a **throwaway** domain with a random name, never
``windows-guest``. It is skipped unless ``--live-libvirt`` is passed:

    pytest tests/test_libvirt_real_destructive.py --live-libvirt
"""

from __future__ import annotations

import subprocess
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator, List, Optional

import pytest

from crossdesk_host.installer.domain_xml import (
    DomainSpec,
    build_domain_xml,
    build_steady_state_domain_xml,
    resolve_ovmf,
)
from crossdesk_host.libvirt_ctl.real import RealLibvirtController

pytestmark = pytest.mark.live_libvirt

PRODUCTION_DOMAIN = "windows-guest"

# Captured at import, before conftest's autouse guard swaps it out per test.
_REAL_CONNECT = RealLibvirtController._connect


@pytest.fixture
def unblocked_libvirt(
    _no_real_libvirt: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-open the choke point the suite-wide guard slams shut.

    conftest's ``_no_real_libvirt`` makes every ``RealLibvirtController._connect``
    raise, after a CLI test once undefined a developer's live ``windows-guest``.
    This test genuinely wants ``qemu:///session`` — it is the escape hatch that
    guard's own docstring describes. Requesting ``_no_real_libvirt`` by name
    forces our re-patch to land *after* it.
    """
    monkeypatch.setattr(RealLibvirtController, "_connect", _REAL_CONNECT)


@pytest.fixture
def throwaway(
    unblocked_libvirt: None, tmp_path: Path
) -> Iterator[RealLibvirtController]:
    """A controller bound to a domain that cannot possibly be the real one."""
    name = f"crossdesk-selftest-{uuid.uuid4().hex[:8]}"
    # Belt and braces. This fixture hands out a controller that will destroy and
    # undefine whatever it is pointed at, so make the name impossible to confuse.
    assert name != PRODUCTION_DOMAIN
    assert name.startswith("crossdesk-selftest-")

    ctl = RealLibvirtController(domain_name=name)
    try:
        yield ctl
    finally:
        # Never leave a domain behind, even if an assertion blew up mid-sequence.
        try:
            ctl.undefine()
        except Exception as exc:  # noqa: BLE001 — cleanup must not mask the failure
            print(f"cleanup: undefine({name}) failed: {exc}")


def _spec(tmp_path: Path, name: str) -> DomainSpec:
    """A minimal domain: it only has to exist and start, not boot anything."""
    disk = tmp_path / "throwaway.qcow2"
    subprocess.run(
        ["qemu-img", "create", "-f", "qcow2", str(disk), "64M"],
        check=True,
        capture_output=True,
    )
    # 1 MiB of zeros is enough for qemu to open them as CD-ROM media. UEFI finds
    # nothing bootable and drops to its shell — the domain is still *running*,
    # which is all this test needs.
    windows_iso = tmp_path / "windows.iso"
    tools_iso = tmp_path / "tools.iso"
    windows_iso.write_bytes(b"\0" * 1024 * 1024)
    tools_iso.write_bytes(b"\0" * 1024 * 1024)

    ovmf_code, ovmf_vars = resolve_ovmf()
    return DomainSpec(
        name=name,
        disk_path=disk,
        windows_iso=windows_iso,
        tools_iso=tools_iso,
        ram_mib=512,
        vcpus=1,
        # No vsock: the production domain pins CID 3, and this test must not
        # collide with it under any circumstances.
        vsock_enabled=False,
        ovmf_code=ovmf_code,
        ovmf_vars=ovmf_vars,
    )


def _xml(ctl: RealLibvirtController, *, persistent: bool) -> ET.Element:
    """Read the domain config back from libvirt itself — the oracle, not the SUT."""
    import libvirt

    conn = ctl._connect()
    dom = conn.lookupByName(ctl.domain_name)
    flags = libvirt.VIR_DOMAIN_XML_INACTIVE if persistent else 0
    return ET.fromstring(dom.XMLDesc(flags))


def _disks(root: ET.Element, device: str) -> List[ET.Element]:
    return [d for d in root.findall("./devices/disk") if d.get("device") == device]


def _boot_order(disk: ET.Element) -> Optional[str]:
    boot = disk.find("boot")
    return None if boot is None else boot.get("order")


def test_recovery_boots_the_disk_after_steady_state_redefine(
    throwaway: RealLibvirtController, tmp_path: Path
) -> None:
    """define_and_start → redefine_steady_state → hard_destroy → undefine.

    The assertion that matters is the one after ``hard_destroy``: the *running*
    domain must have booted the disk with the install media gone. That is exactly
    the property whose absence would silently reinstall Windows over a user's data.
    """
    ctl = throwaway
    spec = _spec(tmp_path, ctl.domain_name)

    # 1. Install-time shape — the installer boots first, as on a fresh install.
    ctl.define_and_start(build_domain_xml(spec, installed=False))
    assert ctl.is_running()

    persistent = _xml(ctl, persistent=True)
    assert any(_boot_order(cd) == "1" for cd in _disks(persistent, "cdrom")), (
        "the install-time config should boot the ISO first"
    )
    assert _boot_order(_disks(persistent, "disk")[0]) == "2"

    # 2. Finalize — what the first agent Hello triggers in production.
    ctl.redefine_steady_state(build_steady_state_domain_xml(spec))

    persistent = _xml(ctl, persistent=True)
    assert _boot_order(_disks(persistent, "disk")[0]) == "1"
    for cd in _disks(persistent, "cdrom"):
        assert cd.find("source") is None, "install media must be ejected"
        assert _boot_order(cd) is None

    # 3. Recovery — the exact call the heartbeat FSM makes on HARD_DESTROY.
    ctl.hard_destroy()
    assert ctl.is_running()

    live = _xml(ctl, persistent=False)
    assert _boot_order(_disks(live, "disk")[0]) == "1", (
        "recovery booted something other than the installed disk — this is the "
        "data-loss path: on a real guest it would re-run autounattend over the disk"
    )
    for cd in _disks(live, "cdrom"):
        assert cd.find("source") is None

    # 4. Clean removal — criterion #10's mechanism, on the same throwaway domain.
    ctl.undefine()
    with pytest.raises(RuntimeError, match="not found"):
        ctl.is_running()


def test_the_guard_still_blocks_real_libvirt_without_the_fixture() -> None:
    """The suite-wide choke point must stay shut for everything else.

    If this ever fails, the escape hatch above has leaked into the default run and
    an ordinary unit test can reach qemu:///session again — which is how a live
    windows-guest got undefined once already.
    """
    ctl = RealLibvirtController(domain_name="crossdesk-selftest-never-connected")
    with pytest.raises(RuntimeError, match="test reached real libvirt"):
        ctl.is_running()
