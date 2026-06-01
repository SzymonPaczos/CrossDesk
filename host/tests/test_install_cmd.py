"""Tests for the ``crossdesk install`` step pipeline (cli/install_cmd.py).

The handler table is exercised with the doctor probe and disk-writing steps
monkeypatched, so the dispatch / state-persistence / gating logic runs on any
platform without a real VM, libvirt, or ~/.config writes.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from crossdesk_host.cli import install_cmd
from crossdesk_host.doctor.checks import CheckResult, Status
from crossdesk_host.installer import credentials, state, tools_iso
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock


def _args(*, iso_path: Path | None = None, dry_run: bool = False) -> argparse.Namespace:
    return argparse.Namespace(iso_path=iso_path, lean=False, dry_run=dry_run)


@pytest.fixture(autouse=True)
def _state_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    sf = tmp_path / "install.state.json"
    monkeypatch.setattr(state, "default_state_file", lambda: sf)
    return sf


@pytest.fixture(autouse=True)
def _mock_libvirt(monkeypatch: pytest.MonkeyPatch) -> LibvirtControllerMock:
    """Inject a mock LibvirtController so create_libvirt_domain never
    touches real libvirt (which on a Linux+KVM box would actually define
    and boot a VM)."""
    ctl = LibvirtControllerMock()
    monkeypatch.setattr(install_cmd, "_libvirt_ctl_override", ctl)
    return ctl


def _ok_doctor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install_cmd, "run_all", lambda checks: [CheckResult("kvm", Status.OK)])
    monkeypatch.setattr(install_cmd, "has_failures", lambda results: False)


def test_dry_run_marks_every_step_done(_state_in_tmp: Path) -> None:
    rc = install_cmd.run(_args(dry_run=True))
    assert rc == 0
    s = state.load(_state_in_tmp)
    assert all(s.is_done(step) for step in install_cmd._STEPS)


def test_doctor_failure_stops_pipeline(monkeypatch: pytest.MonkeyPatch, _state_in_tmp: Path) -> None:
    monkeypatch.setattr(
        install_cmd, "run_all", lambda checks: [CheckResult("kvm", Status.FAIL, "no /dev/kvm")]
    )
    monkeypatch.setattr(install_cmd, "has_failures", lambda results: True)

    rc = install_cmd.run(_args())

    assert rc == 1
    s = state.load(_state_in_tmp)
    assert not s.is_done("doctor")
    assert not s.is_done("generate_credentials")


def test_full_pipeline_with_iso_defines_and_starts_domain(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    _state_in_tmp: Path,
    _mock_libvirt: LibvirtControllerMock,
) -> None:
    _ok_doctor(monkeypatch)
    iso = tmp_path / "Win10.iso"
    iso.write_bytes(b"fake-iso")
    monkeypatch.setattr(credentials, "save", lambda creds, path=None: None)
    monkeypatch.setattr(credentials, "load", lambda path=None: None)
    # Point the tools-ISO inputs at fixtures so resolution is deterministic
    # regardless of whether agent.exe has been built on this box.
    for env, name in (
        ("CROSSDESK_AGENT_EXE", "agent.exe"),
        ("CROSSDESK_PUBLISHER_CA", "ca.crt"),
        ("CROSSDESK_AUTOUNATTEND", "autounattend.xml"),
    ):
        f = tmp_path / name
        f.write_bytes(b"x")
        monkeypatch.setenv(env, str(f))

    def fake_build(**kw: Path) -> Path:
        kw["output_iso"].write_bytes(b"ISO")
        return kw["output_iso"]

    monkeypatch.setattr(tools_iso, "build_tools_iso", fake_build)
    # Pre-create the disk so the qemu-img subprocess is skipped in the test.
    (_state_in_tmp.parent / "crossdesk-win.qcow2").write_bytes(b"qcow")

    rc = install_cmd.run(_args(iso_path=iso))

    assert rc == 0
    s = state.load(_state_in_tmp)
    assert all(s.is_done(step) for step in install_cmd._STEPS)
    # The domain was defined + started exactly once with the right name.
    assert _mock_libvirt.hooks.define_and_start_count == 1
    assert _mock_libvirt.hooks.defined_xml is not None
    assert "windows-guest" in _mock_libvirt.hooks.defined_xml
    assert (_state_in_tmp.parent / "tools.iso").is_file()


def test_prepare_autounattend_substitutes_locale_and_password(tmp_path: Path) -> None:
    src = tmp_path / "autounattend.xml"
    src.write_text(
        "<x><InputLocale>en-US</InputLocale><UILanguage>en-US</UILanguage>"
        "<Value>__CROSSDESK_PASSWORD__</Value></x>"
    )
    out = install_cmd._prepare_autounattend(src, "pl-PL", "p@ss<&>", tmp_path)
    assert out != src
    text = out.read_text()
    assert "en-US" not in text and text.count("pl-PL") == 2
    # Placeholder filled, password XML-escaped.
    assert "__CROSSDESK_PASSWORD__" not in text
    assert "p@ss&lt;&amp;&gt;" in text


def test_prepare_autounattend_default_locale_keeps_language_fills_password(tmp_path: Path) -> None:
    src = tmp_path / "autounattend.xml"
    src.write_text("<x><InputLocale>en-US</InputLocale><Value>__CROSSDESK_PASSWORD__</Value></x>")
    out = install_cmd._prepare_autounattend(src, "en-US", "secret", tmp_path)
    text = out.read_text()
    assert text.count("en-US") == 1  # locale untouched at default
    assert "secret" in text and "__CROSSDESK_PASSWORD__" not in text


def test_download_iso_requires_iso_path(monkeypatch: pytest.MonkeyPatch, _state_in_tmp: Path) -> None:
    _ok_doctor(monkeypatch)
    rc = install_cmd.run(_args(iso_path=None))  # no --iso-path → Fido not wired
    assert rc == 1
    s = state.load(_state_in_tmp)
    assert s.is_done("doctor")
    assert not s.is_done("download_iso")


def test_build_tools_iso_fails_when_agent_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _state_in_tmp: Path
) -> None:
    _ok_doctor(monkeypatch)
    iso = tmp_path / "Win11.iso"
    iso.write_bytes(b"fake-iso")
    monkeypatch.setattr(credentials, "save", lambda creds, path=None: None)
    # Force the agent.exe input to a path that does not exist.
    monkeypatch.setenv("CROSSDESK_AGENT_EXE", str(tmp_path / "nope" / "agent.exe"))

    rc = install_cmd.run(_args(iso_path=iso))

    assert rc == 1
    s = state.load(_state_in_tmp)
    assert s.is_done("generate_credentials")
    assert not s.is_done("build_tools_iso")
