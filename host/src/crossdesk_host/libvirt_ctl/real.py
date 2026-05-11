"""Real libvirt controller — wraps ``libvirt-python`` against
``qemu:///session``. Linux-only; importable on Mac/Windows for type
checking but constructing it raises if ``libvirt`` is not installed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from crossdesk_host.abstractions.libvirt import LibvirtController

if TYPE_CHECKING:
    import libvirt as _libvirt_t

logger = logging.getLogger(__name__)


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

    def graceful_shutdown(self) -> None:
        import libvirt

        domain = self._domain()
        logger.info("graceful_shutdown: virsh shutdown %s", self.domain_name)
        try:
            domain.shutdown()
        except libvirt.libvirtError as exc:
            raise RuntimeError(f"shutdown failed: {exc}") from exc

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

        domain = self._domain()
        device_xml = (
            f"<filesystem type='mount' accessmode='passthrough'>"
            f"  <driver type='virtiofs'/>"
            f"  <source dir='{host_path}'/>"
            f"  <target dir='{share_id}'/>"
            f"</filesystem>"
        )
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

        domain = self._domain()
        # libvirt detach matches by target tag, so we only need the
        # share_id to identify which device to remove.
        device_xml = (
            f"<filesystem type='mount'>"
            f"  <target dir='{share_id}'/>"
            f"</filesystem>"
        )
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
