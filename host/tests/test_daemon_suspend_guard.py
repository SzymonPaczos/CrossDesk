"""Guard: the real libvirt controller must not run without host-suspend
protection (the D-Bus PrepareForSleep listener).

Without it a host sleep strands the heartbeat FSMs ticking across the pause,
escalating to a HARD_DESTROY = ``virsh destroy`` = the VM and everything
unsaved in it. The mock controller has nothing to lose, so dev hosts without
D-Bus are allowed through.
"""

from __future__ import annotations

import pytest

from crossdesk_host.daemon import _assert_suspend_protection
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock


class _RealishController:
    """A non-mock controller stand-in. The guard only distinguishes the
    mock from everything else via ``isinstance``, so a bare object is
    enough to stand in for the real controller here."""


def test_mock_without_listener_is_allowed() -> None:
    # Dev host: mock controller, no D-Bus listener — nothing to lose.
    _assert_suspend_protection(LibvirtControllerMock(), listener_active=False)


def test_real_controller_without_listener_refuses() -> None:
    with pytest.raises(RuntimeError, match="host-suspend"):
        _assert_suspend_protection(
            _RealishController(),  # type: ignore[arg-type]
            listener_active=False,
        )


def test_real_controller_with_listener_is_allowed() -> None:
    _assert_suspend_protection(
        _RealishController(),  # type: ignore[arg-type]
        listener_active=True,
    )


def test_mock_with_listener_is_allowed() -> None:
    _assert_suspend_protection(LibvirtControllerMock(), listener_active=True)
