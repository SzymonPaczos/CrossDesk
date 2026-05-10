"""W3C Trace Context unit tests — round-trip, parse rejection,
metadata extraction, log-context binding.
"""

from __future__ import annotations

import io
import json

import pytest
import structlog

from crossdesk_host.observability import (
    bind_to_log_context,
    child_span,
    clear_log_context,
    configure_logging,
    extract_from_metadata,
    generate_root,
    get_logger,
    metadata_pair,
    parse_traceparent,
)


def test_round_trip_traceparent() -> None:
    ctx = generate_root()
    s = ctx.to_traceparent()
    assert parse_traceparent(s) == ctx
    assert ctx.is_valid()


def test_parse_rejects_wrong_version() -> None:
    assert (
        parse_traceparent("01-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01")
        is None
    )


def test_parse_rejects_short_hex() -> None:
    assert parse_traceparent("00-tooshort-bbbbbbbbbbbbbbbb-01") is None


def test_parse_rejects_non_hex() -> None:
    assert (
        parse_traceparent("00-zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz-bbbbbbbbbbbbbbbb-01")
        is None
    )


def test_child_span_keeps_trace_id() -> None:
    parent = generate_root()
    child = child_span(parent)
    assert child.trace_id == parent.trace_id
    assert child.span_id != parent.span_id


def test_metadata_round_trip() -> None:
    ctx = generate_root()
    md = [metadata_pair(ctx)]
    assert extract_from_metadata(md) == ctx


def test_metadata_missing_returns_none() -> None:
    assert extract_from_metadata([]) is None


def test_metadata_present_but_garbage_returns_none() -> None:
    assert extract_from_metadata([("traceparent", "garbage")]) is None


def test_bind_emits_trace_id_in_log_line() -> None:
    buf = io.StringIO()
    configure_logging(stream=buf)
    structlog.contextvars.clear_contextvars()

    ctx = generate_root()
    bind_to_log_context(ctx)
    try:
        get_logger("host.tests.trace").info("emitted")
    finally:
        clear_log_context()
        structlog.contextvars.clear_contextvars()

    text = buf.getvalue().strip()
    assert text, "expected one log line"
    record = json.loads(text)
    assert record["trace_id"] == ctx.trace_id
    assert record["span_id"] == ctx.span_id


@pytest.mark.parametrize("case", ["", "00-", "00-aaaa-bbbb-cc-extra", "junk"])
def test_parse_robust_to_malformed_input(case: str) -> None:
    assert parse_traceparent(case) is None


# ----- child_span_scope (per-RPC handler span coverage) -----


def test_child_span_scope_mints_root_when_nothing_bound() -> None:
    """No upstream context → scope mints a fresh root."""
    import structlog

    from crossdesk_host.observability.trace_ctx import child_span_scope

    structlog.contextvars.clear_contextvars()
    with child_span_scope() as ctx:
        assert ctx.is_valid()
        bound = structlog.contextvars.get_contextvars()
        assert bound.get("trace_id") == ctx.trace_id
        assert bound.get("span_id") == ctx.span_id
    # Cleared on exit when no prior context existed.
    bound_after = structlog.contextvars.get_contextvars()
    assert "trace_id" not in bound_after


def test_child_span_scope_inherits_trace_id_from_parent() -> None:
    """Bound parent → child span keeps trace_id, fresh span_id."""
    import structlog

    from crossdesk_host.observability.trace_ctx import (
        TraceContext,
        bind_to_log_context,
        child_span_scope,
    )

    structlog.contextvars.clear_contextvars()
    parent = TraceContext(trace_id="a" * 32, span_id="b" * 16)
    bind_to_log_context(parent)
    try:
        with child_span_scope() as child:
            assert child.trace_id == parent.trace_id
            assert child.span_id != parent.span_id
        # After exit, parent restored.
        bound = structlog.contextvars.get_contextvars()
        assert bound.get("trace_id") == parent.trace_id
        assert bound.get("span_id") == parent.span_id
    finally:
        structlog.contextvars.clear_contextvars()


def test_nested_child_span_scopes_each_get_own_span() -> None:
    """Nesting scopes (e.g., RPC handler calling a helper) produces a
    chain of distinct span_ids, all sharing one trace_id."""
    import structlog

    from crossdesk_host.observability.trace_ctx import (
        TraceContext,
        bind_to_log_context,
        child_span_scope,
    )

    structlog.contextvars.clear_contextvars()
    bind_to_log_context(TraceContext(trace_id="c" * 32, span_id="d" * 16))
    try:
        with child_span_scope() as outer:
            with child_span_scope() as inner:
                assert outer.trace_id == inner.trace_id
                assert outer.span_id != inner.span_id
            # Inner exit → outer's span restored.
            bound = structlog.contextvars.get_contextvars()
            assert bound.get("span_id") == outer.span_id
    finally:
        structlog.contextvars.clear_contextvars()
