"""VM credential tests (Week 15)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from crossdesk_host.installer import credentials


def test_generate_produces_strong_password() -> None:
    c = credentials.generate()
    assert c.username == "crossdesk"
    assert len(c.password) == 20
    assert c.password != credentials.generate().password  # different each call


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "vm.toml"
    creds = credentials.VmCredentials(username="alice", password='p"a"s"s')
    credentials.save(creds, target)
    loaded = credentials.load(target)
    assert loaded == creds


def test_save_sets_0600_permissions(tmp_path: Path) -> None:
    target = tmp_path / "vm.toml"
    credentials.save(credentials.generate(), target)
    if os.name == "posix":
        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o600


def test_load_missing_file_returns_none(tmp_path: Path) -> None:
    assert credentials.load(tmp_path / "nope.toml") is None


def test_load_malformed_raises(tmp_path: Path) -> None:
    """Garbled TOML fails out — exact exception comes from the
    backend (tomllib raises TOMLDecodeError; older tomli raises
    a subclass). Pinning to the abstract base lets us match both."""
    import tomllib

    target = tmp_path / "vm.toml"
    target.write_text("garbage =")
    with pytest.raises(tomllib.TOMLDecodeError):
        credentials.load(target)


def test_save_does_not_leave_tmp(tmp_path: Path) -> None:
    target = tmp_path / "vm.toml"
    credentials.save(credentials.generate(), target)
    leftover = list(tmp_path.glob("vm.toml.*.tmp"))
    assert leftover == []


# ----- health_check / repair_permissions -----


def test_health_check_missing(tmp_path: Path) -> None:
    h = credentials.health_check(tmp_path / "nope.toml")
    assert not h.ok
    assert not h.present
    assert h.remediation() is not None
    assert "install" in h.remediation()


def test_health_check_happy_path(tmp_path: Path) -> None:
    target = tmp_path / "vm.toml"
    credentials.save(credentials.generate(), target)
    h = credentials.health_check(target)
    assert h.ok
    assert h.present
    assert h.parsable
    assert h.permissions_ok
    assert h.remediation() is None


def test_health_check_malformed(tmp_path: Path) -> None:
    target = tmp_path / "vm.toml"
    target.write_text("garbage =")
    if os.name == "posix":
        os.chmod(target, 0o600)
    h = credentials.health_check(target)
    assert not h.ok
    assert h.present
    assert not h.parsable
    assert "malformed" in h.remediation()


def test_health_check_bad_permissions(tmp_path: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX-only file mode test")
    target = tmp_path / "vm.toml"
    credentials.save(credentials.generate(), target)
    os.chmod(target, 0o644)
    h = credentials.health_check(target)
    assert not h.ok
    assert h.present
    assert h.parsable
    assert not h.permissions_ok
    assert "0600" in h.remediation()


def test_repair_permissions_fixes_bad_mode(tmp_path: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX-only")
    target = tmp_path / "vm.toml"
    credentials.save(credentials.generate(), target)
    os.chmod(target, 0o644)
    assert credentials.repair_permissions(target) is True
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_repair_permissions_noop_when_already_0600(tmp_path: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX-only")
    target = tmp_path / "vm.toml"
    credentials.save(credentials.generate(), target)
    assert credentials.repair_permissions(target) is False


# ----- verify_with_guest -----


@pytest.mark.asyncio
async def test_verify_with_guest_maps_ok_status() -> None:
    from crossdesk_host.installer.credentials import VmCredentials, verify_with_guest
    from crossdesk_host.proto.crossdesk.v1 import control_pb2

    class StubCoord:
        async def verify(
            self, username: str, password: str, domain: str = "", timeout: float = 5.0
        ) -> control_pb2.VerifyCredentialsResult:
            return control_pb2.VerifyCredentialsResult(
                request_id="x",
                status=control_pb2.VerifyCredentialsResult.Status.STATUS_OK,
                detail="logon ok",
                win32_error=0,
            )

    res = await verify_with_guest(
        StubCoord(), creds=VmCredentials(username="u", password="p")
    )
    assert res.ok
    assert res.status_label == "ok"
    assert res.repair_hint is None


@pytest.mark.asyncio
async def test_verify_with_guest_maps_failures_to_repair_hints() -> None:
    from crossdesk_host.installer.credentials import VmCredentials, verify_with_guest
    from crossdesk_host.proto.crossdesk.v1 import control_pb2

    Status = control_pb2.VerifyCredentialsResult.Status
    cases = {
        Status.STATUS_FAIL_BAD_CREDENTIALS: ("bad_credentials", "repair"),
        Status.STATUS_FAIL_ACCOUNT_LOCKED: ("account_locked", "lock"),
        Status.STATUS_FAIL_PASSWORD_EXPIRED: ("password_expired", "rotate"),
        Status.STATUS_UNAVAILABLE: ("unavailable", "doctor"),
    }
    for status, (label, hint_word) in cases.items():
        class _Coord:
            def __init__(self, s: int) -> None:
                self._s = s

            async def verify(
                self, username: str, password: str, domain: str = "", timeout: float = 5.0
            ) -> control_pb2.VerifyCredentialsResult:
                return control_pb2.VerifyCredentialsResult(
                    request_id="x", status=self._s, detail="", win32_error=0
                )

        res = await verify_with_guest(
            _Coord(status), creds=VmCredentials(username="u", password="p")
        )
        assert not res.ok
        assert res.status_label == label
        assert res.repair_hint is not None
        assert hint_word in res.repair_hint


@pytest.mark.asyncio
async def test_verify_with_guest_loads_creds_from_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from crossdesk_host.installer.credentials import (
        VmCredentials,
        save,
        verify_with_guest,
    )
    from crossdesk_host.proto.crossdesk.v1 import control_pb2

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    creds = VmCredentials(username="alice", password="hunter2")
    cred_dir = tmp_path / ".config" / "crossdesk"
    cred_dir.mkdir(parents=True)
    save(creds, cred_dir / "vm.toml")

    captured: dict[str, str] = {}

    class _Coord:
        async def verify(
            self, username: str, password: str, domain: str = "", timeout: float = 5.0
        ) -> control_pb2.VerifyCredentialsResult:
            captured["username"] = username
            captured["password"] = password
            return control_pb2.VerifyCredentialsResult(
                request_id="x",
                status=control_pb2.VerifyCredentialsResult.Status.STATUS_OK,
                detail="",
                win32_error=0,
            )

    await verify_with_guest(_Coord())
    assert captured == {"username": "alice", "password": "hunter2"}


@pytest.mark.asyncio
async def test_verify_with_guest_raises_on_missing_vm_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from crossdesk_host.installer.credentials import verify_with_guest

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    class _Coord:
        async def verify(self, *a, **k):  # pragma: no cover - never called
            raise AssertionError("should not reach guest if vm.toml missing")

    with pytest.raises(FileNotFoundError):
        await verify_with_guest(_Coord())
