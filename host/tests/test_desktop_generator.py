"""Tests for integrations.mime — .desktop file generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from crossdesk_host.integrations.mime import (
    _OFFICE_MIME_TYPES,
    install_app,
    install_office_handler,
    uninstall_all,
    uninstall_app,
)


@pytest.fixture()
def apps_dir(tmp_path: Path) -> Path:
    return tmp_path / "applications"


class TestInstallApp:
    def test_creates_file(self, apps_dir: Path) -> None:
        path = install_app("notepad", "Notepad", applications_dir=apps_dir)
        assert path.exists()
        assert path.name == "crossdesk-notepad.desktop"

    def test_required_fields(self, apps_dir: Path) -> None:
        install_app("calc", "Calculator", applications_dir=apps_dir)
        text = (apps_dir / "crossdesk-calc.desktop").read_text()
        assert "[Desktop Entry]" in text
        assert "Exec=crossdesk launch calc %F" in text
        assert "StartupWMClass=crossdesk-calc" in text
        assert "Type=Application" in text

    def test_display_name(self, apps_dir: Path) -> None:
        install_app("word", "Microsoft Word", applications_dir=apps_dir)
        text = (apps_dir / "crossdesk-word.desktop").read_text()
        assert "Name=Microsoft Word" in text

    def test_categories(self, apps_dir: Path) -> None:
        install_app("word", "Word", categories=["Office", "WordProcessor"],
                    applications_dir=apps_dir)
        text = (apps_dir / "crossdesk-word.desktop").read_text()
        assert "Categories=Office;WordProcessor;" in text

    def test_mime_types(self, apps_dir: Path) -> None:
        install_app(
            "word", "Word",
            mime_types=["application/vnd.oasis.opendocument.text"],
            applications_dir=apps_dir,
        )
        text = (apps_dir / "crossdesk-word.desktop").read_text()
        assert "MimeType=application/vnd.oasis.opendocument.text;" in text

    def test_no_mime_types(self, apps_dir: Path) -> None:
        install_app("notepad", "Notepad", mime_types=[], applications_dir=apps_dir)
        text = (apps_dir / "crossdesk-notepad.desktop").read_text()
        assert "MimeType" not in text

    def test_custom_icon(self, apps_dir: Path) -> None:
        install_app("notepad", "Notepad", icon="text-editor",
                    applications_dir=apps_dir)
        text = (apps_dir / "crossdesk-notepad.desktop").read_text()
        assert "Icon=text-editor" in text

    def test_idempotent(self, apps_dir: Path) -> None:
        install_app("calc", "Calculator", applications_dir=apps_dir)
        install_app("calc", "Calculator", applications_dir=apps_dir)
        assert len(list(apps_dir.glob("crossdesk-calc.desktop"))) == 1

    def test_creates_parent_dir(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "apps"
        install_app("notepad", "Notepad", applications_dir=nested)
        assert nested.exists()

    def test_returns_path(self, apps_dir: Path) -> None:
        p = install_app("calc", "Calculator", applications_dir=apps_dir)
        assert isinstance(p, Path)
        assert p.name == "crossdesk-calc.desktop"


class TestOfficeHandler:
    def test_creates_file(self, apps_dir: Path) -> None:
        path = install_office_handler(applications_dir=apps_dir)
        assert path.exists()
        assert path.name == "crossdesk-ms-office-handler.desktop"

    def test_claims_all_schemes(self, apps_dir: Path) -> None:
        install_office_handler(applications_dir=apps_dir)
        text = (apps_dir / "crossdesk-ms-office-handler.desktop").read_text()
        for scheme in _OFFICE_MIME_TYPES:
            assert scheme in text

    def test_no_display(self, apps_dir: Path) -> None:
        install_office_handler(applications_dir=apps_dir)
        text = (apps_dir / "crossdesk-ms-office-handler.desktop").read_text()
        assert "NoDisplay=true" in text

    def test_exec_line(self, apps_dir: Path) -> None:
        install_office_handler(applications_dir=apps_dir)
        text = (apps_dir / "crossdesk-ms-office-handler.desktop").read_text()
        assert "Exec=crossdesk launch manual %u" in text


class TestUninstall:
    def test_uninstall_existing(self, apps_dir: Path) -> None:
        install_app("notepad", "Notepad", applications_dir=apps_dir)
        removed = uninstall_app("notepad", applications_dir=apps_dir)
        assert removed is True
        assert not (apps_dir / "crossdesk-notepad.desktop").exists()

    def test_uninstall_missing_returns_false(self, apps_dir: Path) -> None:
        removed = uninstall_app("ghost", applications_dir=apps_dir)
        assert removed is False

    def test_uninstall_all(self, apps_dir: Path) -> None:
        install_app("notepad", "Notepad", applications_dir=apps_dir)
        install_app("calc", "Calculator", applications_dir=apps_dir)
        install_office_handler(applications_dir=apps_dir)
        removed = uninstall_all(applications_dir=apps_dir)
        assert len(removed) == 3
        assert not any(apps_dir.glob("crossdesk-*.desktop"))

    def test_uninstall_all_empty(self, apps_dir: Path) -> None:
        apps_dir.mkdir(parents=True)
        removed = uninstall_all(applications_dir=apps_dir)
        assert removed == []
