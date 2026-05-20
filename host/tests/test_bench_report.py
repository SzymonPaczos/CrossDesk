"""bench_report.py unit tests.

Drives the Markdown renderer with synthetic pytest-benchmark JSON
fragments + handcrafted baselines so each report state — no regressions,
one regression, one improvement, missing baseline, missing result,
malformed input — is exercised without running real benchmarks.

Patterns mirror test_bench_check.py (importlib.util to load a script
that lives at repo root, not under the host package).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BENCH_REPORT_PATH = _REPO_ROOT / "scripts" / "bench_report.py"

_spec = importlib.util.spec_from_file_location("bench_report", _BENCH_REPORT_PATH)
assert _spec is not None and _spec.loader is not None
bench_report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench_report)


def _write(tmp_path: Path, name: str, payload: Dict[str, Any]) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _baselines(threshold_pct: int = 20, **tests: int) -> Dict[str, Any]:
    return {
        "_threshold_pct": threshold_pct,
        "tests": {name: {"ns_mean": ns} for name, ns in tests.items()},
    }


def _report(**tests: float) -> Dict[str, Any]:
    return {
        "benchmarks": [
            {"name": name, "stats": {"mean": seconds}}
            for name, seconds in tests.items()
        ]
    }


def test_no_regressions_no_improvements_renders_ok_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rep = _write(tmp_path, "rep.json", _report(test_a=4.5e-6))  # 4.5us vs 5us baseline
    base = _write(tmp_path, "base.json", _baselines(20, test_a=5000))
    rc = bench_report.main(["--results", str(rep), "--baseline", str(base)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "## Microbench report" in out
    assert "All benchmarks within" in out
    assert "test_a" in out
    assert "OK" in out
    assert "Regression" not in out
    assert "Improvement" not in out


def test_one_regression_highlighted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rep = _write(tmp_path, "rep.json", _report(test_a=10e-6))  # +100% vs 5us
    base = _write(tmp_path, "base.json", _baselines(20, test_a=5000))
    rc = bench_report.main(["--results", str(rep), "--baseline", str(base)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "**Regression**" in out
    assert "1 regression(s)" in out
    assert "+100.0%" in out


def test_one_improvement_highlighted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rep = _write(
        tmp_path, "rep.json", _report(test_a=1e-6)
    )  # 1us vs 5us baseline → -80%
    base = _write(tmp_path, "base.json", _baselines(20, test_a=5000))
    rc = bench_report.main(["--results", str(rep), "--baseline", str(base)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "**Improvement**" in out
    assert "1 improvement(s)" in out
    assert "-80.0%" in out


def test_missing_baseline_is_informational(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Benchmark appears in results with no matching baseline → 'No baseline'
    row, but the overall report still exits 0 and does not call it a
    regression."""
    rep = _write(tmp_path, "rep.json", _report(brand_new_bench=2e-6))
    base = _write(tmp_path, "base.json", _baselines(20))  # no tests entries
    rc = bench_report.main(["--results", str(rep), "--baseline", str(base)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "brand_new_bench" in out
    assert "No baseline" in out
    assert "Regression" not in out


def test_missing_result_marked_skip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Baseline expects a benchmark that didn't run → 'Skip' row,
    exit 0 (the report is purely descriptive; gating is bench_check's job)."""
    rep = _write(tmp_path, "rep.json", _report(other=1e-6))
    base = _write(tmp_path, "base.json", _baselines(20, test_a=5000))
    rc = bench_report.main(["--results", str(rep), "--baseline", str(base)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "test_a" in out
    assert "Skip" in out
    assert "missing from results" in out


def test_zero_baseline_is_collect_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A 0-ns baseline (bootstrap rows in perf-baselines.json) renders
    without a delta and is not flagged as regression even at any
    measured value."""
    rep = _write(tmp_path, "rep.json", _report(test_a=999e-6))
    base = _write(tmp_path, "base.json", _baselines(20, test_a=0))
    rc = bench_report.main(["--results", str(rep), "--baseline", str(base)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Collect-only" in out
    assert "(collect-only)" in out
    assert "Regression" not in out


def test_malformed_results_returns_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rep = tmp_path / "rep.json"
    rep.write_text("not json {{{", encoding="utf-8")
    base = _write(tmp_path, "base.json", _baselines(20, test_a=5000))
    rc = bench_report.main(["--results", str(rep), "--baseline", str(base)])
    assert rc == 2
    assert "malformed" in capsys.readouterr().err


def test_malformed_baselines_returns_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Baselines with a non-object 'tests' field → reported as malformed."""
    rep = _write(tmp_path, "rep.json", _report(test_a=1e-6))
    base = tmp_path / "base.json"
    base.write_text(json.dumps({"_threshold_pct": 20, "tests": []}), encoding="utf-8")
    rc = bench_report.main(["--results", str(rep), "--baseline", str(base)])
    assert rc == 2
    assert "malformed" in capsys.readouterr().err


def test_missing_files_returns_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    nonexistent_rep = tmp_path / "nope.json"
    base = _write(tmp_path, "base.json", _baselines(20))
    rc = bench_report.main(["--results", str(nonexistent_rep), "--baseline", str(base)])
    assert rc == 2
    assert "missing" in capsys.readouterr().err


def test_output_flag_writes_file(tmp_path: Path) -> None:
    rep = _write(tmp_path, "rep.json", _report(test_a=4.5e-6))
    base = _write(tmp_path, "base.json", _baselines(20, test_a=5000))
    out_path = tmp_path / "bench-report.md"
    rc = bench_report.main(
        [
            "--results",
            str(rep),
            "--baseline",
            str(base),
            "--output",
            str(out_path),
        ]
    )
    assert rc == 0
    assert out_path.exists()
    body = out_path.read_text(encoding="utf-8")
    assert "## Microbench report" in body
    assert "test_a" in body


def test_threshold_pct_drives_classification(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A 10% delta is OK under a 20% threshold and Regression under 5%."""
    rep = _write(tmp_path, "rep.json", _report(test_a=5.5e-6))  # +10%

    base_loose = _write(tmp_path, "base-loose.json", _baselines(20, test_a=5000))
    rc = bench_report.main(["--results", str(rep), "--baseline", str(base_loose)])
    assert rc == 0
    assert "Regression" not in capsys.readouterr().out

    base_strict = _write(tmp_path, "base-strict.json", _baselines(5, test_a=5000))
    rc = bench_report.main(["--results", str(rep), "--baseline", str(base_strict)])
    assert rc == 0
    assert "**Regression**" in capsys.readouterr().out
