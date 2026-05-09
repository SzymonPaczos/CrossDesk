"""Redaction allow-list tests.

Strict mode (the default during ``pytest``) raises on any field name
not on the allow-list and on any value containing a forbidden
substring (`password`, `secret`, `token`, `clipboard_content`).
Lenient mode replaces violating values with ``<redacted>``.
"""

from __future__ import annotations

import io
import json

import pytest

from crossdesk_host.observability import (
    RedactionViolation,
    configure_logging,
    get_logger,
)
from crossdesk_host.observability.redaction import redaction_processor


def _emit(buf: io.StringIO, **fields: object) -> str:
    log = get_logger("host.tests.redaction")
    log.info("event_marker", **fields)
    return buf.getvalue().strip()


def test_allowed_field_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROSSDESK_STRICT_LOG", "1")
    buf = io.StringIO()
    configure_logging(stream=buf)
    text = _emit(buf, fsm_state="HEALTHY", duration_ms=12)
    record = json.loads(text)
    assert record["fsm_state"] == "HEALTHY"
    assert record["duration_ms"] == 12


def test_strict_mode_raises_on_unknown_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROSSDESK_STRICT_LOG", "1")
    buf = io.StringIO()
    configure_logging(stream=buf)
    with pytest.raises(RedactionViolation, match="not in allow-list"):
        _emit(buf, password="hunter2")


def test_strict_mode_raises_on_forbidden_substring_in_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CROSSDESK_STRICT_LOG", "1")
    buf = io.StringIO()
    configure_logging(stream=buf)
    with pytest.raises(RedactionViolation, match="matches"):
        # `value` IS allow-listed, but its content contains "password"
        _emit(buf, value="user-password=hunter2")


def test_lenient_mode_replaces_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CROSSDESK_STRICT_LOG", raising=False)
    buf = io.StringIO()
    configure_logging(stream=buf)
    text = _emit(buf, value="something secret here")
    record = json.loads(text)
    assert record["value"] == "<redacted>"
    assert record["redaction_drop_count"] == 1


def test_lenient_mode_drops_unknown_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CROSSDESK_STRICT_LOG", raising=False)
    buf = io.StringIO()
    configure_logging(stream=buf)
    text = _emit(buf, totally_random_field="nothing dangerous")
    record = json.loads(text)
    # Field was unknown — replaced with <redacted> but kept under same
    # key so structlog's downstream JSON renderer doesn't blow up.
    assert record["totally_random_field"] == "<redacted>"
    assert record["redaction_drop_count"] == 1


def test_processor_handles_nested_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dict-valued field with a forbidden substring should still be
    caught by the processor."""
    monkeypatch.setenv("CROSSDESK_STRICT_LOG", "1")
    event = {"event": "x", "value": {"inner": "x-token-y"}}
    with pytest.raises(RedactionViolation, match="matches"):
        redaction_processor(None, "info", event)


def test_processor_handles_list_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CROSSDESK_STRICT_LOG", "1")
    event = {"event": "x", "value": ["clean", "secret-thing", "clean2"]}
    with pytest.raises(RedactionViolation):
        redaction_processor(None, "info", event)
