"""Path validation at the JIT mount boundary.

Phase 5 SPOF (ROADMAP): handshake ReleaseAck failures cause permanent
share leaks. Adjacent to that — and equally critical to the security
posture per docs/THREAT_MODEL.md TA3 — is the rule that the host MUST
NOT mount a path the user didn't intend.

This module is the choke point: every host path that enters the
``trigger_mount`` flow goes through :func:`validate_mount_path` first.
Rejection results are structured so the caller can return them as
gRPC errors / log them with reason codes.

Validation rules:
1. Path must be absolute.
2. Path must normalise to itself (no ``..`` traversal that resolves
   to a different physical location after symlink follow).
3. Path must live under one of the configured ``allowed_roots``.
4. Path must not be inside a deny-listed system root (``/proc``,
   ``/sys``, ``/dev``, ``/etc/shadow`` direct mount, etc.).
5. Path must exist (otherwise we'd be exposing a guest mount over
   nothing, surfacing weird errors on first access).

The default allowed_roots is ``[~]`` — the user's home directory.
Tests can override to drive edge cases.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_DEFAULT_DENYLIST: tuple[str, ...] = (
    "/proc",
    "/sys",
    "/dev",
    "/run",
    "/boot",
    "/etc",
)


class MountPathError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedMountPath:
    canonical: Path
    """Absolute, symlink-resolved path that survived validation. Use
    this for the actual virtiofs attach call rather than the original
    user-supplied string."""


def validate_mount_path(
    raw: str,
    allowed_roots: Optional[List[Path]] = None,
    denylist: tuple[str, ...] = _DEFAULT_DENYLIST,
) -> ValidatedMountPath:
    if not raw:
        raise MountPathError("empty path")
    if not raw.startswith("/"):
        raise MountPathError(f"path must be absolute (got {raw!r})")

    if allowed_roots is None:
        allowed_roots = [Path.home()]

    # Resolve symlinks so we catch a symlink chain that points at /etc.
    candidate = Path(raw)
    try:
        canonical = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise MountPathError(f"path does not exist: {raw}") from exc

    # Block denylist roots. Check both the lexical input and the
    # symlink-resolved canonical, because on macOS /etc is a symlink
    # to /private/etc — we need to reject the lexical /etc as well so
    # a user-readable error fires rather than a confusing "not under
    # /private/etc" message after resolution.
    canonical_str = str(canonical)
    raw_normalised = os.path.normpath(raw)
    for forbidden in denylist:
        for path_str in (raw_normalised, canonical_str):
            if path_str == forbidden or path_str.startswith(forbidden + "/"):
                raise MountPathError(
                    f"path under denylisted root {forbidden}: {raw}"
                )

    # Must be inside at least one allowed root after resolution.
    for root in allowed_roots:
        try:
            canonical.relative_to(root.resolve())
            break
        except ValueError:
            continue
    else:
        raise MountPathError(
            f"path {canonical} is not under any allowed root "
            f"({[str(r) for r in allowed_roots]})"
        )

    return ValidatedMountPath(canonical=canonical)


def parent_share_path(file_path: Path) -> Path:
    """Phase 5 minimal-path share: when the user opens
    ``/home/u/Documents/spec.docx`` we expose only the parent
    ``Documents/`` directory, not the entire home. Caller still must
    run :func:`validate_mount_path` on the result."""
    if not file_path.is_absolute():
        raise MountPathError(f"file_path must be absolute: {file_path}")
    return file_path.parent


def os_supports_resolve_strict() -> bool:
    """Path.resolve(strict=True) is available on all our supported
    Python versions (3.9+); function exists for symmetry with the
    Rust side which has its own canonicalisation."""
    return os.name == "posix"
