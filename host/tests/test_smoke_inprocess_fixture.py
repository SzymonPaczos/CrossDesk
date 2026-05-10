"""Unit coverage for the ``cargo_built_agent`` fixture in
``test_smoke_inprocess.py`` — specifically the
``CROSSDESK_PREBUILT_AGENT`` env-var path used by the compat-matrix
GitHub workflow.

These tests deliberately live outside ``test_smoke_inprocess.py`` so
they're not gated on the smoke harness's pytestmark (PKI material,
``CROSSDESK_SKIP_INPROCESS``, etc.). They exercise the fixture's
build-vs-prebuilt branching directly without ever opening a gRPC
server or spawning the real Rust agent.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

# Pull the underlying function out of the FixtureFunctionMarker wrapper
# so we can call it as a plain callable. Pytest's @fixture-decorated
# objects expose the original function via ``__wrapped__``.
from tests.test_smoke_inprocess import cargo_built_agent as _cargo_built_agent_fixture

_cargo_built_agent = _cargo_built_agent_fixture.__wrapped__  # type: ignore[attr-defined]


def _make_executable_stub(tmp_path: Path) -> Path:
    """Drop a tiny executable file in ``tmp_path``. Content is irrelevant
    — the fixture only validates existence + the executable bit; it
    never invokes the binary."""
    stub = tmp_path / "agent-stub"
    stub.write_bytes(b"#!/bin/sh\nexit 0\n")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return stub


def test_prebuilt_env_var_returns_path_and_skips_cargo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Set ``CROSSDESK_PREBUILT_AGENT`` to a real executable; assert the
    fixture returns it as a Path and that ``subprocess.run`` is NEVER
    invoked (the cargo branch must be skipped entirely — that's the
    whole point of the env var: avoid a redundant ~30s cargo build in
    the compat-matrix job)."""
    stub = _make_executable_stub(tmp_path)
    monkeypatch.setenv("CROSSDESK_PREBUILT_AGENT", str(stub))

    def _explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "subprocess.run must not be called when CROSSDESK_PREBUILT_AGENT is set"
        )

    monkeypatch.setattr(subprocess, "run", _explode)

    result = _cargo_built_agent()
    assert isinstance(result, Path)
    assert result == stub


def test_prebuilt_env_var_missing_file_fails_clearly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pointing at a non-existent path must raise a pytest.fail with a
    message that names the offending env var — operators reading CI
    output should not have to grep a stack trace for the cause."""
    bogus = tmp_path / "does-not-exist"
    monkeypatch.setenv("CROSSDESK_PREBUILT_AGENT", str(bogus))

    with pytest.raises(pytest.fail.Exception) as excinfo:
        _cargo_built_agent()
    assert "CROSSDESK_PREBUILT_AGENT" in str(excinfo.value)


def test_prebuilt_env_var_non_executable_fails_clearly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing-but-non-executable file must fail with an actionable
    message (mentions the env var + hints at chmod). The compat-matrix
    workflow ``cp``s the binary into ``$GITHUB_WORKSPACE``; if the
    source ever loses its +x bit, this is what catches it."""
    not_exec = tmp_path / "agent-noexec"
    not_exec.write_bytes(b"placeholder")
    not_exec.chmod(0o644)
    monkeypatch.setenv("CROSSDESK_PREBUILT_AGENT", str(not_exec))

    with pytest.raises(pytest.fail.Exception) as excinfo:
        _cargo_built_agent()
    msg = str(excinfo.value)
    assert "CROSSDESK_PREBUILT_AGENT" in msg
    assert "executable" in msg


def test_unset_env_var_falls_through_to_cargo_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the env var is unset (or empty), the fixture must take the
    cargo path. We stub subprocess.run to confirm cargo is invoked
    with the expected argv — this guards against an accidental
    short-circuit that would silently break local + standard-CI runs.
    """
    monkeypatch.delenv("CROSSDESK_PREBUILT_AGENT", raising=False)

    invocations: list[list[str]] = []

    class _FakeCompleted:
        returncode = 0
        stdout = ""
        stderr = ""

    def _capture(argv: list[str], **_kwargs: object) -> _FakeCompleted:
        invocations.append(argv)
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", _capture)

    # The fixture asserts the resulting binary path exists. We don't
    # actually want a real cargo build, so we also stub Path.exists for
    # the expected target — module-level _GUEST_DIR is the only path
    # the fixture probes.
    from tests import test_smoke_inprocess as _mod

    expected_binary = _mod._GUEST_DIR / "target" / "debug" / "agent"
    real_exists = Path.exists

    def _exists(self: Path) -> bool:
        if self == expected_binary:
            return True
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", _exists)

    result = _cargo_built_agent()
    assert result == expected_binary
    assert len(invocations) == 1
    assert invocations[0][:2] == ["cargo", "build"]
    assert "--features" in invocations[0]
    assert "mock" in invocations[0]


def test_empty_string_env_var_falls_through_to_cargo_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``CROSSDESK_PREBUILT_AGENT=""`` (set but empty) is treated as
    unset — bash users who write ``CROSSDESK_PREBUILT_AGENT=`` in a
    one-liner shouldn't crash the harness. Same falsy semantics as
    ``os.environ.get(...)`` returning ``None``."""
    monkeypatch.setenv("CROSSDESK_PREBUILT_AGENT", "")

    called = False

    class _FakeCompleted:
        returncode = 0
        stdout = ""
        stderr = ""

    def _capture(argv: list[str], **_kwargs: object) -> _FakeCompleted:
        nonlocal called
        called = True
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", _capture)

    from tests import test_smoke_inprocess as _mod

    expected_binary = _mod._GUEST_DIR / "target" / "debug" / "agent"
    real_exists = Path.exists

    def _exists(self: Path) -> bool:
        if self == expected_binary:
            return True
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", _exists)

    _cargo_built_agent()
    assert called, "cargo branch must run when env var is empty string"


# Sanity check — `os` is referenced in the fixture and we want a
# regression-style guard that future refactors don't accidentally
# remove the import. Trivial but cheap.
def test_fixture_module_imports_os() -> None:
    from tests import test_smoke_inprocess as _mod

    assert hasattr(_mod, "os")
    assert _mod.os is os
