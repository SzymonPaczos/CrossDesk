"""Log facade contract test.

Every log line emitted via ``crossdesk_host.observability.get_logger``
must be a single JSON object with the mandatory schema fields. Drift
from this shape breaks downstream tooling (CLI ``crossdesk logs``,
future OTLP exporter, perf-budget telemetry).
"""

from __future__ import annotations

import io
import json

import pytest

from crossdesk_host.observability import (
    LOG_SCHEMA_FIELDS,
    configure_logging,
    get_logger,
)


@pytest.fixture
def log_buffer() -> io.StringIO:
    buf = io.StringIO()
    configure_logging(stream=buf)
    return buf


def _emit(buf: io.StringIO, component: str) -> dict[str, object]:
    log = get_logger(component)
    log.info("test_event", key="value", n=7)
    text = buf.getvalue().strip()
    assert text, "no log line emitted"
    assert "\n" not in text, f"expected single line, got:\n{text}"
    return json.loads(text)


def test_log_line_is_valid_json_with_schema_fields(log_buffer: io.StringIO) -> None:
    record = _emit(log_buffer, "host.tests.log")
    missing = LOG_SCHEMA_FIELDS - record.keys()
    assert not missing, f"missing mandatory schema fields: {missing}"


def test_log_line_carries_component_binding(log_buffer: io.StringIO) -> None:
    record = _emit(log_buffer, "host.tests.binding")
    assert record["component"] == "host.tests.binding"


def test_log_line_preserves_extra_fields(log_buffer: io.StringIO) -> None:
    record = _emit(log_buffer, "host.tests.extras")
    assert record["key"] == "value"
    assert record["n"] == 7
    assert record["event"] == "test_event"


def test_timestamp_is_iso8601_utc(log_buffer: io.StringIO) -> None:
    record = _emit(log_buffer, "host.tests.ts")
    ts = record["timestamp"]
    assert isinstance(ts, str) and ts.endswith("Z"), f"non-UTC timestamp: {ts!r}"
