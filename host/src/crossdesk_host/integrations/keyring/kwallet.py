"""KWallet backend. Linux+KDE only.

Uses ``kwallet5-cli`` (or ``kwallet6-cli``) via subprocess so we don't
add a build-time dep on a KDE library. The performance hit doesn't
matter — we read the credential once at daemon startup and cache.

End-to-end testing requires a running KWallet daemon (Linux+KDE).
The Mac dev environment simply reports ``is_available() == False``;
the picker falls through to the file backend.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional

from crossdesk_host.integrations.keyring.base import Keyring, KeyringError

_FOLDER = "CrossDesk"


def _resolve_cli() -> Optional[str]:
    for binary in ("kwallet-query", "kwallet5-cli", "kwallet6-cli"):
        path = shutil.which(binary)
        if path is not None:
            return path
    return None


class KwalletKeyring(Keyring):
    name = "kwallet"

    def is_available(self) -> bool:
        return _resolve_cli() is not None

    def get(self, key: str) -> Optional[str]:
        cli = _resolve_cli()
        if cli is None:
            return None
        try:
            result = subprocess.run(
                [cli, "--read-password", key, "--folder", _FOLDER, "kdewallet"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise KeyringError(f"kwallet read failed: {exc}") from exc
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value if value else None

    def set(self, key: str, value: str) -> None:
        cli = _resolve_cli()
        if cli is None:
            raise KeyringError("kwallet CLI not available")
        try:
            result = subprocess.run(
                [cli, "--write-password", key, "--folder", _FOLDER, "kdewallet"],
                input=value,
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise KeyringError(f"kwallet write failed: {exc}") from exc
        if result.returncode != 0:
            raise KeyringError(
                f"kwallet write returned {result.returncode}: {result.stderr}"
            )

    def delete(self, key: str) -> None:
        cli = _resolve_cli()
        if cli is None:
            return
        # `kwallet-query --remove-password` is the canonical removal verb.
        subprocess.run(
            [cli, "--remove-password", key, "--folder", _FOLDER, "kdewallet"],
            check=False,
            capture_output=True,
            timeout=5.0,
        )
