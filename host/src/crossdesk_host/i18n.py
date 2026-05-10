"""gettext facade for user-facing CLI strings.

Why a facade and not a bare ``gettext.gettext``: per ``docs/I18N.md``
the CLI ships ``.mo`` catalogs to ``/usr/share/locale/<lang>/LC_MESSAGES/``
when distro-installed but lives in-repo at ``i18n/`` during development.
A small initializer hides that lookup so call sites only ever see
``_("...")`` and never have to know which path won.

The module degrades to ``NullTranslations`` when no catalog is found —
in that mode ``_("Hello")`` returns ``"Hello"`` unchanged, which is
exactly what we want during early development before any ``.mo`` file
ships. No exceptions, no warnings; the unconfigured path is the
English path.

Per ``docs/I18N.md`` "Strings we don't translate" — log messages,
component identifiers, error codes, and configuration field names
stay English. Only user-visible CLI output gets wrapped in ``_(...)``.
"""

from __future__ import annotations

import gettext
import os
from pathlib import Path
from typing import List, Optional

DOMAIN = "crossdesk-host"


def _candidate_localedirs() -> List[Path]:
    """Return localedirs to probe, in priority order.

    1. ``$CROSSDESK_LOCALEDIR`` if set (test fixtures, dev override).
    2. ``$XDG_DATA_DIRS``-derived ``locale/`` paths (system install).
    3. The in-repo ``i18n/`` directory three levels above this file
       (development checkout — the ``.mo`` files are produced by
       ``msgfmt`` from ``i18n/pl/LC_MESSAGES/crossdesk-host.po``).
    """
    candidates: List[Path] = []

    override = os.environ.get("CROSSDESK_LOCALEDIR")
    if override:
        candidates.append(Path(override))

    xdg_data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    for entry in xdg_data_dirs.split(":"):
        if entry:
            candidates.append(Path(entry) / "locale")

    # Repo layout: host/src/crossdesk_host/i18n.py → repo_root/i18n/
    repo_i18n = Path(__file__).resolve().parents[3] / "i18n"
    candidates.append(repo_i18n)

    return candidates


def _load() -> gettext.NullTranslations:
    """Pick the first candidate dir that yields a catalog.

    Returns ``NullTranslations`` (identity ``gettext``) when none match
    so the caller never has to branch on "i18n configured?".
    """
    languages: Optional[List[str]] = None  # let gettext honor $LANGUAGE/$LC_*

    for localedir in _candidate_localedirs():
        if not localedir.is_dir():
            continue
        try:
            return gettext.translation(
                DOMAIN, localedir=str(localedir), languages=languages, fallback=False
            )
        except FileNotFoundError:
            continue

    return gettext.NullTranslations()


_translations: gettext.NullTranslations = _load()


def _(message: str) -> str:
    """Translate ``message`` via the active catalog (identity if none)."""
    return _translations.gettext(message)


def reload() -> None:
    """Re-probe localedirs.

    Used by tests after writing a fixture catalog and by
    ``CROSSDESK_LOCALEDIR`` overrides set after import. Production
    code does not call this — the load happens once at import.
    """
    global _translations
    _translations = _load()
