"""Binary-resolution contract for ``RealFreeRDPInvocation``.

Covers ``CROSSDESK_FREERDP_BIN`` env pin behaviour and the
candidate-chain → flatpak fallback documented in
``host/src/crossdesk_host/freerdp/real.py``. Real spawn paths
(actually launching the subprocess) live in ``linux_only`` smoke
tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import pytest

from crossdesk_host.freerdp import real as freerdp_real

_WHICH_TARGET = "crossdesk_host.freerdp.real.shutil.which"


def _which_factory(*found: str) -> Callable[[str], Optional[str]]:
    table = {name: f"/usr/bin/{name}" for name in found}

    def fake_which(name: str) -> Optional[str]:
        return table.get(name)

    return fake_which


def test_env_pin_resolves_via_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROSSDESK_FREERDP_BIN", "xfreerdp3")
    monkeypatch.setattr(_WHICH_TARGET, _which_factory("xfreerdp3"))

    argv = freerdp_real._resolve_freerdp_binary()

    assert argv == ["/usr/bin/xfreerdp3"]


def test_env_pin_absolute_path_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "xfreerdp-custom"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    monkeypatch.setenv("CROSSDESK_FREERDP_BIN", str(binary))

    argv = freerdp_real._resolve_freerdp_binary()

    assert argv == [str(binary)]


def test_env_pin_missing_binary_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROSSDESK_FREERDP_BIN", "xfreerdp-nope")
    monkeypatch.setattr(_WHICH_TARGET, _which_factory())

    with pytest.raises(FileNotFoundError, match="not executable or not on PATH"):
        freerdp_real._resolve_freerdp_binary()


def test_env_pin_absolute_path_not_executable_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "xfreerdp-noexec"
    binary.write_text("not executable")
    binary.chmod(0o644)
    monkeypatch.setenv("CROSSDESK_FREERDP_BIN", str(binary))

    with pytest.raises(FileNotFoundError, match="not executable or not on PATH"):
        freerdp_real._resolve_freerdp_binary()


def test_candidate_chain_picks_first_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CROSSDESK_FREERDP_BIN", raising=False)
    monkeypatch.setattr(_WHICH_TARGET, _which_factory("xfreerdp", "xfreerdp3"))

    argv = freerdp_real._resolve_freerdp_binary()

    assert argv == ["/usr/bin/xfreerdp"]


def test_candidate_chain_skips_to_next_when_first_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CROSSDESK_FREERDP_BIN", raising=False)
    monkeypatch.setattr(_WHICH_TARGET, _which_factory("sdl-freerdp3"))

    argv = freerdp_real._resolve_freerdp_binary()

    assert argv == ["/usr/bin/sdl-freerdp3"]


def test_flatpak_used_when_no_native_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CROSSDESK_FREERDP_BIN", raising=False)
    monkeypatch.setattr(_WHICH_TARGET, _which_factory("flatpak"))

    argv = freerdp_real._resolve_freerdp_binary()

    assert argv == ["/usr/bin/flatpak", "run", "com.freerdp.FreeRDP"]


def test_no_candidate_and_no_flatpak_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CROSSDESK_FREERDP_BIN", raising=False)
    monkeypatch.setattr(_WHICH_TARGET, _which_factory())

    with pytest.raises(FileNotFoundError, match="no FreeRDP binary on PATH"):
        freerdp_real._resolve_freerdp_binary()


def test_env_pin_takes_precedence_over_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CROSSDESK_FREERDP_BIN", "xfreerdp3")
    monkeypatch.setattr(_WHICH_TARGET, _which_factory("xfreerdp", "xfreerdp3"))

    argv = freerdp_real._resolve_freerdp_binary()

    assert argv == ["/usr/bin/xfreerdp3"]
