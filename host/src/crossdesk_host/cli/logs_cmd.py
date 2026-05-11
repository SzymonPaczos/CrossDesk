"""``crossdesk logs`` — aggregate and display log streams.

Interleaves log lines from multiple sources, sorted by timestamp:

- **host**: systemd journal for ``crossdesk-host.service`` (Linux) or
  the rotating file at ``~/.local/state/crossdesk/logs/crossdesk-host.jsonl``
  (Mac / no systemd).
- **libvirt**: ``/var/log/libvirt/qemu/crossdesk-vm.log``.
- **freerdp**: ``~/.config/freerdp/client/X11/log`` or
  ``~/.local/share/FreeRDP/log/*.log``.
- **guest**: P2 — gRPC pull from agent structured-log buffer. Use
  ``--component guest`` to get an explicit not-yet-implemented notice.

Options::

    --since DURATION      Show logs from the last DURATION (e.g. 5m, 1h, 30s).
                          Default: 5m.
    --follow              Stream new lines as they appear. Ctrl-C to stop.
    --component {host,libvirt,freerdp,guest,all}
                          Which source(s) to show. Default: all.
    --json                Output raw JSON per line (adds _source field).
    --lines N             Most-recent lines per source (default 100).
                          Ignored when --since is given.

All sources are optional — if a source is unavailable the command prints
a warning to stderr and continues. If **all** sources are unavailable it
exits 0 (availability gap, not a bug).

Guest log streaming is P2 (not yet implemented). ``--component guest``
warns and exits 0.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import io
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional, Sequence, Tuple

from crossdesk_host.i18n import _

# ---------------------------------------------------------------------------
# Duration parsing
# ---------------------------------------------------------------------------

_DURATION_RE = re.compile(
    r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$",
    re.IGNORECASE,
)


def _parse_duration(text: str) -> timedelta:
    """Convert a human duration string (e.g. "5m", "1h30m", "90s") to a
    :class:`~datetime.timedelta`.

    Raises :exc:`ValueError` when the string is empty or doesn't match the
    ``[Nh][Nm][Ns]`` pattern.
    """
    m = _DURATION_RE.match(text.strip())
    if not m or not any(m.groups()):
        raise ValueError(
            _("invalid duration {text!r}: expected e.g. 5m, 1h, 30s, 2h30m").format(
                text=text
            )
        )
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


# ---------------------------------------------------------------------------
# Timestamp parsing helpers
# ---------------------------------------------------------------------------

_LIBVIRT_TS_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\+\d{4}"
)

_ISO_FRACS_RE = re.compile(r"(\.\d+)")


def _parse_iso(ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp, stripping sub-second fractions before
    passing to ``datetime.fromisoformat`` for Python 3.9 compat.

    Returns ``None`` if the string cannot be parsed.
    """
    # Normalise Z suffix — Python 3.9's fromisoformat doesn't accept "Z".
    ts = ts.replace("Z", "+00:00")
    # Strip sub-second fractions that exceed 6 digits (Python 3.9 limit).
    ts = _ISO_FRACS_RE.sub(lambda mo: mo.group(0)[:7], ts)
    try:
        dt = datetime.fromisoformat(ts)
        # Treat naive timestamps as UTC so comparisons work uniformly.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _parse_libvirt_ts(line: str) -> Optional[datetime]:
    """Extract the leading ``YYYY-MM-DD HH:MM:SS.fff+0000`` timestamp from
    a libvirt log line and return an aware UTC ``datetime``.

    Returns ``None`` if the line has no recognisable prefix.
    """
    m = _LIBVIRT_TS_RE.match(line)
    if not m:
        return None
    raw = m.group(1)  # "2026-05-10 12:34:56.123"
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S.%f")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Log record abstraction
# ---------------------------------------------------------------------------


class _LogRecord:
    """A single parsed log line from any source.

    Attributes:
        source: One of ``"host"``, ``"libvirt"``, ``"freerdp"``.
        ts:     Parsed UTC-aware timestamp (``None`` = unparseable, sorts last).
        raw:    The original line text (JSON or plain).
        data:   Parsed JSON dict when the source is ``"host"``; ``None`` otherwise.
    """

    __slots__ = ("source", "ts", "raw", "data")

    def __init__(
        self,
        source: str,
        ts: Optional[datetime],
        raw: str,
        data: Optional[Dict[str, object]] = None,
    ) -> None:
        self.source = source
        self.ts = ts
        self.raw = raw
        self.data = data

    def sort_key(self) -> Tuple[int, datetime]:
        if self.ts is None:
            # Lines without timestamps sort to the far future so they appear
            # after timestamped lines rather than crashing the sort.
            return (1, datetime(9999, 12, 31, tzinfo=timezone.utc))
        return (0, self.ts)


