"""``crossdesk doctor`` CLI wrapper around :mod:`doctor.checks`."""

from __future__ import annotations

import argparse

from crossdesk_host.doctor import has_failures, run_all
from crossdesk_host.doctor.checks import Status


def add_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    sub.add_parser("doctor", help="Run pre-flight environment checks")


_GLYPH = {Status.OK: "✓", Status.WARN: "!", Status.FAIL: "✗"}


def run(_args: argparse.Namespace) -> int:
    results = run_all()
    for r in results:
        glyph = _GLYPH[r.status]
        line = f"  {glyph} {r.name:<16} [{r.status.value}]"
        if r.message:
            line += f" — {r.message}"
        print(line)
    return 1 if has_failures(results) else 0
