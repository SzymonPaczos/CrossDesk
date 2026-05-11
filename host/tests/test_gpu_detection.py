"""Tests for doctor GPU passthrough detection checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from crossdesk_host.doctor.checks import (
    GpuInfo,
    Status,
    _classify_gpu,
    _iommu_enabled,
    _iommu_group_devices,
    _iommu_group_for,
    _parse_lspci_output,
    check_gpu_passthrough,
)

# Minimal lspci -nn output for different GPU tiers
_LSPCI_NVIDIA_RTX3080 = (
    "01:00.0 VGA compatible controller [0300] "
    "NVIDIA Corporation GA102 [GeForce RTX 3080] [10de:2206] "
    "(rev a1)"
)
_LSPCI_NVIDIA_GTX1080 = (
    "01:00.0 VGA compatible controller [0300] "
    "NVIDIA Corporation GP104 [GeForce GTX 1080] [10de:1b80] "
    "(rev a1)"
)
_LSPCI_AMD_RX6800 = (
    "09:00.0 VGA compatible controller [0300] "
    "Advanced Micro Devices [AMD/ATI] Navi 21 [Radeon RX 6800 XT] [1002:73bf] "
    "(rev c1)"
)
_LSPCI_AMD_RX580 = (
    "09:00.0 VGA compatible controller [0300] "
    "Advanced Micro Devices [AMD/ATI] Ellesmere [Radeon RX 580] [1002:67df] "
    "(rev e7)"
)
_LSPCI_INTEL_ARC = (
    "00:02.0 VGA compatible controller [0300] "
    "Intel Corporation Arc A770 [8086:56a0] "
    "(rev 08)"
)
_LSPCI_TWO_GPUS = "\n".join([_LSPCI_AMD_RX6800, _LSPCI_INTEL_ARC])


class TestParseLspciOutput:
    def test_nvidia_rtx(self) -> None:
        gpus = _parse_lspci_output(_LSPCI_NVIDIA_RTX3080)
        assert len(gpus) == 1
        assert gpus[0].vendor_id == "10de"
        assert gpus[0].device_id == "2206"
        assert gpus[0].pci_id == "01:00.0"

    def test_amd_rx6800(self) -> None:
        gpus = _parse_lspci_output(_LSPCI_AMD_RX6800)
        assert len(gpus) == 1
        assert gpus[0].vendor_id == "1002"
        assert gpus[0].device_id == "73bf"

    def test_intel_arc(self) -> None:
        gpus = _parse_lspci_output(_LSPCI_INTEL_ARC)
        assert len(gpus) == 1
        assert gpus[0].vendor_id == "8086"

    def test_two_gpus(self) -> None:
        gpus = _parse_lspci_output(_LSPCI_TWO_GPUS)
        assert len(gpus) == 2

    def test_empty_output(self) -> None:
        assert _parse_lspci_output("") == []

    def test_non_gpu_lines_ignored(self) -> None:
        output = (
            "00:1f.3 Audio device [0403] Intel Corporation [8086:a3f0]\n"
            + _LSPCI_NVIDIA_RTX3080
        )
        gpus = _parse_lspci_output(output)
        assert len(gpus) == 1


class TestClassifyGpu:
    def test_nvidia_rtx3080_tier1(self) -> None:
        gpu = GpuInfo(pci_id="01:00.0", vendor_id="10de", device_id="2206", name="RTX 3080")
        assert _classify_gpu(gpu) == 1

    def test_nvidia_gtx1080_tier2(self) -> None:
        gpu = GpuInfo(pci_id="01:00.0", vendor_id="10de", device_id="1b80", name="GTX 1080")
        assert _classify_gpu(gpu) == 2

    def test_amd_rdna2_tier1(self) -> None:
        gpu = GpuInfo(pci_id="09:00.0", vendor_id="1002", device_id="73bf", name="RX 6800 XT")
        assert _classify_gpu(gpu) == 1

    def test_amd_rdna3_tier1(self) -> None:
        gpu = GpuInfo(pci_id="09:00.0", vendor_id="1002", device_id="744c", name="RX 7900 XTX")
        assert _classify_gpu(gpu) == 1

    def test_amd_rx580_tier2(self) -> None:
        gpu = GpuInfo(pci_id="09:00.0", vendor_id="1002", device_id="67df", name="RX 580")
        assert _classify_gpu(gpu) == 2

    def test_intel_tier3(self) -> None:
        gpu = GpuInfo(pci_id="00:02.0", vendor_id="8086", device_id="56a0", name="Arc A770")
        assert _classify_gpu(gpu) == 3


class TestIommuHelpers:
    def test_iommu_enabled_with_devices(self, tmp_path: Path) -> None:
        iommu_dir = tmp_path / "class" / "iommu"
        iommu_dir.mkdir(parents=True)
        (iommu_dir / "dmar0").touch()
        assert _iommu_enabled(tmp_path) is True

    def test_iommu_disabled_empty_dir(self, tmp_path: Path) -> None:
        iommu_dir = tmp_path / "class" / "iommu"
        iommu_dir.mkdir(parents=True)
        assert _iommu_enabled(tmp_path) is False

    def test_iommu_disabled_no_dir(self, tmp_path: Path) -> None:
        assert _iommu_enabled(tmp_path) is False

    def test_iommu_group_for_device(self, tmp_path: Path) -> None:
        group_target = tmp_path / "kernel" / "iommu_groups" / "7"
        group_target.mkdir(parents=True)
        link_dir = tmp_path / "bus" / "pci" / "devices" / "0000:01:00.0"
        link_dir.mkdir(parents=True)
        (link_dir / "iommu_group").symlink_to(group_target)
        result = _iommu_group_for("01:00.0", tmp_path)
        assert result == "7"

    def test_iommu_group_missing(self, tmp_path: Path) -> None:
        result = _iommu_group_for("01:00.0", tmp_path)
        assert result is None

    def test_iommu_group_devices(self, tmp_path: Path) -> None:
        devices_dir = tmp_path / "kernel" / "iommu_groups" / "7" / "devices"
        devices_dir.mkdir(parents=True)
        (devices_dir / "0000:01:00.0").touch()
        (devices_dir / "0000:01:00.1").touch()
        devs = _iommu_group_devices("7", tmp_path)
        assert "0000:01:00.0" in devs
        assert "0000:01:00.1" in devs


class TestCheckGpuPassthrough:
    def _make_iommu_sys(self, tmp_path: Path, group: str = "7") -> Path:
        """Create a minimal /sys tree with IOMMU enabled + one GPU in its own group."""
        iommu_class = tmp_path / "class" / "iommu"
        iommu_class.mkdir(parents=True)
        (iommu_class / "dmar0").touch()

        group_target = tmp_path / "kernel" / "iommu_groups" / group
        group_target.mkdir(parents=True)
        devices_dir = group_target / "devices"
        devices_dir.mkdir()
        (devices_dir / "0000:01:00.0").touch()
        (devices_dir / "0000:01:00.1").touch()

        link_dir = tmp_path / "bus" / "pci" / "devices" / "0000:01:00.0"
        link_dir.mkdir(parents=True)
        (link_dir / "iommu_group").symlink_to(group_target)
        return tmp_path

    def test_non_linux_returns_warn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "crossdesk_host.doctor.checks.platform.system", lambda: "Darwin"
        )
        result = check_gpu_passthrough()
        assert result.status == Status.WARN
        assert "non-Linux" in result.message

    def test_tier1_nvidia_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "crossdesk_host.doctor.checks.platform.system", lambda: "Linux"
        )
        sys_root = self._make_iommu_sys(tmp_path)
        result = check_gpu_passthrough(
            sys_root=sys_root,
            lspci_output=_LSPCI_NVIDIA_RTX3080,
        )
        assert result.status == Status.OK
        assert "Tier 1" in result.message

    def test_amd_rdna2_tier1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "crossdesk_host.doctor.checks.platform.system", lambda: "Linux"
        )
        sys_root = self._make_iommu_sys(tmp_path, group="3")
        # Wire the AMD GPU's PCI ID into the sys tree
        link_dir = tmp_path / "bus" / "pci" / "devices" / "0000:09:00.0"
        link_dir.mkdir(parents=True)
        group_target = tmp_path / "kernel" / "iommu_groups" / "3"
        (link_dir / "iommu_group").symlink_to(group_target)
        result = check_gpu_passthrough(
            sys_root=sys_root,
            lspci_output=_LSPCI_AMD_RX6800,
        )
        assert result.status == Status.OK
        assert "Tier 1" in result.message

    def test_iommu_disabled_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "crossdesk_host.doctor.checks.platform.system", lambda: "Linux"
        )
        result = check_gpu_passthrough(
            sys_root=tmp_path,
            lspci_output=_LSPCI_NVIDIA_RTX3080,
        )
        assert result.status == Status.FAIL
        assert "IOMMU" in result.message

    def test_intel_tier3_warns(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "crossdesk_host.doctor.checks.platform.system", lambda: "Linux"
        )
        result = check_gpu_passthrough(
            sys_root=tmp_path,
            lspci_output=_LSPCI_INTEL_ARC,
        )
        assert result.status == Status.WARN

    def test_no_gpus_warns(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "crossdesk_host.doctor.checks.platform.system", lambda: "Linux"
        )
        result = check_gpu_passthrough(sys_root=tmp_path, lspci_output="")
        assert result.status == Status.WARN
        assert "no VGA-class" in result.message

    def test_tier2_gpu_warns(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "crossdesk_host.doctor.checks.platform.system", lambda: "Linux"
        )
        sys_root = self._make_iommu_sys(tmp_path)
        result = check_gpu_passthrough(
            sys_root=sys_root,
            lspci_output=_LSPCI_NVIDIA_GTX1080,
        )
        assert result.status == Status.WARN
        assert "Tier 2" in result.message
