"""Contract tests for :mod:`crossdesk_host.filesystem_ctl`.

Verifies both implementations satisfy the
:class:`FilesystemController` Protocol and behave the same way
under attach/detach/idempotent retries. The libvirt wrapper is
exercised against a :class:`MagicMock` of :class:`LibvirtController`
so we never instantiate a real libvirt connection.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from crossdesk_host.abstractions.filesystem import FilesystemController
from crossdesk_host.filesystem_ctl import (
    LibvirtFilesystemController,
    MockFilesystemController,
)


def test_mock_satisfies_protocol() -> None:
    assert isinstance(MockFilesystemController(), FilesystemController)


def test_libvirt_wrapper_satisfies_protocol() -> None:
    libvirt = MagicMock()
    ctl = LibvirtFilesystemController(libvirt)
    assert isinstance(ctl, FilesystemController)


# ---------------------------------------------------------------------------
# Mock — attach
# ---------------------------------------------------------------------------


def test_mock_attach_records_pair_and_returns_true() -> None:
    ctl = MockFilesystemController()
    assert ctl.attach_share("s1", "/srv/foo") is True
    assert list(ctl.list_active_shares()) == ["s1"]
    assert ctl.hooks.attached_pairs == [("s1", "/srv/foo")]


def test_mock_attach_is_idempotent() -> None:
    ctl = MockFilesystemController()
    ctl.attach_share("s1", "/srv/foo")
    assert ctl.attach_share("s1", "/srv/foo") is False
    assert list(ctl.list_active_shares()) == ["s1"]


def test_mock_attach_failure_injection() -> None:
    ctl = MockFilesystemController()
    ctl.hooks.fail_next_attach = True
    with pytest.raises(RuntimeError, match="mock-injected attach failure"):
        ctl.attach_share("s1", "/srv/foo")
    assert ctl.hooks.fail_next_attach is False  # flag self-clears
    # subsequent attach succeeds
    assert ctl.attach_share("s1", "/srv/foo") is True


# ---------------------------------------------------------------------------
# Mock — detach
# ---------------------------------------------------------------------------


def test_mock_detach_removes_share() -> None:
    ctl = MockFilesystemController()
    ctl.attach_share("s1", "/srv/foo")
    assert ctl.detach_share("s1") is True
    assert list(ctl.list_active_shares()) == []


def test_mock_detach_unknown_is_idempotent() -> None:
    ctl = MockFilesystemController()
    assert ctl.detach_share("ghost") is False


def test_mock_detach_failure_injection() -> None:
    ctl = MockFilesystemController()
    ctl.attach_share("s1", "/srv/foo")
    ctl.hooks.fail_next_detach = True
    with pytest.raises(RuntimeError, match="mock-injected detach failure"):
        ctl.detach_share("s1")
    # share is still attached because the failure happened before bookkeeping
    assert "s1" in ctl.list_active_shares()


# ---------------------------------------------------------------------------
# Libvirt wrapper — delegates and tracks state
# ---------------------------------------------------------------------------


def test_libvirt_wrapper_calls_attach_virtiofs() -> None:
    libvirt = MagicMock()
    libvirt.attach_virtiofs.return_value = True
    ctl = LibvirtFilesystemController(libvirt)

    assert ctl.attach_share("s1", "/srv/foo") is True
    libvirt.attach_virtiofs.assert_called_once_with("s1", "/srv/foo")
    assert "s1" in ctl.list_active_shares()


def test_libvirt_wrapper_idempotent_attach_does_not_call_libvirt() -> None:
    libvirt = MagicMock()
    libvirt.attach_virtiofs.return_value = True
    ctl = LibvirtFilesystemController(libvirt)
    ctl.attach_share("s1", "/srv/foo")
    libvirt.attach_virtiofs.reset_mock()

    assert ctl.attach_share("s1", "/srv/foo") is False
    libvirt.attach_virtiofs.assert_not_called()


def test_libvirt_wrapper_detach_delegates() -> None:
    libvirt = MagicMock()
    libvirt.attach_virtiofs.return_value = True
    libvirt.detach_virtiofs.return_value = True
    ctl = LibvirtFilesystemController(libvirt)
    ctl.attach_share("s1", "/srv/foo")

    assert ctl.detach_share("s1") is True
    libvirt.detach_virtiofs.assert_called_once_with("s1")
    assert list(ctl.list_active_shares()) == []


def test_libvirt_wrapper_detach_unknown_skips_libvirt() -> None:
    libvirt = MagicMock()
    ctl = LibvirtFilesystemController(libvirt)

    assert ctl.detach_share("ghost") is False
    libvirt.detach_virtiofs.assert_not_called()


def test_libvirt_wrapper_attach_propagates_failure_return() -> None:
    libvirt = MagicMock()
    libvirt.attach_virtiofs.return_value = False
    ctl = LibvirtFilesystemController(libvirt)

    assert ctl.attach_share("s1", "/srv/foo") is False
    # libvirt was called once but we did NOT register the share locally
    assert "s1" not in ctl.list_active_shares()
