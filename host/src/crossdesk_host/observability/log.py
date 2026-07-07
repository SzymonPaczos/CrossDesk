"""Structlog facade with JSON Lines output.

JSON Lines schema (one event per line):

    {"timestamp": "2026-05-08T12:34:56.789Z",
     "level": "info",
     "component": "host.ipc.control",
     "trace_id": "<32 hex or empty>",
     "span_id": "<16 hex or empty>",
     "event": "human-readable event name",
     ...arbitrary structured fields...}

Per DEC-0006 every component logs through this facade, so future
exporters (OTLP, Honeycomb) can rely on the schema.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, List, MutableMapping, Optional

import structlog

from crossdesk_host.observability.redaction import redaction_processor

# Bounded rotating file: 5 MiB per file, one backup (.1) → ~10 MiB ceiling.
# Enough history to diagnose a session without unbounded growth for users
# not running under journald (which would rotate for us).
_LOG_FILE_MAX_BYTES = 5 * 1024 * 1024
_LOG_FILE_BACKUPS = 1


class _RotatingFileWriter:
    """Minimal size-rotating text sink with a ``write``/``flush`` surface
    so it can sit behind structlog's ``PrintLoggerFactory`` and a stdlib
    ``StreamHandler`` alike. Rotates between writes (each write is one
    complete JSON line), so a line is never split across files. Best-effort:
    an IO error degrades to dropping the line rather than crashing the
    logging call."""

    def __init__(self, path: Path, max_bytes: int, backups: int) -> None:
        self._path = path
        self._max_bytes = max_bytes
        self._backups = backups
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._size = path.stat().st_size if path.exists() else 0
        # Repair a pre-existing looser file to 0600 first, then keep every
        # (re)open owner-only: the daemon log carries operational detail and
        # must never be world-readable.
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        self._fh = open(
            path, "a", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)
        )

    def write(self, s: str) -> int:
        data_len = len(s.encode("utf-8"))
        with self._lock:
            try:
                if self._size + data_len > self._max_bytes:
                    self._rotate()
                n = self._fh.write(s)
                self._size += data_len
                return n
            except OSError:
                return 0

    def flush(self) -> None:
        with self._lock:
            try:
                self._fh.flush()
            except OSError:
                pass

    def _rotate(self) -> None:
        self._fh.close()
        if self._backups > 0:
            backup = self._path.with_name(self._path.name + ".1")
            try:
                os.replace(self._path, backup)
            except OSError:
                pass
        self._fh = open(
            self._path, "w", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)
        )
        self._size = 0


class _Tee:
    """Fan a ``write``/``flush`` out to several sinks (stderr + the
    rotating file). Used so both structlog's own lines and foreign stdlib
    records land in the file as well as the console."""

    def __init__(self, sinks: List[Any]) -> None:
        self._sinks = sinks

    def write(self, s: str) -> int:
        for sink in self._sinks:
            sink.write(s)
        return len(s)

    def flush(self) -> None:
        for sink in self._sinks:
            sink.flush()

# Mandatory fields every log line MUST carry. Renderers and tests verify
# this set is present even when callers forget to bind them — missing
# fields land as empty strings rather than raising, so a logger never
# breaks the calling code.
LOG_SCHEMA_FIELDS: frozenset[str] = frozenset(
    {"timestamp", "level", "component", "trace_id", "span_id", "event"}
)


def _ensure_schema_fields(
    _logger: Any, _name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Inject empty defaults for any mandatory schema field the caller
    didn't bind. Keeps the JSON schema stable even for ad-hoc log lines.

    structlog's `add_log_level` and `TimeStamper(fmt='iso', utc=True)`
    set ``level`` and ``timestamp`` upstream of this processor; we
    cover the rest here so every line is self-describing.
    """
    for field in LOG_SCHEMA_FIELDS:
        event_dict.setdefault(field, "")
    return event_dict


def _stringify_event(
    _logger: Any, _name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """structlog uses ``event`` as the message key; coerce to string so
    callers can pass any object without breaking the JSON renderer."""
    if "event" in event_dict and not isinstance(event_dict["event"], str):
        event_dict["event"] = str(event_dict["event"])
    return event_dict


def configure_logging(
    level: str = "INFO", stream: Any = None, log_file: Optional[Path] = None
) -> None:
    """Configure structlog + stdlib logging to emit JSON Lines.

    ``stream`` defaults to whatever ``sys.stderr`` resolves to at log
    emission time (so pytest's capture and runtime stderr redirection
    both work). Tests that need direct capture pass an ``io.StringIO``.

    ``log_file`` (production daemon only) additionally tees every line into
    a bounded size-rotating file at that path, so ``crossdesk logs`` works
    without journald and a beta user can attach it. When ``None`` (the
    default, and every test) nothing is written to disk and the behaviour
    is byte-identical to the stream-only path.

    Idempotent — calling more than once rebinds the processor chain.
    """
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp")

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        _ensure_schema_fields,
        _stringify_event,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redaction_processor,
    ]

    if stream is None:
        # Lazily resolve sys.stderr at every call so writers always hit
        # the current file (pytest capsys, redirected stderr in tests,
        # etc.). PrintLoggerFactory snapshots `file=` at construction,
        # which would defeat that — so we wrap in a thin proxy.
        class _LiveStderr:
            def write(self, s: str) -> int:
                return sys.stderr.write(s)

            def flush(self) -> None:
                sys.stderr.flush()

        stream = _LiveStderr()

    if log_file is not None:
        # Tee the resolved stream and the rotating file so both structlog
        # lines (via PrintLoggerFactory) and foreign stdlib records (via
        # the StreamHandler below) reach disk as well as the console.
        stream = _Tee([stream, _RotatingFileWriter(log_file, _LOG_FILE_MAX_BYTES, _LOG_FILE_BACKUPS)])

    structlog.configure(
        processors=shared_processors
        + [structlog.processors.JSONRenderer(sort_keys=True)],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=False,
    )

    # stdlib loggers (e.g. grpc, asyncio) flow through the same JSON
    # output. Replace any prior handlers so we don't double-emit.
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(sort_keys=True),
            foreign_pre_chain=shared_processors,
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(component: str) -> Any:
    """Return a logger bound to ``component``. Convention: dotted path,
    e.g. ``"host.ipc.control"`` or ``"host.watchdog.fsm"``.

    Return type is ``Any`` because structlog's wrapper class is built
    dynamically from ``make_filtering_bound_logger`` and the static
    type doesn't match the runtime BoundLogger we actually get.
    """
    return structlog.get_logger().bind(component=component)
