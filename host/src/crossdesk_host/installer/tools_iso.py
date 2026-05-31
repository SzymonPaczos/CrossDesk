"""Build the CrossDesk *tools ISO* — the second optical drive (``D:``) the
Windows guest boots alongside the Windows installation media.

Its root holds the three files that ``infra/autounattend.xml``'s
``FirstLogonCommands`` consume on first boot:

- ``CrossDeskAgent.exe``     — the cross-compiled NT-service agent
  (copied to ``C:\\Windows\\System32`` and registered as a service).
- ``publisher-root-ca.crt``  — the publisher root CA imported into the
  guest trust store (its leaf signed ``CrossDeskAgent.exe``).
- ``autounattend.xml``       — the Windows unattended-install answer file
  (Windows Setup auto-discovers it on any drive root).

The ISO is produced with ``xorriso`` in mkisofs-emulation mode. The bytes
are written to a sibling ``*.tmp`` in the destination directory and
``os.replace``-d into place, so a crashed or interrupted build never leaves
a half-written ISO at ``output_iso`` (same atomicity contract as
:mod:`crossdesk_host.utils.atomic_write`, adapted for a binary artifact a
subprocess produces).
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Canonical names inside the ISO root — these are the literal paths
# infra/autounattend.xml copies from D:\, so they are a hard contract.
_AGENT_ISO_NAME = "CrossDeskAgent.exe"
_CA_ISO_NAME = "publisher-root-ca.crt"
_AUTOUNATTEND_ISO_NAME = "autounattend.xml"
_VOLUME_ID = "CROSSDESK"

# A local mkisofs run on three small files is bounded; a hang means a broken
# xorriso, not slow work — fail loudly rather than wedge the install.
_XORRISO_TIMEOUT_S = 120.0


class ToolsIsoError(RuntimeError):
    """Raised when the tools ISO cannot be built (missing input, missing
    ``xorriso``, or a non-zero ``xorriso`` exit)."""


def _run_xorriso(xorriso: str, staging: Path, out_tmp: Path) -> None:
    """Invoke ``xorriso`` to pack *staging* into the ISO at *out_tmp*.

    Split out so tests can monkeypatch the subprocess boundary without a
    real ``xorriso`` on the box.
    """
    argv = [
        xorriso,
        "-as",
        "mkisofs",
        "-V",
        _VOLUME_ID,
        "-J",  # Joliet — long/mixed-case names readable by Windows
        "-r",  # Rock Ridge — POSIX names (harmless on Windows, helps Linux QA)
        "-o",
        str(out_tmp),
        str(staging),
    ]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_XORRISO_TIMEOUT_S,
            check=False,
        )
    except FileNotFoundError as exc:  # xorriso vanished between which() and run()
        raise ToolsIsoError(f"xorriso not found: {xorriso}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolsIsoError(
            f"xorriso timed out after {_XORRISO_TIMEOUT_S:.0f}s"
        ) from exc
    if proc.returncode != 0:
        raise ToolsIsoError(
            f"xorriso exited {proc.returncode}: {proc.stderr.strip()}"
        )


def _iso9660_name(name: str) -> str:
    """Derive a Level-3 ISO9660 identifier (uppercase, ``A-Z0-9_`` + one
    dot) from a canonical name. Windows reads the Joliet long name, so this
    legacy identifier only has to be valid, not pretty."""
    base, dot, ext = name.rpartition(".")
    if not dot:
        base, ext = name, ""

    def clean(s: str) -> str:
        return "".join(c if c.isalnum() else "_" for c in s.upper())

    return f"{clean(base)}.{clean(ext)}" if ext else clean(base)


def _build_with_pycdlib(inputs: "dict[str, Path]", out_tmp: Path) -> None:
    """Fallback ISO writer when ``xorriso`` is absent. Adds each input at
    the root under its canonical Joliet name (the legacy ISO9660 name is
    mangled but unused by Windows)."""
    try:
        import pycdlib
    except ImportError as exc:  # neither backend available
        raise ToolsIsoError(
            "no ISO builder available — install xorriso "
            "(`sudo apt-get install -y xorriso`) or pycdlib (`pip install pycdlib`)"
        ) from exc

    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=3, joliet=3, vol_ident=_VOLUME_ID)
    try:
        for iso_name, src in inputs.items():
            iso.add_file(
                str(src),
                iso_path=f"/{_iso9660_name(iso_name)};1",
                joliet_path=f"/{iso_name}",
            )
        iso.write(str(out_tmp))
    finally:
        iso.close()


def build_tools_iso(
    *,
    agent_exe: Path,
    ca_cert: Path,
    autounattend: Path,
    output_iso: Path,
    xorriso: str | None = None,
) -> Path:
    """Build the tools ISO at *output_iso* and return its path.

    The three inputs are placed at the ISO root under their canonical names
    (``CrossDeskAgent.exe`` / ``publisher-root-ca.crt`` / ``autounattend.xml``),
    so the caller's on-disk filenames don't matter. Uses ``xorriso`` when
    present (override the binary with *xorriso*) and otherwise falls back to
    the pure-Python ``pycdlib`` writer.

    Raises :class:`ToolsIsoError` if any input is missing, if neither ISO
    backend is available, or if the pack fails.
    """
    inputs = {
        _AGENT_ISO_NAME: agent_exe,
        _CA_ISO_NAME: ca_cert,
        _AUTOUNATTEND_ISO_NAME: autounattend,
    }
    for iso_name, src in inputs.items():
        if not src.is_file():
            raise ToolsIsoError(f"input for {iso_name} is not a file: {src}")

    resolved = xorriso or shutil.which("xorriso")
    output_iso.parent.mkdir(parents=True, exist_ok=True)

    # Pack into a sibling temp file, then atomically publish it. A rename
    # within the same directory stays on one filesystem.
    fd, tmp_str = tempfile.mkstemp(
        dir=str(output_iso.parent), prefix=output_iso.name + ".", suffix=".tmp"
    )
    os.close(fd)
    out_tmp = Path(tmp_str)
    try:
        if resolved is not None:
            with tempfile.TemporaryDirectory(
                dir=str(output_iso.parent), prefix="tools-iso-stage."
            ) as staging_str:
                staging = Path(staging_str)
                for iso_name, src in inputs.items():
                    shutil.copyfile(src, staging / iso_name)
                _run_xorriso(resolved, staging, out_tmp)
        else:
            _build_with_pycdlib(inputs, out_tmp)
        os.replace(out_tmp, output_iso)
    except BaseException:
        with contextlib.suppress(OSError):
            out_tmp.unlink()
        raise

    return output_iso
