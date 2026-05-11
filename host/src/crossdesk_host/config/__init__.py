"""Typed configuration schema for the CrossDesk host daemon.

Single Pydantic v2 entry point for every host-side knob: filesystem
paths, transport endpoint + mTLS material, heartbeat FSM tuning,
peripheral redirection policy, and daemon identity. Loaded from
``~/.config/crossdesk/config.toml`` via :func:`load_from_toml`; all
fields have sensible defaults so a missing file still produces a
working config.

Why a single typed schema instead of the per-feature dataclasses
already scattered through the package (``installer.settings.Settings``,
``watchdog.fsm.FsmConfig``, etc.): those are still the source of truth
for *user-facing preferences* (mutated at runtime by the GUI) and
*FSM-internal tuning* (kept colocated with the algorithm). This
module is the *operator-facing* wiring — paths, ports, cert
locations, peripheral allow-list — that the daemon reads once at
startup and never mutates.

Migration: this module is **additive**. Existing call sites
(``installer.credentials._default_path``, ``daemon.main``'s hardcoded
PKI paths, ``HeartbeatServiceServicer.__init__`` defaults) keep
working unchanged. A separate "migrate call sites" PR will route them
through ``CrossdeskConfig`` once it's been exercised by tests and
review.

Threat model touchpoint: any field that affects the security boundary
(mTLS cert paths, peripheral allow-list, transport endpoint) is
validated at parse time — bad TOML fails loudly at startup rather
than silently at first frame.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

if sys.version_info >= (3, 11):
    import tomllib as _tomllib  # type: ignore[import-not-found,unused-ignore]
else:  # pragma: no cover - Python <3.11 fallback
    import tomli as _tomllib  # type: ignore[import-not-found]


_FROZEN_MODEL_CONFIG = ConfigDict(frozen=True, extra="forbid")
"""All sub-models share these knobs: immutable + reject unknown fields.

``frozen=True`` matches the existing dataclass(frozen=True) style of
``VmCredentials`` and ``CredentialFileHealth`` and prevents accidental
mutation by callers (the daemon reads config once at startup).
``extra='forbid'`` catches typos in user TOML — silent ignore is the
opposite of what an operator wants when their setting "doesn't seem
to apply"."""


def _user_config_dir() -> Path:
    return Path.home() / ".config" / "crossdesk"


def _user_state_dir() -> Path:
    return Path.home() / ".local" / "state" / "crossdesk"


def _user_data_dir() -> Path:
    return Path.home() / ".local" / "share" / "crossdesk"


def _repo_pki_dir() -> Path:
    """In-tree default PKI dir.

    Resolved at call time from this file's location: ``infra/certs/pki``
    relative to the repo root. Production installs override via TOML or
    by passing a config file explicitly.
    """
    # config/__init__.py lives at host/src/crossdesk_host/config/__init__.py
    # so we need 5 parents to reach the repo root (config/ → crossdesk_host/
    # → src/ → host/ → repo-root).
    return Path(__file__).resolve().parent.parent.parent.parent.parent / "infra" / "certs" / "pki"


class PathsConfig(BaseModel):
    """Filesystem locations the daemon reads or writes.

    Defaults follow the XDG Base Directory pattern already used across
    the package. Overriding via TOML is intended for packaged installs
    (system-wide ``/etc/crossdesk/`` deployments) and tests.
    """

    model_config = _FROZEN_MODEL_CONFIG

    config_dir: Path = Field(default_factory=_user_config_dir)
    """Where ``vm.toml``, ``settings.toml``, ``keyring.toml`` live."""

    state_dir: Path = Field(default_factory=_user_state_dir)
    """Where ``install.state.json`` and ``recovery/`` live."""

    data_dir: Path = Field(default_factory=_user_data_dir)
    """Where the user-app catalog and ratings live."""

    pki_dir: Path = Field(default_factory=_repo_pki_dir)
    """Where ``ca.crt``, ``host.crt``, ``host.key`` live."""

    @property
    def vm_credentials_file(self) -> Path:
        return self.config_dir / "vm.toml"

    @property
    def settings_file(self) -> Path:
        return self.config_dir / "settings.toml"

    @property
    def install_state_file(self) -> Path:
        return self.state_dir / "install.state.json"

    @property
    def ca_cert(self) -> Path:
        return self.pki_dir / "ca.crt"

    @property
    def host_cert(self) -> Path:
        return self.pki_dir / "host.crt"

    @property
    def host_key(self) -> Path:
        return self.pki_dir / "host.key"


