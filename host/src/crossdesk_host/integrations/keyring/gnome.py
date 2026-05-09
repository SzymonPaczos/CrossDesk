"""GNOME / freedesktop libsecret backend via ``secretstorage`` Python lib.

Linux + GNOME (or any DE that ships a libsecret-implementing keyring).
Uses ``secretstorage`` rather than ``secret-tool`` subprocess so we get
typed errors and don't pay a fork cost on every read.

End-to-end testing requires gnome-keyring-daemon running under D-Bus
(Linux+GNOME). On Mac dev we silently no-op via ``is_available() ==
False`` and the picker falls back to file/mock.
"""

from __future__ import annotations

from typing import Any, Optional, cast

from crossdesk_host.integrations.keyring.base import Keyring, KeyringError

_ATTRIBUTE_KEY = "crossdesk.key"


class GnomeKeyring(Keyring):
    name = "gnome"

    def __init__(self) -> None:
        self._connection: Optional[Any] = None

    def _open(self) -> Optional[Any]:
        if self._connection is not None:
            return self._connection
        try:
            import secretstorage  # type: ignore[import-not-found]
        except ImportError:
            return None
        try:
            connection = secretstorage.dbus_init()
        except Exception:
            return None
        self._connection = connection
        return cast(Any, connection)

    def is_available(self) -> bool:
        return self._open() is not None

    def _collection(self) -> Optional[Any]:
        connection = self._open()
        if connection is None:
            return None
        try:
            import secretstorage

            collection = secretstorage.get_default_collection(connection)
            if collection.is_locked():
                collection.unlock()
            return cast(Any, collection)
        except Exception as exc:
            raise KeyringError(f"libsecret collection unreachable: {exc}") from exc

    def get(self, key: str) -> Optional[str]:
        collection = self._collection()
        if collection is None:
            return None
        for item in collection.search_items({_ATTRIBUTE_KEY: key}):
            secret = item.get_secret().decode("utf-8")
            return cast(str, secret)
        return None

    def set(self, key: str, value: str) -> None:
        collection = self._collection()
        if collection is None:
            raise KeyringError("libsecret unavailable")
        # Replace any existing entry first so we don't accumulate.
        self.delete(key)
        collection.create_item(
            label=f"CrossDesk: {key}",
            attributes={_ATTRIBUTE_KEY: key},
            secret=value.encode("utf-8"),
        )

    def delete(self, key: str) -> None:
        collection = self._collection()
        if collection is None:
            return
        for item in collection.search_items({_ATTRIBUTE_KEY: key}):
            try:
                item.delete()
            except Exception:
                pass
