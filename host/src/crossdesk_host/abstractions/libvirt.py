"""Libvirt controller Protocol — host-side abstraction for VM lifecycle
and virtiofs hot-plug operations.

The real implementation (``crossdesk_host.libvirt_ctl.real``) wraps
``libvirt-python`` (Linux-only). The mock (``crossdesk_host.libvirt_ctl.mock``)
is in-memory state with failure-injection hooks. Both implement this
Protocol so consumers (heartbeat FSM, filesystem service, future
installer) can be parameterised over it.
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable


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

    def define_and_start(self, domain_xml: str) -> None:
        """Define a persistent domain from *domain_xml* and start it.

        Used once by ``crossdesk install`` to bring the guest into
        existence (DEC-0016). Redefining the same ``<name>`` updates the
        config; if the domain is already running the start is a no-op.
        Raises ``RuntimeError`` on libvirt error.
        """
        ...

    def send_key(self, keycodes: Sequence[int]) -> None:
        """Inject key presses into the guest console (Linux keycodes).

        Used by ``crossdesk install`` to satisfy the "Press any key to boot
        from CD or DVD" prompt on the first boot of a fresh install — the
        Windows installer media waits for a keystroke and an unattended
        install has no human to provide one. Best-effort: swallow the
        transient libvirt error raised while the guest console isn't ready
        for input yet (the caller sends a short burst to cover the window).
        """
        ...

    def hard_destroy(self) -> None:
        """Forceful kill+restart: ``virsh destroy`` then ``virsh start``."""
        ...

    def redefine_steady_state(self, domain_xml: str) -> None:
        """Overwrite the PERSISTENT domain config with post-install steady-state
        XML (installed disk on ``<boot order='1'>``, install media ejected).

        Called once after the first successful agent Hello. Critical: the
        install-time definition keeps the Windows ISO on ``<boot order='1'>``
        for the VM's whole life, so a later ``hard_destroy`` (destroy+create)
        would boot the installer and reinstall over the disk — data loss. This
        rewrites the persistent definition (``defineXML`` with the live domain's
        UUID preserved, so it updates in place instead of minting a new domain)
        so every future ``create`` boots the installed disk. The running domain
        is untouched until its next boot. Raises ``RuntimeError`` on libvirt
        error. Build the XML via
        ``installer.domain_xml.build_steady_state_domain_xml``.
        """
        ...

    def graceful_shutdown(self) -> None:
        """Polite shutdown: ``virsh shutdown`` (ACPI signal)."""
        ...

    def is_running(self) -> bool:
        """Return ``True`` if the domain is currently in a running state.

        Used by the shutdown CLI to poll for ACPI completion: after
        ``graceful_shutdown()`` the guest takes seconds to finish its
        shutdown sequence, and ``is_running()`` returning ``False`` is
        the signal the CLI uses to declare the shutdown clean.

        Real impl wraps ``virDomain.isActive()`` (1 == running, 0 ==
        defined-but-off). Raises ``RuntimeError`` on libvirt errors.
        """
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
