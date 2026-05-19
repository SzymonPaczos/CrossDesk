"""Production :class:`FilesystemController` — thin shim over
:class:`LibvirtController` so the filesystem servicer doesn't depend
on libvirt directly.

The libvirt methods already implement the idempotent attach/detach
semantics; this wrapper just narrows the surface and tracks the
set of currently-attached share IDs so ``list_active_shares`` is
cheap.
"""

from __future__ import annotations

from typing import Iterable

from crossdesk_host.abstractions.filesystem import FilesystemController
from crossdesk_host.abstractions.libvirt import LibvirtController


class LibvirtFilesystemController(FilesystemController):
    def __init__(self, libvirt_ctl: LibvirtController) -> None:
        self._libvirt = libvirt_ctl
        self._attached: set[str] = set()

    def attach_share(self, share_id: str, host_path: str) -> bool:
        if share_id in self._attached:
            return False
        ok = self._libvirt.attach_virtiofs(share_id, host_path)
        if ok:
            self._attached.add(share_id)
        return ok

    def detach_share(self, share_id: str) -> bool:
        if share_id not in self._attached:
            return False
        ok = self._libvirt.detach_virtiofs(share_id)
        if ok:
            self._attached.discard(share_id)
        return ok

    def list_active_shares(self) -> Iterable[str]:
        return tuple(self._attached)
