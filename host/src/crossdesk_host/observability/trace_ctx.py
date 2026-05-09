"""W3C Trace Context — minimal `traceparent` parser/serializer used to
propagate distributed-trace IDs across the host↔guest gRPC boundary.

Format (per W3C TraceContext §3.2.2.1):

    traceparent: 00-<32-hex trace-id>-<16-hex span-id>-<2-hex flags>

We support version `00` only and treat the flags byte as opaque (read
back what we got). The trace ID is preserved across the boundary; each
side mints its own span ID for the local span.

Field name on the wire is the lowercase ASCII string ``traceparent``,
matching the W3C spec — gRPC metadata is case-insensitive but we
normalise to lowercase so explicit lookups work.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

import structlog

_TRACEPARENT_KEY = "traceparent"
_TRACEPARENT_RE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")
_INVALID_TRACE_ID = "0" * 32
_INVALID_SPAN_ID = "0" * 16


@dataclass(frozen=True)
class TraceContext:
    """Parsed traceparent. Either component may be invalid (all zeros)
    if the upstream sent only a partial header — we still propagate
    what we can to keep downstream debugging coherent.
    """

    trace_id: str
    span_id: str
    flags: str = "01"

    def to_traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.span_id}-{self.flags}"

    def is_valid(self) -> bool:
        return self.trace_id != _INVALID_TRACE_ID and self.span_id != _INVALID_SPAN_ID


def generate_root() -> TraceContext:
    """Mint a fresh root context — used by CLI commands and any
    server-initiated operation that has no upstream trace."""
    return TraceContext(
        trace_id=secrets.token_hex(16),
        span_id=secrets.token_hex(8),
        flags="01",
    )


def child_span(parent: TraceContext) -> TraceContext:
    """Inherit `trace_id`, mint a fresh `span_id`. Use this when
    crossing a process / RPC boundary so each leg of the trace has a
    distinct span while keeping the root trace ID intact.
    """
    return TraceContext(
        trace_id=parent.trace_id,
        span_id=secrets.token_hex(8),
        flags=parent.flags,
    )


def parse_traceparent(value: str) -> TraceContext | None:
    """Return ``None`` if the header is not a recognisable W3C
    traceparent (wrong version, malformed hex, etc.). Callers fall
    back to ``generate_root()`` in that case rather than rejecting
    the request — propagation must never break a working call path.
    """
    match = _TRACEPARENT_RE.match(value.strip())
    if match is None:
        return None
    trace_id, span_id, flags = match.groups()
    return TraceContext(trace_id=trace_id, span_id=span_id, flags=flags)


def extract_from_metadata(metadata: object) -> TraceContext | None:
    """Read the first ``traceparent`` entry from a gRPC metadata
    container. Returns ``None`` if absent or unparseable.

    `metadata` is anything iterable as ``[(key, value), ...]`` — gRPC
    server contexts return a tuple-of-tuples, async clients return
    similar. Typed as ``object`` here to avoid a hard dependency on
    grpc symbols; a TypeError on iteration falls back cleanly.
    """
    if metadata is None:
        return None
    try:
        items = list(metadata)  # type: ignore[call-overload]
    except TypeError:
        return None
    for key, value in items:
        if str(key).lower() == _TRACEPARENT_KEY:
            return parse_traceparent(str(value))
    return None


def metadata_pair(ctx: TraceContext) -> tuple[str, str]:
    """Convenience for `metadata=[trace_ctx.metadata_pair(ctx)]`
    plumbing into gRPC clients."""
    return (_TRACEPARENT_KEY, ctx.to_traceparent())


def bind_to_log_context(ctx: TraceContext) -> None:
    """Inject ``trace_id`` and ``span_id`` into structlog's
    contextvars so subsequent log lines on this asyncio task
    automatically carry them.

    Servicers call this at the top of each RPC handler (after they
    extract or mint a context). Once bound, every nested
    ``get_logger("...").info(...)`` line includes the IDs without
    callers having to thread them.
    """
    structlog.contextvars.bind_contextvars(
        trace_id=ctx.trace_id,
        span_id=ctx.span_id,
    )


def clear_log_context() -> None:
    structlog.contextvars.unbind_contextvars("trace_id", "span_id")
