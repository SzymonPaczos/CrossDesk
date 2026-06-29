"""Opt-in crash-report capture (default OFF).

When an unhandled exception escapes the CLI dispatcher or the daemon's
last-resort catch, the user always gets a friendly, actionable message
instead of a raw Python traceback. *Additionally*, when crash reporting
is enabled (``[observability] crash_report_enabled = true`` or
``CROSSDESK_CONFIG__OBSERVABILITY__CRASH_REPORT_ENABLED=true`` — default
OFF), a self-contained, redacted crash-report file is written under
``paths.state_dir/crash-reports/`` so the user can attach it to a bug
report.

Nothing is transmitted off the machine in either mode: the report is a
local artifact the user chooses to share. CrossDesk ships no telemetry
backend, and the audience is privacy-minded; users who *want* their own
collector wire it through the OTLP exporter (``observability/otlp.py``).
A crash *report* is the smallest honest thing — a redacted dump the user
can read before sending.
"""

from __future__ import annotations

import json
import platform
import traceback
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

from crossdesk_host.observability.log import get_logger
from crossdesk_host.observability.redaction import mask_sensitive
from crossdesk_host.utils.atomic_write import atomic_write

_logger = get_logger("host.observability.crash_reporter")


@dataclass(frozen=True)
class CrashReport:
    """A redacted, self-contained record of an unhandled exception.

    Deliberately excludes frame-local variable values: ``traceback`` is
    built from :func:`traceback.format_exception` (stack frames + the
    exception message only, no locals), then each line is passed through
    :func:`mask_sensitive` so a secret that happens to live in the
    message or a path can't ride along into a shared file.
    """

    timestamp: str
    component: str
    command: str
    host_version: str
    python_version: str
    platform: str
    exception_type: str
    exception_message: str
    traceback: List[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_crash_report(
    exc: BaseException,
    *,
    component: str,
    command: Sequence[str],
    host_version: str,
    timestamp: str,
) -> CrashReport:
    """Assemble a redacted :class:`CrashReport` from ``exc``."""
    frames = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return CrashReport(
        timestamp=timestamp,
        component=component,
        command=mask_sensitive(" ".join(command)),
        host_version=host_version,
        python_version=platform.python_version(),
        platform=platform.platform(),
        exception_type=type(exc).__name__,
        exception_message=mask_sensitive(str(exc)),
        traceback=[mask_sensitive(frame) for frame in frames],
    )


def write_crash_report(report: CrashReport, report_dir: Path) -> Path:
    """Write ``report`` atomically to a unique file under ``report_dir``
    and return the path. The filename embeds the timestamp plus a short
    random suffix so two crashes in the same second never collide."""
    safe_ts = "".join(c for c in report.timestamp if c.isalnum())
    path = report_dir / f"crash-{safe_ts}-{uuid.uuid4().hex[:8]}.json"
    atomic_write(path, report.to_json())
    return path


def report_exception(
    exc: BaseException,
    *,
    component: str,
    command: Sequence[str],
    host_version: str,
    enabled: bool,
    report_dir: Path,
    timestamp: Optional[str] = None,
) -> Optional[Path]:
    """Write a redacted crash-report file when ``enabled``; return its
    path (or ``None`` when disabled, or when the write failed).

    Best-effort by contract: any failure to build or write the report is
    swallowed (logged, not raised) so crash reporting can never mask the
    original error or raise from inside an exception handler.
    """
    if not enabled:
        return None
    try:
        report = build_crash_report(
            exc,
            component=component,
            command=command,
            host_version=host_version,
            timestamp=timestamp or _utc_now_iso(),
        )
        return write_crash_report(report, report_dir)
    except Exception:  # noqa: BLE001 - never raise from a crash handler
        _logger.warning("crash_report_write_failed")
        return None