# ---------------------------------------------------------------------------
# Source readers (synchronous batch mode)
# ---------------------------------------------------------------------------


def _host_log_path() -> Path:
    """Return the fallback JSONL log path under XDG state dir."""
    return (
        Path.home() / ".local" / "state" / "crossdesk" / "logs" / "crossdesk-host.jsonl"
    )


def _read_host_logs(
    lines: int, cutoff: Optional[datetime]
) -> Tuple[List[_LogRecord], Optional[str]]:
    """Read host daemon logs.

    Strategy:
    1. Try ``journalctl --user -u crossdesk-host.service --output json``
       (Linux with systemd).
    2. Fall back to the rotating JSONL file.
    3. If neither is available, return an empty list + a warning message.
    """
    # --- attempt 1: journalctl ---
    try:
        result = subprocess.run(
            [
                "journalctl",
                "--user",
                "-u",
                "crossdesk-host.service",
                "--output",
                "json",
                "--no-pager",
                f"--lines={lines}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _parse_jsonl_stream(
                io.StringIO(result.stdout), source="host", cutoff=cutoff
            )
        # journalctl exited non-zero or produced empty output — fall through
        # to file fallback below.
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # --- attempt 2: JSONL file ---
    log_file = _host_log_path()
    if log_file.exists():
        try:
            text = log_file.read_text(encoding="utf-8", errors="replace")
            all_records, warn = _parse_jsonl_stream(
                io.StringIO(text), source="host", cutoff=cutoff
            )
            return all_records[-lines:], warn
        except OSError as exc:
            return [], _("warning: could not read host log file {path}: {err}").format(
                path=log_file, err=exc
            )

    return [], _(
        "warning: host logs not available "
        "(no systemd journal; no log file at {path})"
    ).format(path=log_file)


def _parse_jsonl_stream(
    stream: io.StringIO,
    *,
    source: str,
    cutoff: Optional[datetime],
) -> Tuple[List[_LogRecord], Optional[str]]:
    """Parse a JSON-Lines stream into :class:`_LogRecord` instances.

    Both the host JSONL file and ``journalctl --output json`` produce one
    JSON object per line.  ``journalctl`` uses ``__REALTIME_TIMESTAMP``
    (microseconds since epoch) while our own log schema uses ``timestamp``
    (ISO-8601); we handle both.
    """
    records: List[_LogRecord] = []
    for raw_line in stream:
        line = raw_line.strip()
        if not line:
            continue
        ts: Optional[datetime] = None
        data: Optional[Dict[str, object]] = None
        try:
            obj: Dict[str, object] = json.loads(line)
            data = obj
            # journalctl JSON uses __REALTIME_TIMESTAMP (microseconds).
            if "__REALTIME_TIMESTAMP" in obj:
                us = int(str(obj["__REALTIME_TIMESTAMP"]))
                ts = datetime.fromtimestamp(us / 1_000_000, tz=timezone.utc)
            elif "timestamp" in obj:
                ts = _parse_iso(str(obj["timestamp"]))
        except (json.JSONDecodeError, ValueError):
            # Malformed line — keep it, sort to end.
            pass

        if cutoff is not None and ts is not None and ts < cutoff:
            continue
        records.append(_LogRecord(source=source, ts=ts, raw=line, data=data))
    return records, None


def _libvirt_log_path() -> Path:
    return Path("/var/log/libvirt/qemu/crossdesk-vm.log")


def _read_libvirt_logs(
    lines: int, cutoff: Optional[datetime]
) -> Tuple[List[_LogRecord], Optional[str]]:
    log_path = _libvirt_log_path()
    if not log_path.exists():
        return [], _(
            "warning: libvirt logs not available (file not found: {path})"
        ).format(path=log_path)
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [], _(
            "warning: could not read libvirt log {path}: {err}"
        ).format(path=log_path, err=exc)

    records: List[_LogRecord] = []
    all_lines = text.splitlines()
    for raw_line in all_lines[-lines:] if cutoff is None else all_lines:
        line = raw_line.strip()
        if not line:
            continue
        ts = _parse_libvirt_ts(line)
        if cutoff is not None and ts is not None and ts < cutoff:
            continue
        records.append(_LogRecord(source="libvirt", ts=ts, raw=line))
    return records, None


def _freerdp_log_paths() -> List[Path]:
    """Return candidate FreeRDP log paths (those that exist)."""
    candidates: List[Path] = []
    home = Path.home()
    # Standard XDG path used by the X11 FreeRDP client.
    p1 = home / ".config" / "freerdp" / "client" / "X11" / "log"
    if p1.exists():
        candidates.append(p1)
    # Alternate location used by newer FreeRDP builds.
    pattern = str(home / ".local" / "share" / "FreeRDP" / "log" / "*.log")
    for match in glob.glob(pattern):
        candidates.append(Path(match))
    return candidates


def _read_freerdp_logs(
    lines: int, cutoff: Optional[datetime]
) -> Tuple[List[_LogRecord], Optional[str]]:
    paths = _freerdp_log_paths()
    if not paths:
        return [], _(
            "warning: FreeRDP logs not available "
            "(checked ~/.config/freerdp/client/X11/log "
            "and ~/.local/share/FreeRDP/log/*.log)"
        )
    records: List[_LogRecord] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(
                _("warning: could not read FreeRDP log {path}: {err}").format(
                    path=path, err=exc
                ),
                file=sys.stderr,
            )
            continue
        all_lines = text.splitlines()
        for raw_line in all_lines[-lines:] if cutoff is None else all_lines:
            line = raw_line.strip()
            if not line:
                continue
            # FreeRDP plain-text lines don't carry a structured timestamp;
            # we leave ts=None so they sort to the end but still appear.
            records.append(_LogRecord(source="freerdp", ts=None, raw=line))
    return records, None


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

_SOURCE_LABEL: Dict[str, str] = {
    "host": "[HOST]   ",
    "libvirt": "[LIBVIRT]",
    "freerdp": "[FREERDP]",
}


def _format_human(record: _LogRecord) -> str:
    label = _SOURCE_LABEL.get(record.source, f"[{record.source.upper()}]")
    if record.data is not None:
        # Host JSON record: show timestamp + level + event.
        ts_str = str(record.data.get("timestamp", ""))
        level = str(record.data.get("level", "")).upper()
        event = str(record.data.get("event", record.raw))
        return f"{label} {ts_str} [{level}] {event}"
    return f"{label} {record.raw}"


def _format_json_line(record: _LogRecord) -> str:
    if record.data is not None:
        obj = dict(record.data)
    else:
        obj = {"raw": record.raw}
    obj["_source"] = record.source
    return json.dumps(obj, sort_keys=True)


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------


def add_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser(
        "logs",
        help="Aggregate and display CrossDesk log streams",
        description=(
            "Interleave log lines from host daemon, libvirt, and FreeRDP, "
            "sorted by timestamp. Guest log streaming is P2 (not yet implemented)."
        ),
    )
    p.add_argument(
        "--since",
        default="5m",
        metavar="DURATION",
        help="Show logs from the last DURATION (e.g. 5m, 1h, 30s). Default: 5m.",
    )
    p.add_argument(
        "--follow",
        action="store_true",
        help="Stream new log lines as they appear. Ctrl-C to stop.",
    )
    p.add_argument(
        "--component",
        choices=["host", "libvirt", "freerdp", "guest", "all"],
        default="all",
        help="Which source(s) to show. Default: all.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Output raw JSON per line (adds _source field).",
    )
    p.add_argument(
        "--lines",
        type=int,
        default=100,
        metavar="N",
        help="Most-recent lines per source (default 100). Ignored when --since is given.",
    )


# ---------------------------------------------------------------------------
# Batch (non-follow) mode
# ---------------------------------------------------------------------------


def _collect_batch(
    component: str,
    cutoff: Optional[datetime],
    lines: int,
) -> Tuple[List[_LogRecord], List[str]]:
    """Collect and interleave log records from all requested sources.

    Returns the sorted record list and a (possibly empty) list of warning
    messages.
    """
    warnings: List[str] = []
    all_records: List[_LogRecord] = []

    sources: Sequence[str]
    if component == "all":
        sources = ["host", "libvirt", "freerdp"]
    else:
        sources = [component]

    for src in sources:
        if src == "host":
            recs, warn = _read_host_logs(lines, cutoff)
        elif src == "libvirt":
            recs, warn = _read_libvirt_logs(lines, cutoff)
        elif src == "freerdp":
            recs, warn = _read_freerdp_logs(lines, cutoff)
        else:
            # Should not be reachable via the argparse choices constraint.
            continue
        if warn:
            warnings.append(warn)
        all_records.extend(recs)

    all_records.sort(key=lambda r: r.sort_key())
    return all_records, warnings


# ---------------------------------------------------------------------------
# --follow (async tailing)
# ---------------------------------------------------------------------------


async def _tail_file(path: Path, source: str) -> AsyncIterator[_LogRecord]:
    """Yield new lines appended to *path* as an async stream.

    Seeks to the end on first open, then waits for new content using
    ``asyncio.sleep``.  This avoids the inotify / kqueue dependency while
    keeping the loop non-blocking.

    The interval is short (0.25 s) because ``--follow`` is an interactive
    mode where a 1-frame delay is noticeable.
    """
    try:
        fh = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        fh.seek(0, 2)  # seek to end
        while True:
            line = fh.readline()
            if not line:
                await asyncio.sleep(0.25)
                continue
            stripped = line.strip()
            if not stripped:
                continue
            ts: Optional[datetime] = None
            data: Optional[Dict[str, object]] = None
            try:
                obj: Dict[str, object] = json.loads(stripped)
                data = obj
                if "timestamp" in obj:
                    ts = _parse_iso(str(obj["timestamp"]))
            except (json.JSONDecodeError, ValueError):
                if source == "libvirt":
                    ts = _parse_libvirt_ts(stripped)
            yield _LogRecord(source=source, ts=ts, raw=stripped, data=data)


async def _tail_journalctl(source: str) -> AsyncIterator[_LogRecord]:
    """Run ``journalctl --follow`` in a subprocess and yield parsed records."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "journalctl",
            "--user",
            "-u",
            "crossdesk-host.service",
            "--output",
            "json",
            "--follow",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return

    assert proc.stdout is not None
    while True:
        raw = await proc.stdout.readline()
        if not raw:
            break
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        ts: Optional[datetime] = None
        data: Optional[Dict[str, object]] = None
        try:
            obj: Dict[str, object] = json.loads(line)
            data = obj
            if "__REALTIME_TIMESTAMP" in obj:
                us = int(str(obj["__REALTIME_TIMESTAMP"]))
                ts = datetime.fromtimestamp(us / 1_000_000, tz=timezone.utc)
            elif "timestamp" in obj:
                ts = _parse_iso(str(obj["timestamp"]))
        except (json.JSONDecodeError, ValueError):
            pass
        yield _LogRecord(source=source, ts=ts, raw=line, data=data)


async def _follow_sources(
    component: str,
    emit_json: bool,
    cutoff: Optional[datetime],
) -> None:
    """Merge async iterators from all requested follow sources and print lines
    as they arrive.

    Each source runs as a separate asyncio task that feeds into a shared
    queue; a consumer drains the queue and prints.  Tasks are cancelled
    cleanly on ``KeyboardInterrupt``.
    """
    queue: asyncio.Queue[_LogRecord] = asyncio.Queue()

    async def _pump(ait: AsyncIterator[_LogRecord]) -> None:
        async for record in ait:
            await queue.put(record)

    tasks: List[asyncio.Task[None]] = []
    sources: Sequence[str]
    if component == "all":
        sources = ["host", "libvirt", "freerdp"]
    else:
        sources = [component]

    for src in sources:
        if src == "host":
            # Prefer journalctl; fall back to file tail.
            tasks.append(asyncio.create_task(_pump(_tail_journalctl(src))))
            fallback_path = _host_log_path()
            if fallback_path.exists():
                tasks.append(asyncio.create_task(_pump(_tail_file(fallback_path, src))))
        elif src == "libvirt":
            lv_path = _libvirt_log_path()
            if lv_path.exists():
                tasks.append(asyncio.create_task(_pump(_tail_file(lv_path, src))))
            else:
                print(
                    _("warning: libvirt log not found, skipping follow: {path}").format(
                        path=lv_path
                    ),
                    file=sys.stderr,
                )
        elif src == "freerdp":
            for fp in _freerdp_log_paths():
                tasks.append(asyncio.create_task(_pump(_tail_file(fp, src))))

    if not tasks:
        print(
            _("warning: no log sources available for --follow"),
            file=sys.stderr,
        )
        return

    while True:
        try:
            record = await asyncio.wait_for(queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        if cutoff is not None and record.ts is not None and record.ts < cutoff:
            continue
        if emit_json:
            print(_format_json_line(record))
        else:
            print(_format_human(record))
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    if args.component == "guest":
        print(
            _("warning: guest log streaming is not yet implemented (P2 scope)"),
            file=sys.stderr,
        )
        return 0

    # Determine cutoff — if --since was provided use it; --lines is ignored.
    # When --since defaults to "5m" we always apply it.
    try:
        duration = _parse_duration(args.since)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    cutoff: Optional[datetime] = datetime.now(tz=timezone.utc) - duration

    if args.follow:
        try:
            asyncio.run(_follow_sources(args.component, args.emit_json, cutoff))
        except KeyboardInterrupt:
            pass
        return 0

    # Batch mode: when --since is explicitly set we use the cutoff and
    # ignore --lines; otherwise we apply --lines per source.
    records, warnings = _collect_batch(args.component, cutoff, args.lines)

    for warn in warnings:
        print(warn, file=sys.stderr)

    if not records and warnings:
        # All sources were unavailable — still exit 0, it's an env limitation.
        return 0

    for record in records:
        if args.emit_json:
            print(_format_json_line(record))
        else:
            print(_format_human(record))

    return 0


__all__ = ["add_subparser", "run"]
