"""Tests for ``crossdesk config migrate``."""

from __future__ import annotations

from pathlib import Path

import pytest

from crossdesk_host.cli.config_cmd import _run_migrate
from crossdesk_host.installer import credentials


def _write_toml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_missing_file_returns_1(tmp_path: Path) -> None:
    path = tmp_path / "vm.toml"
    assert _run_migrate(path) == 1


def test_already_current_schema_returns_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "vm.toml"
    creds = credentials.generate()
    credentials.save(creds, path)
    rc = _run_migrate(path)
    assert rc == 0
    out = capsys.readouterr().out
    assert "already at schema version" in out


def test_legacy_file_without_schema_version_migrates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "vm.toml"
    # Simulate a file written before schema_version was introduced (v1 shape).
    _write_toml(path, 'username = "crossdesk"\npassword = "s3cr3t"\n')
    rc = _run_migrate(path)
    # v1 is the current schema, so the legacy file is already "current" after
    # defaulting to v1 — migration is a no-op.
    assert rc == 0


def test_future_schema_returns_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "vm.toml"
    _write_toml(
        path,
        f'schema_version = {credentials.SCHEMA_VERSION + 1}\n'
        'username = "crossdesk"\npassword = "s3cr3t"\n',
    )
    rc = _run_migrate(path)
    assert rc == 1
    out = capsys.readouterr().out
    assert "newer than this build" in out


def test_non_integer_schema_version_returns_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "vm.toml"
    _write_toml(path, 'schema_version = "one"\nusername = "x"\npassword = "y"\n')
    rc = _run_migrate(path)
    assert rc == 1
    out = capsys.readouterr().out
    assert "not an integer" in out


def test_config_migrate_via_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: ``crossdesk config migrate`` returns 0 via main()."""
    from crossdesk_host.cli.main import main

    cred_path = tmp_path / "vm.toml"
    creds = credentials.generate()
    credentials.save(creds, cred_path)

    monkeypatch.setattr(credentials, "_default_path", lambda: cred_path)

    rc = main(["config", "migrate"])
    assert rc == 0
