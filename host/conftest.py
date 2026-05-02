"""Top-level pytest config: makes `crossdesk_host` importable without `pip install`.

The host package isn't pip-installable on macOS (libvirt-python wheel needs
libvirt-dev headers we don't ship), but the modules under test are pure Python
+ generated proto stubs. Inserting both source roots onto sys.path lets pytest
import them straight from the working tree, mirroring what run_mock_macos.sh
does for the daemon process.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SRC = _HERE / "src"
_PROTO = _SRC / "crossdesk_host" / "proto"

for path in (_SRC, _PROTO):
    sys.path.insert(0, str(path))
