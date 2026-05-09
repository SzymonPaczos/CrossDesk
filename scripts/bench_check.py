#!/usr/bin/env python3
"""Compare pytest-benchmark JSON output against committed baselines.

Run via:

    pytest host/benches --benchmark-json=bench-out.json
    python scripts/bench_check.py bench-out.json

Exits 0 if every measured benchmark stays within ``_threshold_pct``
of its baseline, exits 1 (with a summary on stderr) otherwise. The
microbench CI job invokes this and posts the summary as a PR comment.

Baselines live in ``.github/perf-baselines.json`` (single source of
truth; updates land via dedicated PRs so a perf change is reviewed
on its own).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    return data


def _measured_means(report: Dict[str, Any]) -> Dict[str, float]:
    """Extract test_name → mean nanoseconds from a pytest-benchmark JSON
    report. The report's ``benchmarks`` list carries one entry per test
    with ``stats.mean`` in seconds."""
    out: Dict[str, float] = {}
    for entry in report.get("benchmarks", []):
        name = entry.get("name") or entry.get("fullname")
        stats = entry.get("stats", {})
        mean_seconds = stats.get("mean")
        if name is None or mean_seconds is None:
            continue
        out[name] = float(mean_seconds) * 1_000_000_000
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="microbench gate")
    parser.add_argument(
        "report",
        type=Path,
        help="pytest-benchmark JSON output to check",
    )
    parser.add_argument(
        "--baselines",
        type=Path,
        default=Path(".github/perf-baselines.json"),
        help="path to baseline JSON (default: .github/perf-baselines.json)",
    )
    args = parser.parse_args(argv)

    if not args.report.exists():
        print(f"bench report missing: {args.report}", file=sys.stderr)
        return 2
    if not args.baselines.exists():
        print(f"baselines missing: {args.baselines}", file=sys.stderr)
        return 2

    report = _load_json(args.report)
    baselines = _load_json(args.baselines)

    threshold_pct = float(baselines.get("_threshold_pct", 20))
    expected_tests: Dict[str, Dict[str, Any]] = baselines.get("tests", {})

    measured = _measured_means(report)
    failures: List[str] = []

    for name, baseline_entry in expected_tests.items():
        baseline_ns = float(baseline_entry.get("ns_mean", 0))
        if name not in measured:
            failures.append(f"{name}: missing from report")
            continue
        actual_ns = measured[name]
        # 0 baseline means "no gate yet, accept any value" — used while
        # we collect first-run measurements.
        if baseline_ns <= 0:
            continue
        delta_pct = (actual_ns - baseline_ns) / baseline_ns * 100.0
        if delta_pct > threshold_pct:
            failures.append(
                f"{name}: {actual_ns:.0f}ns vs baseline {baseline_ns:.0f}ns "
                f"(+{delta_pct:.1f}% > {threshold_pct:.1f}%)"
            )

    if failures:
        print("perf regression detected:", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(f"OK — {len(measured)} benches within +{threshold_pct:.0f}% of baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
