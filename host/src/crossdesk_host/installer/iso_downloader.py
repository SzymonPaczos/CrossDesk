"""Windows ISO downloader (Fido-style).

The user runs ``crossdesk install`` without supplying ``--iso-path``;
this module fetches a Windows ISO from Microsoft's public download
endpoint, validates the SHA-256 against ``infra/known_isos.toml``,
and caches it under ``~/.cache/crossdesk/iso/``.

The actual scrape is the same multi-step API dance Fido performs;
the live wire calls are gated on Linux+KVM hardware and external
network reachability. Here we ship the orchestration skeleton +
SHA-256 verification + cache layout so the unit tests cover what
*can* be tested without real downloads.

Pluggable :class:`ScrapeBackend` Protocol lets the caller swap a
mock that returns canned URLs / bytes; the default
:class:`HttpScrapeBackend` is hardware-gated.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol
import contextlib

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "crossdesk" / "iso"


@dataclass(frozen=True)
class IsoSpec:
    """One row of ``infra/known_isos.toml``."""

    edition: str
    version: str
    language: str
    architecture: str
    expected_sha256: str
    """Hex digest, lowercase, no spaces."""


class ScrapeBackend(Protocol):
    def resolve_download_url(self, spec: IsoSpec) -> str:
        """Return the time-limited ``aka.ms``-style URL for the ISO.

        Real backends hit Microsoft's API; mocks return canned strings."""
        ...

    def download(self, url: str, dest: Path) -> None:
        """Stream the ISO to ``dest``. Atomic from the caller's
        perspective (writes to ``dest.tmp`` then renames)."""
        ...


def cache_path(spec: IsoSpec, cache_dir: Path = _DEFAULT_CACHE_DIR) -> Path:
    return (
        cache_dir
        / f"{spec.edition}-{spec.version}-{spec.language}-{spec.architecture}.iso"
    )


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def fetch(
    spec: IsoSpec,
    backend: ScrapeBackend,
    cache_dir: Path = _DEFAULT_CACHE_DIR,
) -> Path:
    """Resolve, download (skipping if cached + checksum-OK), verify,
    and return the local path."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_path(spec, cache_dir)
    if target.exists() and sha256_of(target).lower() == spec.expected_sha256.lower():
        return target

    if target.exists():
        # Stale file with wrong checksum — back up before overwriting
        # so we don't silently delete user data if the cache layout
        # collides with something the user dropped here.
        backup = target.with_suffix(target.suffix + ".stale")
        shutil.move(str(target), str(backup))

    url = backend.resolve_download_url(spec)
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        backend.download(url, tmp)
        actual = sha256_of(tmp).lower()
        if actual != spec.expected_sha256.lower():
            raise IsoChecksumError(
                f"sha256 mismatch for {spec.edition}: "
                f"expected {spec.expected_sha256}, got {actual}"
            )
        os.rename(tmp, target)
    finally:
        if tmp.exists():
            with contextlib.suppress(OSError):
                os.unlink(tmp)
    return target


class IsoChecksumError(RuntimeError):
    pass
