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
    fail_next_attach_virtiofs: bool = False
    fail_next_detach_virtiofs: bool = False

    hard_destroy_count: int = 0
    graceful_shutdown_count: int = 0
    attach_virtiofs_count: int = 0
    detach_virtiofs_count: int = 0

    attached_shares: set[str] = field(default_factory=set)
    """Shares currently attached. Tests assert this matches the
    expected state after a sequence of attach/detach calls."""


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

    def graceful_shutdown(self) -> None:
        if self.hooks.fail_next_graceful_shutdown:
            self.hooks.fail_next_graceful_shutdown = False
            raise RuntimeError("mock-injected graceful_shutdown failure")
        logger.warning(
            "[LIBVIRT MOCK] graceful_shutdown: virsh shutdown %s",
            self.domain_name,
        )
        self.hooks.graceful_shutdown_count += 1

    def attach_virtiofs(self, share_id: str, host_path: str) -> bool:
        if self.hooks.fail_next_attach_virtiofs:
            self.hooks.fail_next_attach_virtiofs = False
            raise RuntimeError(
                f"mock-injected attach_virtiofs({share_id!r}) failure"
            )
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
            raise RuntimeError(
                f"mock-injected detach_virtiofs({share_id!r}) failure"
            )
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
