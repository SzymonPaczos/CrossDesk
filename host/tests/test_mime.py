"""mime.update_mime_database — best-effort desktop-cache refresh.

The subprocess must carry a timeout (a hung ``update-desktop-database``
otherwise blocks the CLI forever) and swallow both a missing tool and a
timeout without propagating.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List

import pytest

from crossdesk_host.integrations import mime


def test_update_mime_database_passes_a_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: Dict[str, Any] = {}

    def fake_run(argv: List[str], **kwargs: Any) -> None:
        captured["argv"] = argv
        captured["kwargs"] = kwargs

    monkeypatch.setattr(mime.subprocess, "run", fake_run)
    mime.update_mime_database(applications_dir=tmp_path)

    assert captured["argv"][0] == "update-desktop-database"
    # Mandatory: never start the subprocess without a timeout.
    assert captured["kwargs"].get("timeout") is not None


def test_update_mime_database_swallows_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def raise_timeout(argv: List[str], **kwargs: Any) -> None:
        raise subprocess.TimeoutExpired(cmd=argv, timeout=15)

    monkeypatch.setattr(mime.subprocess, "run", raise_timeout)
    # Must not propagate — best-effort.
    mime.update_mime_database(applications_dir=tmp_path)


def test_update_mime_database_swallows_missing_tool(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def raise_missing(argv: List[str], **kwargs: Any) -> None:
        raise FileNotFoundError("update-desktop-database")

    monkeypatch.setattr(mime.subprocess, "run", raise_missing)
    mime.update_mime_database(applications_dir=tmp_path)
