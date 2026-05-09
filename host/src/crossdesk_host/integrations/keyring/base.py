"""Keyring Protocol — every backend implements this surface."""

from __future__ import annotations

from typing import Optional, Protocol


class KeyringError(RuntimeError):
    """Raised on backend-side failure (KWallet not running, libsecret
    permission denied, etc). Callers catch this and fall through to
    :class:`FileKeyring` as a last resort."""


class Keyring(Protocol):
    name: str  # human-readable; used in diagnostics + logs

    def get(self, key: str) -> Optional[str]:
        """Return the value for ``key`` or ``None`` if missing."""
        ...

    def set(self, key: str, value: str) -> None:
        """Store ``value`` under ``key`` (overwrites any existing)."""
        ...

    def delete(self, key: str) -> None:
        """Remove ``key``. No-op if absent."""
        ...

    def is_available(self) -> bool:
        """Cheap probe — does this backend actually work right now?"""
        ...
