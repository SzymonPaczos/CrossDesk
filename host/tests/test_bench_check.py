"""bench_check.py unit tests.

Drives the comparator with synthetic pytest-benchmark JSON fragments
so the gate logic can be verified without actually running benchmarks.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BENCH_CHECK_PATH = _REPO_ROOT / "scripts" / "bench_check.py"

_spec = importlib.util.spec_from_file_location("bench_check", _BENCH_CHECK_PATH)
assert _spec is not None and _spec.loader is not None
bench_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench_check)


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


def test_passes_when_within_threshold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rep = _write(tmp_path, "rep.json", _report(test_a=4.5e-6))  # 4.5us
    base = _write(tmp_path, "base.json", _baselines(20, test_a=5000))
    rc = bench_check.main([str(rep), "--baselines", str(base)])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_fails_when_over_threshold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rep = _write(tmp_path, "rep.json", _report(test_a=10e-6))  # 10us, +100%
    base = _write(tmp_path, "base.json", _baselines(20, test_a=5000))
    rc = bench_check.main([str(rep), "--baselines", str(base)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "test_a" in err
    assert "+100" in err


def test_zero_baseline_is_no_gate(tmp_path: Path) -> None:
    """A baseline of 0 means 'collect data, don't gate yet' — used in
    bootstrap weeks."""
    rep = _write(tmp_path, "rep.json", _report(test_a=999e-6))
    base = _write(tmp_path, "base.json", _baselines(20, test_a=0))
    rc = bench_check.main([str(rep), "--baselines", str(base)])
    assert rc == 0


def test_missing_test_in_report_is_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rep = _write(tmp_path, "rep.json", _report(other=1e-6))
    base = _write(tmp_path, "base.json", _baselines(20, test_a=5000))
    rc = bench_check.main([str(rep), "--baselines", str(base)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "missing from report" in err


def test_threshold_pct_drives_pass_or_fail(tmp_path: Path) -> None:
    rep = _write(tmp_path, "rep.json", _report(test_a=5.5e-6))  # +10%

    base_strict = _write(tmp_path, "base-strict.json", _baselines(5, test_a=5000))
    assert bench_check.main([str(rep), "--baselines", str(base_strict)]) == 1

    base_loose = _write(tmp_path, "base-loose.json", _baselines(20, test_a=5000))
    assert bench_check.main([str(rep), "--baselines", str(base_loose)]) == 0


def test_missing_files_returns_2(tmp_path: Path) -> None:
    nonexistent = tmp_path / "nope.json"
    base = _write(tmp_path, "base.json", _baselines(20))
    rc = bench_check.main([str(nonexistent), "--baselines", str(base)])
    assert rc == 2
