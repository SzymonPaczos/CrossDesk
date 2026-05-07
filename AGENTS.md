# AGENTS.md

Navigation for AI agents and new human contributors working on
CrossDesk. Read this first.

## Project at a glance

CrossDesk runs Windows applications as native Linux windows. A Linux
host (Python) controls a Windows VM (libvirt `qemu:///session`) over
gRPC/AF_VSOCK with mTLS and per-frame authentication. A Rust NT
service in the guest forwards window events to the host, which spawns
FreeRDP RAIL processes to render each app as its own native Wayland
or X11 window.

Status: pre-release. Phase 1 (VM bootstrap + NT service) complete.
Phase 2 (transport) in progress. Phases 3–5 not started. See
`ROADMAP.md`.

## Where things are

| Question | Answer |
|----------|--------|
| What does CrossDesk *do*? | `README.md` + `docs/GOALS.md` |
| What must it do, how well? | `docs/REQUIREMENTS.md` |
| Why this stack? | `docs/TECH_STACK.md` |
| What does the architecture look like? | `docs/GOALS.md` (vision) + `docs/TECH_STACK.md` (components) |
| What's the security model? | `docs/THREAT_MODEL.md` |
| What's the roadmap? | `ROADMAP.md` (phases) + `FOLLOWUPS.md` (action items) |
| Why X over Y? | `docs/DECISIONS.md` (ADRs `DEC-NNNN`) |
| What does the competition look like? | `docs/COMPETITION.md` + `docs/COMPARISON_WINAPPS.md` |
| Coding rules? | The "Coding rules" section below |
| Anything in `third_party/`? | `third_party/winapps/` — vendored for reference, AGPLv3, do not copy verbatim |

## Repository layout

```
crossdesk/
├── README.md                 # pitch + quick start
├── ROADMAP.md                # 5 phases, terse
├── FOLLOWUPS.md              # action-item tracking, prioritized by area
├── AGENTS.md                 # this file — navigation + coding rules
│
├── docs/
│   ├── GOALS.md              # vision, primary goals, non-goals, success criteria
│   ├── REQUIREMENTS.md       # F* functional, N* non-functional
│   ├── TECH_STACK.md         # what we picked and why
│   ├── THREAT_MODEL.md       # STRIDE per component
│   ├── COMPETITION.md        # landscape — WinApps, Cassowary, Wine, etc.
│   ├── COMPARISON_WINAPPS.md # deep comparison with the vendored WinApps
│   ├── DECISIONS.md          # ADRs (DEC-NNNN). Newest at top.
│   ├── GPU_PASSTHROUGH.md    # full deliberation, decision pending
│   ├── CROSS_PLATFORM_DEV.md # mock-driven testing strategy (Mac vacuum + long-term)
│   ├── DISPLAY.md            # RAIL pipeline, Wayland-native, multi-monitor, HiDPI
│   ├── PERIPHERALS.md        # audio, clipboard, DnD, mic/cam, smartcard, printer, USB
│   ├── OBSERVABILITY.md      # structured logs, trace propagation, in-memory metrics
│   ├── PERFORMANCE.md        # benchmark harness + CI integration for SLO enforcement
│   ├── VERSIONING.md         # semver, N-1 minor compat window, Hello handshake
│   ├── PACKAGING.md          # deb/rpm/AUR/NixOS/PyPI; skipped Flatpak/AppImage/Snap
│   ├── LIFECYCLE.md          # suspend/resume FSM coordination, systemd, autostart
│   └── I18N.md               # gettext + Qt tr; English + Polish initial
│
├── host/                     # Python 3.9+ host daemon
│   ├── pyproject.toml
│   ├── conftest.py
│   ├── build_proto.py
│   ├── src/crossdesk_host/
│   │   ├── ipc/              # gRPC servicers (control, heartbeat, filesystem, auth)
│   │   ├── display/          # RAIL spawning (Phase 4)
│   │   ├── watchdog/         # heartbeat FSM (Phase 3)
│   │   ├── proto/            # generated proto stubs (regenerated via build_proto.py)
│   │   └── installer/        # crossdesk install engine (planned)
│   └── tests/
│
├── guest/                    # Rust NT service workspace
│   └── crates/
│       ├── agent-svc/        # NT service entry point + windows-rs
│       ├── ipc-vsock/        # AF_VSOCK transport (still TCP-loopback in dev — see FOLLOWUPS)
│       ├── proto/            # tonic-generated proto types
│       ├── rail-bridge/      # RAIL window event forwarding
│       └── fs-mount/         # JIT VirtioFS mount/flush handlers
│
├── gui/                      # Qt6/QML wizard (CXX-Qt)
│   └── crates/crossdesk-gui/
│
├── proto/                    # gRPC IDL — single source of truth
│   ├── buf.yaml
│   └── crossdesk/v1/         # control, heartbeat, filesystem, common
│
├── infra/                    # PKI, autounattend, VM launch
│   ├── certs/                # mTLS PKI artifacts (leaves are gitignored)
│   ├── autounattend.xml      # Windows unattended install
│   └── launch-vm.py          # libvirt domain creation
│
└── third_party/winapps/      # vendored reference (AGPLv3); see docs/COMPARISON_WINAPPS.md
```

