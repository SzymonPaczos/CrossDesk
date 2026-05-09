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
