"""Tests for the tools-ISO builder.

The subprocess boundary (``_run_xorriso``) is monkeypatched so the staging /
validation / atomic-publish logic is exercised on any platform without a real
``xorriso``. One end-to-end test builds a real ISO and is skipped when
``xorriso`` is not installed.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from crossdesk_host.installer import tools_iso
from crossdesk_host.installer.tools_iso import ToolsIsoError, build_tools_iso


def _stub_inputs(d: Path) -> dict[str, Path]:
    agent = d / "agent.exe"
    agent.write_bytes(b"MZ\x90\x00fake-pe")
    ca = d / "ca.crt"
    ca.write_text("-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----\n")
    unattend = d / "autounattend.xml"
    unattend.write_text("<unattend/>\n")
    return {"agent_exe": agent, "ca_cert": ca, "autounattend": unattend}


def test_missing_agent_raises(tmp_path: Path) -> None:
    ins = _stub_inputs(tmp_path)
    ins["agent_exe"].unlink()
    with pytest.raises(ToolsIsoError, match="CrossDeskAgent.exe"):
        build_tools_iso(**ins, output_iso=tmp_path / "tools.iso", xorriso="xorriso")


def test_falls_back_to_pycdlib_when_no_xorriso(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No xorriso on PATH → the pure-Python pycdlib writer builds the ISO.
    ins = _stub_inputs(tmp_path)
    monkeypatch.setattr(tools_iso.shutil, "which", lambda _name: None)
    out = tmp_path / "tools.iso"

    result = build_tools_iso(**ins, output_iso=out)

    assert result == out
    data = out.read_bytes()
    assert len(data) > 0
    assert b"CROSSDESK" in data  # volume id landed → right image
    # The Joliet long names autounattend.xml copies from D:\ are present.
    assert "CrossDeskAgent.exe".encode("utf-16-be") in data
    assert "publisher-root-ca.crt".encode("utf-16-be") in data


def test_no_iso_backend_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Neither xorriso nor pycdlib available → a clear, actionable error.
    import sys

    ins = _stub_inputs(tmp_path)
    monkeypatch.setattr(tools_iso.shutil, "which", lambda _name: None)
    monkeypatch.setitem(sys.modules, "pycdlib", None)
    with pytest.raises(ToolsIsoError, match="no ISO builder available"):
        build_tools_iso(**ins, output_iso=tmp_path / "tools.iso")


def test_stages_canonical_names_and_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ins = _stub_inputs(tmp_path)
    out = tmp_path / "out" / "tools.iso"
    seen: dict[str, object] = {}

    def fake_run(xorriso: str, staging: Path, out_tmp: Path) -> None:
        seen["xorriso"] = xorriso
        seen["staged"] = sorted(p.name for p in staging.iterdir())
        out_tmp.write_bytes(b"ISO\x00data")  # stand in for a real image

    monkeypatch.setattr(tools_iso, "_run_xorriso", fake_run)

    result = build_tools_iso(**ins, output_iso=out, xorriso="/usr/bin/xorriso")

    assert result == out
    assert out.is_file()
    assert out.read_bytes() == b"ISO\x00data"
    assert seen["xorriso"] == "/usr/bin/xorriso"
    # Inputs were renamed to the names autounattend.xml copies from D:\.
    assert seen["staged"] == [
        "CrossDeskAgent.exe",
        "autounattend.xml",
        "publisher-root-ca.crt",
    ]
    # No leftover temp artifacts in the destination directory.
    assert sorted(p.name for p in out.parent.iterdir()) == ["tools.iso"]


def test_failed_pack_leaves_no_partial_iso(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ins = _stub_inputs(tmp_path)
    out = tmp_path / "tools.iso"

    def boom(xorriso: str, staging: Path, out_tmp: Path) -> None:
        out_tmp.write_bytes(b"partial")  # a half-written image...
        raise ToolsIsoError("xorriso exited 1: disc full")

    monkeypatch.setattr(tools_iso, "_run_xorriso", boom)

    with pytest.raises(ToolsIsoError, match="disc full"):
        build_tools_iso(**ins, output_iso=out, xorriso="xorriso")

    assert not out.exists()
    # The .tmp was cleaned up — destination dir holds only the stub inputs.
    leftover = [p.name for p in out.parent.iterdir() if p.name.startswith("tools.iso")]
    assert leftover == []


def _stub_mtls(d: Path) -> dict[str, Path]:
    ca = d / "mtls-ca.crt"
    ca.write_text("-----BEGIN CERTIFICATE-----\nmtls-ca\n-----END CERTIFICATE-----\n")
    cert = d / "mtls-guest.crt"
    cert.write_text("-----BEGIN CERTIFICATE-----\nguest\n-----END CERTIFICATE-----\n")
    key = d / "mtls-guest.key"
    key.write_text("-----BEGIN PRIVATE KEY-----\nguest\n-----END PRIVATE KEY-----\n")
    return {"mtls_ca": ca, "mtls_guest_cert": cert, "mtls_guest_key": key}


def test_mtls_pki_trio_staged_under_canonical_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ins = _stub_inputs(tmp_path)
    pki = _stub_mtls(tmp_path)
    out = tmp_path / "out" / "tools.iso"
    seen: dict[str, object] = {}

    def fake_run(xorriso: str, staging: Path, out_tmp: Path) -> None:
        seen["staged"] = sorted(p.name for p in staging.iterdir())
        out_tmp.write_bytes(b"ISO\x00data")

    monkeypatch.setattr(tools_iso, "_run_xorriso", fake_run)

    build_tools_iso(**ins, **pki, output_iso=out, xorriso="/usr/bin/xorriso")

    # The mTLS trio lands at the ISO root under the exact names the guest's
    # TlsMaterial::from_dir + autounattend.xml expect.
    assert seen["staged"] == [
        "CrossDeskAgent.exe",
        "autounattend.xml",
        "ca.crt",
        "guest.crt",
        "guest.key",
        "publisher-root-ca.crt",
    ]


def test_partial_mtls_pki_rejected(tmp_path: Path) -> None:
    ins = _stub_inputs(tmp_path)
    pki = _stub_mtls(tmp_path)
    # Drop one leg of the trio → all-or-nothing contract violated.
    del pki["mtls_guest_key"]
    with pytest.raises(ToolsIsoError, match="all-or-nothing"):
        build_tools_iso(
            **ins, **pki, output_iso=tmp_path / "tools.iso", xorriso="xorriso"
        )


def test_mtls_missing_file_named_in_error(tmp_path: Path) -> None:
    ins = _stub_inputs(tmp_path)
    pki = _stub_mtls(tmp_path)
    pki["mtls_guest_key"].unlink()
    with pytest.raises(ToolsIsoError, match="guest.key"):
        build_tools_iso(
            **ins, **pki, output_iso=tmp_path / "tools.iso", xorriso="xorriso"
        )


def test_mtls_pki_in_pycdlib_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ins = _stub_inputs(tmp_path)
    pki = _stub_mtls(tmp_path)
    monkeypatch.setattr(tools_iso.shutil, "which", lambda _name: None)
    out = tmp_path / "tools.iso"

    build_tools_iso(**ins, **pki, output_iso=out)

    data = out.read_bytes()
    # Joliet long names for the mTLS material are present in the image.
    assert "guest.crt".encode("utf-16-be") in data
    assert "guest.key".encode("utf-16-be") in data


@pytest.mark.skipif(shutil.which("xorriso") is None, reason="xorriso not installed")
def test_real_xorriso_builds_iso(tmp_path: Path) -> None:
    ins = _stub_inputs(tmp_path)
    out = tmp_path / "tools.iso"

    result = build_tools_iso(**ins, output_iso=out)

    assert result.is_file()
    assert result.stat().st_size > 0
    # The Joliet/Primary volume descriptor carries the volume id; assert it
    # landed so we know the right image was produced.
    assert b"CROSSDESK" in out.read_bytes()
    # Atomic publish left nothing but the final image.
    assert not any(p.name.endswith(".tmp") for p in out.parent.iterdir())
    assert os.access(out, os.R_OK)
