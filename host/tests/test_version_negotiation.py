"""Version negotiation tests (DEC-0007 N-1 minor compat window)."""

from __future__ import annotations

import pytest

from crossdesk_host.ipc.version_negotiation import (
    ParsedVersion,
    VersionParseError,
    is_compatible,
    negotiate_features,
)


def test_parse_strips_v_prefix() -> None:
    assert ParsedVersion.parse("v1.2.3") == ParsedVersion(1, 2, 3)
    assert ParsedVersion.parse("1.2.3") == ParsedVersion(1, 2, 3)


def test_parse_rejects_garbage() -> None:
    with pytest.raises(VersionParseError):
        ParsedVersion.parse("not-a-version")


def test_compat_same_version() -> None:
    assert is_compatible("v0.1.0", "v0.1.0").accepted


def test_compat_minor_off_by_one() -> None:
    assert is_compatible("v0.1.0", "v0.2.0").accepted
    assert is_compatible("v0.2.0", "v0.1.0").accepted


def test_compat_minor_off_by_two_rejected() -> None:
    result = is_compatible("v0.1.0", "v0.3.0")
    assert not result.accepted
    assert "minor" in result.reason


def test_compat_major_mismatch_rejected() -> None:
    result = is_compatible("v0.1.0", "v1.1.0")
    assert not result.accepted
    assert "major" in result.reason


def test_compat_invalid_input_rejected() -> None:
    result = is_compatible("garbage", "v0.1.0")
    assert not result.accepted


def test_negotiate_features_intersects() -> None:
    assert negotiate_features(["rail.v1", "virtiofs.jit"], ["rail.v1", "audio.v1"]) == [
        "rail.v1"
    ]


def test_negotiate_features_empty_intersection() -> None:
    assert negotiate_features(["a"], ["b"]) == []


def test_negotiate_features_sorted_output() -> None:
    assert negotiate_features(["zebra", "alpha", "mid"], ["mid", "alpha", "zebra"]) == [
        "alpha",
        "mid",
        "zebra",
    ]
