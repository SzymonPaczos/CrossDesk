#!/usr/bin/env python3
"""Render a Markdown perf report comparing pytest-benchmark output to baselines.

Companion to ``scripts/bench_check.py``: where ``bench_check`` exits non-zero
on regressions to gate CI, ``bench_report`` produces a human-readable table
that the microbench CI job posts as a PR comment. Both consume the same two
files (``host/bench-results.json`` from the bench run + ``.github/perf-baselines.json``)
and share the CLI shape so the workflow YAML stays uniform.

Output is Markdown, written to stdout (CI redirects to ``bench-report.md``
before ``gh pr comment --body-file``). Each row reports one benchmark with
current mean, baseline mean, and percent delta; rows are annotated:

  *  Regression  — current is more than threshold_pct above baseline.
     Improvement — current is more than threshold_pct below baseline.
  *  No baseline — benchmark appeared in results but not in baselines
     (informational, never gates).
  *  Skip        — benchmark is in baselines but absent from results
     (e.g., the bench file was renamed or the run crashed before it
     executed). Surfaced so reviewers notice missing coverage.

A baseline of 0 (collect-only) is rendered without a delta because there's
no meaningful comparison; the row appears so reviewers can see the
current value being collected toward a future baseline update.

Calling conventions (matches bench_check.py):

    python scripts/bench_report.py --results host/bench-results.json \
        --baseline .github/perf-baselines.json > bench-report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object at top level")
    return data


def _measured_means(report: Dict[str, Any]) -> Dict[str, float]:
    """Extract test_name → mean nanoseconds from pytest-benchmark JSON.

    Mirrors ``bench_check._measured_means`` so the two tools see the same
    set of benchmarks. ``stats.mean`` is in seconds; we convert to ns to
    match the baseline file's ``ns_mean`` units.
    """
    out: Dict[str, float] = {}
    benchmarks = report.get("benchmarks", [])
    if not isinstance(benchmarks, list):
        raise ValueError("malformed report: 'benchmarks' must be a list")
    for entry in benchmarks:
        name = entry.get("name") or entry.get("fullname")
        stats = entry.get("stats", {})
        mean_seconds = stats.get("mean")
        if name is None or mean_seconds is None:
            continue
        out[str(name)] = float(mean_seconds) * 1_000_000_000
    return out


def _format_ns(ns: float) -> str:
    """Human-readable ns/us/ms with one decimal for the report table."""
    if ns >= 1_000_000:
        return f"{ns / 1_000_000:.2f} ms"
    if ns >= 1_000:
        return f"{ns / 1_000:.2f} us"
    return f"{ns:.0f} ns"


def _row(name: str, current: str, baseline: str, delta: str, status: str) -> str:
    return f"| `{name}` | {current} | {baseline} | {delta} | {status} |"


def render_report(
    report: Dict[str, Any],
    baselines: Dict[str, Any],
) -> str:
    """Render the Markdown body. Pure function — no I/O — for testability."""
    threshold_pct = float(baselines.get("_threshold_pct", 20))
    expected_tests: Dict[str, Dict[str, Any]] = baselines.get("tests", {})
    if not isinstance(expected_tests, dict):
        raise ValueError("malformed baselines: 'tests' must be an object")

    measured = _measured_means(report)

    regressions: List[str] = []
    improvements: List[str] = []
    rows: List[str] = []

    # Walk baselines first so rows render in baseline order (stable across runs)
    # and missing-from-results entries surface explicitly.
    for name, baseline_entry in expected_tests.items():
        baseline_ns = float(baseline_entry.get("ns_mean", 0))
        baseline_str = _format_ns(baseline_ns) if baseline_ns > 0 else "(collect-only)"

        if name not in measured:
            rows.append(
                _row(name, "—", baseline_str, "—", "Skip (missing from results)")
            )
            continue

        current_ns = measured[name]
        current_str = _format_ns(current_ns)

        if baseline_ns <= 0:
            rows.append(_row(name, current_str, baseline_str, "—", "Collect-only"))
            continue

        delta_pct = (current_ns - baseline_ns) / baseline_ns * 100.0
        delta_str = f"{delta_pct:+.1f}%"

        if delta_pct > threshold_pct:
            status = "**Regression**"
            regressions.append(name)
        elif delta_pct < -threshold_pct:
            status = "**Improvement**"
            improvements.append(name)
        else:
            status = "OK"
        rows.append(_row(name, current_str, baseline_str, delta_str, status))

    # Results-only benchmarks (no baseline yet) sort alphabetically after the
    # baseline-driven rows so reviewers see "what's new" at the bottom of the
    # table without the order shuffling on every run.
    extras = sorted(set(measured) - set(expected_tests))
    for name in extras:
        current_ns = measured[name]
        rows.append(_row(name, _format_ns(current_ns), "—", "—", "No baseline"))

    lines: List[str] = []
    lines.append("## Microbench report")
    lines.append("")
    if regressions:
        lines.append(
            f"**{len(regressions)} regression(s) over {threshold_pct:.0f}% threshold:** "
            + ", ".join(f"`{n}`" for n in regressions)
        )
        lines.append("")
    if improvements:
        lines.append(
            f"**{len(improvements)} improvement(s) over {threshold_pct:.0f}% threshold:** "
            + ", ".join(f"`{n}`" for n in improvements)
        )
        lines.append("")
    if not regressions and not improvements:
        lines.append(f"All benchmarks within ±{threshold_pct:.0f}% of baseline.")
        lines.append("")

    if not rows:
        lines.append("_No benchmarks reported._")
        lines.append("")
    else:
        lines.append("| Benchmark | Current | Baseline | Delta | Status |")
        lines.append("|-----------|---------|----------|-------|--------|")
        lines.extend(rows)
        lines.append("")

    lines.append(
        f"_Threshold: ±{threshold_pct:.0f}%. Baseline source: "
        "`.github/perf-baselines.json`._"
    )
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="render Markdown microbench report for PR comments",
    )
    parser.add_argument(
        "--results",
        type=Path,
        required=True,
        help="pytest-benchmark JSON output (e.g., host/bench-results.json)",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(".github/perf-baselines.json"),
        help="path to baseline JSON (default: .github/perf-baselines.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="write report to this file instead of stdout",
    )
    args = parser.parse_args(argv)

    if not args.results.exists():
        print(f"bench results missing: {args.results}", file=sys.stderr)
        return 2
    if not args.baseline.exists():
        print(f"baselines missing: {args.baseline}", file=sys.stderr)
        return 2

    try:
        report = _load_json(args.results)
        baselines = _load_json(args.baseline)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"malformed input: {exc}", file=sys.stderr)
        return 2

    try:
        body = render_report(report, baselines)
    except ValueError as exc:
        print(f"malformed input: {exc}", file=sys.stderr)
        return 2

    if args.output is not None:
        args.output.write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
