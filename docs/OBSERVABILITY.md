# Observability

How CrossDesk emits logs, traces, and metrics so that bugs are
diagnosable, performance regressions are visible, and a user filing
"it didn't work" can hand over data we can act on.

Three layers, each with a clear contract:

1. **Structured logs** — every component emits JSON-shaped events.
   Filesystem-local (no telemetry leaves the machine — see
   `docs/DECISIONS.md` DEC-0002).
2. **Distributed traces** — a single trace ID propagates from CLI
   command through host process, across the gRPC channel, into the
   guest agent. One ID per user-initiated action.
3. **Metrics** — in-memory counters and histograms exposed via a
   gRPC RPC and via `crossdesk metrics` CLI. No external time-series
   database required by default.

## Structured logs

### Format
JSON Lines. One event per line. Mandatory fields:

```json
{
  "timestamp": "2026-05-07T22:14:33.412Z",
  "level": "info",
  "component": "host.installer",
  "trace_id": "0af7651916cd43dd8448eb211c80319c",
  "span_id": "b9c7c989f97918e1",
  "event": "iso_download_started",
  "url_host": "software-download.microsoft.com",
  "expected_size_bytes": 5242880000
}
```

- **`component`** — fully-qualified module path. Helps grep.
- **`trace_id` / `span_id`** — W3C Trace Context identifiers.
- **`event`** — short snake_case identifier; treated as a
  semi-structured key, not free text. Tooling can group by `event`.
- **No PII** — passwords, paths under `$HOME` (other than the active
  mount), AuthContext fingerprints, etc. are excluded by an
  allow-list.

### Implementation
- Python: `structlog` configured to emit JSON with the schema above.
  Wraps stdlib `logging`. Ours is a thin facade in
  `host/src/crossdesk_host/observability/log.py`.
- Rust: `tracing` crate with `tracing-subscriber` and a JSON
  formatter. Both `tracing_subscriber::fmt::layer().json()` and
  `tracing_opentelemetry` for trace export.

### Storage
Logs land in `~/.local/state/crossdesk/logs/` rotated daily, kept
14 days by default. systemd journal duplication if the user runs
the host as a systemd user service.

