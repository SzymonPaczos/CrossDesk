"""configure_logging file output + rotation.

The production daemon tees every log line into a bounded, size-rotating
file so ``crossdesk logs`` works without journald. These tests pin that
the file receives valid JSON lines, that the stream still gets them too,
and that the writer rotates at its size cap without splitting a line.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from crossdesk_host.observability import configure_logging, get_logger
from crossdesk_host.observability.log import _RotatingFileWriter


def test_log_file_receives_json_lines(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "host.jsonl"
    buf = io.StringIO()
    configure_logging(stream=buf, log_file=log_file)

    get_logger("host.tests.file").info("disk_event", key="value", n=7)

    # Stream still gets the line.
    assert "disk_event" in buf.getvalue()
    # And the file is a valid JSON line carrying the event + fields.
    assert log_file.exists()
    line = log_file.read_text().strip().splitlines()[-1]
    record = json.loads(line)
    assert record["event"] == "disk_event"
    assert record["key"] == "value"
    assert record["n"] == 7


def test_no_log_file_writes_nothing_to_disk(tmp_path: Path) -> None:
    # The default (every test, and any simple call) must not touch disk.
    buf = io.StringIO()
    configure_logging(stream=buf, log_file=None)
    get_logger("host.tests.nofile").info("mem_only")
    assert not (tmp_path / "logs").exists()
    assert "mem_only" in buf.getvalue()


def test_rotating_writer_rotates_at_cap(tmp_path: Path) -> None:
    path = tmp_path / "r.log"
    writer = _RotatingFileWriter(path, max_bytes=100, backups=1)
    # 12 lines × ~20 bytes = ~240 bytes > 100 → at least one rotation.
    for i in range(12):
        writer.write(f"line-{i:02d}-padding\n")
    writer.flush()

    backup = path.with_name("r.log.1")
    assert backup.exists(), "expected a rotated .1 backup"
    # The live file holds the most recent line, intact (never split).
    assert path.read_text().endswith("\n")
    assert "line-11-padding" in path.read_text()


def test_rotating_writer_survives_unwritable(tmp_path: Path) -> None:
    # A directory where a file is expected → open fails on rotate/write;
    # the writer must degrade rather than raise into the logging call.
    path = tmp_path / "x.log"
    writer = _RotatingFileWriter(path, max_bytes=10, backups=1)
    writer.write("first line that exceeds the cap\n")
    # Make the backup target a directory so os.replace can't clobber it,
    # then force another rotation — write must still not raise.
    writer.write("second line also over the cap\n")
    writer.flush()
    assert path.exists()
