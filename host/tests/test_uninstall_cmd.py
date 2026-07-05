"""crossdesk uninstall CLI — the destructive-confirmation gate + --force.

Uninstall wipes the VM, disk, and the mTLS keys / vm.toml, so the CLI must not
run without an explicit yes (or --force). These tests spy on the removal so the
gate logic is exercised without touching the real home.
"""

from __future__ import annotations

import argparse
from typing import Any, Dict

import pytest

from crossdesk_host.cli import uninstall_cmd
from crossdesk_host.uninstall import UninstallReport


def _args(*, dry_run: bool = False, force: bool = False) -> argparse.Namespace:
    return argparse.Namespace(dry_run=dry_run, force=force, keep_config=False)


def _forbidden_input(prompt: str = "") -> str:
    raise AssertionError("input() must not be called on this path")


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    calls: Dict[str, Any] = {}

    def fake_uninstall(**kwargs: Any) -> UninstallReport:
        calls["ran"] = True
        calls["kwargs"] = kwargs
        return UninstallReport()

    monkeypatch.setattr(uninstall_cmd, "uninstall", fake_uninstall)
    monkeypatch.setattr(uninstall_cmd, "_resolve_libvirt_ctl", lambda: object())
    return calls


def test_force_skips_prompt_and_runs(
    spy: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("builtins.input", _forbidden_input)
    assert uninstall_cmd.run(_args(force=True)) == 0
    assert spy["ran"]


def test_dry_run_skips_prompt(
    spy: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("builtins.input", _forbidden_input)
    assert uninstall_cmd.run(_args(dry_run=True)) == 0
    assert spy["kwargs"]["dry_run"] is True


def test_declining_aborts_without_running(
    spy: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert uninstall_cmd.run(_args()) == 0
    assert "ran" not in spy  # the removal never happened


def test_yes_confirms_and_runs(
    spy: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt="": "  Yes  ")
    assert uninstall_cmd.run(_args()) == 0
    assert spy["ran"]


def test_confirm_treats_eof_as_no(monkeypatch: pytest.MonkeyPatch) -> None:
    # A piped / non-interactive stdin must never be read as consent.
    def eof(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    assert uninstall_cmd._confirm_destructive() is False
