"""Tests for the TOML app catalog (catalog/schema.py + catalog/loader.py)
and the ``crossdesk apps`` CLI (cli/apps_cmd.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crossdesk_host.catalog import AppEntry, find_app, load_catalog
from crossdesk_host.catalog.loader import load_catalog as _load_catalog_direct
from crossdesk_host.cli.main import _build_parser

# ---------------------------------------------------------------------------
# Catalog loader — bundled apps.toml
# ---------------------------------------------------------------------------


def test_load_catalog_returns_nonempty_list() -> None:
    """The bundled apps.toml ships at least 10 entries."""
    apps = load_catalog()
    assert len(apps) >= 10


def test_find_app_word_returns_correct_name() -> None:
    entry = find_app("word")
    assert entry is not None
    assert entry.name == "Microsoft Word"


def test_find_app_unknown_returns_none() -> None:
    assert find_app("nonexistent-app-xyz") is None


def test_app_entry_fields_typed() -> None:
    """Every entry in the bundled catalog has non-empty app_id, name, win_executable."""
    apps = load_catalog()
    for a in apps:
        assert a.app_id, f"Empty app_id in {a!r}"
        assert a.name, f"Empty name in {a!r}"
        assert a.win_executable, f"Empty win_executable in {a!r}"


def test_load_catalog_returns_app_entry_instances() -> None:
    apps = load_catalog()
    for a in apps:
        assert isinstance(a, AppEntry)


def test_find_app_excel_has_mime_types() -> None:
    entry = find_app("excel")
    assert entry is not None
    assert "application/vnd.ms-excel" in entry.mime_types


def test_find_app_cmd_has_correct_executable() -> None:
    entry = find_app("cmd")
    assert entry is not None
    assert "cmd.exe" in entry.win_executable.lower()


def test_load_catalog_contains_expected_apps() -> None:
    ids = {a.app_id for a in load_catalog()}
    for expected in ("word", "excel", "powerpoint", "outlook", "cmd", "powershell"):
        assert expected in ids, f"Expected app {expected!r} not in catalog"


# ---------------------------------------------------------------------------
# Loader with custom TOML path
# ---------------------------------------------------------------------------


def test_load_catalog_returns_empty_for_missing_file(tmp_path: Path) -> None:
    apps = _load_catalog_direct(tmp_path / "nonexistent.toml")
    assert apps == []


def test_load_catalog_parses_custom_toml(tmp_path: Path) -> None:
    toml_file = tmp_path / "test.toml"
    toml_file.write_text(
        """
[[apps]]
app_id = "my-app"
name = "My Custom App"
win_executable = 'C:\\\\test\\\\app.exe'
categories = ["Dev"]
mime_types = ["text/plain"]
icon = "my-icon"
""",
        encoding="utf-8",
    )
    apps = _load_catalog_direct(toml_file)
    assert len(apps) == 1
    a = apps[0]
    assert a.app_id == "my-app"
    assert a.name == "My Custom App"
    assert a.categories == ["Dev"]
    assert a.mime_types == ["text/plain"]
    assert a.icon == "my-icon"


def test_load_catalog_skips_entries_missing_required_fields(tmp_path: Path) -> None:
    toml_file = tmp_path / "bad.toml"
    toml_file.write_text(
        """
[[apps]]
name = "No ID Here"
win_executable = 'C:\\\\test.exe'

[[apps]]
app_id = "no-name"
win_executable = 'C:\\\\test.exe'

[[apps]]
app_id = "good"
name = "Good App"
win_executable = 'C:\\\\good.exe'
""",
        encoding="utf-8",
    )
    apps = _load_catalog_direct(toml_file)
    assert len(apps) == 1
    assert apps[0].app_id == "good"


# ---------------------------------------------------------------------------
# AppEntry dataclass
# ---------------------------------------------------------------------------


def test_app_entry_is_frozen() -> None:
    """AppEntry must be frozen — direct attribute assignment raises FrozenInstanceError."""
    a = AppEntry(app_id="x", name="X", win_executable="C:\\\\x.exe")
    with pytest.raises(Exception):
        # Using setattr (not object.__setattr__) triggers the frozen check.
        setattr(a, "name", "Y")


def test_app_entry_defaults() -> None:
    a = AppEntry(app_id="x", name="X", win_executable="C:\\\\x.exe")
    assert a.categories == []
    assert a.mime_types == []
    assert a.icon == ""


# ---------------------------------------------------------------------------
# CLI — ``crossdesk apps list``
# ---------------------------------------------------------------------------


def test_apps_list_cli_output(capsys: pytest.CaptureFixture[str]) -> None:
    """``crossdesk apps list`` prints at least 'word' and 'Word' in the table."""
    parser = _build_parser()
    args = parser.parse_args(["apps", "list"])
    from crossdesk_host.cli import apps_cmd

    rc = apps_cmd.run(args)
    assert rc == 0
    captured = capsys.readouterr()
    assert "word" in captured.out
    assert "Word" in captured.out


def test_apps_list_shows_table_header(capsys: pytest.CaptureFixture[str]) -> None:
    parser = _build_parser()
    args = parser.parse_args(["apps", "list"])
    from crossdesk_host.cli import apps_cmd

    apps_cmd.run(args)
    out = capsys.readouterr().out
    assert "ID" in out
    assert "Name" in out
    assert "Executable" in out


def test_apps_install_unknown_app_returns_1(capsys: pytest.CaptureFixture[str]) -> None:
    parser = _build_parser()
    args = parser.parse_args(["apps", "install", "definitely-not-a-real-app-xyz"])
    from crossdesk_host.cli import apps_cmd

    rc = apps_cmd.run(args)
    assert rc == 1
    err = capsys.readouterr().err
    assert "not found" in err


def test_apps_install_known_app_writes_desktop_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """install word → .desktop file written under tmp_path."""
    from crossdesk_host.integrations import mime as mime_mod

    # Redirect the default applications dir to a temp location so the
    # test doesn't touch $HOME.
    monkeypatch.setattr(mime_mod, "_APPLICATIONS_DIR", tmp_path)

    parser = _build_parser()
    args = parser.parse_args(["apps", "install", "word"])
    from crossdesk_host.cli import apps_cmd

    rc = apps_cmd.run(args)
    assert rc == 0
    desktop = tmp_path / "crossdesk-word.desktop"
    assert desktop.exists()
    content = desktop.read_text(encoding="utf-8")
    assert "Microsoft Word" in content
    assert "crossdesk launch word" in content
