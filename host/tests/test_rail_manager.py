"""Idempotency and ghost-window tests for RailManager.

ROADMAP Phase 4 SPOF: drift between HWND and Linux window state must not produce
ghost windows or orphaned processes. These tests pin the rules: CREATE registers
exactly one window, repeat CREATE for the same HWND is a no-op (warns), DESTROY
on unknown HWND is silent, MOVE on unknown HWND is rejected (warns).
"""

from __future__ import annotations

import logging

import pytest

from crossdesk_host.display.rail_manager import RailManager
from crossdesk_host.proto.crossdesk.v1 import control_pb2

Kind = control_pb2.RailWindowEvent.Kind


def _event(
    hwnd: int,
    kind: int,
    *,
    title: str = "",
    x: int = 0,
    y: int = 0,
    w: int = 0,
    h: int = 0,
) -> control_pb2.RailWindowEvent:
    return control_pb2.RailWindowEvent(
        window_id=hwnd,
        kind=kind,
        title=title,
        geometry=control_pb2.Rect(x=x, y=y, width=w, height=h),
    )


@pytest.fixture
def mgr() -> RailManager:
    return RailManager()


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------


def test_create_registers_window_with_geometry(mgr: RailManager) -> None:
    mgr.handle_rail_event(
        _event(0xABC, Kind.KIND_CREATED, title="Notepad", x=10, y=20, w=800, h=600)
    )
    win = mgr._windows[0xABC]
    assert win["title"] == "Notepad"
    assert win["x"] == 10 and win["y"] == 20
    assert win["width"] == 800 and win["height"] == 600


def test_create_uses_unnamed_when_title_missing(mgr: RailManager) -> None:
    mgr.handle_rail_event(_event(0x1, Kind.KIND_CREATED))
    assert mgr._windows[0x1]["title"] == "<unnamed>"


def test_duplicate_create_is_idempotent(
    mgr: RailManager, caplog: pytest.LogCaptureFixture
) -> None:
    """Second CREATE for same HWND must NOT clobber the original entry."""
    mgr.handle_rail_event(_event(0xAA, Kind.KIND_CREATED, title="First", w=100, h=100))
    with caplog.at_level(logging.WARNING):
        mgr.handle_rail_event(
            _event(0xAA, Kind.KIND_CREATED, title="Second", w=999, h=999)
        )
    assert mgr._windows[0xAA]["title"] == "First"
    assert mgr._windows[0xAA]["width"] == 100
    assert any("already exists" in r.message for r in caplog.records)


def test_multiple_windows_tracked_independently(mgr: RailManager) -> None:
    mgr.handle_rail_event(_event(0x1, Kind.KIND_CREATED, title="A"))
    mgr.handle_rail_event(_event(0x2, Kind.KIND_CREATED, title="B"))
    assert set(mgr._windows.keys()) == {0x1, 0x2}
    assert mgr._windows[0x1]["title"] == "A"
    assert mgr._windows[0x2]["title"] == "B"


# ---------------------------------------------------------------------------
# DESTROY
# ---------------------------------------------------------------------------


def test_destroy_removes_window(mgr: RailManager) -> None:
    mgr.handle_rail_event(_event(0x1, Kind.KIND_CREATED))
    mgr.handle_rail_event(_event(0x1, Kind.KIND_DESTROYED))
    assert 0x1 not in mgr._windows


def test_destroy_unknown_hwnd_is_silent_noop(mgr: RailManager) -> None:
    """A DESTROY without preceding CREATE is the 'lost CREATE' case from
    ROADMAP — must not raise."""
    mgr.handle_rail_event(_event(0xDEAD, Kind.KIND_DESTROYED))  # no exception


# ---------------------------------------------------------------------------
# MOVED / RESIZED
# ---------------------------------------------------------------------------


def test_moved_updates_geometry_in_place(mgr: RailManager) -> None:
    mgr.handle_rail_event(_event(0x1, Kind.KIND_CREATED, x=0, y=0, w=100, h=100))
    mgr.handle_rail_event(_event(0x1, Kind.KIND_MOVED, x=50, y=60, w=200, h=300))
    win = mgr._windows[0x1]
    assert (win["x"], win["y"], win["width"], win["height"]) == (50, 60, 200, 300)


def test_resized_uses_same_path_as_moved(mgr: RailManager) -> None:
    mgr.handle_rail_event(_event(0x1, Kind.KIND_CREATED, w=100, h=100))
    mgr.handle_rail_event(_event(0x1, Kind.KIND_RESIZED, w=400, h=500))
    assert mgr._windows[0x1]["width"] == 400
    assert mgr._windows[0x1]["height"] == 500


