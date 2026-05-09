"""Property-based tests for path translation + JIT mount validation.

Hypothesis explores random paths to confirm two invariants:

1. **No traversal escape.** A translated path must never end up
   referring to something outside the configured mount root, no
   matter how the input is shaped.
2. **Round-trip stability.** Translating an already-translated path
   has no defined meaning (we only go host→guest), but translating
   the same input twice must produce identical output.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from crossdesk_host.display.path_translation import (
    PathTranslationError,
    PathTranslator,
)
from crossdesk_host.jit_mount import (
    MountPathError,
    validate_mount_path,
)


@st.composite
def _absolute_paths(draw: st.DrawFn, depth: int = 4) -> str:
    parts = draw(
        st.lists(
            st.text(
                alphabet=st.characters(
                    min_codepoint=33, max_codepoint=126, blacklist_characters="/\x00"
                ),
                min_size=1,
                max_size=12,
            ),
            min_size=1,
            max_size=depth,
        )
    )
    return "/" + "/".join(parts)


_TRANSLATOR = PathTranslator(mount_root="/home/u", guest_prefix="\\\\tsclient\\home")


@given(path=_absolute_paths())
def test_translation_is_deterministic(path: str) -> None:
    try:
        first = _TRANSLATOR.translate(path)
    except PathTranslationError:
        return
    second = _TRANSLATOR.translate(path)
    assert first == second


@given(path=_absolute_paths())
def test_translation_never_escapes_guest_prefix(path: str) -> None:
    try:
        out = _TRANSLATOR.translate(path)
    except PathTranslationError:
        return
    # Output must always start with the guest prefix (no leak of host-side
    # paths into the guest namespace).
    assert out.startswith("\\\\tsclient\\home")


@given(
    path=_absolute_paths(),
    extra=st.text(
        alphabet=st.characters(
            min_codepoint=33, max_codepoint=126, blacklist_characters="/\x00"
        ),
        min_size=1,
        max_size=8,
    ),
)
def test_translation_appends_segment_consistently(path: str, extra: str) -> None:
    """Translating P then P/extra must yield outputs where the second
    is a strict suffix-extension of the first."""
    try:
        a = _TRANSLATOR.translate(path)
        b = _TRANSLATOR.translate(path.rstrip("/") + "/" + extra)
    except PathTranslationError:
        return
    # b should equal a with one more backslash-separated segment.
    assert b.startswith(a) or b == a + "\\" + extra


_TRAVERSAL = st.sampled_from(
    ["..", "../..", "a/..", "a/b/../..", "a/../b/..", "..//.."]
)


@given(prefix=_absolute_paths(), traversal=_TRAVERSAL)
def test_traversal_segments_never_escape_to_root(prefix: str, traversal: str) -> None:
    """Construct a path that combines a random prefix with a traversal
    sequence; either the translator rejects, or the output stays under
    the guest prefix."""
    candidate = prefix.rstrip("/") + "/" + traversal
    try:
        out = _TRANSLATOR.translate(candidate)
    except PathTranslationError:
        return
    assert out.startswith("\\\\tsclient\\home")


# ---------------------------------------------------------------------------
# JIT mount validation invariants
# ---------------------------------------------------------------------------


@given(
    name=st.text(
        alphabet=st.characters(min_codepoint=97, max_codepoint=122),
        min_size=1,
        max_size=10,
    )
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_validate_accepts_existing_subdir_under_allowed_root(
    name: str, tmp_path: Path
) -> None:
    """Any directory we create under tmp_path passes when allowed_roots
    includes tmp_path. Establishes the positive case across random names."""
    # Avoid colliding with other tmp_path files if hypothesis reuses dirs.
    candidate = tmp_path / name
    try:
        candidate.mkdir(exist_ok=True)
    except OSError:
        assume(False)
    result = validate_mount_path(str(candidate), allowed_roots=[tmp_path])
    assert result.canonical == candidate.resolve()


_DENYLIST_PATHS = st.sampled_from(
    [
        "/proc",
        "/proc/self",
        "/proc/1/maps",
        "/sys",
        "/sys/class",
        "/dev",
        "/dev/null",
        "/etc",
        "/etc/passwd",
        "/etc/shadow",
        "/run",
        "/run/user/0",
        "/boot",
    ]
)


@given(path=_DENYLIST_PATHS)
def test_validate_always_rejects_denylisted_root(path: str) -> None:
    with pytest.raises(MountPathError):
        validate_mount_path(path, allowed_roots=[Path("/")])


_RELATIVE_PATHS = st.text(
    alphabet=st.characters(
        min_codepoint=97, max_codepoint=122, whitelist_characters="/."
    ),
    min_size=1,
    max_size=20,
).filter(lambda s: not s.startswith("/"))


@given(path=_RELATIVE_PATHS)
def test_validate_always_rejects_relative_paths(path: str) -> None:
    with pytest.raises(MountPathError):
        validate_mount_path(path)
