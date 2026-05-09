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
