"""Cross-cutting observability facade per DEC-0006.

Single entry point for structured logging, W3C trace context, and the
in-memory metrics registry. Other modules import from here and never
configure ``logging``/``structlog`` directly.
"""

from crossdesk_host.observability.log import (
    LOG_SCHEMA_FIELDS,
    configure_logging,
    get_logger,
)
from crossdesk_host.observability.metrics import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    MetricNames,
    Registry,
)
from crossdesk_host.observability.redaction import (
    ALLOWED_FIELDS,
    RedactionViolation,
)
from crossdesk_host.observability.trace_ctx import (
    TraceContext,
    bind_to_log_context,
    child_span,
    clear_log_context,
    extract_from_metadata,
    generate_root,
    metadata_pair,
    parse_traceparent,
)

__all__ = [
    "ALLOWED_FIELDS",
    "LOG_SCHEMA_FIELDS",
    "REGISTRY",
    "Counter",
    "Gauge",
    "Histogram",
    "MetricNames",
    "RedactionViolation",
    "Registry",
    "TraceContext",
    "bind_to_log_context",
    "child_span",
    "clear_log_context",
    "configure_logging",
    "extract_from_metadata",
    "generate_root",
    "get_logger",
    "metadata_pair",
    "parse_traceparent",
]
