"""xfreerdp RAIL command builder tests."""

from __future__ import annotations

import pytest

from crossdesk_host.display.rail_command import (
    AppLaunchSpec,
    FreeRDPConnectionSpec,
    build_rail_argv,
)


def _conn(scale: int = 100) -> FreeRDPConnectionSpec:
    return FreeRDPConnectionSpec(
        host="localhost",
        port=3389,
        username="cdtest",
        password="cdtest-pass",
        scale=scale,
    )


def test_basic_argv_for_notepad() -> None:
    app = AppLaunchSpec(
        app_id="notepad",
        executable_guest_path="C:\\Windows\\notepad.exe",
        display_name="Notepad",
    )
    argv = build_rail_argv(app, _conn())
    assert "/v:localhost:3389" in argv
    assert "/u:cdtest" in argv
    assert "/p:cdtest-pass" in argv
    assert "/cert:tofu" in argv
    assert "/scale:100" in argv
    assert "+auto-reconnect" in argv
    assert any(a.startswith("/app:program:||C:\\Windows\\notepad.exe") for a in argv)
    assert "/wm-class:notepad" in argv


def test_argv_carries_translated_cmd_argument() -> None:
    app = AppLaunchSpec(
        app_id="notepad",
        executable_guest_path="C:\\Windows\\notepad.exe",
        argv=("\\\\tsclient\\home\\report.docx",),
        display_name="Notepad",
    )
    argv = build_rail_argv(app, _conn())
    program = next(a for a in argv if a.startswith("/app:"))
    assert 'cmd:"\\\\tsclient\\home\\report.docx"' in program


def test_argv_includes_icon_when_provided() -> None:
    app = AppLaunchSpec(
        app_id="word",
        executable_guest_path="C:\\Program Files\\Microsoft Office\\WINWORD.EXE",
        display_name="Word",
        icon_path="C:\\Program Files\\Microsoft Office\\WINWORD.EXE",
    )
    argv = build_rail_argv(app, _conn())
    program = next(a for a in argv if a.startswith("/app:"))
    assert "icon:C:\\Program Files\\Microsoft Office\\WINWORD.EXE" in program


def test_scale_140_accepted() -> None:
    app = AppLaunchSpec(
        app_id="notepad",
        executable_guest_path="C:\\Windows\\notepad.exe",
    )
    argv = build_rail_argv(app, _conn(scale=140))
    assert "/scale:140" in argv


def test_invalid_scale_rejected() -> None:
    app = AppLaunchSpec(
        app_id="notepad",
        executable_guest_path="C:\\Windows\\notepad.exe",
    )
    with pytest.raises(ValueError):
        build_rail_argv(app, _conn(scale=125))


def test_app_id_drives_wm_class() -> None:
    app = AppLaunchSpec(
        app_id="cmd",
        executable_guest_path="C:\\Windows\\System32\\cmd.exe",
    )
    argv = build_rail_argv(app, _conn())
    assert "/wm-class:cmd" in argv
