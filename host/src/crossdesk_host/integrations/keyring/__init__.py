"""Credential keyring abstraction (KDE / GNOME / file / mock).

The host writes the VM password somewhere; we'd prefer that ``somewhere``
to be the desktop-managed vault rather than a 0600 plaintext file. This
module's Protocol lets the daemon pick a backend at startup based on the
user's actual desktop environment, with a safe file-based fallback.

Available backends (the picker order matches what users care about):

1. :class:`KwalletKeyring` — KDE Plasma (uses ``kwallet5``/``kwallet6``).
2. :class:`GnomeKeyring` — GNOME / freedesktop libsecret (uses
   ``secretstorage`` Python lib).
3. :class:`FileKeyring` — 0600 TOML at ``~/.config/crossdesk/vm.toml``;
   the existing pre-Phase-7 storage stays as a graceful fallback for
   headless / minimal sessions.
4. :class:`MockKeyring` — in-memory; tests + Mac dev.

Mac dev defaults to :class:`MockKeyring` chained with
:class:`FileKeyring` because the file backend works everywhere.
"""

from crossdesk_host.integrations.keyring.base import Keyring, KeyringError
from crossdesk_host.integrations.keyring.file_backend import FileKeyring
from crossdesk_host.integrations.keyring.gnome import GnomeKeyring
from crossdesk_host.integrations.keyring.kwallet import KwalletKeyring
from crossdesk_host.integrations.keyring.mock import MockKeyring
from crossdesk_host.integrations.keyring.picker import detect_backend

__all__ = [
    "FileKeyring",
    "GnomeKeyring",
    "Keyring",
    "KeyringError",
    "KwalletKeyring",
    "MockKeyring",
    "detect_backend",
]
