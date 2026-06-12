"""Unit coverage for the guest-side drive-map logon script generator.

The script is a provisioning artifact: its body depends only on the
:class:`PeripheralsConfig`, so these tests pin the exact commands the guest
will run (drive mapping, shell-folder redirect, restore-on-absence) rather
than just smoke-testing that something is emitted.
"""

from __future__ import annotations

from crossdesk_host.config.peripherals import PeripheralsConfig
from crossdesk_host.installer.drive_map import render_drive_map_script


def _cfg(**kw: object) -> PeripheralsConfig:
    base: dict[str, object] = {
        "shared_folder_enabled": True,
        "shared_folder_path": "/tmp/cd-share",
    }
    base.update(kw)
    return PeripheralsConfig(**base)  # type: ignore[arg-type]


def test_maps_default_letter_to_share() -> None:
    script = render_drive_map_script(_cfg())
    # Maps Z: to the rdpdr share, dropping any stale mapping first.
    assert 'net use Z: /delete /y' in script
    assert 'net use Z: "\\\\tsclient\\CrossDesk" /persistent:no' in script
    # Guards the whole thing on the share being present this session.
    assert 'if exist "\\\\tsclient\\CrossDesk\\" (' in script


def test_honours_custom_drive_letter_and_share_name() -> None:
    script = render_drive_map_script(
        _cfg(shared_folder_drive_letter="m", shared_folder_name="Linux_Home")
    )
    assert "net use M:" in script
    assert "\\\\tsclient\\Linux_Home" in script
    assert "net use Z:" not in script


def test_documents_redirect_on_by_default() -> None:
    script = render_drive_map_script(_cfg())
    # Personal (Documents) shell folder points at the drive root in the
    # share-present branch, and is restored to the default in the absent branch.
    assert '/v Personal /t REG_EXPAND_SZ /d "Z:\\"' in script
    assert '/v Personal /t REG_EXPAND_SZ /d "%USERPROFILE%\\Documents"' in script


def test_desktop_redirect_off_by_default() -> None:
    script = render_drive_map_script(_cfg())
    assert "/v Desktop " not in script


def test_desktop_redirect_when_enabled() -> None:
    script = render_drive_map_script(_cfg(shared_folder_redirect_desktop=True))
    assert '/v Desktop /t REG_EXPAND_SZ /d "Z:\\"' in script
    assert '/v Desktop /t REG_EXPAND_SZ /d "%USERPROFILE%\\Desktop"' in script


def test_documents_redirect_can_be_disabled() -> None:
    script = render_drive_map_script(_cfg(shared_folder_redirect_documents=False))
    assert "/v Personal " not in script
    # Mapping still happens — only the shell-folder redirect is suppressed.
    assert "net use Z:" in script


def test_restore_branch_drops_mapping_and_resets_folders() -> None:
    script = render_drive_map_script(_cfg(shared_folder_redirect_desktop=True))
    # The else (share-absent) branch must both restore the shell folders and
    # delete the drive mapping so nothing points at a dead drive.
    else_branch = script.split(") else (", 1)[1]
    assert "%USERPROFILE%\\Documents" in else_branch
    assert "%USERPROFILE%\\Desktop" in else_branch
    assert "net use Z: /delete /y" in else_branch


def test_deterministic_output() -> None:
    cfg = _cfg(shared_folder_drive_letter="Y", shared_folder_redirect_desktop=True)
    assert render_drive_map_script(cfg) == render_drive_map_script(cfg)


def test_well_formed_cmd_header_and_branches() -> None:
    script = render_drive_map_script(_cfg())
    assert script.startswith("@echo off")
    # Exactly one if/else/endif structure.
    assert script.count("if exist") == 1
    assert script.count(") else (") == 1
    assert script.rstrip().endswith(")")
