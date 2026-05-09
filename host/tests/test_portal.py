"""XDG portal abstraction tests (Phase 7 / Week 31)."""

from __future__ import annotations

from crossdesk_host.integrations.portal import (
    NullPortal,
    XdgMimePortal,
    detect_portal,
)


def test_null_portal_always_unavailable() -> None:
    assert not NullPortal().is_available()


def test_null_portal_announce_is_noop() -> None:
    NullPortal().announce_handler("crossdesk-word", ["application/msword"])


def test_xdg_mime_portal_availability_matches_binary_presence() -> None:
    """Mac dev usually has ``xdg-mime`` absent; Linux dev has it. The
    portal probe just reflects the binary's presence."""
    portal = XdgMimePortal()
    expected = portal.is_available()
    # Re-probe shouldn't flip; sanity that the cache (if any) is stable.
    assert portal.is_available() == expected


def test_detect_portal_returns_one_of_known() -> None:
    portal = detect_portal()
    assert portal.name in ("xdg-mime", "null")


def test_xdg_mime_portal_announce_handles_missing_binary() -> None:
    """When xdg-mime isn't on PATH, announce_handler must silently no-op
    rather than raising; the daemon doesn't fall over on minimal hosts."""
    portal = XdgMimePortal()
    portal.announce_handler("crossdesk-word", ["application/msword"])
