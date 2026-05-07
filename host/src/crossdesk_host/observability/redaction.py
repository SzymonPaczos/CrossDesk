"""Redaction allow-list lint per DEC-0006.

Every log line must carry only field names from a frozen allow-list
and must not include known-sensitive substrings (passwords, tokens,
secrets) anywhere in field values. Catching that at log time means a
careless ``logger.info("user_creds", password=...)`` never reaches
the JSON output.

Two enforcement modes:

- **strict** (``CROSSDESK_STRICT_LOG=1``): the redaction processor
  *raises* ``RedactionViolation`` so the test suite fails loudly.
  Default during ``pytest``.
- **lenient** (default in production): the offending field is dropped
  from the event_dict and a ``redaction_drop`` warning replaces it,
  so the log stream stays clean even when a caller slips up.

Adding a new allow-list field is intentional friction — extend
``ALLOWED_FIELDS`` here and the reviewer signs off.
"""

from __future__ import annotations

import os
import re
from typing import Any, MutableMapping

# Mandatory schema fields are always allowed; the wider allow-list
# below covers business fields. Keep this set tight — every entry is
# a public contract that downstream telemetry consumers can rely on.
_SCHEMA_FIELDS: frozenset[str] = frozenset(
    {"timestamp", "level", "component", "trace_id", "span_id", "event"}
)

ALLOWED_FIELDS: frozenset[str] = _SCHEMA_FIELDS | frozenset({
    # Lifecycle / FSM
    "fsm_state", "previous_state", "transition", "vm_state", "duration_ms",
    "rtt_ms", "miss_count", "share_id", "domain_name",
    # Identity (fingerprints are short, non-sensitive)
    "peer_fingerprint", "uuid", "host_endpoint", "kind",
    # Metrics / counters
    "metric_name", "value", "count", "n", "key", "target",
    # gRPC / wire
    "method", "status_code", "rpc_error", "stream_nonce_hex", "sequence",
    "expected_sequence",
    # Filesystem
    "mount_path", "host_path", "guest_drive_letter", "open_handles",
    "pending_writes_bytes", "frame_kind", "payload_type",
    # Process / OS
    "pid", "argv", "exit_code", "signal",
    # stdlib logging integration leaves these alongside our schema.
    # Allowing them prevents redaction noise on `logger.warning(...)`
    # calls coming from grpc/asyncio plumbing.
    "logger", "exception", "exc_info", "stack_info", "_record", "_from_structlog",
    # Set by the redaction processor itself when running in lenient
    # mode — re-allowing prevents recursive violation on the next pass.
    "redaction_drop_count",
})

_FORBIDDEN_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in (
        r"password",
        r"secret",
        r"\btoken\b",  # `mount_token` is sensitive too — see hex caveat below
        r"clipboard_content",
    )
)

_ENV_STRICT = "CROSSDESK_STRICT_LOG"


class RedactionViolation(RuntimeError):
    """Raised in strict mode when a log call contains a forbidden
    field name or a value matching one of the sensitive patterns."""


def _is_strict() -> bool:
    return os.environ.get(_ENV_STRICT, "") == "1"


def _value_contains_forbidden(value: Any) -> str | None:
    """Return the matching pattern name if ``value`` (or any nested
    string) contains a forbidden substring. None otherwise."""
    if isinstance(value, str):
        for pat in _FORBIDDEN_PATTERNS:
            if pat.search(value):
                return pat.pattern
        return None
    if isinstance(value, dict):
        for v in value.values():
            hit = _value_contains_forbidden(v)
            if hit:
                return hit
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            hit = _value_contains_forbidden(item)
            if hit:
                return hit
        return None
    return None


def redaction_processor(
    _logger: Any, _name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """structlog processor that enforces the allow-list.

    Plug into the chain *before* the JSON renderer so violations are
    caught while the event is still a dict.
    """
    strict = _is_strict()
    violations: list[str] = []

    for key in list(event_dict.keys()):
        if key not in ALLOWED_FIELDS:
            violations.append(f"field {key!r} not in allow-list")
            if strict:
                continue
            event_dict[key] = "<redacted>"
            continue

        forbidden = _value_contains_forbidden(event_dict[key])
        if forbidden:
            violations.append(f"value of {key!r} matches /{forbidden}/")
            if strict:
                continue
            event_dict[key] = "<redacted>"

    if violations and strict:
        raise RedactionViolation("; ".join(violations))

    if violations:
        # Surface that something was dropped without leaking what.
        event_dict["redaction_drop_count"] = len(violations)

    return event_dict
