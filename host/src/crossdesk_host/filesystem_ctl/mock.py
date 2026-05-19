"""In-memory :class:`FilesystemController` for tests.

Tracks attached share IDs and the host-path each was bound to. The
``hooks`` dataclass exposes counters and failure-injection switches
so tests can assert on the sequence of calls and exercise the
error paths without touching libvirt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from crossdesk_host.abstractions.filesystem import FilesystemController


@dataclass
class MockFilesystemHooks:
    attached_pairs: List[tuple[str, str]] = field(default_factory=list)
    detached_ids: List[str] = field(default_factory=list)
    fail_next_attach: bool = False
    fail_next_detach: bool = False


class MockFilesystemController(FilesystemController):
    def __init__(self) -> None:
        self._shares: Dict[str, str] = {}
        self.hooks = MockFilesystemHooks()

    def attach_share(self, share_id: str, host_path: str) -> bool:
        if self.hooks.fail_next_attach:
            self.hooks.fail_next_attach = False
            raise RuntimeError(f"mock-injected attach failure for {share_id}")
        self.hooks.attached_pairs.append((share_id, host_path))
        if share_id in self._shares:
            return False
        self._shares[share_id] = host_path
        return True

    def detach_share(self, share_id: str) -> bool:
        if self.hooks.fail_next_detach:
            self.hooks.fail_next_detach = False
            raise RuntimeError(f"mock-injected detach failure for {share_id}")
        self.hooks.detached_ids.append(share_id)
        if share_id not in self._shares:
            return False
        del self._shares[share_id]
        return True

    def list_active_shares(self) -> Iterable[str]:
        return tuple(self._shares)

    def host_path_for(self, share_id: str) -> str:
        """Test helper: peek at the host-path a share was bound to."""
        return self._shares[share_id]
