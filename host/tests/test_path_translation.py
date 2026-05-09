"""Path translation unit tests (Phase 4 / Week 8)."""

from __future__ import annotations

import pytest

from crossdesk_host.display.path_translation import (
    PathTranslationError,
    PathTranslator,
    winapps_compat,
)


def test_basic_translation_under_home() -> None:
    t = winapps_compat("/home/szymon")
    assert t.translate("/home/szymon/report.docx") == "\\\\tsclient\\home\\report.docx"


def test_subdirectory_translation() -> None:
    t = winapps_compat("/home/szymon")
    assert (
        t.translate("/home/szymon/Documents/spec.txt")
        == "\\\\tsclient\\home\\Documents\\spec.txt"
    )


def test_root_of_mount_returns_prefix() -> None:
    t = PathTranslator(mount_root="/data", guest_prefix="D:")
    assert t.translate("/data") == "D:"


def test_jit_style_mapping() -> None:
    t = PathTranslator(mount_root="/var/lib/crossdesk/mnt/abc", guest_prefix="E:")
    assert t.translate("/var/lib/crossdesk/mnt/abc/file.txt") == "E:\\file.txt"


def test_normalises_double_slashes() -> None:
    t = winapps_compat("/home/szymon")
    assert (
        t.translate("/home/szymon//deep///nested/file")
        == "\\\\tsclient\\home\\deep\\nested\\file"
    )


def test_rejects_path_outside_mount() -> None:
    t = winapps_compat("/home/szymon")
    with pytest.raises(PathTranslationError):
        t.translate("/etc/passwd")


def test_rejects_path_traversal_escape() -> None:
    t = winapps_compat("/home/szymon")
    with pytest.raises(PathTranslationError):
        t.translate("/home/szymon/../../etc/shadow")


def test_rejects_relative_path() -> None:
    t = winapps_compat("/home/szymon")
    with pytest.raises(PathTranslationError):
        t.translate("relative/file")


def test_rejects_empty_path() -> None:
    t = winapps_compat("/home/szymon")
    with pytest.raises(PathTranslationError):
        t.translate("")
