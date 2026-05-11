"""Tests for infra/launch-vm.py GPU passthrough support and elastic resources.

Run from repo root:
    python3 -m pytest infra/test_launch_vm.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Hyphenated filename can't be imported with `import`; load the module manually.
_spec = importlib.util.spec_from_file_location(
    "launch_vm", Path(__file__).parent / "launch-vm.py"
)
assert _spec is not None and _spec.loader is not None
launch_vm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(launch_vm)  # type: ignore[union-attr]


_FAKE_ISO = Path("/tmp/fake.iso")
_FAKE_TOOLS = Path("/tmp/tools.iso")
_FAKE_OVMF = Path("/tmp/OVMF_CODE.fd")
_FAKE_TPM = Path("/tmp/swtpm.sock")


def _cmd(**kwargs: object) -> list[str]:
    return launch_vm.build_qemu_cmd(
        _FAKE_ISO,
        _FAKE_TOOLS,
        _FAKE_OVMF,
        _FAKE_TPM,
        **kwargs,  # type: ignore[arg-type]
    )


class TestBuildQemuCmdDefaults:
    def test_contains_vnc(self) -> None:
        cmd = _cmd()
        assert "-vnc" in cmd
        assert "127.0.0.1:0" in cmd

    def test_no_vfio_device(self) -> None:
        cmd = _cmd()
        joined = " ".join(cmd)
        assert "vfio-pci" not in joined

    def test_cpu_is_host(self) -> None:
        cmd = _cmd()
        idx = cmd.index("-cpu")
        assert cmd[idx + 1] == "host"

    def test_vsock_present(self) -> None:
        cmd = _cmd()
        joined = " ".join(cmd)
        assert f"guest-cid={launch_vm.VSOCK_CID}" in joined


class TestBuildQemuCmdGpuPassthrough:
    def test_single_gpu_no_vnc(self) -> None:
        cmd = _cmd(gpu_pci_ids=["01:00.0"])
        assert "-vnc" not in cmd

    def test_single_gpu_vfio_device(self) -> None:
        cmd = _cmd(gpu_pci_ids=["01:00.0"])
        assert "vfio-pci,host=01:00.0,multifunction=on" in " ".join(cmd)

    def test_two_gpus_multifunction_on_first_only(self) -> None:
        cmd = _cmd(gpu_pci_ids=["01:00.0", "01:00.1"])
        joined = " ".join(cmd)
        assert "vfio-pci,host=01:00.0,multifunction=on" in joined
        # second BDF must NOT have multifunction=on
        assert "vfio-pci,host=01:00.1," not in joined
        assert "vfio-pci,host=01:00.1" in joined

    def test_empty_gpu_list_keeps_vnc(self) -> None:
        cmd = _cmd(gpu_pci_ids=[])
        assert "-vnc" in cmd


class TestBuildQemuCmdNvidiaHideVm:
    def test_hide_vm_modifies_cpu_flags(self) -> None:
        cmd = _cmd(nvidia_hide_vm=True)
        idx = cmd.index("-cpu")
        cpu_val = cmd[idx + 1]
        assert "kvm=off" in cpu_val
        assert "hv_vendor_id=AuthenticAMD" in cpu_val

    def test_hide_vm_false_keeps_plain_host(self) -> None:
        cmd = _cmd(nvidia_hide_vm=False)
        idx = cmd.index("-cpu")
        assert cmd[idx + 1] == "host"

    def test_hide_vm_with_gpu_combo(self) -> None:
        cmd = _cmd(gpu_pci_ids=["01:00.0"], nvidia_hide_vm=True)
        idx = cmd.index("-cpu")
        assert "kvm=off" in cmd[idx + 1]
        assert "vfio-pci,host=01:00.0,multifunction=on" in " ".join(cmd)


class TestBuildQemuCmdElasticResources:
    def test_balloon_device_present(self) -> None:
        cmd = _cmd()
        assert "virtio-balloon-pci,id=balloon0" in " ".join(cmd)

    def test_drive_has_discard_unmap(self) -> None:
        cmd = _cmd()
        drive_args = [v for i, v in enumerate(cmd) if i > 0 and cmd[i - 1] == "-drive"]
        disk_drive = next(v for v in drive_args if "qcow2" in v)
        assert "discard=unmap" in disk_drive

    def test_ram_mb_arg_overrides_default(self) -> None:
        cmd = _cmd(ram_mb=2048)
        idx = cmd.index("-m")
        assert cmd[idx + 1] == "2048"

    def test_ram_mb_default_is_module_constant(self) -> None:
        cmd = _cmd()
        idx = cmd.index("-m")
        assert cmd[idx + 1] == str(launch_vm.RAM_MB)
