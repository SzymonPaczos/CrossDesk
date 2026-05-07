# Requirements

What the system must do (functional, F\*) and how well it must do it
(non-functional, N\*). Each requirement is uniquely numbered; phases
in `ROADMAP.md` and items in `FOLLOWUPS.md` reference these IDs.

**MVP scope:** v0.1.0 = Phases 1–5 (full pipeline including JIT
VirtioFS) plus supporting cross-cutting work. See `docs/MVP_SCOPE.md`
for the concrete list and acceptance criteria.

Status legend per requirement: ✅ implemented · 🔄 in progress ·
❌ not started.

## Functional requirements

### F1. Install pipeline (Phase 1 + follow-ups)

- F1.1 ❌ — `crossdesk install` brings a fresh system from "no VM" to
  "agent registered and reachable" in one command.
- F1.2 ❌ — Auto-download Windows ISO from Microsoft if no path
  supplied (Fido-style scrape; manual `--iso-path` fallback).
- F1.3 ❌ — Validate ISO SHA256 against a curated list before install.
- F1.4 ❌ — Generate VM credentials atomically; never write the
  password to logs or stdout outside the explicit `credentials show`
  path.
- F1.5 ❌ — Idempotent resume after crash, kill, or power loss
  (`~/.local/state/crossdesk/install.state.json`).
- F1.6 ❌ — Optional Lean Windows profile via `--lean`
  (`infra/lean_profile.ps1`).
- F1.7 ❌ — Equivalent UI flow in the Qt6/QML wizard with "Quick" and
  "Custom" paths sharing one engine.
- F1.8 ✅ — `autounattend.xml` performs unattended Windows install.
- F1.9 ✅ — `agent.exe` registers as `CrossDeskAgent` NT service via
  `<FirstLogonCommands>`.

### F2. App lifecycle (Phase 4)

- F2.1 ❌ — `crossdesk launch <app>` starts the named app and produces
  a native Linux window via FreeRDP RAIL.
- F2.2 ❌ — File arguments forwarded with path translation
  (`$HOME/file` → guest-visible mount path; `/` → `\`).
- F2.3 ❌ — Windows-side file argument is opened in the named app, not
  a default handler.
- F2.4 ❌ — Multi-instance launch: invoking the same app twice
  produces two separate windows.
- F2.5 ❌ — `.desktop` files generated for discovered apps so they
  appear in the Linux app menu.
- F2.6 ❌ — MS Office URL scheme handler (`ms-word://`, `ms-excel://`,
  …) routes to the VM.

### F3. App discovery

- F3.1 ❌ — Enumerate installed Windows apps from registry App Paths,
  Uninstall keys (HKLM + HKCU + WOW6432Node), UWP packages,
  Chocolatey, and Scoop.
- F3.2 ❌ — Extract icons from `.exe` resources where catalog icons
  are not available.
- F3.3 ❌ — Auto-derive MIME types from `HKCR\<ext>` registry.

### F4. Transport & control plane (Phase 2)

- F4.1 🔄 — gRPC over `AF_VSOCK` with mTLS and per-frame
  `AuthContext`.
- F4.2 🔄 — Bidirectional streams; no polling on either side.
- F4.3 🔄 — Reject any frame failing `AuthContext` validation —
  fingerprint, nonce, or sequence mismatch — with no payload
  processing.

### F5. Recovery & observability (Phase 3 + follow-ups)

- F5.1 ❌ — Adaptive heartbeat FSM walks HEALTHY → DEGRADED →
  PROBING → SOFT_RECOVERY → HARD_DESTROY based on EWMA RTT and miss
  count.
- F5.2 ❌ — `crossdesk doctor` runs pre-flight checks; `crossdesk
  logs` aggregates host + libvirt + guest + FreeRDP; `crossdesk
  status` reports current FSM state.
- F5.3 ❌ — Auth health-check before every RAIL launch.

### F6. Filesystem (Phase 5)

- F6.1 ❌ — JIT VirtioFS hot-plug per file open; detach on
  `ReleaseAck`.
- F6.2 ❌ — Mount path leaks no other host directories to the guest.
- F6.3 ❌ — Path traversal blocked at the filesystem service.

### F7. Credentials

- F7.1 ❌ — `crossdesk vm credentials show|rotate|set|repair`.
- F7.2 ❌ — Two-phase commit on rotation: guest accepts → host file
  rewritten atomically. Rollback on partial failure; clear surfaced
  error on irrecoverable divergence.
- F7.3 ❌ — `show` refuses non-TTY stdout unless `--unsafe-stdout`.

### F8. Lifecycle commands

- F8.1 ❌ — `crossdesk uninstall` — clean removal.
- F8.2 ❌ — `crossdesk vm snapshot create|list|restore|delete`.
- F8.3 ❌ — `crossdesk upgrade` — host components + agent hot-swap.
- F8.4 ❌ — `crossdesk export-state` / `import-state` — backup &
  migrate.

## Non-functional requirements

### N1. Performance budgets

Differentiated where the workload realistically differs (e.g., a
Notepad cold launch is not a Photoshop cold launch). Budgets are
grounded in measured baselines from comparable VM-on-Linux setups
and in physical constraints (Windows idle footprint, FreeRDP RAIL
session setup latency, virtio-balloon dynamics).

