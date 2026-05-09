"""File-backed keyring: ``~/.config/crossdesk/keyring.toml`` (0600).

Last-resort backend that always works. Doesn't replace the existing
``~/.config/crossdesk/vm.toml`` — they coexist (vm.toml stays the
canonical store for now; this is for arbitrary keys the GUI or
integrations may need to stash, e.g. cached telemetry tokens).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

if sys.version_info >= (3, 11):
    import tomllib as _tomllib  # type: ignore[import-not-found,unused-ignore]
else:  # pragma: no cover
    import tomli as _tomllib  # type: ignore[import-not-found]

from crossdesk_host.integrations.keyring.base import Keyring
import contextlib


class FileKeyring(Keyring):
    name = "file"

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path: Optional[Path] = path

    def _resolved_path(self) -> Path:
        if self._path is not None:
            return self._path
        return Path.home() / ".config" / "crossdesk" / "keyring.toml"

    def _read(self) -> Dict[str, Any]:
        path = self._resolved_path()
        if not path.exists():
            return {}
        with path.open("rb") as f:
            return dict(_tomllib.load(f))

    def _write(self, data: Dict[str, Any]) -> None:
        path = self._resolved_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for k, v in data.items():
                    if not isinstance(v, str):
                        continue
                    escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
                    f.write(f'{k} = "{escaped}"\n')
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, 0o600)
            os.rename(tmp, path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    def get(self, key: str) -> Optional[str]:
        data = self._read()
        v = data.get(key)
        return v if isinstance(v, str) else None

    def set(self, key: str, value: str) -> None:
        data = self._read()
        data[key] = value
        self._write(data)

    def delete(self, key: str) -> None:
        data = self._read()
        if key in data:
            del data[key]
            self._write(data)

    def is_available(self) -> bool:
        # Filesystem is always reachable.
        return True