`crossdesk logs` (planned in `FOLLOWUPS.md` Operations) aggregates
across host, guest (pulled via the agent's gRPC `LogTail` RPC),
libvirt domain logs, and FreeRDP per-session logs. JSON output by
default; `--pretty` for human-readable.

### Redaction allow-list
The set of allowed fields is enumerated in
`host/src/crossdesk_host/observability/redaction.py` as a frozen
list. Logging code that tries to log a non-allowed field raises a
type error at runtime (in tests and dev) and silently drops in
production.

Examples of fields **never** logged:
- `password`, `secret`, `token` (any field with these substrings)
- `auth_context.fingerprint` (low-entropy if logged with neighboring
  data)
- `vm.disk_path` (filesystem location of the VM disk)
- `clipboard_content` (when clipboard rich mode is on)

## Distributed traces

### Why
With many concurrent operations (heartbeat in flight, install in
progress, a user-launched RAIL session, a credential rotation),
scrolling through unstructured logs to figure out which is which
takes forever. A trace ID lets us answer "what happened to *this*
specific install" by filtering one ID.

### Propagation
W3C Trace Context (`traceparent` HTTP header equivalent), threaded
through:

1. CLI command: every user-initiated CLI invocation generates a
   fresh trace ID at start.
2. Host RPC servicers: receive the trace ID via gRPC metadata if
   present, or generate one if absent (incoming external request).
3. Guest agent RPC handlers: receive trace ID from gRPC metadata,
   pass it to all internal logging.
4. RAIL events: Windows guest tags `RailWindowEvent` messages with
   the trace ID of the launch that produced them.
5. FreeRDP subprocess: trace ID passed via env var
   `CROSSDESK_TRACE_ID`; FreeRDP doesn't read it natively but our
   wrapper logs include it.

### Span structure
- `crossdesk.cli.<command>` is the root span.
- Sub-spans: `host.libvirt.<operation>`, `host.gRPC.<rpc>`,
  `guest.<service>.<rpc>`, `host.freerdp.spawn`.
- Spans carry timing automatically (`tracing` and OpenTelemetry
  Python both do this).

### Storage
Default: traces logged to the same JSONL file as structured logs,
filterable by trace ID. No external trace backend required.

Optional: `OTLP` exporter writes to a user-configured endpoint
(Jaeger, Tempo, Honeycomb) when `crossdesk config set
observability.otlp_endpoint=https://...`. Default is unset (zero
telemetry per DEC-0002).

## Metrics

### Type
- **Counters:** `launches_total`, `heartbeat_misses_total`,
  `mount_attaches_total`, `mount_detaches_total`,
  `auth_context_rejections_total`.
- **Histograms:** `heartbeat_rtt_seconds`, `launch_duration_seconds`,
  `mount_lifetime_seconds`, `agent_rpc_duration_seconds`.
- **Gauges:** `vm_state` (one of: `down`, `starting`, `running`,
  `paused`, `recovering`, `failed`), `current_mounts`,
  `host_rss_bytes`.

### Storage
In-memory ring buffers. Histograms use `hdrhistogram` (Python) or
`hdrhistogram-rs` (Rust). Counters and gauges are atomic.

Exposed via:
- `ControlService.GetMetrics` RPC: returns a snapshot.
- `crossdesk metrics`: CLI wrapper that calls the RPC and prints
  human-readable summary or JSON.

No HTTP endpoint exposed. Users who want Prometheus scraping run a
separate script that calls our RPC and translates to Prometheus
format. Out of scope for the core; community/contributed.

### Performance budgets feed into metrics
Each metric in `docs/REQUIREMENTS.md` N1 has a corresponding
histogram in this layer. The microbench harness (Perf budgets work)
reads from these histograms to enforce regression checks.

## Components and what they emit

### Host process
- `host.installer.*` — install pipeline events.
- `host.watchdog.*` — heartbeat FSM transitions.
- `host.ipc.*` — incoming RPC events (one per call).
- `host.libvirt.*` — libvirt API calls.
- `host.display.*` — RAIL session lifecycle.
- `host.filesystem.*` — JIT mount events.
- `host.credentials.*` — rotation/repair events (no values
  logged, just the action).

### Guest agent
- `guest.svc.*` — NT service lifecycle (start, stop, exception).
- `guest.ipc.*` — RPC handler calls.
- `guest.discovery.*` — app enumeration events.
- `guest.fs.*` — mount handling on guest side.
- `guest.rail.*` — RAIL window event emit (CREATED, DESTROYED, etc.).

### CLI
- `cli.<command>.start` and `cli.<command>.complete` (with status).

## What we do not log

- Password / secret / token contents.
- Cleartext clipboard content (we log mode and length, not
  contents).
- File paths outside the active JIT mount (we log mount tokens
  instead, which are random and short-lived).
- AuthContext fingerprint values (we log a hash of the fingerprint
  if needed for correlation).
- IP addresses on the user's LAN (we use VSOCK; addresses are
  irrelevant).

## What we are not doing

### No automatic upload
Per `docs/DECISIONS.md` DEC-0002: zero telemetry. `crossdesk logs`
aggregates locally; the user explicitly pastes logs into a bug
report if they want to share. No "send anonymous diagnostics on
crash" toggle.

### No external observability backend by default
The OTLP exporter is opt-in. By default everything stays on local
disk.

### No PII collection
We don't ask for user identification. We don't tag events with
machine UUID or any persistent identifier beyond the `vm_id`
(which is a randomly generated UUID local to this install).

## Sequencing of work

### P0 (foundation, lands early)
- `structlog`/`tracing` configured with JSON output.
- Trace ID propagation wiring through gRPC metadata.
- Allow-list redaction enforcement.
- Metrics in-memory counters/histograms.

### P1 (after foundation)
- `crossdesk logs` aggregator (already in Operations &
  lifecycle FOLLOWUPS).
- `crossdesk metrics` CLI command.
- Per-component span structure, complete coverage.
- OTLP exporter (opt-in).

### P2 (later)
- Microbenchmark harness reading from histograms (also in
  Performance budgets work).
- Optional Prometheus translator (community contribution).