def test_moved_for_unknown_hwnd_warns_and_does_not_create(
    mgr: RailManager, caplog: pytest.LogCaptureFixture
) -> None:
    """Moving a ghost window must NOT silently spawn an entry."""
    with caplog.at_level(logging.WARNING):
        mgr.handle_rail_event(_event(0xBEEF, Kind.KIND_MOVED, x=10, y=10))
    assert 0xBEEF not in mgr._windows
    assert any("ghost window" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# FOCUS / TITLE
# ---------------------------------------------------------------------------


def test_title_changed_updates_label(mgr: RailManager) -> None:
    mgr.handle_rail_event(_event(0x1, Kind.KIND_CREATED, title="Untitled"))
    mgr.handle_rail_event(
        _event(0x1, Kind.KIND_TITLE_CHANGED, title="document.txt — Notepad")
    )
    assert mgr._windows[0x1]["title"] == "document.txt — Notepad"


def test_title_change_for_unknown_hwnd_is_noop(mgr: RailManager) -> None:
    mgr.handle_rail_event(_event(0xBEEF, Kind.KIND_TITLE_CHANGED, title="ignored"))
    assert 0xBEEF not in mgr._windows


def test_focus_event_for_unknown_hwnd_is_noop(mgr: RailManager) -> None:
    mgr.handle_rail_event(_event(0xBEEF, Kind.KIND_FOCUS_GAINED))
    assert 0xBEEF not in mgr._windows


def test_destroy_then_recreate_works(mgr: RailManager) -> None:
    """Reusing an HWND after DESTROY must succeed (not blocked by stale entry)."""
    mgr.handle_rail_event(_event(0x1, Kind.KIND_CREATED, title="v1"))
    mgr.handle_rail_event(_event(0x1, Kind.KIND_DESTROYED))
    mgr.handle_rail_event(_event(0x1, Kind.KIND_CREATED, title="v2"))
    assert mgr._windows[0x1]["title"] == "v2"


# ---------------------------------------------------------------------------
# FreeRDP session lifecycle (Week 9: idempotent termination)
# ---------------------------------------------------------------------------


def test_destroy_terminates_freerdp_session() -> None:
    """If a session was registered for the HWND, DESTROY must invoke
    FreeRDPInvocation.terminate exactly once and forget the session."""
    from crossdesk_host.freerdp.mock import MockFreeRDPInvocation

    inv = MockFreeRDPInvocation()
    mgr = RailManager(freerdp_inv=inv)
    session = inv.spawn_rail(["/v:localhost"])  # records pid=1
    mgr.handle_rail_event(_event(0xCAFE, Kind.KIND_CREATED, title="App"))
    mgr.register_session(0xCAFE, session)
    mgr.handle_rail_event(_event(0xCAFE, Kind.KIND_DESTROYED))
    assert 0xCAFE not in mgr._sessions
    assert 0xCAFE not in mgr._windows
    assert inv.hooks.terminated_pids == [session.pid]


def test_destroy_with_no_session_does_not_call_freerdp() -> None:
    from crossdesk_host.freerdp.mock import MockFreeRDPInvocation

    inv = MockFreeRDPInvocation()
    mgr = RailManager(freerdp_inv=inv)
    mgr.handle_rail_event(_event(0xBABE, Kind.KIND_CREATED, title="App"))
    mgr.handle_rail_event(_event(0xBABE, Kind.KIND_DESTROYED))
    assert inv.hooks.terminated_pids == []


def test_destroy_swallows_terminate_exception() -> None:
    """A failure in FreeRDP terminate must not block the HWND cleanup,
    otherwise a flaky guest could leak the entry on the host side."""
    from crossdesk_host.freerdp.mock import MockFreeRDPInvocation

    inv = MockFreeRDPInvocation()
    mgr = RailManager(freerdp_inv=inv)
    session = inv.spawn_rail(["/v:localhost"])
    inv.hooks.fail_next_terminate = True
    mgr.handle_rail_event(_event(0xDEAD, Kind.KIND_CREATED, title="App"))
    mgr.register_session(0xDEAD, session)
    mgr.handle_rail_event(_event(0xDEAD, Kind.KIND_DESTROYED))
    assert 0xDEAD not in mgr._windows
    assert 0xDEAD not in mgr._sessions
