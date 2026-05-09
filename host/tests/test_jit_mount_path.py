"""JIT VirtioFS path validation tests (Phase 5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from crossdesk_host.jit_mount import (
    MountPathError,
    parent_share_path,
    validate_mount_path,
)


def test_accepts_path_under_allowed_root(tmp_path: Path) -> None:
    inside = tmp_path / "Documents"
    inside.mkdir()
    result = validate_mount_path(str(inside), allowed_roots=[tmp_path])
    assert result.canonical == inside.resolve()


def test_rejects_relative_path(tmp_path: Path) -> None:
    with pytest.raises(MountPathError):
        validate_mount_path("Documents/foo", allowed_roots=[tmp_path])


def test_rejects_empty(tmp_path: Path) -> None:
    with pytest.raises(MountPathError):
        validate_mount_path("", allowed_roots=[tmp_path])


def test_rejects_path_outside_allowed_root(tmp_path: Path) -> None:
    other = tmp_path / "elsewhere"
    other.mkdir()
    with pytest.raises(MountPathError):
        validate_mount_path(str(other), allowed_roots=[tmp_path / "Documents"])


def test_rejects_traversal_escape(tmp_path: Path) -> None:
    inside = tmp_path / "Documents"
    inside.mkdir()
    with pytest.raises(MountPathError):
        validate_mount_path(
            str(inside / ".." / ".." / "etc"),
            allowed_roots=[tmp_path],
        )


def test_rejects_nonexistent_path(tmp_path: Path) -> None:
    with pytest.raises(MountPathError):
        validate_mount_path(
            str(tmp_path / "nope"),
            allowed_roots=[tmp_path],
        )


def test_rejects_denylisted_root(tmp_path: Path) -> None:
    """Even with allowed_roots=[/], a path under /proc should be blocked."""
    with pytest.raises(MountPathError):
        validate_mount_path("/proc/self", allowed_roots=[Path("/")])


def test_rejects_etc_paths(tmp_path: Path) -> None:
    with pytest.raises(MountPathError):
        validate_mount_path("/etc/passwd", allowed_roots=[Path("/")])


def test_resolves_symlink_to_canonical(tmp_path: Path) -> None:
    real = tmp_path / "real_dir"
    real.mkdir()
    link = tmp_path / "via_symlink"
    link.symlink_to(real)
    result = validate_mount_path(str(link), allowed_roots=[tmp_path])
    assert result.canonical == real.resolve()


def test_parent_share_path_returns_parent(tmp_path: Path) -> None:
    f = tmp_path / "Documents" / "spec.docx"
    assert parent_share_path(f) == tmp_path / "Documents"


def test_parent_share_path_rejects_relative() -> None:
    with pytest.raises(MountPathError):
        parent_share_path(Path("relative/file"))
