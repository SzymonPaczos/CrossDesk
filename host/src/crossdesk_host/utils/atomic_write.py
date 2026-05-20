"""Atomic file write via tempfile + fsync + rename.

Three callers previously had near-identical copies of this helper
(installer/settings.py, installer/state.py, recovery/snapshot.py).
Audit 2026-05-20 flagged the duplication; consolidating here keeps
the fsync semantics, the exception-safe cleanup, and the parent-dir
creation in one place.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, payload: str) -> None:
    """Write ``payload`` (UTF-8 text) to ``path`` atomically.

    Steps:
        1. ``mkdir -p`` the parent directory (idempotent).
        2. ``mkstemp`` a sibling ``<name>.<random>.tmp`` in the same
           directory so the eventual ``rename`` stays on a single
           filesystem (rename across mounts is not atomic).
        3. Write the payload, ``flush()`` + ``fsync()`` so the bytes
           actually hit disk before we publish the new inode.
        4. ``os.rename`` swaps the temp file into place.

    On any exception the temp file is unlinked best-effort and the
    original exception is re-raised — the caller never sees a partial
    file at ``path``. All three existing callers (installer settings,
    installer state, recovery snapshot) write JSON / TOML text, so
    UTF-8 string mode is the contract.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
