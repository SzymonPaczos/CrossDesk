"""Cross-cutting observability facade per DEC-0006.

Single entry point for structured logging, W3C trace context, and the
in-memory metrics registry. Other modules import from here and never
configure ``logging``/``structlog`` directly.
"""

from crossdesk_host.observability.log import (
    configure_logging,
    get_logger,
    LOG_SCHEMA_FIELDS,
)

__all__ = ["configure_logging", "get_logger", "LOG_SCHEMA_FIELDS"]
