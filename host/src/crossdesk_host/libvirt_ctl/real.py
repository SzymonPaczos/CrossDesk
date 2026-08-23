"""Real libvirt controller — wraps ``libvirt-python`` against
``qemu:///session``. Linux-only; importable on Mac/Windows for type
checking but constructing it raises if ``libvirt`` is not installed.
"""

from __future__ import annotations

import logging
import uuid as _uuid
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Sequence
from xml.sax.saxutils import quoteattr

from crossdesk_host.abstractions.libvirt import LibvirtController

if TYPE_CHECKING:
    import libvirt as _libvirt_t

logger = logging.getLogger(__name__)


def _checked_share_id(share_id: str) -> str:
    """Boundary check for a virtiofs share tag before it reaches libvirt.

    Share IDs are minted host-side as ``uuid4()`` (``ipc/filesystem.py``), but
    the detach path is reached from a guest-supplied frame, so the value is
    validated here rather than trusted. Canonical form only — ``urn:uuid:``,
    braced and undashed spellings parse as UUIDs but are not what we emit, and
    accepting them would mean the tag we attach and the tag we detach can
    differ.
    """
    try:
        parsed = _uuid.UUID(share_id)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"share_id is not a UUID: {share_id!r}") from exc
    if str(parsed) != share_id.lower():
        raise ValueError(f"share_id is not in canonical UUID form: {share_id!r}")
    return share_id


def _virtiofs_attach_xml(share_id: str, host_path: str) -> str:
    """Device XML for a virtiofs hot-plug.

    Pure so the escaping is testable without libvirt — the alternative is a
    test that either needs a live domain or asserts against a copy of the
    format string, which proves nothing about what actually reaches libvirt.

    Attribute values are quoted rather than interpolated raw: a directory name
    may legally contain a quote or an angle bracket, and an f-string would let
    it close the attribute and append device XML of its own.
    """
    return (
        f"<filesystem type='mount' accessmode='passthrough'>"
        f"  <driver type='virtiofs'/>"
        f"  <source dir={quoteattr(host_path)}/>"
        f"  <target dir={quoteattr(_checked_share_id(share_id))}/>"
        f"</filesystem>"
    )


def _virtiofs_detach_xml(share_id: str) -> str:
    """Device XML for a virtiofs hot-unplug. libvirt matches by target tag, so
    the share_id is all that is needed — and it arrives from a guest frame, so
    it is checked, not trusted."""
    return (
        f"<filesystem type='mount'>"
        f"  <target dir={quoteattr(_checked_share_id(share_id))}/>"
        f"</filesystem>"
    )


def _with_domain_uuid(domain_xml: str, uuid: str) -> str:
    """Return *domain_xml* with a ``<uuid>`` child of ``<domain>`` set to *uuid*.

    Inserted right after ``<name>`` if absent (libvirt's canonical ordering),
    replaced if already present. Pure string→string so ``redefine_steady_state``
    can preserve the live domain's identity (making ``defineXML`` an in-place
    update, not a new domain) and stay unit-testable without libvirt.
    """
    root = ET.fromstring(domain_xml)
    existing = root.find("uuid")
    if existing is not None:
        existing.text = uuid
        return ET.tostring(root, encoding="unicode")
    uuid_el = ET.Element("uuid")
    uuid_el.text = uuid
    name_el = root.find("name")
    insert_at = list(root).index(name_el) + 1 if name_el is not None else 0
    root.insert(insert_at, uuid_el)
    return ET.tostring(root, encoding="unicode")