class TransportConfig(BaseModel):
    """gRPC transport endpoint + connection deadlines.

    Per DEC-0006 the production transport is AF_VSOCK with mTLS;
    ``vsock_port`` is the CID-relative port the host listens on.
    Timeouts apply to per-RPC deadlines — never let a stream hang
    forever (see ``.claude/rules/backend.md``).
    """

    model_config = _FROZEN_MODEL_CONFIG

    vsock_port: int = 50051
    """AF_VSOCK port the host server binds. Falls back to TCP loopback in dev."""

    connect_timeout_seconds: float = 5.0
    """Initial gRPC channel connect deadline (mTLS handshake included)."""

    rpc_timeout_seconds: float = 10.0
    """Default deadline for unary RPCs that don't specify their own."""

    @field_validator("vsock_port")
    @classmethod
    def _port_in_range(cls, v: int) -> int:
        # Validated at boundary — TOML parser hands us arbitrary ints.
        if not 1 <= v <= 65535:
            raise ValueError(f"vsock_port must be in 1..65535, got {v}")
        return v

    @field_validator("connect_timeout_seconds", "rpc_timeout_seconds")
    @classmethod
    def _positive_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"timeouts must be > 0, got {v}")
        return v


class HeartbeatConfig(BaseModel):
    """Adaptive-heartbeat tuning knobs.

    Mirrors the subset of ``watchdog.fsm.FsmConfig`` that an operator
    might want to tune from TOML. The FSM dataclass remains the
    runtime carrier (the FSM is constructed with raw floats, not this
    model) — this exists so a future "migrate call sites" PR can pipe
    operator overrides into ``HeartbeatServiceServicer.__init__``.
    """

    model_config = _FROZEN_MODEL_CONFIG

    ping_interval_seconds: float = 1.0
    """Wall-clock spacing between pings on a healthy stream."""

    pong_timeout_seconds: float = 2.0
    """Per-ping deadline before a miss is recorded."""

    ewma_alpha: float = 0.125
    """EWMA smoothing factor (RFC 6298 SRTT default)."""

    ewma_warmup: int = 10
    """Samples averaged into the baseline before EWMA proper takes over."""

    miss_threshold: int = 3
    """Misses-in-DEGRADED before transitioning to PROBING."""

    baseline_multiplier_k1: float = 3.0
    """HEALTHY→DEGRADED RTT trip: ewma > k1 * baseline."""

    @field_validator("ping_interval_seconds", "pong_timeout_seconds")
    @classmethod
    def _positive_seconds(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"intervals must be > 0, got {v}")
        return v

    @field_validator("ewma_alpha")
    @classmethod
    def _alpha_in_unit_interval(cls, v: float) -> float:
        if not 0 < v < 1:
            raise ValueError(f"ewma_alpha must be in (0, 1), got {v}")
        return v

    @field_validator("ewma_warmup", "miss_threshold")
    @classmethod
    def _positive_int(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"counts must be >= 1, got {v}")
        return v

    @field_validator("baseline_multiplier_k1")
    @classmethod
    def _multiplier_above_one(cls, v: float) -> float:
        if v <= 1.0:
            raise ValueError(f"baseline_multiplier_k1 must be > 1, got {v}")
        return v


class PeripheralsConfig(BaseModel):
    """Per-peripheral redirection policy. Default-off everywhere a
    peripheral crosses the host↔guest trust boundary.

    Catalog from FOLLOWUPS:281-340 ("Peripherals & host integration").
    Each enabled item maps to FreeRDP flags + libvirt XML adjustments
    at VM start (wiring lives in ``display/`` — not in this PR).

    Modes are string enums rather than booleans where there's a real
    third state ("off", "playback-only", "full"); for plain on/off the
    field is a bool.
    """

    model_config = _FROZEN_MODEL_CONFIG

    audio_mode: str = "playback"
    """``off`` | ``playback`` | ``full`` (full = playback + microphone)."""

    clipboard_mode: str = "text"
    """``off`` | ``text`` | ``rich`` (rich includes FORMAT_FILELIST)."""

    drag_and_drop_enabled: bool = False
    """Host→guest DnD only; guest→host out of scope."""

    printer_mode: str = "off"
    """``off`` | ``auto`` (forward all CUPS) | ``named:<printer-name>``."""

    smartcard_enabled: bool = False
    """PCSC-Lite passthrough."""

    camera_enabled: bool = False
    """USB webcam redirect."""

    @field_validator("audio_mode")
    @classmethod
    def _audio_known(cls, v: str) -> str:
        if v not in {"off", "playback", "full"}:
            raise ValueError(f"audio_mode must be off|playback|full, got {v!r}")
        return v

    @field_validator("clipboard_mode")
    @classmethod
    def _clipboard_known(cls, v: str) -> str:
        if v not in {"off", "text", "rich"}:
            raise ValueError(f"clipboard_mode must be off|text|rich, got {v!r}")
        return v

    @field_validator("printer_mode")
    @classmethod
    def _printer_known(cls, v: str) -> str:
        if v == "off" or v == "auto" or v.startswith("named:"):
            return v
        raise ValueError(f"printer_mode must be off|auto|named:<name>, got {v!r}")


