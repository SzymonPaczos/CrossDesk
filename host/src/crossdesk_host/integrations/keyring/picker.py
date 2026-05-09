"""Pick the best-available keyring backend for the running session.

Probe order:
1. ``KwalletKeyring`` if KDE Plasma is the active session.
2. ``GnomeKeyring`` if GNOME / libsecret is available.
3. ``FileKeyring`` always.

We fall through cleanly when a probe raises (missing CLI, locked
wallet, etc) so a misconfigured KDE doesn't lock the user out — they
just see file-backed credentials with a warning in logs.
"""

from __future__ import annotations

import os

from crossdesk_host.integrations.keyring.base import Keyring
from crossdesk_host.integrations.keyring.file_backend import FileKeyring
from crossdesk_host.integrations.keyring.gnome import GnomeKeyring
from crossdesk_host.integrations.keyring.kwallet import KwalletKeyring


def _running_kde() -> bool:
    desktop = (os.environ.get("XDG_CURRENT_DESKTOP") or "").upper()
    session = (os.environ.get("DESKTOP_SESSION") or "").lower()
    return "KDE" in desktop or "PLASMA" in desktop or "plasma" in session


def _running_gnome() -> bool:
    desktop = (os.environ.get("XDG_CURRENT_DESKTOP") or "").upper()
    return "GNOME" in desktop or "UNITY" in desktop


def detect_backend(prefer_keyring: bool = True) -> Keyring:
    """Return the best-available backend.

    ``prefer_keyring=False`` short-circuits to :class:`FileKeyring` —
    used when the user disables keyring integration in Settings.
    """
    if prefer_keyring:
        if _running_kde():
            kw = KwalletKeyring()
            if kw.is_available():
                return kw
        if _running_gnome():
            gk = GnomeKeyring()
            if gk.is_available():
                return gk
    return FileKeyring()
