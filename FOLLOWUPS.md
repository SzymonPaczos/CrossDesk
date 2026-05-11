# Follow-ups

Action-item tracking. Two kinds of items live here:

1. **Work in flight** — items deliberately deferred during recent
   audit waves (commits `8eb9ace` → `3098ea7`); each points at the
   file or phase it's blocked on.
2. **Action items by area** — work derived from
   `docs/COMPARISON_WINAPPS.md` and from gap analysis. Organized by
   phase (matching `ROADMAP.md`) and by post-MVP area.

Priority key: **P0** = required for full feature parity / blocking
follow-on work · **P1** = high-value follow-up · **P2** = nice-to-have
where we can beat the competition.

Items reference requirements (`docs/REQUIREMENTS.md` `F*` / `N*`),
ADRs (`docs/DECISIONS.md` `DEC-NNNN`), and source citations into
`third_party/winapps/` where applicable.

## Table of contents

- [Work in flight](#work-in-flight)
  - [Build & verification](#build--verification)
  - [Phase work still owed](#phase-work-still-owed)
  - [Tech debt](#tech-debt)
- [Action items by area](#action-items-by-area)
  - Cross-cutting / foundation (lands across all phases):
    - [Cross-platform development & testing scaffold (URGENT)](#cross-platform-development--testing-scaffold-urgent)
    - [Observability — structured logs, traces, metrics](#observability--structured-logs-traces-metrics)
    - [Performance budgets — enforcement](#performance-budgets--enforcement)
    - [Versioning & compatibility](#versioning--compatibility)
    - [Distribution & packaging](#distribution--packaging)
    - [Internationalization](#internationalization)
  - Feature areas:
    - [Display & forwarding](#display--forwarding)
    - [Peripherals & host integration](#peripherals--host-integration)
    - [Lifecycle: power, suspend/resume, autostart](#lifecycle-power-suspendresume-autostart)
  - GPU work (post-MVP):
    - [GPU passthrough — Phase 4.5 (post-MVP P0)](#gpu-passthrough--phase-45-post-mvp-p0)
    - [Looking Glass integration — post-Phase 4.5 (P0)](#looking-glass-integration--post-phase-45-p0)
    - [Software rendering fallback — post-Phase 4.5 (P1)](#software-rendering-fallback--post-phase-45-p1)
  - Phase-aligned follow-ups:
    - [Phase 1 follow-ups (VM bootstrap)](#phase-1-follow-ups-vm-bootstrap-is-done-but-this-still-needs-to-land-before-phase-4)
    - [Phase 3 follow-ups (Control FSM / Heartbeat)](#phase-3-follow-ups-control-fsm--heartbeat)
    - [Phase 4 follow-ups (RAIL Display Integration)](#phase-4-follow-ups-rail-display-integration)
    - [Post-MVP (cross-phase, winapps parity)](#post-mvp-winapps-parity-features-beyond-phase-5)
    - [Operations & lifecycle (post-MVP)](#operations--lifecycle-post-mvp)
- [Skipped on purpose](#skipped-on-purpose-do-not-implement)

---

# Work in flight

## Build & verification

- **[✅ DONE 2026-05-08] Windows cross-compile verified.** Now exercised
  by both the `rust-guest-cross-compile` CI job (cargo check + clippy
  with `-D warnings`) and a documented local MinGW path on macOS
  (see `docs/CROSS_PLATFORM_DEV.md` "Verified working command
  sequence"). The Windows-only modules (`agent-svc/service.rs`,
  `agent-svc/host_uuid.rs`, `rail-bridge/windows.rs`) compile clean;
  three pre-existing API drift bugs in those modules were fixed at
  the same time.
- **[✅ DONE 2026-05-10] End-to-end mTLS smoke test against the new
  32-byte `mount_token`.** Audit found `test_filesystem_mount_result_recorded`
  was constructing `MountResult` with no `mount_token` field — the bytes
  default of `b""` (length 0) made the host silently drop the frame while
  the test passed (it only checked the bidi handshake). Fixed in
  `chore/smoke-e2e-mount-token-audit`: module-level `_MOUNT_TOKEN` (32
  bytes) shared by both filesystem smoke tests, plus a `caplog`
  assertion on `crossdesk_host.ipc.filesystem` that the accept-path
  log line fires AND no rejection line is emitted. Mutation-tested
  (shrink to 31 bytes ⇒ test fails red with the rejection message).

## Phase work still owed

- **AF_HYPERV vsock connector** —
  `guest/crates/ipc-vsock/src/transport/real.rs::RealTransport`
  still dials TCP loopback. Replace `TcpStream::connect` with a real
  `WSAConnect` against `AF_HYPERV` once we leave dev. The
  `tower::Service<Uri>` shape is already stable across the swap so
  callers don't change.
- **Real virtiofs mount/flush** —
  `guest/crates/fs-mount/src/mount.rs::mock_handle_mount_request` and
  `guest/crates/fs-mount/src/flush.rs::mock_generate_lock_report` /
  `mock_generate_release_ack` are placeholder stubs with the `mock_`
  prefix exactly so call sites flag them at review. Phase 5 replaces
  them with WinFSP/virtiofs-backed implementations.
- **RAIL window icon extraction** —
  `guest/crates/rail-bridge/src/events.rs` leaves `icon_png` empty.
  Phase 4: `ExtractIconExW` + PNG-encode for `KIND_CREATED` and
  `KIND_ICON_CHANGED`.

## Tech debt

- The `// type: ignore[override]` ergonomics on bidirectional gRPC
  servicers were avoided by switching to `AsyncIterator`. If a future
  grpc-stubs bump narrows the parent signature again, the override may
  resurface; keep an eye on `crossdesk_host.proto.*_pb2_grpc.pyi` after
  every regeneration.

---

# Action items by area

Each item cites its source (winapps file:line or our gap analysis) and
points at the CrossDesk file or module where the work lands.

## Cross-platform development & testing scaffold (URGENT)

Foundation work to make `~1 month on macOS without Linux+KVM
hardware` productive instead of placebo. See
`docs/CROSS_PLATFORM_DEV.md` for the strategy and `docs/DECISIONS.md`
DEC-0005 for the architectural commitment.

- **[✅ DONE 2026-05-08] Cross-compile pipeline working from macOS
  (native MinGW).** Verified on Apple Silicon — native `cargo build
  --target x86_64-pc-windows-gnu` produces a working `agent.exe`
  PE32+ binary. See [Verified working command sequence][vws] in
  `docs/CROSS_PLATFORM_DEV.md`. Renamed `[[bin]] name` in
  `guest/crates/agent-svc/Cargo.toml` from `CrossDeskAgent` to
  `agent` so the file matches docs (service name remains
  `CrossDeskAgent`). Vendored `protoc` via `protoc-bin-vendored`
  in `guest/crates/proto/build.rs` so dev hosts and CI runners
  build the `proto` crate without a system `protoc`. Fixed three
  pre-existing Windows-only bugs in `rail-bridge`, `agent-svc`
  (windows-0.58 API drift surfaced by first real cross-compile).
- **[P1] Cross-rs end-to-end build for this repo.** Cross-rs runs
  but fails on this layout: it only mounts the cargo workspace
  (`guest/`), so `proto/build.rs`'s relative paths to
  `CrossDesk/proto/crossdesk/v1/*.proto` (one directory above the
  workspace) escape the container mount. Needs either a
  `Cross.toml` volume mount, a top-level workspace `Cargo.toml` at
  the repo root, or a vendored proto-files copy step. Required
  before Week 22 release pipeline (CI release matrix builds
  `agent.exe` via cross-rs).

[vws]: docs/CROSS_PLATFORM_DEV.md#verified-working-command-sequence-2026-05-08
- **[✅ DONE 2026-05-08] Transport abstraction (trait + real + mock).**
  `tower::Service<Uri>` is the Rust abstraction; `RealTransport`
  (TCP loopback today, AF_HYPERV later) and `MockTransport` (with
  `MockHooks` failure injection, gated `#[cfg(any(test, feature
  ="mock"))]`) both implement it. Python mirror: `Transport`
  Protocol in `abstractions/transport.py` plus
  `transport/{real,mock}.py`. `daemon.py` migrated; `ipc/server.py`
  retained as a thin shim for backwards compat. Unit tests cover
  the failure-injection hooks on both languages.
- **[✅ DONE 2026-05-08] Libvirt client abstraction.** `LibvirtController`
  Protocol with `RealLibvirtController` (lazy `libvirt-python`
  connection, qemu:///session) and `LibvirtControllerMock` (per-method
  `fail_next_*` hooks, call counters, share-tracking set). Consumers
  migrated: `ipc/heartbeat.py` and `ipc/filesystem.py` now type
  against the Protocol. `infra/launch-vm.py` is still plain qemu
  subprocess (no libvirt) — migration deferred to Week 14 install
  pipeline.
- **[✅ DONE 2026-05-08] FreeRDP invocation abstraction.**
  `FreeRDPInvocation` Protocol with `spawn_rail(argv) -> RailSession`,
  `terminate(session)`, `is_alive(session)`. Real impl spawns the
  first binary that resolves on PATH from the chain `xfreerdp` →
  `xfreerdp3` → `sdl-freerdp3` → `sdl3-freerdp` → `flatpak run
  com.freerdp.FreeRDP`. Mock impl records argv to
  `hooks.spawned_argvs` (list of lists), synthesises sequential
  pids, and exposes `fail_next_spawn` failure injection. Wiring
  into `rail_manager.py` lands with Phase 4 RAIL command
  construction (Week 8).
- **[✅ DONE 2026-05-08] In-process integration test harness.**
  `host/tests/test_smoke_inprocess.py` spawns a real Rust agent
  binary (`cargo build -p agent-svc --features mock`) against a
  Python host gRPC server on a free TCP port. Exercises the full
  mTLS + AuthContext + ClientHello → ServerAccept handshake. Surfaced
  three pre-existing bugs fixed in the same commit:
  1. `agent-svc/src/planes.rs::AuthCarrier::new` was being seeded
     with the host cert fingerprint instead of the agent's own
     guest cert fingerprint, which the server's `AuthValidator`
     rejected as a CID-collision spoof.
  2. `agent-svc/src/planes.rs::DEFAULT_HOST_ENDPOINT` was
     `http://` — tonic's `tls_config` only triggers under `https`,
     so the connection was silently plaintext and the host's mTLS
     listener tore it down with a confusing
     `WRONG_VERSION_NUMBER` SSL error.
  3. `host/src/crossdesk_host/ipc/filesystem.py::ShareChannel`
     called `context.core_context.aborted()` — a private
     cython attribute that does not exist in current grpcio
     releases. Replaced with the public `context.cancelled()`.
  Stretch flow (`Installer.run() → Launch(notepad) →
  RailWindowEvent(CREATED)`) deferred until Phase 4 RAIL lands.
- **[✅ DONE 2026-05-08] CI matrix: macOS + Ubuntu.** `.github/workflows/ci.yml`
  has all the jobs spec'd here, all running strict locally:
  - `python-host` runs `mypy --strict src/` + `pytest -q` on Python
    3.9 and 3.12, on Ubuntu and macOS. Both strict-enforced.
  - `rust-guest-cross-compile` runs `cargo check --workspace
    --target x86_64-pc-windows-gnu`, `cargo test --workspace
    --features ipc-vsock/mock`, and `cargo clippy --workspace
    --target x86_64-pc-windows-gnu -- -D warnings`. All
    strict-enforced; the clippy-warnings cleanup landed at the same
    time.
  - `rust-gui` runs `cargo check --workspace` strict.
  - `proto` runs `buf lint` and `buf format --diff --exit-code`,
    both tolerated (`|| true`) until `proto/buf.yaml` rules are
    finalised — see follow-up below.
  - `linux-kvm-smoke` is wired but no-op (placeholder for the
    self-hosted runner that arrives with hardware).
- **[P1] `proto/buf.yaml` lint + format rules.** Currently
  default-permissive — `buf lint` passes trivially. Decide on a
  rule set (BREAKING, DEFAULT, or MINIMAL) and remove `|| true`
  from the proto CI job once codified.
- **[P1] In-process Python↔Rust integration test harness.** Spec'd
  for `host/tests/test_smoke_inprocess.py` driving the host with a
  `cargo run --features mock` guest over `MockTransport`. Exercises
  `Installer.run() → Launch(notepad) → RailWindowEvent(CREATED)`.
  Not blocking Week 1; the standalone unit-level mocks now exist.
- **[P1] Filesystem service abstraction.** Same shape as libvirt
  client. `MockFilesystem` tracks mount/unmount in-memory state.
  Lives in `host/src/crossdesk_host/ipc/filesystem.py` neighborhood.
  Phase 5 dependency.
- **[P1] D-Bus signals abstraction.** Used for suspend/resume
  detection. Mock emits scripted `org.freedesktop.login1.PrepareForSleep`
  events. Tied to lifecycle work.
- **[P1] Windows registry abstraction (guest side).** Behind
  `windows-rs` calls in `guest/crates/agent-svc/`. Mock provides
  builder API for canned registry trees. Used by the future app
  discovery service.
- **[P1] Pyproject + Cargo features for mock toggling.** Document
  in `pyproject.toml` and `Cargo.toml` the `mock`, `linux`, and
  `windows-real` feature gates. Enforce that production paths
  cannot import mock modules — add a CI check.
- **[P2] `cargo deny` rule** preventing direct imports of
  `libvirt-python`, `socket.socket(AF_VSOCK)`, `tokio::net::VsockStream`
  outside the abstraction layer.

## Display & forwarding

How RAIL window pixels reach the Linux compositor and how each
window finds its right monitor with the right scale. See
`docs/DISPLAY.md` for the strategy. GPU passthrough (a separate
sub-topic) lives in `docs/GPU_PASSTHROUGH.md` pending user
decision.

- **[P0] X11 RAIL pipeline (Phase 4 baseline).** Implement
  `host/src/crossdesk_host/display/rail_manager.py` to launch
  FreeRDP RAIL with `GDK_BACKEND=x11` (or native X11), translate
  `RailWindowEvent` messages to compositor operations
  (CREATED → spawn session + set WM_CLASS; DESTROYED → close
  session; FOCUS/TITLE/ICON/MOVED/RESIZED → update WM hints).
  Idempotent and tolerant of out-of-order events.
- **[P1] Wayland-native RAIL.** Investigate FreeRDP 3.x Wayland
  support depth; implement missing `xdg-shell`,
  `xdg-decoration-unstable-v1`, `xdg-foreign-unstable-v2`, and
  `wlr-foreign-toplevel-management` handlers (upstream FreeRDP
  contribution preferred). Migrate `rail_manager.py` to launch
  Wayland-native by default on Wayland sessions, fall back to X11
  on unknown compositors. Beats winapps' XWayland-via-`GDK_BACKEND`
  baseline.
- **[P1] Multi-monitor RAIL window placement.** Enumerate monitors
  via `xdg_output_manager` (Wayland) or RANDR (X11). Place each
  RAIL window via `_NET_WM_DESKTOP` / Wayland output hints. On
  drag-between-monitors with different scale, re-issue
  `/scale-desktop:N`. WinApps explicitly warns this is broken on
  their stack — clear win for us if we land it cleanly.
- **[P1] HiDPI auto-detect.** Read user's effective scale (Wayland
  `wl_output.scale`, X11 RANDR, GNOME `org.gnome.desktop.interface
  scaling-factor`, KDE `kreadconfig5`). Map to nearest FreeRDP-
  supported scale (100/140/180 in 3.x; finer if 4.x). Re-evaluate
  on monitor change events.
- **[P1] RAIL window lifecycle event idempotence.** The
  `RailWindowEvent` consumer in `rail_manager.py` must handle:
  out-of-order CREATED/FOCUS arrivals, repeated DESTROYED, MOVED
  for an unknown window_id (race with CREATED). Phase 4 SPOF —
  see `ROADMAP.md`.
- **[P2] Per-frame display latency benchmark.** Add to the
  microbench harness (Perf budgets work) a measurement of "RAIL
  CREATED event → first frame drawn" on a known-good test app.
  Track on Wayland-native vs XWayland.
- **[P2] Looking Glass as documented alternative.** Document its
  existence in `docs/DISPLAY.md` for power users wanting lower
  latency than RDP encode/decode at the cost of full-desktop
  windowing. Don't integrate; users run Looking Glass directly
  if they want it.
- **[Pending decision] GPU passthrough.** Full deliberation in
  `docs/GPU_PASSTHROUGH.md`. Multi-GPU only, NVIDIA modern + AMD
  RDNA2/3 Tier 1, AMD older + Intel Arc Tier 2, single-GPU
  unsupported. ~3-4 weeks Tier 1 work. Recommended slot: Phase 4.5
  / first major post-MVP follow-up.

## Peripherals & host integration

Audio, clipboard, drag-and-drop, microphone, camera, smart cards,
FIDO2, printers, USB. Default-off opt-in for anything crossing the
trust boundary; typed config in `~/.config/crossdesk/peripherals.toml`
mapping to FreeRDP flags + libvirt XML in our host code. WinApps
exposes none of this as typed config — they put raw FreeRDP flag
strings in their config file. See `docs/PERIPHERALS.md` for the
strategy and per-peripheral notes.

- **[✅ DONE 2026-05-10] Typed config schema for peripherals.** Pydantic model in
  `host/src/crossdesk_host/config/peripherals.py`. Validates
  `~/.config/crossdesk/peripherals.toml` at startup. Maps each
  enabled item to FreeRDP flags + libvirt XML adjustments at VM
  start. Default-off for everything that crosses the trust
  boundary; audio default playback-only; clipboard default
  text-only.
- **[P1] Audio with PipeWire per-app tagging.** FreeRDP
  `/sound:sys:pipewire` (or pulse fallback). Tag each RAIL session's
  audio stream with `PA_PROP_APPLICATION_NAME` so per-window apps
  show as separate streams in `pavucontrol`/`wpctl`. Used by Word,
  Outlook, Spotify-on-Windows, etc.
- **[P1] Clipboard rich-content mode with file-list translation.**
  FreeRDP `+clipboard` with extended formats. In rich mode,
  intercept FORMAT_FILELIST going guest→host and translate UNC
  paths to local equivalents (similar to launch-time path
  translation). In text-only mode, drop FILELIST entries. Off
  default mode = isolation.
- **[P1] Drag-and-drop host-to-guest.** Host compositor initiates
  drag; FreeRDP RAIL receives drop event with FORMAT_FILELIST;
  Windows app opens the file via translated path. Direction limited
  to host→guest; guest→host out of scope.
- **[P1] Microphone (extends audio).** FreeRDP `/microphone:sys:pulse`
  or pipewire. Default off; opt-in per VM via typed config.
- **[P1] Printer redirection via CUPS.** FreeRDP `/printer:CUPS`.
  Mode `auto` forwards all CUPS printers; mode
  `named:<printer-name>` forwards just one. Document Easy Print
  quality caveats (duplex, color may not survive round-trip).
- **[P2] Smart card / PCSC-Lite passthrough.** FreeRDP `/smartcard`
  with `pcscd` host package. Required for corporate workflows
  (banking PKI, government auth). Document host-side `libccid` etc.
  setup.
- **[P2] USB allow-list with libudev hotplug.** Host-side libudev
  watcher attaches/detaches USB devices to the VM via libvirt
  `virsh attach-device` based on vendor:product allow-list in
  config. Default `deny-all`.
- **[P2] Camera USB passthrough.** Default path: pass entire USB
  webcam to VM via libvirt `<hostdev>`. Document virtual-webcam
  alternative (`obs-v4l2sink`) for users wanting host+guest shared
  access.
- **[P2] FIDO2 best-effort documentation.** No native FreeRDP
  channel; users rely on USB passthrough of HID device. Document
  the procedure; don't promise first-class support.
- **[P2] Threat-model rows for each peripheral.** Update
  `docs/THREAT_MODEL.md` with one row per enabled peripheral
  describing what the guest can do with the channel and what's
  default-off.

## Observability — structured logs, traces, metrics

Every component emits JSON-shaped events with W3C Trace Context
propagation across the host↔guest boundary. In-memory metrics
exposed via gRPC RPC. No automatic upload, opt-in OTLP exporter.
See `docs/OBSERVABILITY.md` for the full strategy and
`docs/DECISIONS.md` DEC-0006 for the architectural commitment.
WinApps logs are an unstructured `winapps.log` file with `echo`
when `DEBUG=on` — we are doing materially more.

- **[✅ DONE 2026-05-10] `structlog` (Python) and `tracing` (Rust) JSON-output
  configuration.** Single facade module per language:
  `host/src/crossdesk_host/observability/log.py` and
  `guest/crates/observability/src/lib.rs`. JSON Lines schema with
  mandatory fields (`timestamp`, `level`, `component`, `trace_id`,
  `span_id`, `event`). Used by every other module.
- **[✅ DONE 2026-05-10] Trace ID propagation via gRPC metadata.** W3C Trace
  Context (`traceparent` field). CLI commands generate fresh root
  trace ID; gRPC servicers extract and propagate; guest tags
  `RailWindowEvent` and other emitted events with the originating
  trace. `observability/trace_ctx.py` + `grpc_interceptor.py` +
  `traceparent` field in `common.proto` `AuthContext`. Also wired:
  `verify_coordinator`, every `ManagementService` RPC
  (`child_span_scope()`), and bidi stream planes.
- **[✅ DONE 2026-05-10] Redaction allow-list enforced by lint + test.** Frozen
  list of allowed field names in
  `host/src/crossdesk_host/observability/redaction.py` and
  guest equivalent. Logging non-allowed field raises in tests/dev,
  silently drops in production. Forbidden patterns: `password`,
  `secret`, `token`, `clipboard_content`, full file paths, raw
  AuthContext fingerprints.
- **[✅ DONE 2026-05-10] In-memory metrics: counters, histograms, gauges.** Use
  `hdrhistogram` (Python) and `hdrhistogram-rs` (Rust). Lives in
  `host/src/crossdesk_host/observability/metrics.py`. Counters
  for `launches_total`, `heartbeat_misses_total`,
  `mount_attaches_total`, `auth_context_rejections_total`.
  Histograms for `heartbeat_rtt_seconds`, `launch_duration_seconds`,
  `mount_lifetime_seconds`. Gauges for `vm_state`,
  `current_mounts`, `host_rss_bytes`.
- **[✅ DONE 2026-05-10] `ControlService.GetMetrics` RPC.** Returns a snapshot
  of metrics state. Used by `crossdesk metrics` CLI and the
  microbench harness.
- **[✅ DONE 2026-05-10] `print()` lint rule.** Ruff `T201` enabled in
  `pyproject.toml`. Rust equivalent (clippy `print_stdout`,
  `print_stderr`) in workspace lints.
- **[✅ DONE 2026-05-10] `crossdesk metrics` CLI command.** Calls the RPC, prints
  human-readable summary or `--json`. Covers heartbeat RTT
  histogram, launch latency by app class, current FSM state.
  Landed in `host/src/crossdesk_host/cli/metrics_cmd.py`.
- **[✅ DONE 2026-05-10] Per-component span coverage.** `docs/SPAN_COVERAGE.md`
  documents per-component status; `child_span_scope()` helper in
  `crossdesk_host.observability.trace_ctx`; wired into every
  `ManagementService` RPC. Bidi-stream per-frame decision deferred
  to Phase 7 (hardware-gated streaming path).
- **[✅ DONE 2026-05-10] OTLP exporter (opt-in).** `observability/otlp.py` —
  `configure_otlp_exporter(endpoint, *, insecure=False)`. Reads
  `CROSSDESK_OTLP_ENDPOINT` env var. Off by default (DEC-0002).
  Wired from `daemon.py` after `configure_logging()`. Enables
  Jaeger / Tempo / Honeycomb plug-in.
- **[P2] Optional Prometheus exporter (community).** A small
  script that polls `GetMetrics` and exposes a `/metrics` HTTP
  endpoint. Out of core; document the contract for community
  contribution.
- **[P2] Microbench harness reads from histograms.** Performance
  regression checks in CI consume `heartbeat_rtt_seconds` and
  `launch_duration_seconds` histograms. Tied to perf-budgets
  work.

## Performance budgets — enforcement

The budgets themselves are in `docs/REQUIREMENTS.md` §N1; the
architectural commitment is in `docs/DECISIONS.md` DEC-0004.
This section is about *enforcement* — the benchmark harness,
CI integration, regression detection. See `docs/PERFORMANCE.md`
for the full strategy.

WinApps and Cassowary publish no SLOs and run no benchmarks. Our
positioning depends on enforcing what we promise.

- **[✅ DONE 2026-05-10] `pytest-benchmark` and `criterion` harness configured.**
  `host/benches/` (Python) and `guest/benches/` (Rust). One bench
  file per N1.* metric (stubs OK initially). Naming convention:
  `bench_N1_X_Y_<metric_name>`. Implemented: bench_N1_1_cold_launch.py
  (metric recording + registry snapshot), bench_N1_2_suspend.py (FSM
  suspend/resume transitions + healthy tick rate), bench_N1_6_recovery.py
  (HARD_DESTROY escalation + recovery metric record). `python_files`
  expanded in pyproject.toml so `pytest benches/` discovers bench_*.py.
- **[✅ DONE 2026-05-10] `bench_check.py` tool.** Loads baseline file
  (`.github/perf-baselines.json`), compares JSON-format bench
  results to baselines, fails if any metric regresses by >20%.
  Extended to support `--baseline`/`--results` named flags (CI
  convention) alongside the original positional form.
- **[✅ DONE 2026-05-10] CI job `microbench` on every PR.** Runs Python
  microbenches on ubuntu-latest Python 3.12, invokes bench_check.py
  with `--baseline`/`--results` flags, pass/fail gate. No PR comment
  yet (P1 automation). timeout-minutes: 10.
- **[✅ DONE 2026-05-10] Initial baselines committed.** `.github/perf-baselines.json`
  expanded with 8 new bench entries covering N1.1, N1.2, N1.6 metrics.
  FSM-hot-path entries kept nonzero (5000 ns); new histogram/escalation
  entries set to 0 (collect-only) until real CI runner measurements land.
- **[P1] Integration benchmarks.** `host/tests/benchmarks/`:
  `bench_install_pipeline.py`, `bench_cold_launch_lightweight.py`
  (N1.1a), `bench_recovery_destroy_start.py` (N1.6a). Slower;
  gated by PR label `perf-full`. Run on main-branch nightly.
- **[P1] `tools/bench_report.py`.** Aggregates results across
  runs into a markdown table for release notes.
- **[P1] PR comment automation.** GitHub Action post-comment with
  the perf table.
- **[P2] Self-hosted KVM runner with `hardware-smoke` workflow.**
  Real-hardware numbers gated by PR label and hardware
  availability. Runner doesn't exist yet; wire workflow file
  ready.
- **[P2] Trend analysis** (weekly metric summary over time).
  Lower priority — useful once we have months of history.

## Versioning & compatibility

Three things versioned: the gRPC protocol (`proto/crossdesk/vN/`),
the host package, and the guest agent. N-1 minor compatibility
window. `Hello` handshake on first connect. See
`docs/VERSIONING.md` for the strategy and `docs/DECISIONS.md`
DEC-0007 for the architectural commitment. WinApps doesn't
version anything — we are above that bar.

- **[✅ DONE 2026-05-10] `Hello` message in proto with handshake fields.**
  `protocol_version` field 4 added to `ClientHello` and `ServerAccept` in
  `proto/crossdesk/v1/control.proto`. `agent_version` field 7 added to
  `StatusFrame` in `mgmt.proto`. Guest stamps `protocol_version="1"` in
  `ClientHello`; host echoes it in `ServerAccept`.
- **[✅ DONE 2026-05-10] Handshake compatibility logic.** Host checks
  `protocol_version` major digit in `ClientHello`; rejects with
  `AuthFailure.CODE_FEATURE_NEGOTIATION_FAILED` on major mismatch.
  Guest logs warning on major mismatch in `ServerAccept` but stays
  lenient (host is authoritative per N-1 rule). `on_agent_version`
  callback stores guest version in `MgmtState.agent_version`.
- **[🚧 partial DONE 2026-05-10] CLI semver commitment in v1.x.**
  Documented in `docs/VERSIONING.md` §"CLI versioning": stable
  subcommand list, flag stability rules, exit code conventions.
  CI manifest test (snapshot `--help` output, fail on unexpected
  change) not yet implemented — P1 follow-up before v1.0.0 tag.
- **[P1] `crossdesk upgrade` agent hot-swap with handshake-aware
  sequencing.** Already in Operations FOLLOWUPS. Extend: FSM
  enters `UPGRADING` state during agent swap (suppresses
  HARD_DESTROY for ≤60 s); after new agent's first Hello,
  exits `UPGRADING`.
- **[✅ DONE 2026-05-10] Capabilities flag inventory.** Documented in
  `docs/VERSIONING.md` "Appendix: capability flag inventory":
  authoritative list of stable flags (`rail.v1`, `virtiofs.jit`),
  planned flags (`auth.verify-credentials.v1`, `trace.w3c.v1`,
  `gpu.passthrough.v1`, `looking-glass.v1`), naming convention
  (`<area>.<version>`, `exp:` prefix for experimental), retirement
  procedure, and code references for each side's advertise/negotiate
  point.
- **[P1] Config schema versioning + migration.** `vm.toml` and
  others get a `schema_version` field. Host reads older versions,
  migrates in-memory; `crossdesk config migrate` writes the
  migration to disk. Adding a field is MINOR (no migration);
  removing/renaming is MAJOR.
- **[P1] N-1 agent CI matrix.** GitHub Actions job that builds
  the previous minor version's agent and runs handshake tests
  against current host. Catches accidentally-breaking proto
  changes.
- **[P2] Deprecation tracking.** When a MINOR adds a field
  obsoleting an older one, surface a one-time warning at startup
  until the older one is removed in MAJOR. Tooling: a registry
  in `proto/DEPRECATED.md` tracking deprecation dates.
- **[✅ DONE 2026-05-10] `crossdesk version` command.** Shows host
  version (`importlib.metadata`), agent version (from `ManagementService.Status`
  `agent_version` field), protocol version (constant "1"), and commit
  (from package metadata, falls back to "unknown"). Handles
  "daemon not running" and "not connected" states.

## Distribution & packaging

Five formats: deb, rpm, AUR, NixOS flake, PyPI. Skipping Flatpak
/AppImage/Snap/OCI (sandbox conflicts or no value-add). See
`docs/PACKAGING.md` for the strategy and `docs/DECISIONS.md`
DEC-0008 for the architectural commitment.

`agent.exe` (Rust cross-compiled) ships bundled inside each Linux
package. Sigstore-signed initially; EV cert future.

- **[✅ DONE 2026-05-09] AUR PKGBUILD published.** `packaging/aur/PKGBUILD`
  carries depends on grpcio/cryptography/structlog/libvirt/qemu/freerdp/
  libnotify and installs the systemd user unit + MS Office .desktop.
  Real submission to AUR gated on v0.1.0 tag.
- **[✅ DONE 2026-05-09] PyPI wheel for `crossdesk-host`.** `host/pyproject.toml`
  declares all metadata for `pip install crossdesk-host`. CI
  `build-host-wheel` job produces the wheel on tag.
- **[✅ DONE 2026-05-09] NixOS flake outputs.** `flake.nix` at repo root with
  `crossdesk` and `crossdesk-gui` derivations.
- **[✅ DONE 2026-05-10] CI release matrix on tag.** `.github/workflows/release.yml`
  — 4 jobs: build-agent (MinGW cross-compile), sign-agent (osslsigncode,
  graceful skip on missing PFX), build-host-wheel, publish-release
  (softprops/action-gh-release, SHA-pinned). Draft release uploaded
  for human review; real publish gated on v0.1.0 tag.
- **[P1] `deb` package + apt repo.** `dh-virtualenv` or `fpm`
  packaging. Repo at `https://repo.crossdesk.dev/deb/` (or
  similar) with apt source line documented in install docs.
  GPG-signed.
- **[P1] `rpm` package + Copr/OBS repos.** Fedora Copr (free,
  automated) for Fedora; openSUSE OBS for openSUSE. RPM signing
  via OBS or a self-hosted key.
- **[P1] Sigstore signing for `agent.exe`.** Wired into release
  CI. Public verification key on download page. Documented in
  install docs ("how to verify your CrossDesk download").
- **[P2] Update mechanism docs per distro.** README install
  section explains `apt update`, `dnf upgrade`, `yay -Sua`, etc.
  Distinct from `crossdesk upgrade` which is about the in-VM
  agent.
- **[P2] Distribution-time GPG signing for deb/rpm.** Release key
  stored offline.
- **[P2] Community documentation for adding new distros.** Gentoo
  ebuild template, SBo build script template. We won't ship
  these but we make it easy for community members to.

## Lifecycle: power, suspend/resume, autostart

Coordinated handling of host suspend / resume / shutdown so the
heartbeat FSM doesn't false-positive HARD_DESTROY a perfectly fine
VM that's just paused along with the host. systemd user service
for the host process. Optional VM autostart on login. WinApps's
TimeSync.ps1 marker-file polling is reactive and addresses only
clocks; we coordinate the entire FSM. See `docs/LIFECYCLE.md`.

- **[✅ DONE 2026-05-09] D-Bus listener for power events.** `dbus-next` listener
  on the host process's asyncio loop, subscribed to
  `org.freedesktop.login1.Session.PrepareForSleep` (true/false)
  and `org.freedesktop.login1.Session.PrepareForShutdown`
  (true/false). Lives in
  `host/src/crossdesk_host/lifecycle/dbus_listener.py`.
- **[✅ DONE 2026-05-09] FSM `SUSPENDED` state with proper transitions.** Extends
  the heartbeat FSM with a `SUSPENDED` state entered from any
  prior state on suspend signal. While in `SUSPENDED`, missed
  heartbeats are no-ops. Exit on resume with grace period.
  `host/src/crossdesk_host/watchdog/fsm.py`.
- **[✅ DONE 2026-05-09] Suspend handler.** Sequence: pause FSM → quiesce
  in-flight RPCs → `virsh suspend` → release D-Bus inhibitor.
  `host/src/crossdesk_host/lifecycle/coordinator.py`.
- **[✅ DONE 2026-05-09] Resume handler.** Sequence: `virsh resume` →
  `virsh domtime --sync` → AuthContext re-handshake →
  FSM exits `SUSPENDED` → `PROBING` for ~10 s grace period.
  `host/src/crossdesk_host/lifecycle/coordinator.py`.
- **[✅ DONE 2026-05-09] systemd user service unit.** `infra/crossdesk-host.service`
  shipped in distro packages: `After=graphical-session.target`,
  `PartOf=graphical-session.target`, `Wants=dbus.socket`,
  `Type=notify`, `Restart=on-failure`. Enabled per-user via
  `systemctl --user enable crossdesk-host`.
- **[P1] Shutdown handler.** `virsh shutdown` (ACPI graceful)
  with N-second timeout, fallback to `virsh destroy`. Persist
  install state. Release inhibitor. Default timeout 30 s.
- **[P1] Autopause × balloon × heartbeat coordination.** Single
  supervisor in `lifecycle/` owns FSM state across all three
  mechanisms. Autopause uses the same `SUSPENDED` state path as
  D-Bus suspend. Balloon adjustments are tolerated by the FSM
  (brief RTT spikes don't trigger PROBING).
- **[P1] VM autostart on login (opt-in).** `crossdesk install
  --autostart` and `crossdesk vm autostart enable|disable`.
  Default off. When enabled: host starts VM at session start.
- **[P1] "Missed PrepareForSleep" heuristic detector.** If
  heartbeat goes healthy → 10 misses → healthy in <30 s,
  downgrade SOFT_RECOVERY trigger to a warning. Catches
  configurations where D-Bus signal isn't emitted.
- **[P2] Hibernation-aware handling.** Detect "resumed after
  long absence" (e.g., wall-clock jump >1 hour); force more
  aggressive AuthContext resync.
- **[P2] Power profile docs.** User-facing docs covering laptop
  battery-saver / lid-close-suspend policy interactions, with
  recommended `crossdesk` configuration per scenario.

## Internationalization

`gettext` for Python CLI and host messages, Qt's native `tr()` /
`.ts` for the GUI. English + Polish on first release; community
adds other languages. WinApps is English-only — easy win for
CrossDesk's positioning, especially with non-English users
underserved by the comparable VM-management tooling. See
`docs/I18N.md` for the full strategy.

- **[P0] [✅ DONE 2026-05-10] `gettext` configured in Python host.**
  `crossdesk_host.i18n` module exposes `_()` backed by
  `gettext.translation()`; falls back to `NullTranslations` (identity)
  when no `.mo` is found so unconfigured installs stay English.
  Probes `$CROSSDESK_LOCALEDIR`, `$XDG_DATA_DIRS/locale/`, and the
  in-repo `i18n/` for dev. CLI surfaces migrated:
  `cli/credentials_cmd.py`, `cli/doctor_cmd.py`,
  `cli/uninstall_cmd.py`. Other `print()` call sites in
  `cli/install_cmd.py`, `cli/main.py`, and the `installer/` package
  remain English-literal — follow-up wave can wrap them as user
  testing surfaces them.
- **[P0] [✅ DONE 2026-05-10] `qsTr("...")` markers on every QML
  string in `gui/`.** Full line-audit of all manager pages confirmed
  `qsTr()`-clean: `Apps.qml`, `Storage.qml`, `Lifecycle.qml`,
  `Diagnose.qml`, `Logs.qml`, `Settings.qml`, `Dashboard.qml`.
  Entry-point pages (`Main.qml`, `Manager.qml`,
  `wizard/InstallWizard.qml`, `wizard/Step1Iso.qml`,
  `wizard/Step2Identity.qml`, `wizard/Step3Resources.qml`) were
  already confirmed clean in the prior pass. All user-visible strings
  are picked up by the existing
  `gui/crates/crossdesk-gui/i18n/crossdesk_pl.ts`. `About.qml`
  intentionally has 1 brand string ("CrossDesk Manager", not
  translated) plus 1 deliberate Polish easter-egg per ROADMAP
  (Phase 4 SPOF blurb) — left as-is by design.
- **[P0] [✅ DONE 2026-05-10] `i18n/` directory at repo root with
  templates.** `i18n/crossdesk-host.pot` (gettext skeleton),
  `i18n/pl/LC_MESSAGES/.gitkeep` placeholder for Polish .po,
  `i18n/README.md` documenting the workflow. Qt `.ts` files
  continue to live next to the GUI source under
  `gui/crates/crossdesk-gui/i18n/` (where the Qt resource
  system expects them) — `i18n/README.md` cross-references.
- **[P0] [✅ DONE 2026-05-10] Build tooling.** `scripts/i18n.sh`
  with `extract` and `compile` subcommands. Wraps `xgettext`
  (Python sources → `.pot`) and `lupdate` (QML → `.ts`) for
  extraction; `msgfmt` and `lrelease` for compile. Idempotent —
  re-run with no source changes leaves the templates byte-identical
  (the `POT-Creation-Date` is frozen to keep diffs clean for
  the eventual CI extraction job).
- **[P0] [✅ DONE 2026-05-10] Distro package install rules.**
  Documented in `i18n/README.md`: `.mo` files land at
  `/usr/share/locale/<lang>/LC_MESSAGES/crossdesk-host.mo`,
  `.qm` files at `/usr/share/crossdesk/translations/`. Standard
  freedesktop / Qt paths — distro packagers (deb / rpm / AUR)
  invoke `msgfmt` and `lrelease` from their build steps.
  Compiled artifacts are intentionally not in-repo.
- **[P0] [✅ DONE 2026-05-10] English-string discipline.** Already
  documented in `docs/I18N.md` "Strings we don't translate" — logs
  via structlog, config field names, component identifiers, and
  error codes stay English. Reinforced in `i18n/README.md`
  "Conventions". The `crossdesk_host.i18n` module docstring
  re-states the rule for code readers. Reviewers enforce.
- **[✅ DONE 2026-05-11] Polish translations complete (GUI).** 133
  strings in `gui/crates/crossdesk-gui/i18n/crossdesk_pl.ts`, 0
  unfinished. Compiled via `lrelease` in `build.rs` at build time.
  CLI translations (install_cmd, metrics_cmd, logs_cmd, version_cmd,
  main.py) remain English-literal — follow-up wave P1.
- **[✅ DONE 2026-05-11] CI string-extraction job.** `i18n-extract` job in
  `.github/workflows/ci.yml`: installs qttools5 + gettext, runs
  `scripts/i18n.sh extract`, then `git diff --exit-code` on `.pot`
  and `.ts` — fails if new `_()` / `qsTr()` calls aren't committed.
  Runs on every push and PR.
- **[P1] `CONTRIBUTING.md` translator section.** Workflow for
  adding a new language: copy template, edit, submit PR. Lists
  current language coverage and contributors.
- **[P2] Weblate (or similar) integration.** Hosted translation
  service so translators don't need git. Decision contingent on
  whether community contribution volume warrants the setup.
- **[P2] Plural-form audit.** gettext `ngettext` for strings
  that pluralize. Currently expected to be few; revisit on first
  Polish translation pass.
- **[P2] Locale-aware number/date formatting.** File sizes,
  timestamps in user-visible output. `locale.format_string`
  Python; Qt handles GUI side natively.
- **[P2] RTL language readiness.** When first RTL translation
  arrives (Arabic / Hebrew), audit GUI layouts for RTL behavior.
  Qt handles most automatically. Out-of-scope until needed.

## GPU passthrough — Phase 4.5 (post-MVP P0)

Decision accepted 2026-05-07: GPU passthrough lands as Phase 4.5 /
post-MVP P0; Tier 1 = NVIDIA RTX 20/30/40 driver 465+ and AMD RDNA2/3
multi-GPU; Tier 2 documented (AMD older with `vendor-reset`, NVIDIA
old with hide-the-VM); Tier 3 out (Intel Arc + single-GPU). Full
deliberation in `docs/GPU_PASSTHROUGH.md`; ADR `docs/DECISIONS.md`
DEC-0009.

- **[P0] `crossdesk doctor` GPU detection.** Enumerate GPUs
  (`lspci -nnk`), identify vendor + chip, check IOMMU enabled
  (`/sys/class/iommu/`), check IOMMU group composition
  (`/sys/kernel/iommu_groups/`), classify into Tier 1/2/3.
  Output structured: `{tier, host_gpu, available_for_passthrough,
  warnings, blockers}`. ~200-400 lines in
  `host/src/crossdesk_host/diagnostics.py`. Wired into `crossdesk
  install` as a pre-step.
- **[P0] `crossdesk gpu setup` helper.** Walks user through
  per-distro kernel cmdline params (GRUB, systemd-boot, NixOS),
  per-distro initramfs binding (mkinitcpio, dracut,
  initramfs-tools), GPU + audio function PCI ID identification,
  optional `--commit` to write changes vs `--dry-run` default.
  Plus `crossdesk gpu verify` to confirm post-reboot binding.
- **[P0] libvirt domain XML extension for `<hostdev>`.**
  `infra/launch-vm.py` adds GPU + audio function `<hostdev>`
  blocks based on detected configuration. Plus
  `<features><kvm><hidden state='on'/></kvm></features>` for old
  NVIDIA + `hv_vendor_id` QEMU args when needed.
- **[P0] Tier 1 vendor smoke tests.** Manual QA matrix per
  release: at least one Tier 1 NVIDIA host and one Tier 1 AMD
  host. CI cannot run these without dedicated hardware runners
  (gated separately).
- **[P1] AMD reset-bug Tier 2 docs.** Detection (probe
  `lsmod | grep vendor_reset`); warning surfaced via doctor;
  link to upstream <https://github.com/gnif/vendor-reset>
  installation instructions; we don't ship the module.
- **[P1] NVIDIA pre-2021 Tier 2 hide-the-VM docs.** Explain Code
  43 history; document `<hidden>` flag opt-in; warn that newer
  NVIDIA drivers (465+) make this obsolete; for users stuck on
  old drivers explain the workaround.
- **[P1] TA7 row in `docs/THREAT_MODEL.md`.** Malicious GPU
  firmware threat with mitigations (signed firmware verification,
  no ACS override, IOMMU enforcement). Adds when implementation
  lands per DEC-0009.
- **[P2] Per-distro automated setup support beyond docs.** Auto-
  apply kernel cmdline + initramfs config via `crossdesk gpu
  setup --commit` for the four primary distros. Each distro
  module in `infra/gpu_setup/<distro>/`.
- **[P2] GPU performance benchmarks.** Add to `host/benches/`
  (Performance work) `bench_gpu_filter_latency.py` that measures
  Photoshop-class filter completion time on a known image.
  Real-hardware-only; gated behind `hardware-smoke` workflow.

## Looking Glass integration — post-Phase 4.5 (P0)

Decision deferred to after GPU passthrough lands. LG integration
unlocks single-GPU users via compositor-restart hot-switch and
adds a Desktop-mode alternative giving sub-5ms latency for power
users. See `docs/GPU_PASSTHROUGH.md` §"Crucial: how GPU
passthrough interacts with our RAIL model" and the prior
deliberation in conversation history (turns about Looking Glass
integration).

- **[P0] Bundle LG client in distro packages.** ~5 MB Linux
  binary added to deb/rpm/AUR/NixOS/PyPI artifacts. License
  GPL-2.0+ (compatible with our GPL-3.0). Update
  `docs/PACKAGING.md` packaging item to include.
- **[P0] LG host installer in our Windows install pipeline.**
  Optional component (`crossdesk install --gpu --with-lg`)
  copying LG host to the secondary OEM disk and registering it
  for autostart on Windows side.
- **[P0] IVSHMEM device in `infra/launch-vm.py`.** Add IVSHMEM
  device (8 MB shared memory region typical) to libvirt domain
  XML when LG is enabled.
- **[P0] Scream audio bundling.** LG itself has no audio; Scream
  is the standard companion (low-latency network audio). Bundle
  Scream client + server with the LG package set.
- **[P0] `crossdesk launch --mode=desktop` CLI.** Per-app config
  knob `mode = "rail" | "desktop"` in
  `~/.config/crossdesk/peripherals.toml` or app-specific. When
  `desktop` mode is selected, host spawns LG client instead of
  FreeRDP RAIL session.
- **[P1] Single-GPU hot-switch path.** When `crossdesk doctor`
  detects single-GPU + user requests Desktop mode: orchestrate
  compositor stop, GPU rebind to vfio-pci, VM start with LG host,
  LG client spawn on iGPU/vesa fallback compositor, reverse on
  exit.
- **[P1] C8 IVSHMEM channel in `docs/THREAT_MODEL.md`.** New
  component row covering IVSHMEM as a non-VSOCK trust surface.
  Different from gRPC because no per-frame AuthContext; threat
  is reduced because it's a unidirectional pixel firehose. Document.
- **[P2] Docs/USER_GUIDE_DESKTOP_MODE.md.** When to use RAIL vs
  Desktop, what the trade-offs are, troubleshooting LG audio
  delays via Scream, etc.

## Software rendering fallback — post-Phase 4.5 (P1)

For users whose hardware fundamentally cannot support GPU
passthrough (cheap motherboards with bad IOMMU groups, non-MUX
laptops with dGPU routed through iGPU, iGPU-only systems), we
document software rendering as the always-works fallback.

- **[P1] Document supported app classes per render path.** Word,
  Outlook, Excel, Visual Studio: software rendering fine.
  Photoshop, Premiere, AutoCAD, Blender: software rendering
  unusable. Concrete table in
  `docs/USER_GUIDE_HARDWARE_COMPAT.md` so users can self-assess
  before installing.
- **[P1] `crossdesk doctor` recommends app categories per
  hardware tier.** "Your hardware is Tier 3 for GPU mode but
  fully supports productivity apps via software rendering. We
  recommend CrossDesk for [list]; for [Photoshop, Premiere], use
  Wine, CrossOver, or a cloud GPU service."
- **[P2] Investigate llvmpipe optimizations.** llvmpipe is the
  Mesa software rasterizer. Some apps that "don't work" on
  software rendering may work with newer llvmpipe versions or
  with specific Mesa tuning. Light investigation, no commitment.

## Phase 1 follow-ups (VM bootstrap is "done" but this still needs to land before Phase 4)

- **[✅ DONE 2026-05-09] Replicate critical Windows registry tweaks for RDP RAIL.**
  `infra/RDPApps.reg` — all required keys: `fDenyTSConnections=0`,
  `UserAuthentication=1`, `fDisabledAllowList=1`,
  `fAllowUnlistedRemotePrograms=1`, `IgnoreRemoteKeyboardLayout=1`.
  Applied from `<FirstLogonCommands>` in `infra/autounattend.xml`.
  Hardware verification gated on Linux+KVM+Windows guest.
- **[P2] Locale + timezone propagation.** Source:
  `third_party/winapps/oem/TimeSync.ps1` (concept; their solution is
  marker-file polling). Read host `timedatectl` + locale env once during
  `infra/launch-vm.py` install and inject into `autounattend.xml`'s
  `<TimeZone>` and `<UserLocale>` instead of hardcoding. Skip the runtime
  marker-file mechanism if `qemu-guest-agent` is enabled — `virsh
  domtime` covers post-suspend resync.
- **[🚧 mock DONE 2026-05-09] Auto-download Windows ISO via Fido-style URL generation.**
  `installer/iso_downloader.py` — Python port of Fido scrape logic;
  session-id POST → 24h-signed CDN URL; SHA256 validation against
  `infra/known_isos.toml`; caches to `~/.cache/crossdesk/iso/`.
  `--iso-path` manual override retained. End-to-end scrape verification
  gated on network+hardware (Microsoft's CDN response, not in CI).
- **[🚧 mock DONE 2026-05-09] One-command bootstrap: `crossdesk install`.**
  `cli/install_cmd.py` + `installer/state.py` — 7-step state machine
  (iso_download → credentials → libvirt_domain → autounattend → 
  win_install → agent_register → healthcheck). Idempotent per-step
  progress in `~/.local/state/crossdesk/install.state.json`. 
  `generate_credentials` runs end-to-end without hardware; all other
  steps print "hardware-gated" and return 1. `--dry-run` marks all
  steps done without executing. Full end-to-end acceptance gated on
  Linux+KVM hardware.
- **[✅ DONE 2026-05-10] VM credential management — generate, view, rotate.**
  `installer/credentials.py`: `VmCredentials`, `generate()`, `save()`,
  `load()`, `CredentialFileHealth`, `health_check()`, `repair_permissions()`.
  `cli/credentials_cmd.py`: `show`, `rotate`, `set`, `check`, `repair`.
  RotateCredentials: `VerifyCoordinator.verify()` + `verify_with_guest()` 
  mapping. Doctor probe `check_vm_credentials`. `RotateCredentials` RPC
  hardware-gated (real `NetUserChangePassword` needs Windows guest).
- **[P1] CrossDesk Lean Windows profile — debloat from official ISO
  using Microsoft tools (opt-in).** Goal: ~50-70% of Tiny11's resource
  savings (~1.2 GB idle RAM vs full Win11's ~2 GB; ~12 GB disk vs 22
  GB) without depending on a community-modified ISO. Implement as a
  PowerShell script `infra/lean_profile.ps1` invoked from
  `<FirstLogonCommands>` in `infra/autounattend.xml`. Uses official
  tools only (`Remove-AppxPackage`, `Disable-WindowsOptionalFeature`,
  `dism /Remove-Capability`). Removes: Edge, Cortana, OneDrive setup,
  Tips, Get Started, Microsoft News, bundled games (Solitaire), Skype,
  Teams personal, Xbox app and dependencies. **Keeps**: .NET runtime,
  Visual C++ redistributables, Windows Update, **Windows Defender**
  (defense in depth — kept even though VSOCK+mTLS+JIT-VirtioFS already
  isolate the VM, since Defender catches in-VM threats independent of
  our boundary), audio/video drivers (RAIL needs them). **Opt-in
  only** — default `crossdesk install` produces full Windows 11 Pro;
  lean is enabled via `crossdesk install --lean`. Acceptance test:
  Office, Adobe Creative Cloud, and Visual Studio install and activate
  normally on the lean profile (these are exactly where Tiny11 is
  known to break). Land before Phase 4 so RAIL latency tests run on a
  representative image.
- **[P2] Detect Windows 11 IoT Enterprise LTSC and short-circuit
  redundant debloat steps.** Source: official Microsoft SKU; lacks
  Edge, Cortana, Microsoft Store, and most bloatware out of the box.
  If the user supplies an LTSC ISO (detect by reading the edition
  string from `install.wim`), `infra/lean_profile.ps1` should skip the
  matching `Remove-AppxPackage` calls — they'd be no-ops anyway. Lower
  priority because LTSC requires enterprise licensing through
  resellers, not consumer purchase, so few hobbyist users will hit
  this path.
- **[✅ DONE 2026-05-09] Explicitly configure VM network mode in libvirt domain XML.**
  `infra/launch-vm.py` explicitly sets `-netdev user,id=net0` + virtio-net
  (NAT/user mode). `--network=bridge` flag is a P1 follow-up.
- **[✅ DONE 2026-05-09] Verify EULA acceptance in `infra/autounattend.xml`.**
  `<HideEULAPage>true</HideEULAPage>` in `oobeSystem` — the correct
  Win11 autounattend mechanism (replaces the older `EULAAccepted` key).

## Phase 3 follow-ups (Control FSM / Heartbeat)

- **[✅ DONE 2026-05-10] Auth health-check before every launch.**
  See Phase 4 follow-ups — VerifyCredentials RPC landed (user-approved
  proto edit); `VerifyCoordinator` + `spawn_rail_with_auth_check()` wired.
- **[✅ DONE 2026-05-09] AdaptiveProfile broadcast before recovery action.**
  Per heartbeat.proto contract. Host emits `HostFrame.profile_update`
  carrying the impending `RecoveryAction` and exponential-backoff hint
  BEFORE calling libvirt. Lives in
  `host/src/crossdesk_host/ipc/heartbeat.py::HeartbeatServiceServicer.Channel`.
- **[P1] Two-layer health check before declaring the VM ready.** Source:
  `third_party/winapps/setup.sh:1040-1195`. They probe TCP port + run a
  marker-file round-trip via FreeRDP before considering RDP usable. Our
  equivalent: extend the existing FSM `PROBING` state to (a) confirm
  VSOCK listener is bound (already done), (b) round-trip a real
  `HeartbeatService.Channel` ping with a synthetic `AuthContext` and
  observe the response within `BOOT_TIMEOUT`. Today an asymmetric break
  (vsock up but agent stuck) would not be caught here. Touches
  `host/src/crossdesk_host/watchdog/` (FSM) and
  `host/src/crossdesk_host/ipc/heartbeat.py`.

## Phase 4 follow-ups (RAIL Display Integration)

- **[✅ DONE 2026-05-09] Build the FreeRDP RAIL command from the WinApps template.**
  `host/src/crossdesk_host/display/rail_command.py` — `AppLaunchSpec`
  dataclass + `FreeRDPInvocation.build_argv()`. Essential flags
  (`/app:program:`, `/wm-class:`, `/scale:`, `+auto-reconnect`,
  `/drive:media,`) documented per-flag in module docstring.
- **[✅ DONE 2026-05-09] Path translation helper for `cmd:` argument forwarding.**
  `host/src/crossdesk_host/display/path_translation.py` — `PathTranslator`
  dataclass, `translate()`, and `winapps_compat()` factory. Phase 5 JIT
  mount path integration is a follow-up (Phase 5 not yet started).
- **[P1] FreeRDP version fallback chain.** Source:
  `third_party/winapps/setup.sh:413-454`. Try in order: `xfreerdp` →
  `xfreerdp3` → `sdl-freerdp3` → `sdl3-freerdp` → flatpak
  `com.freerdp.FreeRDP`. Distros pack FreeRDP under many binary names.
  Helper in `host/src/crossdesk_host/display/`.
- **[P2] HiDPI auto-detect — beat winapps here.** Source: their model is
  `RDP_SCALE` config knob with three discrete values
  (`third_party/winapps/setup.sh:504-534`). We can read Wayland
  `wl_output.scale` (or X11 RANDR) at launch time, pick the closest
  FreeRDP-supported scale (still 100/140/180 — FreeRDP limit), and
  re-launch on monitor change. Ours becomes "no config knob, just works."
- **[P2] Multi-monitor RAIL — beat winapps here.** Their own README
  warns multi-monitor is broken (`/multimon` causes black screens).
  Forward each RAIL window to its appropriate output via WM hints. Same
  module as HiDPI.
- **[✅ DONE 2026-05-10] Auth health-check before every RAIL launch.**
  `ControlService.VerifyCredentials` RPC in `proto/control.proto`;
  host `VerifyCoordinator` in `ipc/control.py`; guest `credentials.rs`
  with `mock` cfg-gate and real-Windows scaffold. `RailManager.spawn_rail`
  gated by `session_starter.spawn_rail_with_auth_check()` (raises
  `AuthHealthCheckFailed` with `repair_hint`). `crossdesk vm credentials
  check` + `repair` CLI subcommands. `doctor` probe `check_vm_credentials`.
  Real `LogonUserW` call hardware-gated (Stage 4).

## Post-MVP (winapps-parity features beyond Phase 5)

- **[P0] App discovery service.** Source:
  `third_party/winapps/install/ExtractPrograms.ps1` (336 lines of
  PowerShell). Re-implement as a Rust binary in `guest/` (we already have
  `windows-rs`), expose via gRPC RPC over VSOCK. Sources to enumerate:
  `HKLM\...\App Paths`, `HKLM\...\Uninstall`, `HKCU\...\Uninstall`,
  `WOW6432Node` 32-bit views, UWP via `Get-AppxPackage`, Chocolatey
  shims, Scoop shims. Fix winapps' gap: they only do `App Paths` and
  miss anything in `Uninstall`-only or `WOW6432Node`.
- **[✅ DONE 2026-05-11] `.desktop` file generator.**
  `host/src/crossdesk_host/integrations/mime.py` — `install_app()`:
  writes `crossdesk-<id>.desktop` with `Exec`, `StartupWMClass`,
  `MimeType`, `Categories`; idempotent. `uninstall_app()` /
  `uninstall_all()` mirror uninstall.py cleanup. 18 tests.
- **[✅ DONE 2026-05-11] MS Office URL scheme handler.**
  `install_office_handler()` in `integrations/mime.py` writes
  `crossdesk-ms-office-handler.desktop` claiming all 10 ms-* URL scheme
  MIME types. `NoDisplay=true` so it stays invisible in launchers while
  routing Office links from browsers to the Windows guest.
- **[P1] Adopt the 91-app catalog as a starting point.** Source:
  `third_party/winapps/apps/<name>/info` (91 entries). Copy the
  non-trademark fields (`WIN_EXECUTABLE`, `MIME_TYPES`, `CATEGORIES`)
  into our own catalog format (TOML preferred). Skip the SVG icons —
  they have unclear trademark status (Microsoft / Adobe logos);
  generate icons by extracting from `.exe` resources at discovery time.
- **[P1] Autopause after idle.** Source:
  `third_party/winapps/bin/winapps`, `setup.sh` `AUTOPAUSE` /
  `AUTOPAUSE_TIME` config. After N seconds with no active session,
  `virsh suspend` the VM (RAM stays, CPU drops to zero). Subtract 20s
  from the user's threshold for RAIL cleanup overhead — that constant
  is encoded in their script and is easy to miss.
- **[P1] Sleep/wake time sync.** Source:
  `third_party/winapps/oem/TimeSync.ps1`. Prefer
  `qemu-guest-agent`+`virsh domtime` if available. Otherwise mirror
  WinApps' marker-file approach via gRPC: host writes a "host-resumed"
  signal on D-Bus suspend wakeup → guest agent runs `w32tm /resync`.
- **[P1] GUI launcher / taskbar applet.** Source: separate repo
  `winapps-org/WinApps-Launcher`, packaged at
  `third_party/winapps/packages/winapps-launcher/default.nix` (Bash +
  Yad). Extend our existing Qt6/QML installer wizard (`gui/`) into a
  permanent applet — VM start/stop/pause/reboot, app picker. Bigger
  scope, much nicer UX than Yad.
- **[P1] Desktop notifications via `org.freedesktop.Notifications`.**
  Source: `notify-send` calls scattered throughout
  `third_party/winapps/setup.sh`. Wire host-side errors (VM won't
  start, forced stop, RDP drop) to D-Bus notifications. Cheap polish;
  we already have D-Bus access.
- **[P2] Typed config for redirections.** Source: WinApps' `RDP_FLAGS`
  is a free-form string the user hand-edits
  (`third_party/winapps/README.md:457-463`). Replace with typed TOML
  fields: `enable_audio`, `enable_clipboard`, `enable_printer`,
  `usb_devices: list[str]`. Map to FreeRDP flags in our host code.
  User never sees raw FreeRDP syntax.
- **[P2] Auto-derive MIME types from registry.** Source: WinApps
  hand-curates MIME lists in
  `third_party/winapps/apps/<name>/info` `MIME_TYPES` field
  (unscalable). Read `HKCR\<ext>` and `HKCR\<progid>\shell\open\command`
  during discovery to compute MIME associations automatically.
- **[P2] Auto-extract icons from `.exe` resources.** Source: WinApps
  ships 91 hand-drawn SVGs (`third_party/winapps/apps/<name>/icon.svg`).
  Use `ExtractIconExW` (already on the Phase 4 followups list for RAIL
  window icons) to produce PNGs at discovery time. No hand-drawn art
  required, and the icon always matches whatever version of the app
  the user actually has installed.

## Operations & lifecycle (post-MVP)

UX commands for managing a running CrossDesk install. None of these
block MVP demo (which is `crossdesk install` + `crossdesk launch
notepad`) but each one materially improves the "I can rely on this"
feeling.

- **[P1] `crossdesk doctor` — pre-flight diagnostic.** Checks: libvirt
  service running and reachable (`virsh list` succeeds), KVM kernel
  module loaded, CPU virt extensions enabled
  (`grep -E 'vmx|svm' /proc/cpuinfo`), `qemu-system-x86_64` installed
  with version ≥ minimum, FreeRDP v3+ binary on PATH (using the
  fallback chain), VSOCK kernel module loaded, free disk space ≥ 30 GB
  for the install, `~/.config/crossdesk/` writable, GPU acceleration
  available (warning, not failure). Returns 0 if all green; non-zero
  with summary if any check fails. Saves users from cryptic
  mid-install errors. Touches `host/src/crossdesk_host/cli.py`,
  `host/src/crossdesk_host/diagnostics.py` (new). Wired as both a
  standalone command and a pre-step inside `crossdesk install`.
- **[P1] `crossdesk uninstall` — clean removal.** Removes: libvirt
  domain (`virsh destroy` + `virsh undefine --remove-all-storage`),
  every `~/.local/share/applications/crossdesk-*.desktop`, cached ISO
  at `~/.cache/crossdesk/iso/`, install state at
  `~/.local/state/crossdesk/`. Optionally preserves
  `~/.config/crossdesk/vm.toml` (with `--keep-config`) for reinstall.
  Confirms with the user before any destructive action; `--force`
  skips confirmation. Critical for trust — users won't try CrossDesk
  if they fear they can't get rid of it cleanly.
- **[✅ DONE 2026-05-10 / 🚧 PARTIAL — guest deferred] `crossdesk logs` — log aggregation.**
  Host (journalctl primary, JSONL file fallback), libvirt plain-text, FreeRDP log sources
  implemented. `--since`, `--follow`, `--component`, `--json`, `--lines` flags wired.
  Interleaved by timestamp. `--component guest` warns "not yet implemented (P2 scope)".
  Guest gRPC log pull is P2 (no in-process buffer RPC yet). 14 tests; mypy --strict clean.
  Implemented in `host/src/crossdesk_host/cli/logs_cmd.py`.
- **[P1] First-launch experience after `crossdesk install` succeeds.**
  Send a desktop notification ("CrossDesk is ready — run
  `crossdesk launch notepad` to test") via
  `org.freedesktop.Notifications`, write a brief next-steps file to
  `~/.config/crossdesk/getting-started.md`, optionally auto-launch
  Notepad as a smoke test if the user passed `--launch-test` to
  install. Don't open browsers or do anything else intrusive by
  default.
- **[P2] `crossdesk vm snapshot create|list|restore|delete`.** Wraps
  `virsh snapshot-create-as`, `snapshot-list`, `snapshot-revert`,
  `snapshot-delete`. UX: "make a checkpoint before installing risky
  software, restore if it breaks something." Requires VM in stopped
  or paused state for safe snapshots. Document storage growth (each
  snapshot is a disk-image overlay).
- **[P2] `crossdesk upgrade` — update CrossDesk and the in-VM agent.**
  Updates host packages (Python + Rust components) via the installer
  mechanism we ship with, then hot-swaps the in-VM `agent.exe` via
  gRPC `ControlService.UpgradeAgent` RPC: streams the new binary to
  the guest, agent stages it to a temp path, restarts the NT service
  to load the new binary. No Windows reinstall required. Older agents
  must remain forward-compatible with the new control protocol or
  `crossdesk upgrade` rejects with a clear "full reinstall required"
  notice (must check the protocol-version field we already reserved
  in `proto/`).
- **[P2] `crossdesk export-state` and `import-state` — backup/move
  the install.** Bundles `~/.config/crossdesk/`,
  `~/.local/state/crossdesk/`, and a libvirt domain XML dump into one
  tarball. `import-state` on another machine reproduces the setup
  (the VM disk image is referenced separately by default, with
  `--include-disk` for full portability at the cost of a 30 GB
  tarball). Critical insurance for users — losing `vm.toml` means
  losing access to a Windows install they may have spent days
  configuring.

---

# Skipped on purpose (do not implement)

These are documented in `docs/COMPARISON_WINAPPS.md` §7. Listed here as
guard-rails so they don't drift back in via casual feature-request:

- Docker / Podman backends — collides with `qemu:///session` constraint.
- `dockur/windows` container image — same reason.
- Static `\\tsclient\home` mount — security regression vs JIT VirtioFS.
- Bash-driven control flow — incompatible with async Python + mypy.
- `compose.yaml` — irrelevant without Docker.
- `renovate.json` / `flake.nix` — different packaging stack.
- Verbatim AGPLv3 file copies — license-incompatible direction.
- Tiny11 / Tiny10 / community-modified ISOs — unauthorized modification
  of MS source, distributed via archive.org without authoritative
  hashes, single-maintainer (NTDEV), known to break MS Office and
  Adobe activation. Superseded by our own Lean Windows profile which
  achieves comparable resource savings with official MS tools on
  official ISOs.
