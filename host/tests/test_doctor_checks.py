"""Tests for the new doctor checks added in the P1 batch."""

from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import patch

import pytest

from crossdesk_host.doctor.checks import (
    Status,
    check_config_dir_writable,
    check_cpu_virt_extensions,
    check_ovmf_firmware,
    check_qemu_version,
    check_vsock_module,
)

# ---------------------------------------------------------------------------
# check_ovmf_firmware
# ---------------------------------------------------------------------------


def test_ovmf_non_linux() -> None:
    with patch("crossdesk_host.doctor.checks._is_linux", return_value=False):
        result = check_ovmf_firmware()
    assert result.status == Status.WARN


def test_ovmf_present() -> None:
    with (
        patch("crossdesk_host.doctor.checks._is_linux", return_value=True),
        patch(
            "crossdesk_host.installer.domain_xml.resolve_ovmf",
            return_value=("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_VARS_4M.fd"),
        ),
    ):
        result = check_ovmf_firmware()
    assert result.status == Status.OK
    assert result.message == "/usr/share/OVMF/OVMF_CODE_4M.fd"


def test_ovmf_missing_fails() -> None:
    with (
        patch("crossdesk_host.doctor.checks._is_linux", return_value=True),
        patch(
            "crossdesk_host.installer.domain_xml.resolve_ovmf",
            side_effect=FileNotFoundError("OVMF firmware (CODE) not found — install ovmf"),
        ),
    ):
        result = check_ovmf_firmware()
    assert result.status == Status.FAIL
    assert "ovmf" in result.message.lower()

# ---------------------------------------------------------------------------
# check_cpu_virt_extensions
# ---------------------------------------------------------------------------


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only check")
def test_cpu_virt_extensions_vmx(tmp_path: Path) -> None:
    fake_cpuinfo = "processor\t: 0\nflags\t\t: fpu vme vmx sse4\n"
    with patch("builtins.open", side_effect=lambda *a, **kw: open(str(tmp_path / "cpuinfo"), **kw)):
        (tmp_path / "cpuinfo").write_text(fake_cpuinfo, encoding="utf-8")
    with patch("pathlib.Path.read_text", return_value=fake_cpuinfo):
        result = check_cpu_virt_extensions()
    assert result.status == Status.OK
    assert "vmx" in result.message


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only check")
def test_cpu_virt_extensions_svm(tmp_path: Path) -> None:
    fake_cpuinfo = "processor\t: 0\nflags\t\t: fpu vme svm sse4\n"
    with patch("pathlib.Path.read_text", return_value=fake_cpuinfo):
        result = check_cpu_virt_extensions()
    assert result.status == Status.OK
    assert "svm" in result.message


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only check")
def test_cpu_virt_extensions_missing(tmp_path: Path) -> None:
    fake_cpuinfo = "processor\t: 0\nflags\t\t: fpu vme sse4\n"
    with patch("pathlib.Path.read_text", return_value=fake_cpuinfo):
        result = check_cpu_virt_extensions()
    assert result.status == Status.FAIL
    assert "vmx" in result.message or "svm" in result.message


def test_cpu_virt_extensions_non_linux() -> None:
    with patch("crossdesk_host.doctor.checks._is_linux", return_value=False):
        result = check_cpu_virt_extensions()
    assert result.status == Status.WARN
    assert "skipped" in result.message


# ---------------------------------------------------------------------------
# check_vsock_module
# ---------------------------------------------------------------------------


def test_vsock_dev_present(tmp_path: Path) -> None:
    with (
        patch("crossdesk_host.doctor.checks._is_linux", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
    ):
        result = check_vsock_module()
    assert result.status == Status.OK


def test_vsock_non_linux() -> None:
    with patch("crossdesk_host.doctor.checks._is_linux", return_value=False):
        result = check_vsock_module()
    assert result.status == Status.WARN


def test_vsock_lsmod_fallback() -> None:
    import subprocess

    fake_lsmod = "Module                  Size  Used by\nvhost_vsock            16384  0\n"
    with (
        patch("crossdesk_host.doctor.checks._is_linux", return_value=True),
        patch("pathlib.Path.exists", return_value=False),
        patch("shutil.which", return_value="/usr/bin/lsmod"),
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=fake_lsmod, stderr=""
            ),
        ),
    ):
        result = check_vsock_module()
    assert result.status == Status.OK


def test_vsock_missing() -> None:
    with (
        patch("crossdesk_host.doctor.checks._is_linux", return_value=True),
        patch("pathlib.Path.exists", return_value=False),
        patch("shutil.which", return_value=None),
    ):
        result = check_vsock_module()
    assert result.status == Status.FAIL


# ---------------------------------------------------------------------------
# check_qemu_version
# ---------------------------------------------------------------------------


def test_qemu_version_ok() -> None:
    import subprocess

    with (
        patch("shutil.which", return_value="/usr/bin/qemu-system-x86_64"),
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="QEMU emulator version 8.2.3 (Debian 1:8.2.3)\n",
                stderr="",
            ),
        ),
    ):
        result = check_qemu_version()
    assert result.status == Status.OK
    assert "8.2" in result.message


def test_qemu_version_too_old() -> None:
    import subprocess

    with (
        patch("shutil.which", return_value="/usr/bin/qemu-system-x86_64"),
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="QEMU emulator version 6.2.0\n",
                stderr="",
            ),
        ),
    ):
        result = check_qemu_version(min_version=(7, 0))
    assert result.status == Status.FAIL
    assert "6.2" in result.message


def test_qemu_not_found() -> None:
    with (
        patch("crossdesk_host.doctor.checks._is_linux", return_value=True),
        patch("shutil.which", return_value=None),
    ):
        result = check_qemu_version()
    assert result.status == Status.FAIL


def test_qemu_non_linux() -> None:
    with (
        patch("crossdesk_host.doctor.checks._is_linux", return_value=False),
        patch("shutil.which", return_value=None),
    ):
        result = check_qemu_version()
    assert result.status == Status.WARN


# ---------------------------------------------------------------------------
# check_config_dir_writable
# ---------------------------------------------------------------------------


def test_config_dir_writable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    # Reload Path.home() by patching
    with patch("pathlib.Path.home", return_value=tmp_path):
        result = check_config_dir_writable()
    assert result.status == Status.OK


def test_config_dir_not_writable(tmp_path: Path) -> None:
    config_dir = tmp_path / ".config" / "crossdesk"
    config_dir.mkdir(parents=True)
    config_dir.chmod(0o444)  # read-only
    try:
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = check_config_dir_writable()
        assert result.status == Status.FAIL
    finally:
        config_dir.chmod(0o755)  # restore so tmp_path cleanup works


# ---------------------------------------------------------------------------
# --gpu flag wiring in doctor_cmd
# ---------------------------------------------------------------------------


def test_doctor_gpu_flag_adds_checks() -> None:
    from crossdesk_host.cli.main import main
    from crossdesk_host.doctor.checks import CheckResult

    gpu_result = CheckResult("gpu_passthrough", Status.WARN, "mocked")

    # Suppress all DEFAULT_CHECKS (environment-dependent) and inject a
    # controlled GPU check to verify the --gpu flag is wired correctly.
    with (
        patch("crossdesk_host.cli.doctor_cmd.DEFAULT_CHECKS", []),
        patch("crossdesk_host.cli.doctor_cmd.GPU_CHECKS", [lambda: gpu_result]),
    ):
        rc = main(["doctor", "--gpu"])
    # WARN-only → exit 0
    assert rc == 0
