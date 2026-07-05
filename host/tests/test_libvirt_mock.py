"""LibvirtControllerMock behaviours.

Verifies the failure-injection hooks and the in-memory share tracking
that the mock provides on top of the real libvirt surface. Real
libvirt behaviour is exercised only on hardware via the
``linux_only``-marked smoke tests; this file is the unit-level
contract that mock and real share.
"""

from __future__ import annotations

import pytest

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock


def test_mock_satisfies_protocol() -> None:
    assert isinstance(LibvirtControllerMock(), LibvirtController)


def test_hard_destroy_increments_counter() -> None:
    ctl = LibvirtControllerMock()
    ctl.hard_destroy()
    ctl.hard_destroy()
    assert ctl.hooks.hard_destroy_count == 2


def test_fail_next_hard_destroy_raises_then_clears() -> None:
    ctl = LibvirtControllerMock()
    ctl.hooks.fail_next_hard_destroy = True

    with pytest.raises(RuntimeError, match="mock-injected hard_destroy failure"):
        ctl.hard_destroy()

    assert ctl.hooks.fail_next_hard_destroy is False
    assert ctl.hooks.hard_destroy_count == 0

    # Subsequent call succeeds — hook fires once.
    ctl.hard_destroy()
    assert ctl.hooks.hard_destroy_count == 1


def test_attach_then_detach_tracks_share_state() -> None:
    ctl = LibvirtControllerMock()

    assert ctl.attach_virtiofs("home", "/tmp/home") is True
    assert "home" in ctl.hooks.attached_shares
    assert ctl.hooks.attach_virtiofs_count == 1

    # Idempotent re-attach: returns True but does not double-count.
    assert ctl.attach_virtiofs("home", "/tmp/home") is True
    assert ctl.hooks.attach_virtiofs_count == 1

    assert ctl.detach_virtiofs("home") is True
    assert "home" not in ctl.hooks.attached_shares
    assert ctl.hooks.detach_virtiofs_count == 1

    # Idempotent re-detach.
    assert ctl.detach_virtiofs("home") is True
    assert ctl.hooks.detach_virtiofs_count == 1


def test_fail_next_attach_virtiofs_raises_and_does_not_track() -> None:
    ctl = LibvirtControllerMock()
    ctl.hooks.fail_next_attach_virtiofs = True

    with pytest.raises(RuntimeError, match="mock-injected attach_virtiofs"):
        ctl.attach_virtiofs("docs", "/tmp/docs")

    assert "docs" not in ctl.hooks.attached_shares
    assert ctl.hooks.attach_virtiofs_count == 0


def test_graceful_shutdown_counter() -> None:
    ctl = LibvirtControllerMock()
    ctl.graceful_shutdown()
    assert ctl.hooks.graceful_shutdown_count == 1


def test_set_memory_updates_hooks_and_get_stats() -> None:
    ctl = LibvirtControllerMock()
    assert ctl.hooks.memory_mib == 4096  # default

    ctl.set_memory(2048)
    assert ctl.hooks.memory_mib == 2048
    stats = ctl.get_memory_stats()
    assert stats["actual"] == 2048

    ctl.set_memory(6144)
    assert ctl.get_memory_stats()["actual"] == 6144


def test_get_memory_stats_returns_dict_with_actual() -> None:
    ctl = LibvirtControllerMock()
    stats = ctl.get_memory_stats()
    assert "actual" in stats
    assert isinstance(stats["actual"], int)


def test_is_running_default_true_after_construction() -> None:
    ctl = LibvirtControllerMock()
    assert ctl.is_running() is True
    assert ctl.hooks.is_running_count == 1


def test_graceful_shutdown_with_poll_countdown_flips_running() -> None:
    ctl = LibvirtControllerMock()
    ctl.hooks.shutdown_polls_remaining = 2

    ctl.graceful_shutdown()
    # First poll: still running, countdown decrements 2 → 1.
    assert ctl.is_running() is True
    # Second poll: still running, countdown decrements 1 → 0 (and
    # flips ``running`` to False atomically on this poll).
    assert ctl.is_running() is True
    # Third poll: countdown is 0 and ``running`` is False.
    assert ctl.is_running() is False


def test_hard_destroy_revives_running_flag() -> None:
    ctl = LibvirtControllerMock()
    ctl.hooks.running = False  # pretend the VM was off

    ctl.hard_destroy()
    assert ctl.hooks.running is True
    assert ctl.is_running() is True


def test_fail_next_is_running_raises_then_clears() -> None:
    ctl = LibvirtControllerMock()
    ctl.hooks.fail_next_is_running = True

    with pytest.raises(RuntimeError, match="mock-injected is_running failure"):
        ctl.is_running()

    assert ctl.hooks.fail_next_is_running is False
    # Subsequent call succeeds.
    assert ctl.is_running() is True


def test_redefine_steady_state_records_and_flags() -> None:
    ctl = LibvirtControllerMock()
    assert ctl.hooks.steady_state_applied is False

    ctl.redefine_steady_state("<domain>steady</domain>")

    assert ctl.hooks.redefine_steady_state_count == 1
    assert ctl.hooks.steady_state_xml == "<domain>steady</domain>"
    assert ctl.hooks.steady_state_applied is True


def test_fail_next_redefine_steady_state_raises_then_clears() -> None:
    ctl = LibvirtControllerMock()
    ctl.hooks.fail_next_redefine_steady_state = True

    with pytest.raises(
        RuntimeError, match="mock-injected redefine_steady_state failure"
    ):
        ctl.redefine_steady_state("<domain/>")

    assert ctl.hooks.fail_next_redefine_steady_state is False
    # A failed redefine leaves the domain NOT-finalized so the caller retries.
    assert ctl.hooks.steady_state_applied is False
    ctl.redefine_steady_state("<domain/>")
    assert ctl.hooks.steady_state_applied is True
