"""Libvirt controller Protocol — host-side abstraction for VM lifecycle
and virtiofs hot-plug operations.

The real implementation (``crossdesk_host.libvirt_ctl.real``) wraps
``libvirt-python`` (Linux-only). The mock (``crossdesk_host.libvirt_ctl.mock``)
is in-memory state with failure-injection hooks. Both implement this
Protocol so consumers (heartbeat FSM, filesystem service, future
installer) can be parameterised over it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LibvirtController(Protocol):
    """VM lifecycle + virtiofs hot-plug surface used by the host.

    Methods are deliberately blocking — libvirt-python's bindings are
    synchronous, and the consumer code (FSM transitions, virtiofs
    attach) drives them from background threads or short-lived async
    tasks rather than long-running event loops.

    Failure semantics: implementations raise ``RuntimeError`` on
    libvirt-side errors (or mock-injected ones); they do not return
    exception objects. Boolean returns on the virtiofs methods reflect
    "device was already in the requested state" (idempotent retries).
    """

    def hard_destroy(self) -> None:
        """Forceful kill+restart: ``virsh destroy`` then ``virsh start``."""
        ...

    def graceful_shutdown(self) -> None:
        """Polite shutdown: ``virsh shutdown`` (ACPI signal)."""
        ...

    def suspend(self) -> None:
        """Pause the running domain (``virsh suspend``). Heartbeat traffic
        will stop; the lifecycle layer must move the FSM into
        ``SUSPENDED`` first so misses across the pause don't trip
        false-positive HARD_DESTROY."""
        ...

    def resume(self) -> None:
        """Unpause the domain (``virsh resume``). Caller is responsible
        for re-handshaking AuthContext and moving the FSM out of
        ``SUSPENDED`` (typically into ``PROBING``)."""
        ...

    def attach_virtiofs(self, share_id: str, host_path: str) -> bool:
        """Hot-plug a virtiofs share. Returns ``True`` on success or
        if the share was already attached (idempotent)."""
        ...

    def detach_virtiofs(self, share_id: str) -> bool:
        """Hot-unplug a virtiofs share. Returns ``True`` on success or
        if the share was already detached (idempotent)."""
        ...

    def set_memory(self, target_mib: int) -> None:
        """Adjust the balloon target (virDomainSetMemory).

        ``target_mib`` must be ≤ the domain's maxMemory set at creation time.
        The balloon driver in the guest inflates/deflates to match; Windows
        releases or acquires the difference without a restart.

        No-op if the balloon device is not present in the domain config.
        Raises ``RuntimeError`` on libvirt error.
        """
        ...

    def get_memory_stats(self) -> dict[str, int]:
        """Query balloon statistics from the guest (virDomainMemoryStats).

        Returns a dict with MiB values for keys the balloon driver exposes:
        ``actual``, ``rss``, ``available``, ``unused``, ``usable``, etc.
        Empty dict if balloon stats are unavailable (driver not loaded in guest).
        """
        ...