class DaemonConfig(BaseModel):
    """Daemon identity surfaced via the Hello handshake (DEC-0007).

    ``host_version`` is informational only — it's the value the daemon
    advertises in ``HelloResponse``. ``supported_features`` is a sorted
    tuple of capability tokens the guest can negotiate against.
    """

    model_config = _FROZEN_MODEL_CONFIG

    host_version: str = "0.1.0"
    supported_features: Tuple[str, ...] = (
        "adaptive-heartbeat",
        "credential-verify",
        "rail-multimon",
        "trace-propagation",
    )

    @field_validator("supported_features")
    @classmethod
    def _features_sorted_unique(cls, v: Tuple[str, ...]) -> Tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError(f"supported_features contains duplicates: {v}")
        return tuple(sorted(v))


class CrossdeskConfig(BaseModel):
    """Top-level config aggregate. Every sub-model has defaults so an
    empty TOML file (or a missing one) still produces a valid instance.
    """

    model_config = _FROZEN_MODEL_CONFIG

    paths: PathsConfig = Field(default_factory=PathsConfig)
    transport: TransportConfig = Field(default_factory=TransportConfig)
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    peripherals: PeripheralsConfig = Field(default_factory=PeripheralsConfig)
    daemon: DaemonConfig = Field(default_factory=DaemonConfig)


def default_config_path() -> Path:
    """``~/.config/crossdesk/config.toml`` — same XDG slot as ``vm.toml``.

    Resolved at call time so tests that monkey-patch ``HOME`` see the
    redirected path (mirrors ``installer.credentials._default_path``).
    """
    return Path.home() / ".config" / "crossdesk" / "config.toml"


_ENV_PREFIX = "CROSSDESK_CONFIG__"
"""Env var prefix for ad-hoc overrides. Format::

    CROSSDESK_CONFIG__TRANSPORT__VSOCK_PORT=60001

Maps to ``transport.vsock_port = 60001``. Double-underscore separates
nested keys so single-underscore field names (``vsock_port``,
``ping_interval_seconds``) round-trip correctly.
"""


def _env_overrides(env: Mapping[str, str]) -> Dict[str, Any]:
    """Extract ``CROSSDESK_CONFIG__SECTION__FIELD`` env vars into a
    nested dict suitable for ``CrossdeskConfig.model_validate``.

    Numeric fields are best-effort coerced (``int`` → ``float`` →
    ``str``) so operators don't have to write ``"50051"`` with quotes
    in the env. Pydantic still validates the resulting type — a
    nonsense override fails loudly.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for key, raw in env.items():
        if not key.startswith(_ENV_PREFIX):
            continue
        suffix = key[len(_ENV_PREFIX):]
        parts = suffix.split("__")
        if len(parts) != 2:
            # Only one nesting level is meaningful (sections are flat).
            continue
        section, field = (p.lower() for p in parts)
        out.setdefault(section, {})[field] = _coerce_scalar(raw)
    # Cast to the looser Dict[str, Any] return for caller's merge logic.
    return {section: dict(fields) for section, fields in out.items()}


def _coerce_scalar(raw: str) -> Any:
    """Best-effort scalar coercion for env-var strings.

    Returns int if the string parses as int, float if it parses as
    float, bool for ``true``/``false`` (case-insensitive), else the
    raw string. Pydantic catches type mismatches downstream.
    """
    lowered = raw.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _deep_merge(base: Dict[str, Any], overlay: Mapping[str, Any]) -> Dict[str, Any]:
    """Recursive merge: ``overlay`` wins on scalar conflicts; nested
    dicts merge field-by-field.

    Only used for one nesting level today (env overrides over TOML),
    but written generically so adding a per-host override file later is
    a one-line change at the call site.
    """
    result = dict(base)
    for key, value in overlay.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            result[key] = _deep_merge(existing, value)
        else:
            result[key] = value
    return result


def load_from_toml(
    path: Optional[Path] = None,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> CrossdeskConfig:
    """Load + validate the host config.

    Discovery (matching ``installer.credentials._default_path`` style):
    if ``path`` is omitted, ``~/.config/crossdesk/config.toml`` is
    used; if that file doesn't exist, an all-defaults config is
    returned (no error — bare installs are legal).

    Env overrides via ``CROSSDESK_CONFIG__<SECTION>__<FIELD>`` are
    applied on top of the TOML, so an operator can spike a single
    knob without editing the file. Pass ``env={}`` from tests to
    isolate from the host environment.

    Raises:
        ValueError: TOML parses but a field violates its validator.
        tomllib.TOMLDecodeError: malformed TOML syntax.
    """
    if path is None:
        path = default_config_path()
    if env is None:
        env = os.environ

    raw: Dict[str, Any] = {}
    if path.exists():
        with path.open("rb") as f:
            raw = _tomllib.load(f)

    overrides = _env_overrides(env)
    merged = _deep_merge(raw, overrides)
    # ``model_validate`` runs every field validator — boundary check
    # per .claude/rules/backend.md "Validate at boundaries".
    return CrossdeskConfig.model_validate(merged)
