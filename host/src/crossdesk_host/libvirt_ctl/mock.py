"""Mock libvirt controller — in-memory state with failure-injection hooks.

Used everywhere the real libvirt is unavailable (Mac dev, CI matrix
without KVM, integration tests). Tracks attached/detached virtiofs
shares as a set so consumers can assert lifecycle invariants in tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crossdesk_host.abstractions.libvirt import LibvirtController

logger = logging.getLogger(__name__)


@dataclass
class MockHooks:
    """Knobs flipped by tests to drive deterministic failure scenarios.

    Each hook fires at most once per relevant call so a "fail next
    destroy" pattern is built by toggling between calls.
    """

    fail_next_hard_destroy: bool = False
    fail_next_graceful_shutdown: bool = False
    fail_next_suspend: bool = False
    fail_next_resume: bool = False
    fail_next_attach_virtiofs: bool = False
    fail_next_detach_virtiofs: bool = False
    fail_next_is_running: bool = False

    hard_destroy_count: int = 0
    graceful_shutdown_count: int = 0
    suspend_count: int = 0
    resume_count: int = 0
    attach_virtiofs_count: int = 0
    detach_virtiofs_count: int = 0
    is_running_count: int = 0
    suspended: bool = False

    attached_shares: set[str] = field(default_factory=set)
    """Shares currently attached. Tests assert this matches the
    expected state after a sequence of attach/detach calls."""

    memory_mib: int = 4096
    """Current balloon target in MiB. Adjusted by set_memory()."""

    running: bool = True
    """In-memory power state. ``graceful_shutdown`` only flips this
    after ``shutdown_polls_remaining`` calls to ``is_running`` (so
    tests can script "ACPI takes 3s" vs "ignores ACPI"). The flag is
    flipped back to ``True`` by ``hard_destroy`` (which performs a
    destroy+start) to mirror real libvirt semantics."""

    shutdown_polls_remaining: int = 0
    """Tests set this to N to make ``graceful_shutdown`` require N
    subsequent ``is_running`` polls before the domain reports off.
    Default 0 means the next poll already returns False (instant
    ACPI). Set to a large value to simulate a wedged guest that never
    honours ACPI."""


class LibvirtControllerMock(LibvirtController):
    """In-memory libvirt controller. No external side effects — just
    logs the requested operation and updates internal counters.

    The class-level docstring lists the consumers this mock has stood
    in for since 2026-04: the heartbeat FSM (hard_destroy,
    graceful_shutdown), the filesystem service (attach/detach virtiofs),
    and the daemon entry point.
    """

    def __init__(self, domain_name: str = "windows-guest") -> None:
        self.domain_name = domain_name
        self.hooks = MockHooks()

    def hard_destroy(self) -> None:
        if self.hooks.fail_next_hard_destroy:
            self.hooks.fail_next_hard_destroy = False
            raise RuntimeError("mock-injected hard_destroy failure")
        logger.critical(
            "[LIBVIRT MOCK] hard_destroy: virsh destroy %s + virsh start %s",
            self.domain_name,
            self.domain_name,
        )
        self.hooks.hard_destroy_count += 1
        # Real virsh destroy+start leaves the domain running again;
        # mirror that so subsequent is_running() observations agree.
        self.hooks.running = True
        self.hooks.shutdown_polls_remaining = 0

    def graceful_shutdown(self) -> None:
        if self.hooks.fail_next_graceful_shutdown:
            self.hooks.fail_next_graceful_shutdown = False
            raise RuntimeError("mock-injected graceful_shutdown failure")
        logger.warning(
            "[LIBVIRT MOCK] graceful_shutdown: virsh shutdown %s",
            self.domain_name,
        )
        self.hooks.graceful_shutdown_count += 1
        # ``shutdown_polls_remaining`` is the caller's pre-set knob;
        # don't reset it here. ``is_running`` decrements until 0, at
        # which point the domain reports off.

    def is_running(self) -> bool:
        if self.hooks.fail_next_is_running:
            self.hooks.fail_next_is_running = False
            raise RuntimeError("mock-injected is_running failure")
        self.hooks.is_running_count += 1
        if not self.hooks.running:
            return False
        if self.hooks.shutdown_polls_remaining > 0:
            self.hooks.shutdown_polls_remaining -= 1
            if self.hooks.shutdown_polls_remaining == 0:
                self.hooks.running = False
            return True
        # No pending shutdown countdown: report the persistent flag.
        return self.hooks.running

    def suspend(self) -> None:
        if self.hooks.fail_next_suspend:
            self.hooks.fail_next_suspend = False
            raise RuntimeError("mock-injected suspend failure")
        logger.info("[LIBVIRT MOCK] suspend: virsh suspend %s", self.domain_name)
        self.hooks.suspended = True
        self.hooks.suspend_count += 1

    def resume(self) -> None:
        if self.hooks.fail_next_resume:
            self.hooks.fail_next_resume = False
            raise RuntimeError("mock-injected resume failure")
        logger.info("[LIBVIRT MOCK] resume: virsh resume %s", self.domain_name)
        self.hooks.suspended = False
        self.hooks.resume_count += 1

    def attach_virtiofs(self, share_id: str, host_path: str) -> bool:
        if self.hooks.fail_next_attach_virtiofs:
            self.hooks.fail_next_attach_virtiofs = False
            raise RuntimeError(f"mock-injected attach_virtiofs({share_id!r}) failure")
        if share_id in self.hooks.attached_shares:
            logger.info(
                "[LIBVIRT MOCK] attach_virtiofs: %s already attached",
                share_id,
            )
            return True
        logger.info(
            "[LIBVIRT MOCK] attach_virtiofs: virsh attach-device %s for %s -> %s",
            self.domain_name,
            share_id,
            host_path,
        )
        self.hooks.attached_shares.add(share_id)
        self.hooks.attach_virtiofs_count += 1
        return True

    def detach_virtiofs(self, share_id: str) -> bool:
        if self.hooks.fail_next_detach_virtiofs:
            self.hooks.fail_next_detach_virtiofs = False
            raise RuntimeError(f"mock-injected detach_virtiofs({share_id!r}) failure")
        if share_id not in self.hooks.attached_shares:
            logger.info(
                "[LIBVIRT MOCK] detach_virtiofs: %s not attached, no-op",
                share_id,
            )
            return True
        logger.info(
            "[LIBVIRT MOCK] detach_virtiofs: virsh detach-device %s for %s",
            self.domain_name,
            share_id,
        )
        self.hooks.attached_shares.discard(share_id)
        self.hooks.detach_virtiofs_count += 1
        return True

    def set_memory(self, target_mib: int) -> None:
        logger.info(
            "[LIBVIRT MOCK] set_memory: %d MiB (was %d MiB)",
            target_mib,
            self.hooks.memory_mib,
        )
        self.hooks.memory_mib = target_mib

    def get_memory_stats(self) -> dict[str, int]:
        return {
            "actual": self.hooks.memory_mib,
            "available": self.hooks.memory_mib,
        }
