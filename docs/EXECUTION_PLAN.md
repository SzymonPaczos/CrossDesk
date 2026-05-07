# Execution Plan to MVP (v0.1.0)

Today: **2026-05-07**.
Target: **MVP-pełny-z-VirtioFS** (Phases 1–5 + supporting cross-cutting work) — see `docs/MVP_SCOPE.md` for the full scope.
Estimated MVP date: **late 2026-10 / early 2026-11** (~24 weeks; assumes Linux+KVM hardware arrives by **2026-06-04** and one solo developer + AI agents working steadily).

This plan sequences items from `FOLLOWUPS.md` into weekly buckets with dependencies, acceptance criteria, and parallelization where possible. Each week has a primary theme; smaller cross-cutting items run in parallel.

The plan is **a living document**. As work progresses, push completed items off the list and add discoveries. Update the "Today" line and roll forward.

---

## How to use this plan

- An agent (or you) picks the **current week's primary work** as their next task.
- Items reference `FOLLOWUPS.md` sections by heading-keyword in italics.
- Dependencies between weeks are marked **Depends on:**.
- Each week has **Acceptance** — what must be true to consider the week done.
- Buffer weeks are real — don't compress them.

Branch naming: `feat/<short-task-name>` per task, merged locally to `main` (per user's directive — no GitHub PRs at this stage).

---

## Phase 0: Pre-agent foundation (now → ~2026-05-09)

### THIS WEEK
**Theme:** Bootstrap the agent workflow itself.

Items:
- ✅ `feat/pre-agent-setup`: CI workflow, `MVP_SCOPE.md`, `EXECUTION_PLAN.md`, AGENTS.md flow update — **this branch**
- Verify CI green on Mac + Ubuntu (manually trigger initial run)
- Pick first concrete week-1 task and begin

**Acceptance:**
- `.github/workflows/ci.yml` runs on push to main
- `docs/EXECUTION_PLAN.md` exists with weeks 1–24 sketched
- AGENTS.md describes how an agent picks a task, branch policy, and what files are off-limits
- First agent task selected and clearly defined

---

## Mac Vacuum Period (~4 weeks: 2026-05-08 → 2026-06-04)

No Linux+KVM hardware. Maximum work that can be validated on Mac via mocks and cross-compile.

### Week 1 (2026-05-08 → 2026-05-14)
**Theme:** Cross-platform scaffold foundation.

Source: *Cross-platform development & testing scaffold (URGENT)* in FOLLOWUPS.

Items:
- ✅ **[P0] Cross-compile pipeline working from macOS (native MinGW).** `brew install mingw-w64` + `rustup target add x86_64-pc-windows-gnu` + `cargo build --target x86_64-pc-windows-gnu` from `guest/`. Produces a working `agent.exe` PE32+ binary on Apple Silicon. Cross-rs end-to-end build is a known follow-up (P1 in FOLLOWUPS) — proto-IDL path lives outside the workspace mount cross-rs creates.
- ✅ **[P0] Transport abstraction** (DEC-0005). `tower::Service<Uri>` is the trait surface. `RealTransport` (TCP loopback today, AF_HYPERV later) and `MockTransport` (TCP loopback + failure-injection hooks, gated `#[cfg(any(test, feature="mock"))]`) both implement it. `channel::connect` uses `RealTransport`; tests use `connect_with_transport(...)` to inject mocks. Python mirror in `host/src/crossdesk_host/abstractions/transport.py` (`Transport` Protocol) + `transport/real.py` + `transport/mock.py`. `daemon.py` migrated; `ipc/server.py` kept as backwards-compat shim. Unit tests for both mocks.
- ✅ **[P0] Initial CI green.** All `cargo` jobs (check + test + clippy `-D warnings`) on macOS + Ubuntu run strict; mypy `--strict` and pytest run strict; GUI `cargo check` runs strict (cxx-qt 0.7 deps verified locally). Only `buf lint`/`format` remain tolerated (`|| true`) until `proto/buf.yaml` rules are finalised — tracked in FOLLOWUPS.

**Depends on:** Phase 0 done.
**Acceptance:**
- Cross-compile produces `agent.exe` on Mac without errors.
- All existing call sites of vsock socket use the `Transport` trait.
- `MockTransport` in both languages; unit tests for both.
- CI green (or yellow with documented `continue-on-error` items).

### Week 2 (2026-05-15 → 2026-05-21)
**Theme:** Mock infrastructure — libvirt + FreeRDP + integration harness.

Items:
- ✅ **[P0] Libvirt client abstraction.** `LibvirtController` Protocol in `host/src/crossdesk_host/abstractions/libvirt.py`. `RealLibvirtController` (Linux: wraps `libvirt-python`, lazy connect) and `LibvirtControllerMock` (in-memory state + per-method failure-injection hooks + share-tracking set) both implement it. `ipc/heartbeat.py` and `ipc/filesystem.py` consumers migrated to the Protocol type. Mock unit tests cover hooks + idempotent attach/detach. `infra/launch-vm.py` is plain qemu subprocess today (no libvirt yet) — migration deferred until install pipeline (Week 14).
- ✅ **[P0] FreeRDP invocation abstraction.** `FreeRDPInvocation` Protocol with `RailSession` dataclass. `RealFreeRDPInvocation` spawns via `subprocess.Popen` with the documented binary fallback chain (`xfreerdp` → `xfreerdp3` → `sdl-freerdp3` → `sdl3-freerdp` → `flatpak run com.freerdp.FreeRDP`); SIGTERM-then-SIGKILL terminate. `MockFreeRDPInvocation` records each argv to `hooks.spawned_argvs` and synthesises sequential pids. Consumer `display/rail_manager.py` doesn't yet wire FreeRDP (Phase 4 / Week 8); abstraction is ready when it does.
- **[P0] In-process integration test harness.** `host/tests/test_smoke_inprocess.py` drives Python host + spawned Rust guest (via `cargo run --features mock`) over `MockTransport`, exercising `Installer.run() → Launch(notepad) → RailWindowEvent(CREATED)` end-to-end.

**Depends on:** Week 1 transport abstraction.
**Acceptance:**
- libvirt and FreeRDP mocks compile, pass unit tests
- In-process integration test runs locally on Mac + on Ubuntu CI
- Smoke test exercises a full mock flow end-to-end

### Week 3 (2026-05-22 → 2026-05-28)
**Theme:** Observability foundation + structured logs.

Source: *Observability — structured logs, traces, metrics* in FOLLOWUPS.

Items:
- **[P0] `structlog` (Python) and `tracing` (Rust) JSON output.** Single facade per language. JSON Lines schema with `timestamp`, `level`, `component`, `trace_id`, `span_id`, `event`. Used by every other module.
- **[P0] Trace ID propagation via gRPC metadata.** W3C Trace Context. CLI commands generate fresh root trace ID; gRPC servicers extract and propagate; guest tags `RailWindowEvent` with originating trace.
- **[P0] In-memory metrics.** Counters: `launches_total`, `heartbeat_misses_total`, `mount_attaches_total`, `auth_context_rejections_total`. Histograms: `heartbeat_rtt_seconds`, `launch_duration_seconds`, `mount_lifetime_seconds`. Gauges: `vm_state`, `current_mounts`, `host_rss_bytes`. Use `hdrhistogram` library.
- **[P0] `print()` lint rule.** Ruff `T201` enabled. Rust workspace lints reject `println!`/`eprintln!`.
- **[P0] Redaction allow-list lint.** Frozen list of allowed field names. Logging non-allowed field raises in tests/dev. Forbidden patterns: `password`, `secret`, `token`.

**Depends on:** Week 1 + 2 (so observability can wrap mocked components).
**Acceptance:**
- Logs are JSON Lines with mandatory fields
- A test exercises trace ID propagation through the in-process harness
- Metrics histograms recorded by mock heartbeat round-trips
- CI rejects PRs that introduce `print()` or log forbidden field names

### Week 4 (2026-05-29 → 2026-06-04) — **Buffer + Phase 2 polish**
**Theme:** Phase 2 close-out + ready for hardware arrival.

Items:
- **[P0] AF_HYPERV vsock connector** — `guest/crates/ipc-vsock/src/connector.rs` real `WSAConnect` against `AF_HYPERV`, replacing TCP loopback. Currently in *Phase work still owed*. **This is hardware-bound** for end-to-end validation; can be implemented and unit-tested on Mac, integration-tested on hardware.
- **[P0] End-to-end mTLS smoke test against 32-byte `mount_token`.** Re-read `tests/test_smoke_e2e.py`; confirm any frame it emits over the wire carries a 32-byte token.
- **[P0] AuthContext per-frame validation tests.** Cover the rejection path: send a frame with mismatched fingerprint / nonce / sequence; verify it's rejected before payload processing.
- Buffer for: hardware arrival logistics, finalizing any Week 1–3 spillover

**Depends on:** Weeks 1–3.
**Acceptance:**
- Phase 2 (transport + mTLS + AuthContext) is feature-complete in code (real impl + mock impl + tests)
- Hardware procurement on track; first Linux+KVM machine available before Week 5

---

## Phase 3: Control FSM + Adaptive Heartbeat (~3 weeks: 2026-06-05 → 2026-06-25)

Hardware arrived. First period of integration testing on real Linux+KVM.

### Week 5 (2026-06-05 → 2026-06-11)
**Theme:** Hardware bring-up + Phase 3 FSM design implementation.

Items:
- **First-time end-to-end run on real hardware.** Follow `crossdesk` README quick-start; verify Phase 1 + Phase 2 + observability stack all work on real libvirt + qemu:///session. Document any environment quirks discovered.
- **[P0] Adaptive heartbeat FSM** (Phase 3 fundamental). Implement HEALTHY → DEGRADED → PROBING → SOFT_RECOVERY → HARD_DESTROY transitions in `host/src/crossdesk_host/watchdog/`. EWMA RTT calculation; configurable `miss_threshold` and decay constants.
- **[P0] FSM unit tests** — exercise every transition with mocked time and mocked heartbeats. No real VM needed for FSM correctness.

**Depends on:** Hardware available; transport from Phase 2.
**Acceptance:**
- Real VM (Phase 1 bootstrap) connects to host (Phase 2 transport) without crashes
- FSM transitions verified via unit tests; documented thresholds
- One end-to-end smoke test on real hardware completes successfully

### Week 6 (2026-06-12 → 2026-06-18)
**Theme:** Phase 3 — recovery actions + auth health-check.

Items:
- **[P0] SOFT_RECOVERY action** — `virsh shutdown` with timeout
- **[P0] HARD_DESTROY action** — `virsh destroy` then `virsh start`
- **[P0] Auth health-check before launch** (from Phase 4 follow-ups, but lands now). Host RPCs guest with current credentials; on FAIL surface clear error pointing at `crossdesk vm credentials repair`.
- **[P0] Two-layer health check** (Phase 3 follow-up). Extend FSM PROBING state with VSOCK listener confirmation + round-trip Heartbeat ping with synthetic AuthContext.

**Acceptance:**
- Killing the VM during operation triggers HARD_DESTROY → next launch succeeds within ≤90 s (N1.6a)
- Auth health-check rejects with credential-repair message when password is wrong
- FSM logs all transitions with trace IDs

### Week 7 (2026-06-19 → 2026-06-25)
**Theme:** Phase 3 close-out + lifecycle suspend/resume.

Source: *Lifecycle: power, suspend/resume, autostart* in FOLLOWUPS.

Items:
- **[P0] D-Bus listener for power events.** `dbus-next` on host's asyncio loop, subscribed to `org.freedesktop.login1.Session.PrepareForSleep` and `PrepareForShutdown`.
- **[P0] FSM `SUSPENDED` state.** Extends Phase 3 FSM. Missed heartbeats ignored while in SUSPENDED.
- **[P0] Suspend handler.** Pause FSM → quiesce in-flight RPCs → `virsh suspend` → release D-Bus inhibitor.
- **[P0] Resume handler.** `virsh resume` → `virsh domtime --sync` → AuthContext re-handshake → FSM exits SUSPENDED → PROBING grace period.
- **[P0] systemd user service unit.** `crossdesk-host.service` shipped in distro packages.

**Acceptance:**
- Suspending the laptop with VM running, resuming, leaves VM healthy without false-positive HARD_DESTROY
- systemd user service starts/stops cleanly with graphical session
- Phase 3 milestone: heartbeat FSM with full recovery path complete

---

## Phase 4: RAIL Display Integration (~6 weeks: 2026-06-26 → 2026-08-06)

The biggest single chunk. Display forwarding is intrinsically harder than control plane.

### Week 8 (2026-06-26 → 2026-07-02)
**Theme:** RAIL command construction + path translation.

Items:
- **[P0] FreeRDP RAIL command** (Phase 4 fundamental). Build the full `xfreerdp /app:program:...,hidef:on,icon:...,name:...,cmd:...` command in `host/src/crossdesk_host/display/rail_manager.py`. Use the WinApps template per `docs/COMPARISON_WINAPPS.md` §2.2 as starting point.
- **[P0] Path translation helper.** `$HOME/file` → guest mount path (Phase 5 will make this dynamic; for now use `\\tsclient\home` placeholder); `/` → `\` for Windows. Bind to live mount path from FilesystemService once Phase 5 lands.
- **[P0] FreeRDP version fallback chain.** Try `xfreerdp` → `xfreerdp3` → `sdl-freerdp3` → `sdl3-freerdp` → flatpak `com.freerdp.FreeRDP`. Helper in `host/src/crossdesk_host/display/`.

**Acceptance:**
- Manually triggering a launch from a debug script produces a Notepad RAIL window on the host's X11 (XWayland on Wayland)
- Window class hint matches the app catalog name
- Path translation unit tests pass

### Week 9 (2026-07-03 → 2026-07-09)
**Theme:** RAIL window lifecycle event handling.

Items:
- **[P0] `RailWindowEvent` consumer.** In `rail_manager.py`. CREATED → spawn FreeRDP RAIL session, set WM_CLASS; DESTROYED → close session; FOCUS/TITLE/ICON/MOVED/RESIZED → update WM hints.
- **[P0] Idempotence + ordering tolerance** (Phase 4 SPOF). Handle out-of-order CREATED/FOCUS arrivals, repeated DESTROYED, MOVED for unknown window_id (race with CREATED).
- **[P0] RAIL window icon extraction** (in *Phase work still owed*). `ExtractIconExW` + PNG-encode for KIND_CREATED and KIND_ICON_CHANGED in `guest/crates/rail-bridge/src/events.rs`.

**Acceptance:**
- Launching Notepad twice produces two separate RAIL windows
- Closing one does not affect the other
- Window list in compositor shows correct titles and icons
- Tests cover out-of-order events without leaking windows or processes

### Week 10 (2026-07-10 → 2026-07-16)
**Theme:** Critical Windows registry tweaks + Phase 4 polish.

Items:
- **[P0] Registry tweaks** (Phase 1 follow-up but blocks Phase 4 RAIL). Port `RDPApps.reg` from WinApps to our `infra/RDPApps.reg`. Wire into `<FirstLogonCommands>` in `infra/autounattend.xml`. Critical keys per `docs/COMPARISON_WINAPPS.md` §2.1: `fDenyTSConnections=0`, `UserAuthentication=1`, `fDisabledAllowList=1`, `fAllowUnlistedRemotePrograms=1`, `IgnoreRemoteKeyboardLayout=1`.
- **[P0] HiDPI auto-detect** (Phase 4 follow-up). Read effective scale (Wayland `wl_output.scale`, X11 RANDR, GNOME `gsettings`, KDE `kreadconfig5`); map to nearest FreeRDP supported scale (100/140/180); re-evaluate on monitor change events.
- **[P0] MS Office URL scheme handler.** Port `apps/ms-office-protocol-handler.desktop` from WinApps; install into `~/.local/share/applications/`.

**Acceptance:**
- New VM (re-installed via autounattend) has RAIL working without manual `regedit` step
- Notepad window scales appropriately on a HiDPI monitor
- Clicking `ms-word://example.docx` in a browser launches Word in the VM (verifiable manually with mock browser)

### Week 11 (2026-07-17 → 2026-07-23)
**Theme:** Multi-monitor MVP + lifecycle integration.

Items:
- **[P0] Multi-monitor RAIL window placement.** Enumerate monitors via `xdg_output_manager` (Wayland) or RANDR (X11). Per-window placement via `_NET_WM_DESKTOP` / Wayland output hints.
- **[P0] Notify-send equivalent for host errors.** Wire host-side errors (VM won't start, forced stop, RDP drop) to `org.freedesktop.Notifications`.
- **Phase 4 milestone integration test:** launch Notepad, Calc, and CMD simultaneously; verify three independent windows; suspend host; resume; verify all three still work.

**Acceptance:**
- Multi-monitor: each launched window opens on its appropriate monitor (placement preferred but not strictly required at MVP — accept bugs per DEC discussion)
- D-Bus notifications fire on tested error paths

### Week 12 (2026-07-24 → 2026-07-30)
**Theme:** Performance budget enforcement + perf benchmark harness.

Source: *Performance budgets — enforcement* in FOLLOWUPS.

Items:
- **[P0] `pytest-benchmark` and `criterion` harness configured.** `host/benches/` and `guest/benches/`. One bench file per N1.* metric (stubs OK initially).
- **[P0] `bench_check.py` tool.** Compares JSON results to `.github/perf-baselines.json`; fails on >20% regression.
- **[P0] CI job `microbench`** on every PR. Runs benches, invokes `bench_check.py`, posts a comment summary.
- **[P0] Initial baselines committed** — first measurements with placeholder values until real measurements replace them.

**Acceptance:**
- Microbench CI job is green
- A deliberate slowdown in a heartbeat path causes CI to fail
- Baselines are committed and update via dedicated PR

### Week 13 (2026-07-31 → 2026-08-06) — **Buffer + Phase 4 close-out**
**Theme:** Phase 4 polish, RAIL milestone integration test, ready for install pipeline.

Items:
- Verify all Phase 4 acceptance from prior weeks holds together
- Versioning handshake (DEC-0007) — implement `Hello` message + N-1 minor compat matrix in client + server. Currently in *Versioning & compatibility* in FOLLOWUPS.
- Buffer for spillover

**Acceptance:**
- Phase 4 milestone: `crossdesk launch <app>` works for at least Notepad, Calc, CMD on a freshly-installed VM
- Hello handshake exchanges versions on connect; rejects mismatched majors

---

## Install pipeline + onboarding (~3-4 weeks: 2026-08-07 → 2026-09-03)

This phase makes `crossdesk install` work end-to-end. Many small interdependent pieces.

### Week 14 (2026-08-07 → 2026-08-13)
**Theme:** ISO downloader + install state machine.

Items:
- **[P0] Auto-download Windows ISO via Fido-style scrape.** Port Fido logic to Python in `infra/iso_downloader.py`. Default behavior: `crossdesk install` with no `--iso-path` triggers download. Cache to `~/.cache/crossdesk/iso/`. Validate SHA256 against `infra/known_isos.toml`.
- **[P0] Install state machine.** `~/.local/state/crossdesk/install.state.json` — atomic per-step writes (write to `*.tmp`, fsync, rename).
- **[P0] `crossdesk install` skeleton.** Top-level subcommand that orchestrates the steps documented in `docs/MVP_SCOPE.md` and FOLLOWUPS bootstrap item.

### Week 15 (2026-08-14 → 2026-08-20)
**Theme:** VM credential management + install end-to-end on hardware.

Items:
- **[P0] VM credential management.** `crossdesk vm credentials show|rotate|set|repair`. Two-phase commit on rotate. Generate random username + password at install time, persist atomically to `~/.config/crossdesk/vm.toml` (mode 0600).
- **[P0] First end-to-end `crossdesk install` run on real hardware.** Wall-clock timing, user-attended timing both measured against N1.7 budget.
- **[P0] Network mode in libvirt domain XML.** Default to NAT explicitly in `infra/launch-vm.py`. Optional `--network=bridge` for advanced.
- **[P0] EULA acceptance verified** in `infra/autounattend.xml`.

**Acceptance:**
- `crossdesk install` succeeds on a fresh Linux host within 25 minutes wall-clock and 2 minutes user-attended
- Credentials accessible via `crossdesk vm credentials show`
- `crossdesk vm credentials rotate` updates host file + Windows password atomically

### Week 16 (2026-08-21 → 2026-08-27)
**Theme:** Lean profile + i18n setup.

Source: *Internationalization* in FOLLOWUPS + lean profile from FOLLOWUPS.

Items:
- **[P0] CrossDesk Lean profile** (opt-in via `crossdesk install --lean`). `infra/lean_profile.ps1` invoked from `<FirstLogonCommands>` in `autounattend.xml`. Removes Edge, Cortana, OneDrive setup, Teams personal, Xbox app etc. Keeps .NET, Visual C++, Windows Update, Windows Defender.
- **[P0] gettext + Qt tr() i18n setup.** Configure in Python host + QML. Mark all user-facing strings. Build tooling (`Makefile` or `scripts/i18n.sh`).
- **[P0] Polish translations** for the install flow + main CLI commands.

**Acceptance:**
- `crossdesk install --lean` produces a Win11 image with idle RAM ≤1.5 GB (N1.5a)
- All user-facing strings in `crossdesk install` and `crossdesk launch` available in Polish
- `LANG=pl_PL.UTF-8 crossdesk install --help` displays Polish text

### Week 17 (2026-08-28 → 2026-09-03) — **Buffer + onboarding close-out**
**Theme:** `crossdesk doctor` + `crossdesk uninstall`.

Source: *Operations & lifecycle (post-MVP)* in FOLLOWUPS — but doctor and uninstall are MVP per `docs/MVP_SCOPE.md`.

Items:
- **[P1] `crossdesk doctor`** — pre-flight checks (libvirt running, KVM module, virt extensions, FreeRDP v3+, VSOCK module, disk space, GPU acceleration warning, etc.).
- **[P1] `crossdesk uninstall`** — removes libvirt domain, `.desktop` files, cached ISO, install state. `--keep-config` preserves `vm.toml` for reinstall.
- **[P0] First-launch experience.** D-Bus notification ("CrossDesk is ready") + `~/.config/crossdesk/getting-started.md` after install completes successfully.
- Buffer for any onboarding flow polish

**Acceptance:**
- `crossdesk doctor` returns 0 on healthy host; surfaces actionable errors otherwise
- `crossdesk uninstall` cleanly removes everything; reinstall after uninstall works
- New user runs install, sees notification, follows getting-started.md, runs `crossdesk launch notepad` successfully

---

## Phase 5: JIT VirtioFS + ReleaseAck (~3-4 weeks: 2026-09-04 → 2026-10-01)

The remaining phase — and a security-positioning differentiator vs WinApps's static `\\tsclient\home`.

### Week 18 (2026-09-04 → 2026-09-10)
**Theme:** Real virtiofs mount/flush implementation.

Source: *Phase work still owed* in FOLLOWUPS.

Items:
- **[P0] Real virtiofs mount.** Replace `guest/crates/fs-mount/src/mount.rs::mock_handle_mount_request` with WinFSP/virtiofs-backed implementation.
- **[P0] Real flush logic.** Replace `mock_generate_lock_report` and `mock_generate_release_ack` with real handle-tracking based on Windows `NtQueryInformationFile`.
- **[P0] Path traversal blocking** at the FilesystemService boundary. Reject `..`, normalize paths, refuse absolute paths in mount-relative ops.

### Week 19 (2026-09-11 → 2026-09-17)
**Theme:** ReleaseAck protocol + libvirt hot-plug integration.

Items:
- **[P0] ReleaseAck handshake** (Phase 5 SPOF). Detach happens after ReleaseAck, never before. No ReleaseAck → permanent leak; surface as a recovery scenario.
- **[P0] libvirt `attach-device` / `detach-device` integration.** When user opens a file: host computes minimal-path share → `virsh attach-device` with virtiofs config → guest mounts → guest application reads file → on close, guest emits LockReport(0) → guest emits ReleaseAck → host runs `virsh detach-device`.
- **[P0] mount_token random + validated.** 32-byte token; host generates per-mount; guest echoes token on every related RPC; reject mismatched tokens.

### Week 20 (2026-09-18 → 2026-09-24)
**Theme:** Phase 5 integration + path translation finalization.

Items:
- **[P0] Wire JIT path into RAIL command** (Phase 4 path translation completion). `host/src/crossdesk_host/display/rail_manager.py` now uses live JIT mount path from FilesystemService instead of `\\tsclient\home` placeholder.
- **[P0] MIME-type-aware open.** Right-click `.txt` → "Open with Notepad" path: file manager passes file path → CrossDesk handler activates JIT mount on that file's parent directory → spawns `crossdesk launch notepad <file>` → translated path forwarded to RAIL → Notepad opens it.
- **[P0] Phase 5 integration test on hardware.** Open file, verify mount appears, file opens in app, close app, verify mount disappears. Trace IDs cover the full flow.

**Acceptance:**
- Right-clicking a `.txt` and choosing Notepad opens it through the JIT mount
- Mount detaches within 5 seconds after Notepad closes
- `lsblk` / `findmnt` on guest before and after confirm mount lifecycle
- Path traversal attempts in `MountResult` rejected with structured error

### Week 21 (2026-09-25 → 2026-10-01) — **Buffer + Phase 5 close-out**
**Theme:** Phase 5 polish, integration with auth health-check + heartbeat FSM, full system smoke test.

Items:
- ReleaseAck-on-HARD_DESTROY: when the heartbeat FSM forces destroy, the host force-detaches all live mounts immediately; logs as warnings but doesn't wait for ReleaseAck (the guest is gone).
- Buffer for unexpected Phase 5 issues
- Full-system smoke test: install fresh + launch + open file + suspend + resume + close app + uninstall, all with trace IDs verifiable in `crossdesk logs`.

---

## MVP Polish + Release (~2-3 weeks: 2026-10-02 → 2026-10-22)

### Week 22 (2026-10-02 → 2026-10-08)
**Theme:** AUR + NixOS + PyPI packaging.

Source: *Distribution & packaging* in FOLLOWUPS.

Items:
- **[P0] AUR PKGBUILD published.** First package format. Initial maintenance by us; community welcome.
- **[P0] NixOS flake outputs.** `flake.nix` at repo root with `crossdesk` and `crossdesk-gui` derivations. Reference winapps' flake pattern.
- **[P0] PyPI wheel for `crossdesk-host`.** Host module installable via `pip install --user crossdesk-host`.
- **[P0] CI release matrix** on tag. Build agent.exe via cross-rs, package per-format, upload to GitHub Releases.

**Acceptance:**
- A test user on Arch can `yay -S crossdesk` and run `crossdesk install`
- A NixOS user can `nix run github:SzymonPaczos/CrossDesk#crossdesk`
- PyPI release works for developer install

### Week 23 (2026-10-09 → 2026-10-15)
**Theme:** README + getting-started + final integration test pass.

Items:
- **README quick-start polished.** Tested with a non-trivial new user (someone unfamiliar with the project).
- **Getting started doc.** Linked from first-launch experience.
- **All MVP acceptance criteria** from `docs/MVP_SCOPE.md` re-verified.
- **N1 performance budgets** confirmed against committed baselines on real hardware.

**Acceptance:**
- A user given only the README can install and launch Notepad without external help
- All 12 MVP acceptance criteria pass

### Week 24 (2026-10-16 → 2026-10-22) — **MVP RELEASE WEEK**
**Theme:** Tag v0.1.0, ship.

Items:
- **Tag `v0.1.0` on `main`.** Release notes pulled from CHANGELOG (auto-generated from Conventional Commits).
- **CI release artifacts uploaded** to GitHub Releases.
- **Update README badges** to "v0.1.0 stable" or similar.
- **Public announcement.** Hacker News, /r/linux, /r/VFIO, /r/winapps community, Polish FOSS communities (since Polish is a first-class language). Demo video or GIF.

**Acceptance:**
- v0.1.0 GitHub release exists with artifacts
- A fresh user from a community link can follow the README, install, launch Notepad
- No critical issues in first 48 hours of release

---

## After MVP

In rough order, per `FOLLOWUPS.md`:

1. **Phase 4.5 — GPU passthrough Tier 1** (~3-4 weeks). NVIDIA RTX modern + AMD RDNA2/3 multi-GPU. Per DEC-0009.
2. **Looking Glass integration** (~5-7 weeks). Single-GPU support via hot-switch + Desktop mode opt-in for power users.
3. **App discovery service** (~2-3 weeks). PowerShell/Rust enumeration of installed Windows apps from registry + UWP + Chocolatey + Scoop.
4. **`.desktop` generation** for discovered apps + auto-MIME from registry.
5. **deb/rpm packaging** with hosted apt + Copr/OBS repos.
6. **Wayland-native RAIL.**
7. **Peripherals** (audio per-app PipeWire, clipboard rich, drag-and-drop, microphone, printer, smartcard, USB).
8. **Tier 2 GPU support** (AMD older with vendor-reset, NVIDIA old with hide-the-VM) — documentation only.
9. **Other operations & lifecycle commands** (snapshot, upgrade, export-state).
10. **Additional translations** (community-driven, beyond English + Polish).

---

## Schedule risks and mitigations

| Risk | Mitigation |
|------|------------|
| Hardware doesn't arrive by Week 5 | Extend Mac vacuum work; bench more weeks of mock work; do install pipeline (Week 14) earlier in mocked form |
| Phase 4 RAIL takes longer than 6 weeks | Cut multi-monitor polish (week 11 already accepts bugs at MVP) and HiDPI auto-detection; keep them post-MVP |
| Phase 5 VirtioFS proves harder than 4 weeks | Drop the right-click "Open with" MIME flow; require user to drag file or pass path explicitly. Document the limitation. |
| Solo developer burnout | Buffer weeks (4, 13, 17, 21) are real — don't compress them under any circumstances |
| Linux+KVM hardware fails or is delayed | Cloud GPU instance (AWS p4 / GCP A100) as a temporary stand-in for KVM access; expensive but functional |

---

## Living-document conventions

When a week completes:

1. Mark items `✅` next to them.
2. If a week ran over, push the next week's items forward and note the slip.
3. If a week ran under, pull next week's items in and shorten the timeline.
4. Update the "Today" line at the top.

When discoveries surface new work:

1. Add to `FOLLOWUPS.md` first under the appropriate section.
2. Reference here only if it affects this plan's sequencing.