| ID | Metric | Budget |
|----|--------|--------|
| N1.1a | Cold launch — lightweight app (Notepad, calc, cmd) | ≤3 s p50, ≤6 s p99 |
| N1.1b | Cold launch — productivity app (Word, Outlook, VS Code) | ≤8 s p50, ≤15 s p99 |
| N1.1c | Cold launch — heavy app (Photoshop, Premiere, Visual Studio) | ≤15 s p50, ≤30 s p99 |
| N1.2 | Heartbeat round-trip (steady state) — user-facing budget | <20 ms p50, <100 ms p99 |
| N1.2-internal | Heartbeat round-trip — internal stress target | <5 ms p50, <30 ms p99 |
| N1.3 | Host process resident memory (Python + asyncio + grpcio + libvirt + app) | <300 MB RSS excluding subprocesses |
| N1.4 | Guest agent resident memory (Rust NT service) | <50 MB |
| N1.5a | Idle VM memory — Lean profile, with virtio-balloon | ≤1.5 GB |
| N1.5b | Idle VM memory — full Win11 Pro, with virtio-balloon | ≤2.5 GB |
| N1.6a | Failed-VM-recovery — destroy + start (cold path) | ≤90 s from kill to next successful launch |
| N1.6b | Failed-VM-recovery — snapshot revert (warm path, when available) | ≤20 s from kill to next successful launch |
| N1.7 | `crossdesk install` user-attended time | ≤2 min user attention; wall-clock 15-25 min unattended |

Notes on rationale:

- **N1.1 differentiation:** Notepad starts in 0.3 s on a real Windows;
  Word takes 2-5 s; Photoshop takes 5-10 s. Adding ~1-2 s for FreeRDP
  RAIL session setup means the user-visible cold launch budget has to
  scale with the app class.
- **N1.2:** AF_VSOCK round-trip is microseconds at the kernel level.
  TLS + protobuf serialize + AuthContext check adds milliseconds, not
  hundreds. Earlier 100 ms p50 budget was 10× too loose; we budget
  honestly here while leaving headroom for outliers.
- **N1.3:** A bare CPython interpreter is ~30 MB; with grpcio,
  libvirt-python, asyncio internals, and our application logic, the
  realistic floor is 150-250 MB. Budget is 300 MB, expecting most of
  that gets used.
- **N1.5:** Microsoft's "4 GB minimum to install Windows 11" is the
  install-time minimum, not the steady-state idle. Measured idle
  footprints: Win11 Pro fresh install ~2-2.5 GB, Lean profile ~1.2-
  1.5 GB, Tiny11 (community, rejected per `FOLLOWUPS.md`)
  ~600-800 MB. Our budget reflects what our Lean profile actually
  achieves, not what Tiny11 achieves.
- **N1.6:** A full destroy/start cycle includes Windows boot which
  takes 30-60 s on a typical NVMe. 90 s is the realistic worst case.
  Snapshot revert skips most of that.

Performance budgets are normative — see `docs/DECISIONS.md` DEC-0004.
A regression beyond budget by more than 20% on any metric is a
release blocker, not a "nice to fix later."

### N2. Security

- N2.1 — Host process never elevates beyond user privileges. No
  setuid binaries.
- N2.2 — VM is the trust boundary. Every gRPC frame must carry a
  validated `AuthContext`.
- N2.3 — No host directory is exposed to the guest unless a JIT
  VirtioFS mount is active for an open file.
- N2.4 — Credentials persist with mode 0600. `show` is TTY-gated.
- N2.5 — `agent.exe` is signed (Sigstore initially; EV cert is a
  follow-up).
- N2.6 — Zero telemetry — see `docs/DECISIONS.md` DEC-0004.

Full threat analysis: `docs/THREAT_MODEL.md`.

### N3. Reliability

- N3.1 — Idempotent install: re-running after partial failure resumes
  deterministically.
- N3.2 — No state lost on host suspend/resume.
- N3.3 — No false-positive HARD_DESTROY under normal load.

### N4. Compatibility

- N4.1 — Linux host: KVM-capable kernel, libvirt ≥7.0, FreeRDP ≥3.0.
- N4.2 — Windows guest: Win10 Pro/Enterprise/Server, Win11
  Pro/Enterprise/IoT LTSC. Home is unsupported (no RDP server).
- N4.3 — Display: Wayland and X11 first-class. No XWayland-specific
  hacks where avoidable.
- N4.4 — Linux distros: Debian/Ubuntu/Fedora/Arch/openSUSE/NixOS as
  primary. Distro-specific scripts isolated in `infra/`.

### N5. Operability

- N5.1 — Structured JSON logging from day one.
- N5.2 — Trace ID propagation across host↔guest gRPC.
- N5.3 — `crossdesk doctor` returns non-zero with summary on any
  failed precondition.

### N6. Maintainability

- N6.1 — Python: `mypy --strict`, `pytest`, `black`, asyncio
  end-to-end, no polling.
- N6.2 — Rust: `cargo clippy`, `cargo test`, `unwrap()` requires
  one-line comment justifying infallibility.
- N6.3 — All public protocol changes go through `proto/` codegen.
- N6.4 — Conventional Commits.

### N7. Internationalization

- N7.1 — UI strings extractable into a catalog format from day one.
- N7.2 — At minimum: English + Polish on first release.