## Build & test

```sh
# Host (Python)
cd host && pip install -e . && mypy --strict src/ && pytest

# Guest (Rust, cross-compiled for Windows — required for production)
cd guest && cargo build --release --target x86_64-pc-windows-gnu

# Guest (sanity check on dev host — Mac or Linux)
cd guest && cargo check --workspace

# GUI
cd gui && cargo run -p crossdesk-gui

# Proto regeneration (after editing any .proto)
cd host && python build_proto.py     # regenerates host stubs
cd guest && cargo build              # tonic regenerates guest stubs as part of build
```

## Coding rules

- **No Docker.** Host runs against `qemu:///session` libvirt directly.
  See `docs/DECISIONS.md` DEC-0003.
- **No polling.** Async gRPC streams both ways. No
  `while True: sleep`.
- **Rust:** idiomatic; `unwrap()` / `expect()` need a one-line comment
  explaining infallibility.
- **Python:** asyncio end-to-end, full type hints, `mypy --strict`,
  `black` formatting.
- **Commits:** Conventional Commits.
- **Don't leave TODO** placeholders in merged code; file an issue.
- **Comments explain *why*, not *what*.** The code already says what
  it does.
- **Diffs scoped:** a fix doesn't bundle a refactor.

## Patterns when contributing

- **New RPC:** edit `proto/crossdesk/v1/<service>.proto` →
  regenerate stubs (`python build_proto.py` for host, `cargo build`
  for guest) → implement servicer in
  `host/src/crossdesk_host/ipc/<service>.py` → wire into the FSM in
  `host/src/crossdesk_host/watchdog/` if it affects lifecycle.
- **New install step:** lives in `host/src/crossdesk_host/installer/`
  (planned). Must be idempotent. Must update
  `~/.local/state/crossdesk/install.state.json` atomically (write to
  `*.tmp`, fsync, rename).
- **Touching the security model:** any change requires updating
  `docs/THREAT_MODEL.md` and at least one ADR in
  `docs/DECISIONS.md`.
- **New configuration field:** typed schema in
  `host/src/crossdesk_host/config.py` (planned). Document in
  `docs/REQUIREMENTS.md`. No bash-source-style config — typed only.

## What to read first as a new agent

1. This file.
2. `README.md` — pitch.
3. `docs/GOALS.md` — what we're trying to do.
4. `docs/TECH_STACK.md` — components and stack rationale.
5. `docs/THREAT_MODEL.md` — what we're defending against.
6. `FOLLOWUPS.md` — what's queued, prioritized.

For any specific question, the navigation table at the top of this
file should point you at the right doc.

## When you find something unclear or contradictory

The docs are the source of truth in roughly this order of authority:

1. `docs/THREAT_MODEL.md` for security claims.
2. `docs/REQUIREMENTS.md` for "what must this do."
3. `docs/DECISIONS.md` for "why X over Y."
4. `docs/TECH_STACK.md` for component-level design.
5. `docs/GOALS.md` for vision and scope.
6. `ROADMAP.md` for phase ordering.
7. `FOLLOWUPS.md` for queued work.

If two documents disagree, the higher-authority one wins. File a fix
on the lower one in the same PR — never silently work around it.
