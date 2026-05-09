"""Property-based tests for version negotiation (DEC-0007)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from crossdesk_host.ipc.version_negotiation import (
    ParsedVersion,
    is_compatible,
    negotiate_features,
)

_INTS = st.integers(min_value=0, max_value=2**31 - 1)


@given(major=_INTS, minor=_INTS, patch=_INTS)
def test_parse_round_trip_unprefixed(major: int, minor: int, patch: int) -> None:
    parsed = ParsedVersion.parse(f"{major}.{minor}.{patch}")
    assert parsed == ParsedVersion(major, minor, patch)


@given(major=_INTS, minor=_INTS, patch=_INTS)
def test_parse_round_trip_v_prefixed(major: int, minor: int, patch: int) -> None:
    parsed = ParsedVersion.parse(f"v{major}.{minor}.{patch}")
    assert parsed == ParsedVersion(major, minor, patch)


@given(major=_INTS, minor=_INTS, patch=_INTS)
def test_same_version_always_compatible(major: int, minor: int, patch: int) -> None:
    raw = f"{major}.{minor}.{patch}"
    assert is_compatible(raw, raw).accepted


@given(
    major=_INTS,
    minor_a=_INTS,
    minor_b=_INTS,
    patch_a=_INTS,
    patch_b=_INTS,
)
def test_minor_distance_within_one_compatible(
    major: int, minor_a: int, minor_b: int, patch_a: int, patch_b: int
) -> None:
    """Same major + |minor_a - minor_b| <= 1 → accepted, regardless
    of patch level."""
    a = f"{major}.{minor_a}.{patch_a}"
    b = f"{major}.{minor_b}.{patch_b}"
    expected = abs(minor_a - minor_b) <= 1
    assert is_compatible(a, b).accepted == expected


@given(
    major_a=_INTS,
    major_b=_INTS,
    minor=_INTS,
)
def test_major_mismatch_always_rejected(major_a: int, major_b: int, minor: int) -> None:
    if major_a == major_b:
        return
    a = f"{major_a}.{minor}.0"
    b = f"{major_b}.{minor}.0"
    assert not is_compatible(a, b).accepted


_FEATURE_NAMES = st.text(
    alphabet=st.characters(
        min_codepoint=97, max_codepoint=122, whitelist_characters="."
    ),
    min_size=1,
    max_size=10,
)


@given(
    host=st.lists(_FEATURE_NAMES, max_size=10),
    client=st.lists(_FEATURE_NAMES, max_size=10),
)
def test_negotiate_returns_only_intersection(
    host: list[str], client: list[str]
) -> None:
    result = negotiate_features(host, client)
    host_set = set(host)
    client_set = set(client)
    expected = sorted(host_set & client_set)
    assert result == expected


@given(features=st.lists(_FEATURE_NAMES, max_size=10))
def test_negotiate_with_empty_other_returns_empty(features: list[str]) -> None:
    assert negotiate_features(features, []) == []
    assert negotiate_features([], features) == []


@given(features=st.lists(_FEATURE_NAMES, max_size=10))
def test_negotiate_is_commutative(features: list[str]) -> None:
    same_set = list(features) + ["common"]
    a = negotiate_features(features, same_set)
    b = negotiate_features(same_set, features)
    assert a == b
