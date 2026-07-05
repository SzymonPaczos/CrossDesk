"""Post-install steady-state finalize: persist + idempotent redefine.

Covers the P0 data-loss fix's host-side wiring: the install writes the
steady-state domain XML, and the daemon redefines the domain to it once on the
first agent Hello (installer.steady_state). The live redefine against real
libvirt is a box-gated Phase-2 follow-up; here we drive it against the mock
controller and assert the idempotency + retry contract.
"""

from __future__ import annotations

from pathlib import Path

from crossdesk_host.installer import state
from crossdesk_host.installer.domain_xml import (
    DomainSpec,
    build_steady_state_domain_xml,
)
from crossdesk_host.installer.steady_state import (
    STEADY_STATE_STEP,
    finalize_steady_state,
    persist_steady_state_xml,
)
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock


def _spec() -> DomainSpec:
    return DomainSpec(
        name="windows-guest",
        disk_path=Path("/var/lib/crossdesk/win.qcow2"),
        windows_iso=Path("/isos/win.iso"),
        tools_iso=Path("/isos/tools.iso"),
    )


def _state_path(tmp_path: Path) -> Path:
    return tmp_path / "install.state.json"


def test_persist_writes_steady_state_xml(tmp_path: Path) -> None:
    sp = _state_path(tmp_path)
    written = persist_steady_state_xml(_spec(), state_path=sp)

    assert written == tmp_path / "steady-state.xml"
    assert written.read_text(encoding="utf-8") == build_steady_state_domain_xml(_spec())


def test_finalize_applies_once_and_marks_done(tmp_path: Path) -> None:
    sp = _state_path(tmp_path)
    persist_steady_state_xml(_spec(), state_path=sp)
    ctl = LibvirtControllerMock()

    result = finalize_steady_state(ctl, state_path=sp)

    assert result == "applied"
    assert ctl.hooks.redefine_steady_state_count == 1
    assert ctl.hooks.steady_state_applied is True
    # The applied XML is exactly what the install persisted (boot=1, media out).
    assert ctl.hooks.steady_state_xml == build_steady_state_domain_xml(_spec())
    assert state.load(sp).is_done(STEADY_STATE_STEP)


def test_finalize_is_idempotent_across_reconnects(tmp_path: Path) -> None:
    sp = _state_path(tmp_path)
    persist_steady_state_xml(_spec(), state_path=sp)
    ctl = LibvirtControllerMock()

    assert finalize_steady_state(ctl, state_path=sp) == "applied"
    # A second (and third) Hello must not re-redefine.
    assert finalize_steady_state(ctl, state_path=sp) == "already"
    assert finalize_steady_state(ctl, state_path=sp) == "already"
    assert ctl.hooks.redefine_steady_state_count == 1


def test_finalize_absent_when_no_install_xml(tmp_path: Path) -> None:
    # A dev daemon that never ran `crossdesk install` has no XML to apply.
    ctl = LibvirtControllerMock()

    result = finalize_steady_state(ctl, state_path=_state_path(tmp_path))

    assert result == "absent"
    assert ctl.hooks.redefine_steady_state_count == 0
    assert not state.load(_state_path(tmp_path)).is_done(STEADY_STATE_STEP)


def test_finalize_retries_after_libvirt_error(tmp_path: Path) -> None:
    sp = _state_path(tmp_path)
    persist_steady_state_xml(_spec(), state_path=sp)
    ctl = LibvirtControllerMock()
    ctl.hooks.fail_next_redefine_steady_state = True

    # First Hello: redefine raises → left un-marked so a later Hello retries.
    assert finalize_steady_state(ctl, state_path=sp) == "error"
    assert not state.load(sp).is_done(STEADY_STATE_STEP)

    # Reconnect: the trap must still get closed.
    assert finalize_steady_state(ctl, state_path=sp) == "applied"
    assert ctl.hooks.redefine_steady_state_count == 1
    assert state.load(sp).is_done(STEADY_STATE_STEP)


def test_finalize_error_on_unreadable_state(tmp_path: Path) -> None:
    # A schema-mismatched state file: don't guess — refuse to redefine.
    sp = _state_path(tmp_path)
    persist_steady_state_xml(_spec(), state_path=sp)
    sp.write_text('{"schema_version": 999, "steps": {}}', encoding="utf-8")
    ctl = LibvirtControllerMock()

    assert finalize_steady_state(ctl, state_path=sp) == "error"
    assert ctl.hooks.redefine_steady_state_count == 0
