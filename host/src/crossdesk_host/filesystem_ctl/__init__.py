"""FilesystemController implementations.

- :class:`LibvirtFilesystemController` — production: wraps the
  underlying :class:`LibvirtController` so the existing
  ``attach_virtiofs`` / ``detach_virtiofs`` semantics are reused
  without the servicer learning about libvirt.
- :class:`MockFilesystemController` — in-memory state for unit
  tests; tracks attaches/detaches in a set, supports
  failure-injection.
"""

from __future__ import annotations

from crossdesk_host.filesystem_ctl.mock import MockFilesystemController
from crossdesk_host.filesystem_ctl.real import LibvirtFilesystemController

__all__ = ["LibvirtFilesystemController", "MockFilesystemController"]
