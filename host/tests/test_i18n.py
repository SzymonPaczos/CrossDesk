"""Tests for ``crossdesk_host.i18n`` — the gettext facade.

The unconfigured path (``NullTranslations``) must return inputs
unchanged so a pre-translation install still emits English. The
configured path must resolve a compiled ``.mo`` catalog placed under
``$CROSSDESK_LOCALEDIR``.

We build the catalog inline with ``msgfmt`` so the test does not
depend on a checked-in fixture (one less file to drift with the
canonical .po format). If ``msgfmt`` is missing on the host the
catalog test is skipped — the identity test still runs.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path
from typing import Iterator

import pytest

from crossdesk_host import i18n


@pytest.fixture(autouse=True)
def _restore_translations() -> Iterator[None]:
    """Snapshot+restore the module-level catalog around each test.

    The module loads a catalog at import time; mutating
    ``$CROSSDESK_LOCALEDIR`` and calling ``reload()`` swaps it out.
    Restore the original so test order does not leak state.
    """
    original = i18n._translations
    yield
    i18n._translations = original


def test_identity_when_no_catalog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With no .mo file on any candidate path, _() returns the input."""
    monkeypatch.setenv("CROSSDESK_LOCALEDIR", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path))  # also empty
    i18n.reload()
    assert i18n._("Hello") == "Hello"
    assert i18n._("untranslated string") == "untranslated string"


def test_empty_localedir_falls_back_to_null(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A localedir that exists but holds no catalog still returns identity."""
    (tmp_path / "pl" / "LC_MESSAGES").mkdir(parents=True)
    monkeypatch.setenv("CROSSDESK_LOCALEDIR", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_DIRS", "")
    i18n.reload()
    assert i18n._("Hello") == "Hello"


@pytest.mark.skipif(
    shutil.which("msgfmt") is None,
    reason="msgfmt (gettext) not installed; skipping catalog round-trip",
)
def test_catalog_lookup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A compiled .mo at the right path translates registered messages.

    Builds a tiny pl/LC_MESSAGES/crossdesk-host.mo via msgfmt, points
    CROSSDESK_LOCALEDIR at the temp tree, forces the language to ``pl``,
    and asserts _() returns the Polish string.
    """
    po = tmp_path / "pl" / "LC_MESSAGES" / "crossdesk-host.po"
    po.parent.mkdir(parents=True)
    po.write_text(
        'msgid ""\n'
        'msgstr ""\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Language: pl\\n"\n'
        "\n"
        'msgid "Hello"\n'
        'msgstr "Cześć"\n',
        encoding="utf-8",
    )
    subprocess.run(
        ["msgfmt", str(po), "-o", str(po.with_suffix(".mo"))],
        check=True,
    )

    monkeypatch.setenv("CROSSDESK_LOCALEDIR", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_DIRS", "")
    monkeypatch.setenv("LANGUAGE", "pl")
    monkeypatch.setenv("LC_ALL", "pl_PL.UTF-8")
    i18n.reload()

    assert i18n._("Hello") == "Cześć"
    # Unregistered messages still pass through unchanged — gettext falls
    # back to the msgid when no translation exists for that string.
    assert i18n._("untranslated string") == "untranslated string"


def test_reload_picks_up_new_catalog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Calling reload() after the env changes swaps the active catalog.

    Synthesises a minimal valid .mo file by hand (no msgfmt dependency)
    so we can run on hosts without gettext. The .mo binary format is
    documented in GNU gettext §8.3 — a 28-byte header plus two parallel
    tables of (length, offset) pairs followed by the strings.
    """
    domain_dir = tmp_path / "pl" / "LC_MESSAGES"
    domain_dir.mkdir(parents=True)
    mo_path = domain_dir / "crossdesk-host.mo"
    mo_path.write_bytes(_build_minimal_mo(b"Hello", b"Cze\xc5\x9b\xc4\x87"))

    monkeypatch.setenv("CROSSDESK_LOCALEDIR", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_DIRS", "")
    monkeypatch.setenv("LANGUAGE", "pl")
    monkeypatch.setenv("LC_ALL", "pl_PL.UTF-8")
    i18n.reload()

    assert i18n._("Hello") == "Cześć"


def _build_minimal_mo(msgid: bytes, msgstr: bytes) -> bytes:
    """Hand-roll a one-entry GNU .mo file.

    Layout (little-endian, magic 0x950412de):

      0x00  magic
      0x04  version (0)
      0x08  number of strings (2 — empty header msgid + ours)
      0x0c  offset of msgid table
      0x10  offset of msgstr table
      0x14  size of hash table (0 — none)
      0x18  offset of hash table (0)
      then msgid table (length, offset) * N
      then msgstr table (length, offset) * N
      then string blobs (NUL-terminated).
    """
    empty_metadata = b"Content-Type: text/plain; charset=UTF-8\nLanguage: pl\n"
    msgids = [b"", msgid]
    msgstrs = [empty_metadata, msgstr]

    n = len(msgids)
    header_size = 28
    table_size = 8 * n  # length + offset, 4 bytes each
    msgid_table_offset = header_size
    msgstr_table_offset = msgid_table_offset + table_size
    strings_offset = msgstr_table_offset + table_size

    msgid_entries = []
    msgstr_entries = []
    blob = bytearray()
    cursor = strings_offset

    for s in msgids:
        msgid_entries.append((len(s), cursor))
        blob.extend(s + b"\x00")
        cursor += len(s) + 1
    for s in msgstrs:
        msgstr_entries.append((len(s), cursor))
        blob.extend(s + b"\x00")
        cursor += len(s) + 1

    out = bytearray()
    out.extend(
        struct.pack(
            "<IIIIIII",
            0x950412DE,
            0,
            n,
            msgid_table_offset,
            msgstr_table_offset,
            0,
            0,
        )
    )
    for length, offset in msgid_entries:
        out.extend(struct.pack("<II", length, offset))
    for length, offset in msgstr_entries:
        out.extend(struct.pack("<II", length, offset))
    out.extend(blob)
    return bytes(out)
