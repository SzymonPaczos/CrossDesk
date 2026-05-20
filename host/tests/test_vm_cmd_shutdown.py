"""``crossdesk vm shutdown`` CLI behaviours.

All libvirt interaction is mocked via ``LibvirtControllerMock`` —
``RealLibvirtController`` is only constructed in the production path and
is gated by a Linux-only import inside ``run_shutdown``.

Test matrix:

- happy path: ACPI shutdown completes within timeout → exit 0.
- timeout fallback: guest stays running past --timeout → exit 2 +
  ``hard_destroy`` invoked.
- ``--force``: skip ACPI, go straight to destroy → exit 2 +
  ``graceful_shutdown`` not invoked.
- libvirt error during graceful_shutdown → exit 1.
- libvirt error during is_running poll → exit 1.
- libvirt error during fallback hard_destroy → exit 1.
- libvirt error during forced hard_destroy → exit 1.
- ``--timeout 0`` → exit 2 (input validation at the CLI boundary).

Polling uses ``asyncio.sleep`` so the timeout-fallback test stays fast
on a real event loop — we monkey-patch ``asyncio.sleep`` to a no-op so
the wait-loop runs at memory speed regardless of the configured
timeout. The mock controller's ``shutdown_polls_remaining`` knob drives
"ACPI honoured after N polls" scenarios.
"""

from __future__ import annotations

import argparse
from typing import List

import pytest

from crossdesk_host.cli import vm_cmd
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock


def _make_args(
    *,
    timeout: int = 60,
    force: bool = False,
    domain: str = "windows-guest",
) -> argparse.Namespace:
    return argparse.Namespace(timeout=timeout, force=force, domain=domain)


@pytest.fixture(autouse=True)
def _instant_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace ``asyncio.sleep`` with an instant coroutine so the
    1-second poll cadence doesn't drag the suite."""

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("crossdesk_host.cli.vm_cmd.asyncio.sleep", _no_sleep)


def test_graceful_path_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    ctl = LibvirtControllerMock()
    # ACPI completes after one poll: the mock flips ``running`` to False.
    ctl.hooks.shutdown_polls_remaining = 1

    rc = vm_cmd.run_shutdown(_make_args(timeout=5), _libvirt_ctl_override=ctl)

    assert rc == 0
    assert ctl.hooks.graceful_shutdown_count == 1
    assert ctl.hooks.hard_destroy_count == 0
    # First poll consumes the countdown (still running), second sees off.
    assert ctl.hooks.is_running_count >= 1
    out = capsys.readouterr().out
    assert "stopped cleanly" in out


