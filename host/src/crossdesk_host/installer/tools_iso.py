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


def build_tools_iso(
    *,
    agent_exe: Path,
    ca_cert: Path,
    autounattend: Path,
    output_iso: Path,
    xorriso: str | None = None,
) -> Path:
    """Build the tools ISO at *output_iso* and return its path.

    The three inputs are staged under their canonical ISO-root names
    (``CrossDeskAgent.exe`` / ``publisher-root-ca.crt`` / ``autounattend.xml``)
    before packing, so the caller's on-disk filenames don't matter.

    Raises :class:`ToolsIsoError` if any input is missing, if ``xorriso`` is
    not on ``PATH`` (override with *xorriso*), or if the pack fails.
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
    if resolved is None:
        raise ToolsIsoError(
            "xorriso not found on PATH — install it "
            "(e.g. `sudo apt-get install -y xorriso`)"
        )

    output_iso.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        dir=str(output_iso.parent), prefix="tools-iso-stage."
    ) as staging_str:
        staging = Path(staging_str)
        for iso_name, src in inputs.items():
            shutil.copyfile(src, staging / iso_name)

        # Pack into a sibling temp file, then atomically publish it. A
        # rename within the same directory stays on one filesystem.
        fd, tmp_str = tempfile.mkstemp(
            dir=str(output_iso.parent), prefix=output_iso.name + ".", suffix=".tmp"
        )
        os.close(fd)
        out_tmp = Path(tmp_str)
        try:
            _run_xorriso(resolved, staging, out_tmp)
            os.replace(out_tmp, output_iso)
        except BaseException:
            with contextlib.suppress(OSError):
                out_tmp.unlink()
            raise

    return output_iso
