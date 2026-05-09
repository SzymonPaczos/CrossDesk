"""JIT VirtioFS host-side helpers (Phase 5).

Pure-logic modules — the actual gRPC ShareChannel orchestration lives
in :mod:`crossdesk_host.ipc.filesystem`; this package adds the
security boundary (:mod:`path_validation`) and minimal-path share
computation."""

from crossdesk_host.jit_mount.path_validation import (
    MountPathError,
    ValidatedMountPath,
    parent_share_path,
    validate_mount_path,
)

__all__ = [
    "MountPathError",
    "ValidatedMountPath",
    "parent_share_path",
    "validate_mount_path",
]