def test_timeout_falls_back_to_hard_destroy(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ctl = LibvirtControllerMock()
    # No shutdown_polls_remaining → ``is_running`` keeps reporting True
    # → loop exhausts the timeout budget.

    rc = vm_cmd.run_shutdown(_make_args(timeout=3), _libvirt_ctl_override=ctl)

    assert rc == 2
    assert ctl.hooks.graceful_shutdown_count == 1
    assert ctl.hooks.hard_destroy_count == 1
    # We polled exactly ``timeout`` times before giving up.
    assert ctl.hooks.is_running_count == 3
    out = capsys.readouterr().out
    assert "did not stop" in out
    assert "hard destroy" in out


def test_force_skips_acpi_and_destroys(capsys: pytest.CaptureFixture[str]) -> None:
    ctl = LibvirtControllerMock()

    rc = vm_cmd.run_shutdown(_make_args(force=True), _libvirt_ctl_override=ctl)

    assert rc == 2
    assert ctl.hooks.graceful_shutdown_count == 0
    assert ctl.hooks.hard_destroy_count == 1
    assert ctl.hooks.is_running_count == 0
    out = capsys.readouterr().out
    assert "--force" in out


def test_graceful_shutdown_libvirt_error_returns_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ctl = LibvirtControllerMock()
    ctl.hooks.fail_next_graceful_shutdown = True

    rc = vm_cmd.run_shutdown(_make_args(timeout=5), _libvirt_ctl_override=ctl)

    assert rc == 1
    assert ctl.hooks.hard_destroy_count == 0
    assert ctl.hooks.is_running_count == 0
    out = capsys.readouterr().out
    assert "graceful shutdown failed" in out


def test_is_running_error_during_poll_returns_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ctl = LibvirtControllerMock()
    ctl.hooks.fail_next_is_running = True

    rc = vm_cmd.run_shutdown(_make_args(timeout=5), _libvirt_ctl_override=ctl)

    assert rc == 1
    assert ctl.hooks.graceful_shutdown_count == 1
    assert ctl.hooks.hard_destroy_count == 0
    out = capsys.readouterr().out
    assert "status probe failed" in out


def test_fallback_hard_destroy_error_returns_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ctl = LibvirtControllerMock()
    # ACPI succeeds but guest stays running, then hard_destroy fails.
    ctl.hooks.fail_next_hard_destroy = True

    rc = vm_cmd.run_shutdown(_make_args(timeout=2), _libvirt_ctl_override=ctl)

    assert rc == 1
    assert ctl.hooks.graceful_shutdown_count == 1
    assert ctl.hooks.is_running_count == 2
    out = capsys.readouterr().out
    assert "hard destroy failed" in out


def test_force_hard_destroy_error_returns_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ctl = LibvirtControllerMock()
    ctl.hooks.fail_next_hard_destroy = True

    rc = vm_cmd.run_shutdown(_make_args(force=True), _libvirt_ctl_override=ctl)

    assert rc == 1
    assert ctl.hooks.graceful_shutdown_count == 0
    out = capsys.readouterr().out
    assert "hard destroy failed" in out


@pytest.mark.parametrize("bad", [0, -1, -60])
def test_non_positive_timeout_rejected(
    bad: int, capsys: pytest.CaptureFixture[str]
) -> None:
    ctl = LibvirtControllerMock()

    rc = vm_cmd.run_shutdown(_make_args(timeout=bad), _libvirt_ctl_override=ctl)

    assert rc == 2
    assert ctl.hooks.graceful_shutdown_count == 0
    assert ctl.hooks.hard_destroy_count == 0
    out = capsys.readouterr().out
    assert "positive integer" in out


def test_argparse_wiring_via_main_force_path(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end argparse parse of ``vm shutdown --force --domain X``.

    Stubs ``RealLibvirtController`` so the test works on hosts without
    ``libvirt-python``; asserts argparse plumbed ``--force`` and
    ``--domain`` through to ``run_shutdown``'s libvirt call.
    """
    from crossdesk_host.cli import main as main_mod

    fake_ctl = LibvirtControllerMock()

    seen_domain: List[str] = []
    real_factory_calls: List[str] = []

    class _FakeRealCtl:
        def __init__(self, domain_name: str = "windows-guest") -> None:
            real_factory_calls.append(domain_name)
            self._inner = fake_ctl

        def __getattr__(self, name: str) -> object:
            return getattr(self._inner, name)

    # The module-local import (``from ... import RealLibvirtController``)
    # happens inside ``run_shutdown`` only when no override is given.
    import crossdesk_host.libvirt_ctl.real as real_mod

    monkeypatch.setattr(real_mod, "RealLibvirtController", _FakeRealCtl)

    original = vm_cmd.run_shutdown

    def _spy(args: argparse.Namespace) -> int:
        seen_domain.append(args.domain)
        return original(args)

    monkeypatch.setattr(main_mod.vm_cmd, "run_shutdown", _spy)

    rc = main_mod.main(["vm", "shutdown", "--force", "--domain", "test-vm"])
    assert rc == 2
    assert seen_domain == ["test-vm"]
    assert real_factory_calls == ["test-vm"]
    assert fake_ctl.hooks.hard_destroy_count == 1