class RealLibvirtController(LibvirtController):
    """Drives a libvirt domain via ``virsh``-equivalent API calls.

    Connects on construction (lazy: the first method that needs the
    daemon establishes the connection). Failures from the daemon are
    re-raised as ``RuntimeError`` with the libvirt error string
    attached so the consumer can log and decide whether to back off.
    """

    def __init__(self, domain_name: str = "windows-guest") -> None:
        self.domain_name = domain_name
        self._conn: "_libvirt_t.virConnect | None" = None

    def _connect(self) -> "_libvirt_t.virConnect":
        if self._conn is not None:
            return self._conn
        try:
            import libvirt
        except ImportError as exc:
            raise RuntimeError(
                "libvirt-python is not installed; install with "
                "`pip install crossdesk-host[linux]` on a Linux host."
            ) from exc
        try:
            conn = libvirt.open("qemu:///session")
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"libvirt open failed: {exc}") from exc
        if conn is None:
            raise RuntimeError("libvirt.open returned None")
        self._conn = conn
        return conn

    def _domain(self) -> "_libvirt_t.virDomain":
        import libvirt

        try:
            return self._connect().lookupByName(self.domain_name)
        except libvirt.libvirtError as exc:
            raise RuntimeError(
                f"libvirt domain {self.domain_name!r} not found: {exc}"
            ) from exc

    def define_and_start(self, domain_xml: str) -> None:
        import libvirt

        conn = self._connect()
        logger.info("define_and_start: defineXML + create for %s", self.domain_name)
        # A prior definition (or a failed earlier attempt) would collide:
        # defineXML mints a fresh UUID each call, so libvirt rejects it as
        # "already exists with uuid <old>". Clear any existing domain of this
        # name first — UNDEFINE_NVRAM also drops the per-domain UEFI nvram so
        # a clean redefine works.
        try:
            existing = conn.lookupByName(self.domain_name)
        except libvirt.libvirtError:
            existing = None
        if existing is not None:
            try:
                if existing.isActive():
                    existing.destroy()
                existing.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_NVRAM)
            except libvirt.libvirtError as exc:
                raise RuntimeError(f"undefine existing domain failed: {exc}") from exc
        try:
            dom = conn.defineXML(domain_xml)
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"defineXML failed: {exc}") from exc
        if dom is None:
            raise RuntimeError("defineXML returned None")
        try:
            if not dom.isActive():
                dom.create()
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"domain create failed: {exc}") from exc

    def hard_destroy(self) -> None:
        import libvirt

        domain = self._domain()
        logger.warning("hard_destroy: virsh destroy %s", self.domain_name)
        try:
            domain.destroy()
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"destroy failed: {exc}") from exc
        logger.warning("hard_destroy: virsh start %s", self.domain_name)
        try:
            domain.create()
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"start after destroy failed: {exc}") from exc

    def start(self) -> None:
        import libvirt

        domain = self._domain()
        try:
            if domain.isActive():
                # Already back — most likely hard_destroy's own create() beat us
                # to it. Recovery must be safe to fire twice.
                return
            logger.warning("start: virsh start %s (recovery)", self.domain_name)
            domain.create()
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"start failed: {exc}") from exc

    def redefine_steady_state(self, domain_xml: str) -> None:
        import libvirt

        domain = self._domain()
        try:
            uuid = domain.UUIDString()
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"read domain uuid failed: {exc}") from exc
        # defineXML matches by <name>; without the live UUID libvirt would
        # reject (name exists with a different uuid) or mint a new domain.
        # Inject the existing UUID so this UPDATES the persistent config in
        # place. The running domain keeps its install-time definition until its
        # next boot — a later hard_destroy's create() then boots the installed
        # disk instead of re-running the installer.
        xml_with_uuid = _with_domain_uuid(domain_xml, uuid)
        conn = self._connect()
        logger.warning(
            "redefine_steady_state: defineXML (eject media, disk boot=1) for %s",
            self.domain_name,
        )
        try:
            dom = conn.defineXML(xml_with_uuid)
        except libvirt.libvirtError as exc:
            raise RuntimeError(
                f"redefine_steady_state defineXML failed: {exc}"
            ) from exc
        if dom is None:
            raise RuntimeError("redefine_steady_state defineXML returned None")

    def send_key(self, keycodes: Sequence[int]) -> None:
        import libvirt

        domain = self._domain()
        try:
            # codeset=LINUX, holdtime=0, keycodes, nkeycodes, flags=0
            domain.sendKey(libvirt.VIR_KEYCODE_SET_LINUX, 0, list(keycodes), len(keycodes), 0)
        except libvirt.libvirtError as exc:
            # Best-effort: the console may not accept input yet in early boot;
            # the caller sends a short burst so a single miss is harmless.
            logger.debug("send_key ignored (%s): %s", list(keycodes), exc)

    def graceful_shutdown(self) -> None:
        import libvirt

        domain = self._domain()
        logger.info("graceful_shutdown: virsh shutdown %s", self.domain_name)
        try:
            domain.shutdown()
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"shutdown failed: {exc}") from exc

    def undefine(self) -> None:
        import libvirt

        conn = self._connect()
        try:
            domain = conn.lookupByName(self.domain_name)
        except libvirt.libvirtError:
            # Idempotent: nothing to remove (already gone / never installed).
            logger.info("undefine: domain %s not found, nothing to do", self.domain_name)
            return
        try:
            if domain.isActive():
                logger.warning("undefine: virsh destroy %s", self.domain_name)
                domain.destroy()
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"destroy before undefine failed: {exc}") from exc
        # UNDEFINE_NVRAM drops the per-domain UEFI nvram (mirrors the cleanup in
        # define_and_start). No REMOVE_ALL_STORAGE — see the Protocol docstring:
        # our disk is removed with the state dir, and it would risk the user's ISO.
        logger.warning("undefine: virsh undefine %s", self.domain_name)
        try:
            domain.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_NVRAM)
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"undefine failed: {exc}") from exc

    def is_running(self) -> bool:
        import libvirt

        domain = self._domain()
        try:
            # virDomain.isActive returns 1 if running, 0 if defined-but-off.
            return bool(domain.isActive())
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"isActive failed: {exc}") from exc

    def suspend(self) -> None:
        import libvirt

        domain = self._domain()
        logger.info("suspend: virsh suspend %s", self.domain_name)
        try:
            domain.suspend()
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"suspend failed: {exc}") from exc

    def resume(self) -> None:
        import libvirt

        domain = self._domain()
        logger.info("resume: virsh resume %s", self.domain_name)
        try:
            domain.resume()
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"resume failed: {exc}") from exc

    def attach_virtiofs(self, share_id: str, host_path: str) -> bool:
        import libvirt

        # Built (and validated) before the domain lookup, so a bad share_id
        # never reaches libvirt at all.
        device_xml = _virtiofs_attach_xml(share_id, host_path)
        domain = self._domain()
        try:
            domain.attachDeviceFlags(
                device_xml,
                libvirt.VIR_DOMAIN_AFFECT_LIVE,
            )
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"attach_virtiofs({share_id!r}) failed: {exc}") from exc
        return True

    def detach_virtiofs(self, share_id: str) -> bool:
        import libvirt

        device_xml = _virtiofs_detach_xml(share_id)
        domain = self._domain()
        try:
            domain.detachDeviceFlags(
                device_xml,
                libvirt.VIR_DOMAIN_AFFECT_LIVE,
            )
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"detach_virtiofs({share_id!r}) failed: {exc}") from exc
        return True

    def set_memory(self, target_mib: int) -> None:
        import libvirt

        domain = self._domain()
        logger.info("set_memory: balloon target → %d MiB", target_mib)
        try:
            # virDomainSetMemory expects KiB
            domain.setMemory(target_mib * 1024)
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"set_memory({target_mib} MiB) failed: {exc}") from exc

    def get_memory_stats(self) -> dict[str, int]:
        import libvirt

        domain = self._domain()
        try:
            raw: dict[str, int] = domain.memoryStats()
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"get_memory_stats failed: {exc}") from exc
        # libvirt returns KiB; convert to MiB for consistent units
        return {k: v // 1024 for k, v in raw.items()}
