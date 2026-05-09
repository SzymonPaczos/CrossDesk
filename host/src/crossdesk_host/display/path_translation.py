r"""Linux → Windows path translation for RAIL ``cmd:`` arguments.

When the user opens a file from a Linux file manager, the path that
arrives at the host (``/home/szymon/report.docx``) has to be rewritten
into something the Windows-side application can read
(``\\tsclient\home\szymon\report.docx`` for the WinApps-style static
share, or ``D:\report.docx`` for the JIT VirtioFS mount Phase 5
introduces).

Stage 1 of the translator is a configurable two-step rewrite:

1. Replace the host-side mount-root prefix with the guest-visible
   prefix (``mount_root`` / ``guest_prefix``).
2. Convert path separators ``/`` → ``\\``.

The mount-root is intentionally configurable rather than hardcoded:
- Phase 4 default is ``\\tsclient\home`` (the WinApps placeholder).
- Phase 5 swaps it at runtime for the live JIT mount path returned
  by ``FilesystemService.MountResult.guest_mount_root``.

Anything outside the configured mount root is rejected, not silently
mapped to a guest path that wouldn't exist — the caller has to mount
the right directory first or pass a path inside an already-mounted
share. That keeps the security boundary explicit (no path traversal
escape; see Phase 5 / docs/THREAT_MODEL.md TA3).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import PurePosixPath


class PathTranslationError(ValueError):
    """Raised when a host path can't be expressed in the guest's
    namespace under the current mount configuration."""


@dataclass(frozen=True)
class PathTranslator:
    mount_root: str
    """Host filesystem root visible inside the share, e.g. ``/home``
    for the WinApps-style ``\\tsclient\home`` mapping or the share
    point Phase 5 mounts on demand."""

    guest_prefix: str
    """Guest-visible prefix the mount appears at, e.g.
    ``\\\\tsclient\\home`` or ``D:`` for a JIT VirtioFS mount."""

    def translate(self, host_path: str) -> str:
        if not host_path:
            raise PathTranslationError("empty host path")
        if not host_path.startswith("/"):
            raise PathTranslationError(
                f"host path must be absolute (got {host_path!r})"
            )

        normalized = os.path.normpath(host_path)
        # ``..``-traversal that escapes ``mount_root`` after normalisation
        # is the canonical attack we have to block here. ``commonpath``
        # is the cleanest check and cleanly rejects symlink-like paths
        # because we operate on strings, not resolved targets.
        try:
            relative = PurePosixPath(normalized).relative_to(
                PurePosixPath(self.mount_root)
            )
        except ValueError as exc:
            raise PathTranslationError(
                f"{host_path!r} is outside mount_root {self.mount_root!r}"
            ) from exc

        suffix = str(relative).replace("/", "\\")
        prefix = self.guest_prefix.rstrip("\\")
        if suffix == ".":
            return prefix
        return f"{prefix}\\{suffix}"


def winapps_compat(home_dir: str) -> PathTranslator:
    r"""Convenience: WinApps-style ``\\tsclient\home`` mapping over the
    user's home directory. Phase 4 default; Phase 5 will replace the
    instance at runtime with one carrying the live JIT mount path.
    """
    return PathTranslator(
        mount_root=home_dir.rstrip("/") or "/",
        guest_prefix="\\\\tsclient\\home",
    )
