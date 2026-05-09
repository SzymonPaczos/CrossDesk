"""In-memory keyring for tests + Mac dev."""

from __future__ import annotations

from typing import Dict, Optional

from crossdesk_host.integrations.keyring.base import Keyring


class MockKeyring(Keyring):
    name = "mock"

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def set(self, key: str, value: str) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def is_available(self) -> bool:
        return True
