# Performance budgets — implementation strategy

The budgets themselves live in `docs/REQUIREMENTS.md` §N1. The
architectural commitment that they are normative (not aspirational)
lives in `docs/DECISIONS.md` DEC-0004. This document covers how we
*enforce* the budgets: benchmark harness, CI integration, regression
detection.

## Why this matters

Without enforcement, "performance budgets" drift release by release
until users feel the regression and we can't say when it happened.
With enforcement, every PR demonstrates it doesn't make the relevant
metric worse (or makes it better). Bisecting a regression takes
minutes instead of hours.

WinApps publishes no SLOs and runs no benchmark harness. Cassowary
the same. Most desktop projects rely on "it feels OK to me" as the
quality gate. We aim higher because our positioning depends on it.

## Architecture

Three layers:

1. **Microbenchmarks** — measure individual hot paths (heartbeat
   round-trip, AuthContext validation, mount handshake). Run on
   every PR. Fast (seconds).
2. **Integration benchmarks** — measure user-visible flows
   (`crossdesk install` end-to-end, `crossdesk launch <app>` cold).
   Run on PRs touching the relevant subsystems. Slower (minutes).
3. **Real-hardware smoke** — measure the same things on a real
   Linux+KVM host. Gated behind a self-hosted runner (when one
   exists) and a PR label.

All three feed into the same metric histograms (see
`docs/OBSERVABILITY.md`) so the format is consistent.

## Microbenchmark harness

Lives in `host/benches/` for Python and `guest/benches/` for Rust.
Tools:

- **Python:** `pytest-benchmark` for Python microbenches; reads/
  writes JSON-formatted result files.
- **Rust:** `criterion` for Rust microbenches; produces machine-
  readable output.

Each benchmark targets a specific metric from REQUIREMENTS.md N1.
Naming convention: `bench_N1_2_heartbeat_rtt`.

### Examples

**Python (`host/benches/test_heartbeat.py`):**

```python
@pytest.mark.benchmark(group="N1.2_heartbeat_rtt")
def test_heartbeat_rtt(benchmark, mock_transport):
    """Round-trip a HeartbeatService.Channel ping over MockTransport."""
    client = make_heartbeat_client(mock_transport)
    benchmark(lambda: asyncio.run(client.ping()))
```

**Rust (`guest/crates/agent-svc/benches/heartbeat.rs`):**

```rust
fn bench_heartbeat_handler(c: &mut Criterion) {
    c.bench_function("N1.2_heartbeat_rtt", |b| {
        let svc = test_heartbeat_service();
        b.iter(|| svc.handle_ping(black_box(test_request())));
    });
}
```

## Integration benchmarks

Run the in-process integration test harness (host+guest in one
process via mocks) against scripted flows. Measure end-to-end
latency.

Located in `host/tests/benchmarks/`. Examples:

- `bench_install_pipeline.py` — runs `Installer.run()` against
  mocked libvirt, ISO downloader, FreeRDP. Asserts wall-clock
  steps within budget.
- `bench_cold_launch_lightweight.py` — Notepad cold launch
  timeline. Asserts ≤3 s p50 (N1.1a).
- `bench_recovery_destroy_start.py` — kill VM, observe time to
  next successful launch. Asserts ≤90 s (N1.6a).

These are slow (10s of seconds each) so they run only on PRs
labelled `perf` or on main-branch nightly runs.

## CI integration

### Per-PR microbenches
GitHub Actions job `microbench` runs on every PR:

```yaml
microbench:
  runs-on: ubuntu-latest
  steps:
    - python -m pytest host/benches/ --benchmark-only
        --benchmark-json=bench_results.json
    - cd guest && cargo bench --workspace --features mock
        -- --output-format=json > bench_results_rust.json
    - python tools/bench_check.py
        --baseline .github/perf-baselines.json
        --results bench_results.json,bench_results_rust.json
        --threshold 0.20
```

The `bench_check.py` tool:
1. Loads the `.github/perf-baselines.json` file (committed; updated
   only by explicit PR).
2. Compares each result to its baseline.
3. Fails the job if any metric exceeds budget by >20%.
4. Posts a PR comment summarizing changes (improvements + regressions
   above noise threshold).

### Baseline updates
Baselines update only via dedicated PRs (`perf: update baselines`)
that show the measurements taken. This makes baseline drift
auditable.

### Per-PR integration benches (label-gated)
Slower benchmarks (cold launch, install pipeline) run only when a
PR is labelled `perf-full`. Default off because they're slow.

### Real-hardware smoke
Runs on the self-hosted KVM runner (when one exists) on a label
`hardware-smoke`. Captures real-world numbers separately from the
mock-based numbers.

## Reporting

`crossdesk metrics --histograms` (already in Observability work)
reads the in-memory histograms from a running host and prints
percentile breakdowns. Useful for ad-hoc measurement on a developer
machine.

`tools/bench_report.py` aggregates results across multiple runs
and produces a markdown table for release notes.

## What we do not benchmark

- **End-to-end with real Microsoft Windows ISO + real Photoshop
  install + real Adobe activation.** These take 30+ minutes and
  depend on Microsoft / Adobe servers. Out of automated CI; manual
  QA per release.
- **GPU-accelerated app workloads.** These require real hardware
  and are gated on the GPU passthrough decision pending in
  `docs/GPU_PASSTHROUGH.md`.
- **Network-bound paths.** We don't have any user-visible network
  paths (no telemetry, no auto-update). The only outbound network
  is ISO download, and we benchmark only the local handling, not
  the actual MS CDN.

## Regression triage

When a PR fails the perf check:

1. The PR comment shows which metric regressed and by how much.
2. Author must either:
   - Fix the regression (bring metric back within budget).
   - File a deliberate baseline update PR with measurements
     justifying why the new number is correct (e.g., "added new
     security check, +5 ms is unavoidable").
3. Reviewer uses the baseline update as a checkpoint to verify
   the rationale is honest.

## Sequencing

### P0 (foundation)
- `pytest-benchmark` and `criterion` configured.
- One bench per N1.* metric — even if it's a stub initially.
- `bench_check.py` tool with baseline file format.
- CI job `microbench` running on every PR.
- Initial baselines committed (best-effort first measurements).

### P1 (after foundation)
- Integration benchmarks (cold launch, install pipeline,
  recovery).
- `tools/bench_report.py` for release notes aggregation.
- PR comment automation (results summarized in comment).

### P2 (later)
- Self-hosted KVM runner with `hardware-smoke` workflow.
- Trend analysis (weekly summary of metrics over time).

## Cost

The harness adds ~30-60 seconds to PR CI for microbenches. The
discipline of "every PR must show it didn't regress" adds ~10
minutes of author time when a real regression appears (rare).

The payoff: regressions are caught at PR time, not at release time.
Bisecting takes minutes when you have the data; days when you don't.
