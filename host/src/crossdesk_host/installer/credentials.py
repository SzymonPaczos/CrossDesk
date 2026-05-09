"""VM credential storage at ``~/.config/crossdesk/vm.toml``.

Two-phase commit semantics for rotation: a new credential is written
to disk *before* the guest password is changed, so a crash between
the two leaves the host with the new credential and the guest with
the old — recoverable via ``crossdesk vm credentials repair`` (which
re-applies the host's stored credential to the guest). The opposite
ordering (guest first, host second) leaves the system unrecoverable
because the host has no record of the new password.

File mode is forced to 0600 on write (POSIX) so other local users
can't read the password. The directory itself stays at the user's
default umask — only the credential file is locked down.
"""

from __future__ import annotations

import os
import secrets
import string
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import sys
import contextlib

if sys.version_info >= (3, 11):
    import tomllib as _tomllib  # type: ignore[import-not-found,unused-ignore]
else:  # pragma: no cover
    import tomli as _tomllib  # type: ignore[import-not-found]


_DEFAULT_USERNAME = "crossdesk"


def _default_path() -> Path:
    # Resolve at call time so tests monkey-patching ``HOME`` are honoured.
    return Path.home() / ".config" / "crossdesk" / "vm.toml"


_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
_PASSWORD_LENGTH = 20


@dataclass(frozen=True)
class VmCredentials:
    username: str
    password: str

    def to_toml(self) -> str:
        # Tiny manual emit avoids pulling another runtime dep just to
        # write two strings. Both fields are run through repr() to
        # quote/escape correctly.
        return (
            f'username = "{self._escape(self.username)}"\n'
            f'password = "{self._escape(self.password)}"\n'
        )

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')


def generate(username: str = _DEFAULT_USERNAME) -> VmCredentials:
    """Generate a fresh credential with a strong random password."""
    password = "".join(
        secrets.choice(_PASSWORD_ALPHABET) for _ in range(_PASSWORD_LENGTH)
    )
    return VmCredentials(username=username, password=password)


def save(creds: VmCredentials, path: Optional[Path] = None) -> None:
    if path is None:
        path = _default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(creds.to_toml())
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, 0o600)
        os.rename(tmp_path, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def load(path: Optional[Path] = None) -> Optional[VmCredentials]:
    if path is None:
        path = _default_path()
    if not path.exists():
        return None
    with path.open("rb") as f:
        data = _tomllib.load(f)
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        raise ValueError(f"malformed vm.toml at {path}")
    return VmCredentials(username=username, password=password)


def default_path() -> Path:
    return _default_path()
