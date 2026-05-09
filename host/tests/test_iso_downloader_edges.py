"""ISO downloader cache + checksum edge cases (Week 14)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from crossdesk_host.installer.iso_downloader import (
    IsoChecksumError,
    IsoSpec,
    ScrapeBackend,
    cache_path,
    fetch,
    sha256_of,
)

_PAYLOAD = b"fake-iso-bytes-for-testing-purposes"
_PAYLOAD_SHA = hashlib.sha256(_PAYLOAD).hexdigest()


def _spec(sha: str = _PAYLOAD_SHA) -> IsoSpec:
    return IsoSpec(
        edition="Win11Pro",
        version="23H2",
        language="en-US",
        architecture="x64",
        expected_sha256=sha,
    )


class _ScriptedBackend(ScrapeBackend):
    def __init__(
        self, payload: bytes = _PAYLOAD, url: str = "https://example/iso"
    ) -> None:
        self.payload = payload
        self.url = url
        self.calls = 0

    def resolve_download_url(self, spec: IsoSpec) -> str:
        return self.url

    def download(self, url: str, dest: Path) -> None:
        self.calls += 1
        dest.write_bytes(self.payload)


def test_cache_path_is_deterministic(tmp_path: Path) -> None:
    spec = _spec()
    p1 = cache_path(spec, tmp_path)
    p2 = cache_path(spec, tmp_path)
    assert p1 == p2
    assert p1.parent == tmp_path
    assert "Win11Pro" in p1.name
    assert "23H2" in p1.name


def test_sha256_of_known_bytes(tmp_path: Path) -> None:
    target = tmp_path / "blob"
    target.write_bytes(_PAYLOAD)
    assert sha256_of(target) == _PAYLOAD_SHA


def test_fetch_downloads_when_cache_empty(tmp_path: Path) -> None:
    backend = _ScriptedBackend()
    out = fetch(_spec(), backend, tmp_path)
    assert out.exists()
    assert sha256_of(out) == _PAYLOAD_SHA
    assert backend.calls == 1


def test_fetch_skips_download_when_cache_matches(tmp_path: Path) -> None:
    spec = _spec()
    target = cache_path(spec, tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_PAYLOAD)
    backend = _ScriptedBackend()
    out = fetch(spec, backend, tmp_path)
    assert out == target
    assert backend.calls == 0


def test_fetch_refetches_when_cache_has_wrong_checksum(tmp_path: Path) -> None:
    spec = _spec()
    target = cache_path(spec, tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"wrong-content")
    backend = _ScriptedBackend()
    out = fetch(spec, backend, tmp_path)
    assert sha256_of(out) == _PAYLOAD_SHA
    assert backend.calls == 1
    # Stale file should have been backed up rather than silently overwritten.
    backups = list(tmp_path.glob("*.stale"))
    assert len(backups) == 1


def test_fetch_raises_on_checksum_mismatch_after_download(tmp_path: Path) -> None:
    """If the upstream URL serves something whose hash doesn't match
    the spec's expected_sha256, refuse to install and surface the
    mismatch — better a loud failure than a silently-wrong ISO."""
    spec = _spec(sha="0" * 64)  # Wrong expected hash
    backend = _ScriptedBackend()
    with pytest.raises(IsoChecksumError):
        fetch(spec, backend, tmp_path)


def test_fetch_cleans_up_tmp_after_failure(tmp_path: Path) -> None:
    spec = _spec(sha="0" * 64)
    backend = _ScriptedBackend()
    with pytest.raises(IsoChecksumError):
        fetch(spec, backend, tmp_path)
    leftover = list(tmp_path.glob("*.tmp"))
    assert leftover == []


def test_cache_path_distinguishes_editions(tmp_path: Path) -> None:
    pro = IsoSpec("Pro", "23H2", "en", "x64", "a" * 64)
    home = IsoSpec("Home", "23H2", "en", "x64", "a" * 64)
    assert cache_path(pro, tmp_path) != cache_path(home, tmp_path)


def test_cache_path_distinguishes_languages(tmp_path: Path) -> None:
    en = IsoSpec("Pro", "23H2", "en-US", "x64", "a" * 64)
    pl = IsoSpec("Pro", "23H2", "pl-PL", "x64", "a" * 64)
    assert cache_path(en, tmp_path) != cache_path(pl, tmp_path)


def test_sha256_of_handles_large_files_in_chunks(tmp_path: Path) -> None:
    """The reader uses 1 MB chunks. Drive a file large enough to span
    several chunks; the digest must still match the single-pass digest."""
    target = tmp_path / "blob"
    payload = b"x" * (4 * 1024 * 1024 + 17)  # ~4MB + odd tail
    target.write_bytes(payload)
    assert sha256_of(target, chunk=1024) == sha256_of(target, chunk=8 * 1024 * 1024)
