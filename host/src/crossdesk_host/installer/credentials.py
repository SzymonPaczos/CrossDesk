"""VM credential storage at ``~/.config/crossdesk/vm.toml``.

Two-phase commit semantics for rotation: a new credential is written
to disk *before* the guest password is changed, so a crash between
the two leaves the host with the new credential and the guest with
the old — recoverable via ``crossdesk vm credentials repair`` (which
re-applies the host's stored credential to the guest). The opposite
ordering (guest first, host second) leaves the system unrecoverable
because the host has no record of the new password.

File mode is forced to 0600 on write (POSIX) so other local users
can't read the password. The directory itself stays at the user's
default umask — only the credential file is locked down.

Auth health-check (DEC-0001 + FOLLOWUPS:928-935): ``verify_with_guest``
asks an active guest session whether the stored password actually
logs on. Wraps :class:`VerifyCoordinator.verify` and maps the proto
status enum into a typed :class:`VerifyResult` whose ``repair_hint``
is the user-facing instruction shown by RAIL spawn / doctor / CLI.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import stat
import string
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if sys.version_info >= (3, 11):
    import tomllib as _tomllib  # type: ignore[import-not-found,unused-ignore]
else:  # pragma: no cover
    import tomli as _tomllib  # type: ignore[import-not-found]


if TYPE_CHECKING:
    from crossdesk_host.ipc.verify_coordinator import VerifyCoordinator


_DEFAULT_USERNAME = "crossdesk"


def _default_path() -> Path:
    # Resolve at call time so tests monkey-patching ``HOME`` are honoured.
    return Path.home() / ".config" / "crossdesk" / "vm.toml"


_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
_PASSWORD_LENGTH = 20


@dataclass(frozen=True)
class VmCredentials:
    username: str
    password: str

    def to_toml(self) -> str:
        # Tiny manual emit avoids pulling another runtime dep just to
        # write two strings. Both fields are run through repr() to
        # quote/escape correctly.
        return (
            f'username = "{self._escape(self.username)}"\n'
            f'password = "{self._escape(self.password)}"\n'
        )

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')


def generate(username: str = _DEFAULT_USERNAME) -> VmCredentials:
    """Generate a fresh credential with a strong random password."""
    password = "".join(
        secrets.choice(_PASSWORD_ALPHABET) for _ in range(_PASSWORD_LENGTH)
    )
    return VmCredentials(username=username, password=password)


def save(creds: VmCredentials, path: Optional[Path] = None) -> None:
    if path is None:
        path = _default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(creds.to_toml())
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, 0o600)
        os.rename(tmp_path, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def load(path: Optional[Path] = None) -> Optional[VmCredentials]:
    if path is None:
        path = _default_path()
    if not path.exists():
        return None
    with path.open("rb") as f:
        data = _tomllib.load(f)
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        raise ValueError(f"malformed vm.toml at {path}")
    return VmCredentials(username=username, password=password)


def default_path() -> Path:
    return _default_path()


@dataclass(frozen=True)
class CredentialFileHealth:
    """Filesystem-level credential health (no guest contact required).

    Used by ``crossdesk vm credentials check`` and the doctor probe so
    the user gets a clear pre-flight diagnosis before anything tries to
    actually log on.
    """

    path: Path
    present: bool
    parsable: bool
    permissions_ok: bool

    @property
    def ok(self) -> bool:
        return self.present and self.parsable and self.permissions_ok

    def remediation(self) -> Optional[str]:
        if not self.present:
            return "no credentials yet — run `crossdesk install`"
        if not self.parsable:
            return f"vm.toml at {self.path} is malformed; recover via `crossdesk vm credentials set`"
        if not self.permissions_ok:
            return f"vm.toml at {self.path} is world-readable; run `crossdesk vm credentials repair` to lock to 0600"
        return None


def health_check(path: Optional[Path] = None) -> CredentialFileHealth:
    """Inspect vm.toml without contacting the guest.

    Reports presence + parsability + POSIX file mode. Mode check is a
    no-op on non-POSIX platforms (always reported OK there).
    """
    if path is None:
        path = _default_path()
    if not path.exists():
        return CredentialFileHealth(
            path=path, present=False, parsable=False, permissions_ok=False
        )
    parsable = True
    try:
        load(path)
    except Exception:
        parsable = False
    permissions_ok = True
    if os.name == "posix":
        mode = stat.S_IMODE(path.stat().st_mode)
        permissions_ok = mode == 0o600
    return CredentialFileHealth(
        path=path,
        present=True,
        parsable=parsable,
        permissions_ok=permissions_ok,
    )


def repair_permissions(path: Optional[Path] = None) -> bool:
    """Force vm.toml to 0600 on POSIX. Returns True if a change was made."""
    if path is None:
        path = _default_path()
    if os.name != "posix" or not path.exists():
        return False
    current = stat.S_IMODE(path.stat().st_mode)
    if current == 0o600:
        return False
    os.chmod(path, 0o600)
    return True


@dataclass(frozen=True)
class VerifyResult:
    """Host-facing summary of a guest LogonUserW probe.

    ``status_label`` mirrors the proto enum but as a short string
    suitable for logs and CLI output. ``repair_hint`` is the actionable
    instruction surfaced to the user when ``ok`` is False.
    """

    ok: bool
    status_label: str
    detail: str
    win32_error: int
    repair_hint: Optional[str]


async def verify_with_guest(
    coordinator: "VerifyCoordinator",
    *,
    creds: Optional[VmCredentials] = None,
    timeout: float = 5.0,
) -> VerifyResult:
    """Ask the active guest session to validate the stored credentials.

    Loads ``vm.toml`` if ``creds`` not passed. Translates the proto
    status into a typed result; on the failure paths the
    ``repair_hint`` field tells the caller exactly what to print or
    surface in the UI.

    Raises:
        FileNotFoundError: ``vm.toml`` is missing — caller should run
            ``crossdesk install`` or ``vm credentials set`` first.
        NoActiveSession: no guest session registered with the
            coordinator (re-raised verbatim from ``coordinator.verify``).
        asyncio.TimeoutError: guest didn't respond within ``timeout``.
    """
    # Local import: keeps ``installer.credentials`` importable in
    # contexts where the proto stubs haven't been generated yet (pure
    # filesystem ops in install pipeline).
    from crossdesk_host.proto.crossdesk.v1 import control_pb2

    if creds is None:
        loaded = load()
        if loaded is None:
            raise FileNotFoundError(
                "no vm.toml — run `crossdesk install` or `vm credentials set`"
            )
        creds = loaded

    proto_result = await coordinator.verify(
        creds.username, creds.password, timeout=timeout
    )

    Status = control_pb2.VerifyCredentialsResult.Status
    status_map = {
        Status.STATUS_OK: ("ok", None),
        Status.STATUS_FAIL_BAD_CREDENTIALS: (
            "bad_credentials",
            "host vm.toml password no longer logs on the guest — "
            "run `crossdesk vm credentials repair` after rotating the guest password",
        ),
        Status.STATUS_FAIL_ACCOUNT_LOCKED: (
            "account_locked",
            f"guest account {creds.username!r} is locked out — "
            "wait for the lockout window to expire and retry, or unlock from inside the VM",
        ),
        Status.STATUS_FAIL_PASSWORD_EXPIRED: (
            "password_expired",
            f"guest password for {creds.username!r} expired — "
            "run `crossdesk vm credentials rotate` to issue a fresh one",
        ),
        Status.STATUS_UNAVAILABLE: (
            "unavailable",
            "guest agent could not reach LSA — check `crossdesk doctor` for VM health",
        ),
        Status.STATUS_UNSPECIFIED: (
            "unspecified",
            "guest returned no status — likely an agent version mismatch",
        ),
    }
    label, hint = status_map.get(
        proto_result.status,
        ("unknown", f"unknown status code {proto_result.status}"),
    )
    return VerifyResult(
        ok=proto_result.status == Status.STATUS_OK,
        status_label=label,
        detail=proto_result.detail,
        win32_error=proto_result.win32_error,
        repair_hint=hint,
    )
