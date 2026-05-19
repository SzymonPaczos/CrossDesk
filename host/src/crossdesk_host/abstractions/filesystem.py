"""FilesystemController Protocol — host-side abstraction for virtiofs
share attach/detach operations.

Separates the Filesystem-service surface from the libvirt surface:
the real implementation just delegates into the libvirt controller,
but the abstraction lets tests inject a :class:`MockFilesystemController`
that tracks share state in-memory and supports failure injection
without touching libvirt.

Why two abstractions instead of one wide ``LibvirtController``: the
Filesystem servicer only ever needs the share-plumbing methods; the
heartbeat FSM only ever needs domain lifecycle. Keeping them separate
narrows the Protocol surface that each consumer parametrises over.
"""

from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable


@runtime_checkable
class FilesystemController(Protocol):
    """Virtiofs share lifecycle as seen by the host filesystem servicer.

    Methods are blocking (libvirt's bindings are synchronous); the
    servicer drives them from short-lived async tasks rather than the
    request loop. Both methods are idempotent — re-attach of an
    already-attached share, or re-detach of an unknown share, returns
    ``False`` and logs (or raises in the mock when failure-injection
    is enabled).
    """

    def attach_share(self, share_id: str, host_path: str) -> bool:
        """Hot-plug ``host_path`` as virtiofs share ``share_id``.

        Returns ``True`` on a fresh attach, ``False`` if ``share_id``
        was already attached (idempotent retry). Raises
        ``RuntimeError`` on a controller-side error.
        """
        ...

    def detach_share(self, share_id: str) -> bool:
        """Hot-unplug ``share_id``. Returns ``True`` on a successful
        detach, ``False`` if the share wasn't attached (idempotent).
        """
        ...

    def list_active_shares(self) -> Iterable[str]:
        """Snapshot the share IDs currently attached. Used by tests
        and by the ``crossdesk doctor`` probe in future work."""
        ...
