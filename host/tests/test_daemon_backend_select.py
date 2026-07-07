"""select_libvirt_backend: mock vs real controller selection, backend logging,
and the mock→no-finalize-hook guard.

The mock must NOT get a finalize hook — running finalize against it would mark
the steady-state step done without redefining anything, masking the P0
data-loss path once the real controller lands. That guard is exactly the
refactor-flip the audit feared, so it is pinned here.
"""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import MagicMock

import structlog

import crossdesk_host.daemon as daemon
from crossdesk_host.config import CrossdeskConfig
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.libvirt_ctl.real import RealLibvirtController


def test_mock_backend_selects_mock_with_no_finalize_hook() -> None:
    cfg = CrossdeskConfig()  # default: libvirt.backend == "mock"
    with structlog.testing.capture_logs() as logs:
        ctl, hook = daemon.select_libvirt_backend(cfg)

    assert isinstance(ctl, LibvirtControllerMock)
    assert hook is None
    assert any(
        e["event"] == "libvirt_backend_selected"
        and e.get("kind") == "mock"
        and e["log_level"] == "warning"
        for e in logs
    )


def test_real_backend_selects_real_with_finalize_hook() -> None:
    cfg = CrossdeskConfig(libvirt={"backend": "real"})
    with structlog.testing.capture_logs() as logs:
        ctl, hook = daemon.select_libvirt_backend(cfg)

    # RealLibvirtController's constructor is lazy — no libvirt connection — so
    # the autouse anti-real-libvirt guard stays green. Do NOT call the hook: it
    # would read the real install state file.
    assert isinstance(ctl, RealLibvirtController)
    assert hook is not None
    assert any(
        e["event"] == "libvirt_backend_selected"
        and e.get("kind") == "real"
        and e.get("domain_name") == cfg.libvirt.domain_name
        and e["log_level"] == "info"
        for e in logs
    )


def test_finalize_hook_is_single_flight(monkeypatch: Any) -> None:
    entered: list[int] = []
    release = threading.Event()

    def fake_finalize(ctl: Any) -> None:
        entered.append(1)
        release.wait(timeout=2)

    monkeypatch.setattr(daemon, "finalize_steady_state", fake_finalize)
    hook = daemon._make_finalize_hook(MagicMock())

    t1 = threading.Thread(target=hook)
    t1.start()
    # Wait until t1 holds the lock and is inside fake_finalize.
    deadline = time.monotonic() + 2
    while not entered and time.monotonic() < deadline:
        time.sleep(0.001)
    assert entered, "first finalize never entered"

    # Second concurrent call finds the lock held → returns immediately without
    # entering finalize (single-flight).
    t2 = threading.Thread(target=hook)
    t2.start()
    t2.join(timeout=2)
    assert not t2.is_alive()
    assert len(entered) == 1

    release.set()
    t1.join(timeout=2)
    assert len(entered) == 1
