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


@pytest.fixture(autouse=True)
def _isolate_freerdp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect _freerdp_config_dir into tmp for EVERY test. create_libvirt_domain
    now clears the guest's FreeRDP TOFU pin (fix: reinstall cert rotation), which
    would otherwise delete the developer's real ~/.config/freerdp/server pin when
    the full-pipeline test drives that step — the suite must never write ~/.config."""
    cfg = tmp_path / "freerdp"
    monkeypatch.setattr(install_cmd, "_freerdp_config_dir", lambda: cfg)
    return cfg


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
    # No real key-send sleep in the test.
    monkeypatch.setattr(install_cmd, "_BOOT_KEY_INTERVAL_S", 0.0)
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
    # The boot-from-CD key burst fired (ENTER, one press per iteration) so a
    # fresh unattended install clears "Press any key to boot from CD or DVD".
    assert _mock_libvirt.hooks.sent_keys == [[install_cmd._KEY_ENTER]] * install_cmd._BOOT_KEY_PRESSES


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


# ---------------------------------------------------------------------------
# last_error population + doctor re-check on resume (A7 install idempotency)
# ---------------------------------------------------------------------------


def test_step_failure_records_last_error(
    monkeypatch: pytest.MonkeyPatch, _state_in_tmp: Path
) -> None:
    # doctor fails → the stop reason is persisted to last_error (was lost).
    monkeypatch.setattr(
        install_cmd, "run_all", lambda checks: [CheckResult("kvm", Status.FAIL, "no /dev/kvm")]
    )
    monkeypatch.setattr(install_cmd, "has_failures", lambda results: True)

    assert install_cmd.run(_args()) == 1
    s = state.load(_state_in_tmp)
    assert s.last_error is not None
    assert "doctor" in s.last_error


def test_hardware_gated_step_records_last_error(
    monkeypatch: pytest.MonkeyPatch, _state_in_tmp: Path
) -> None:
    _ok_doctor(monkeypatch)
    # No --iso-path → download_iso is hardware-gated; the reason is recorded.
    assert install_cmd.run(_args(iso_path=None)) == 1
    s = state.load(_state_in_tmp)
    assert s.last_error is not None
    assert "download_iso" in s.last_error
    assert "hardware-gated" in s.last_error


def test_last_error_cleared_on_success(
    monkeypatch: pytest.MonkeyPatch, _state_in_tmp: Path
) -> None:
    # A failed run sets last_error; a later run that completes the step clears it.
    monkeypatch.setattr(
        install_cmd, "run_all", lambda checks: [CheckResult("kvm", Status.FAIL)]
    )
    monkeypatch.setattr(install_cmd, "has_failures", lambda results: True)
    assert install_cmd.run(_args()) == 1
    assert state.load(_state_in_tmp).last_error is not None

    # dry-run marks every step done → mark('done') clears last_error.
    assert install_cmd.run(_args(dry_run=True)) == 0
    assert state.load(_state_in_tmp).last_error is None


def test_last_error_surfaced_on_resume(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], _state_in_tmp: Path
) -> None:
    s = state.InstallState()
    install_cmd._ensure_steps(s)
    s.last_error = "download_iso: boom from a prior run"
    state.save(s, _state_in_tmp)
    _ok_doctor(monkeypatch)

    install_cmd.run(_args(iso_path=None))
    out = capsys.readouterr().out
    assert "last attempt stopped" in out
    assert "download_iso: boom from a prior run" in out


def test_doctor_rechecked_on_resume_catches_regression(
    monkeypatch: pytest.MonkeyPatch, _state_in_tmp: Path
) -> None:
    # A prior run got past doctor; the environment then regressed. On resume,
    # doctor must re-run (not be skipped as 'done') and catch it.
    s = state.InstallState()
    install_cmd._ensure_steps(s)
    s.mark("doctor", "done")
    state.save(s, _state_in_tmp)

    monkeypatch.setattr(
        install_cmd, "run_all", lambda checks: [CheckResult("kvm", Status.FAIL, "no /dev/kvm")]
    )
    monkeypatch.setattr(install_cmd, "has_failures", lambda results: True)

    assert install_cmd.run(_args()) == 1
    s2 = state.load(_state_in_tmp)
    assert not s2.is_done("doctor")  # reset to pending + re-run, which failed
    assert s2.last_error is not None and "doctor" in s2.last_error


def test_completed_install_does_not_recheck_doctor(
    monkeypatch: pytest.MonkeyPatch, _state_in_tmp: Path
) -> None:
    # A fully-done install stays a no-op: no doctor re-run, no work.
    s = state.InstallState()
    install_cmd._ensure_steps(s)
    for step in install_cmd._STEPS:
        s.mark(step, "done")
    state.save(s, _state_in_tmp)

    called = {"doctor": False}

    def _boom(checks: object) -> list[CheckResult]:
        called["doctor"] = True
        return [CheckResult("kvm", Status.FAIL)]

    monkeypatch.setattr(install_cmd, "run_all", _boom)
    assert install_cmd.run(_args()) == 0
    assert called["doctor"] is False  # doctor was not re-run


# ---------------------------------------------------------------------------
# Packaged-input resolution (D packaging: /usr/share/crossdesk fallback)
# ---------------------------------------------------------------------------


def test_resolve_input_env_override_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pinned = tmp_path / "custom-agent.exe"
    pinned.write_bytes(b"x")
    monkeypatch.setenv("CROSSDESK_AGENT_EXE", str(pinned))
    out = install_cmd._resolve_input("CROSSDESK_AGENT_EXE", tmp_path / "repo.exe", "agent.exe")
    assert out == pinned


def test_resolve_input_packaged_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("CROSSDESK_AGENT_EXE", raising=False)
    monkeypatch.setenv("CROSSDESK_DATA_DIR", str(tmp_path))
    (tmp_path / "agent.exe").write_bytes(b"x")
    out = install_cmd._resolve_input(
        "CROSSDESK_AGENT_EXE", tmp_path / "nope" / "repo.exe", "agent.exe"
    )
    assert out == tmp_path / "agent.exe"


def test_resolve_input_repo_path_preferred_over_packaged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("CROSSDESK_AGENT_EXE", raising=False)
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "agent.exe").write_bytes(b"pkg")
    monkeypatch.setenv("CROSSDESK_DATA_DIR", str(pkg))
    repo = tmp_path / "repo.exe"
    repo.write_bytes(b"repo")
    out = install_cmd._resolve_input("CROSSDESK_AGENT_EXE", repo, "agent.exe")
    assert out == repo  # the in-repo dev path wins over the packaged copy


def test_resolve_input_missing_returns_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("CROSSDESK_AGENT_EXE", raising=False)
    monkeypatch.setenv("CROSSDESK_DATA_DIR", str(tmp_path / "empty"))
    out = install_cmd._resolve_input("CROSSDESK_AGENT_EXE", tmp_path / "nope.exe", "agent.exe")
    assert out is None


# _resolve_tools_inputs: the aggregator the install actually calls. Simulate a
# distro-package layout (no in-repo files; everything under
# /usr/share/crossdesk) — the contract the AUR/deb/rpm PKGBUILD relies on.
def _no_repo_no_env(monkeypatch: pytest.MonkeyPatch, empty: Path) -> None:
    for env in ("CROSSDESK_AGENT_EXE", "CROSSDESK_PUBLISHER_CA", "CROSSDESK_AUTOUNATTEND"):
        monkeypatch.delenv(env, raising=False)
    # Point the in-repo root at a nonexistent dir so only the packaged copies
    # (CROSSDESK_DATA_DIR) can satisfy the lookup — the real deb/AUR situation.
    monkeypatch.setattr(install_cmd, "_repo_root", lambda: empty)


def test_resolve_tools_inputs_from_packaged_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _no_repo_no_env(monkeypatch, tmp_path / "norepo")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    for name in ("agent.exe", "publisher-root-ca.crt", "autounattend.xml"):
        (pkg / name).write_bytes(b"x")
    monkeypatch.setenv("CROSSDESK_DATA_DIR", str(pkg))

    agent, ca, autounattend = install_cmd._resolve_tools_inputs()
    assert agent == pkg / "agent.exe"
    assert ca == pkg / "publisher-root-ca.crt"
    assert autounattend == pkg / "autounattend.xml"


@pytest.mark.parametrize(
    "present,missing_match",
    [
        ((), "agent.exe"),
        (("agent.exe",), "publisher CA"),
        (("agent.exe", "publisher-root-ca.crt"), "autounattend.xml"),
    ],
)
def test_resolve_tools_inputs_missing_raises_named_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    present: tuple[str, ...],
    missing_match: str,
) -> None:
    _no_repo_no_env(monkeypatch, tmp_path / "norepo")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    for name in present:
        (pkg / name).write_bytes(b"x")
    monkeypatch.setenv("CROSSDESK_DATA_DIR", str(pkg))

    with pytest.raises(install_cmd._StepFailed, match=missing_match):
        install_cmd._resolve_tools_inputs()


def _freerdp_cfg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    cfg = tmp_path / "freerdp"
    monkeypatch.setattr(install_cmd, "_freerdp_config_dir", lambda: cfg)
    return cfg


def test_clear_tofu_pin_removes_stale_server_pem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A reinstall rotates the guest RDP cert; the old per-host pin must go so
    # the daemon-spawned FreeRDP (no stdin) doesn't deadlock on the cert-change
    # prompt at the next managed launch.
    cfg = _freerdp_cfg(monkeypatch, tmp_path)
    pin = cfg / "server" / "localhost_3389.pem"
    pin.parent.mkdir(parents=True)
    pin.write_text("-----BEGIN CERTIFICATE-----\nstale\n", encoding="utf-8")
    install_cmd._clear_guest_rdp_tofu_pin()
    assert not pin.exists()


def test_clear_tofu_pin_absent_is_noop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # First install on a host has no pin yet — must not raise.
    _freerdp_cfg(monkeypatch, tmp_path)
    install_cmd._clear_guest_rdp_tofu_pin()  # no FileNotFoundError


def test_clear_tofu_pin_prunes_only_guest_known_hosts_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The alternate line-per-host store: drop the guest's entry, keep others.
    cfg = _freerdp_cfg(monkeypatch, tmp_path)
    cfg.mkdir(parents=True)
    known = cfg / "known_hosts2"
    known.write_text(
        "localhost 3389 CN=CrossDesk-Guest oldfingerprint\n"
        "example.com 3389 CN=Other otherfingerprint\n",
        encoding="utf-8",
    )
    install_cmd._clear_guest_rdp_tofu_pin()
    remaining = known.read_text(encoding="utf-8")
    assert "localhost 3389" not in remaining
    assert "example.com 3389" in remaining


def test_clear_tofu_pin_honours_host_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A non-default endpoint clears its own pin, not the default one.
    cfg = _freerdp_cfg(monkeypatch, tmp_path)
    (cfg / "server").mkdir(parents=True)
    default_pin = cfg / "server" / "localhost_3389.pem"
    custom_pin = cfg / "server" / "127.0.0.1_13389.pem"
    default_pin.write_text("keep", encoding="utf-8")
    custom_pin.write_text("drop", encoding="utf-8")
    install_cmd._clear_guest_rdp_tofu_pin(host="127.0.0.1", port=13389)
    assert not custom_pin.exists()
    assert default_pin.exists()
