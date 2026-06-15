"""`_expected_endpoint` address-family selection.

Pure-function coverage for the ``bind_kind`` override added for the
QEMU user-net (SLIRP) bring-up: the guest dials ``10.0.2.2`` which SLIRP
NATs to the host's loopback, so the daemon must be able to bind
``127.0.0.1`` on Linux instead of AF_VSOCK. ``bind_kind`` lets the
operator pick the family without a platform change; ``auto`` preserves
the previous platform-canonical behaviour.

No socket is opened here — ``_expected_endpoint`` only computes the
endpoint string + kind label.
"""

from __future__ import annotations

import pytest

from crossdesk_host.transport.real import _expected_endpoint


def test_tcp_forces_loopback_on_any_platform() -> None:
    endpoint, kind = _expected_endpoint(50051, "tcp")
    assert kind == "tcp"
    assert endpoint == "127.0.0.1:50051"


def test_vsock_forces_vsock_on_any_platform() -> None:
    endpoint, kind = _expected_endpoint(50051, "vsock")
    assert kind == "vsock"
    assert endpoint == "vsock:-1:50051"


def test_auto_matches_platform_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # Linux → vsock; mac/win → tcp. Patch sys.platform inside the module.
    monkeypatch.setattr("crossdesk_host.transport.real.sys.platform", "linux")
    assert _expected_endpoint(50051, "auto") == ("vsock:-1:50051", "vsock")
    monkeypatch.setattr("crossdesk_host.transport.real.sys.platform", "darwin")
    assert _expected_endpoint(50051, "auto") == ("127.0.0.1:50051", "tcp")
    monkeypatch.setattr("crossdesk_host.transport.real.sys.platform", "win32")
    assert _expected_endpoint(50051, "auto") == ("127.0.0.1:50051", "tcp")


def test_auto_is_the_default_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Omitting bind_kind behaves like "auto" — no behaviour change for
    # existing callers that pre-date the parameter.
    monkeypatch.setattr("crossdesk_host.transport.real.sys.platform", "linux")
    assert _expected_endpoint(50051) == ("vsock:-1:50051", "vsock")


def test_tcp_overrides_linux_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # The SLIRP bring-up case: on Linux, "tcp" must beat the vsock default.
    monkeypatch.setattr("crossdesk_host.transport.real.sys.platform", "linux")
    assert _expected_endpoint(50051, "tcp") == ("127.0.0.1:50051", "tcp")


def test_port_is_interpolated() -> None:
    assert _expected_endpoint(60123, "tcp")[0].endswith(":60123")
    assert _expected_endpoint(60123, "vsock")[0].endswith(":60123")
