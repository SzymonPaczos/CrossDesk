# CrossDesk domain and workflow reference

Read only sections relevant to the assigned task. CLAUDE.md and active
META/technical decisions override the archived historical entrypoints.

## Repository layout

```
crossdesk/
├── README.md                 # pitch + quick start
├── ROADMAP.md                # 5 phases, terse
├── CLAUDE.md                 # canonical project instructions
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
│   ├── src/crossdesk_host/   # 20 subpackages; key ones:
│   │   ├── ipc/              # gRPC servicers (control, heartbeat, filesystem, auth)
│   │   ├── display/          # RAIL spawning + window icons (Phase 4)
│   │   ├── watchdog/         # heartbeat FSM (Phase 3)
│   │   ├── libvirt_ctl/      # LibvirtController abstraction (real / mock)
│   │   ├── filesystem_ctl/   # FilesystemController abstraction
│   │   ├── transport/        # AF_VSOCK / TCP mTLS transport (real / mock)
│   │   ├── lifecycle/        # suspend/resume coordinator, notifications
│   │   ├── cli/              # crossdesk CLI subcommands
│   │   ├── doctor/           # pre-flight diagnostics
│   │   ├── installer/        # crossdesk install engine + PKI + state
│   │   ├── config/           # typed config schema (peripherals, transport…)
│   │   ├── observability/    # structlog + trace context + OTLP
│   │   ├── abstractions/     # Protocol seams (libvirt, transport, freerdp…)
│   │   ├── proto/            # generated proto stubs (regen via build_proto.py)
│   │   └── … catalog, freerdp, integrations, jit_mount, recovery,
│   │       utils (recovery + catalog scaffolds: see .claude/ignorefiles.md)
│   └── tests/
│
├── guest/                    # Rust NT service workspace
│   └── crates/
│       ├── agent-svc/        # NT service entry point + windows-rs
│       ├── ipc-vsock/        # AF_VSOCK transport (still TCP-loopback in dev — see .claude/backlog.md)
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


## Technical boundaries and navigation

Owner approval is required for docs/DECISIONS.md, docs/THREAT_MODEL.md,
docs/REQUIREMENTS.md, docs/MVP_SCOPE.md, docs/GOALS.md, proto/**/*.proto
and ROADMAP.md. docs/EXECUTION_PLAN.md remains frozen. Never turn a warning
into permission. Source changes, tests and build config remain within the
assigned brief, with owner authorization for protected boundaries.

Requirements explain what, technical ADRs why, threat model security claims,
TECH_STACK components, GOALS vision and ROADMAP phase order. Conflicts become
recorded findings; never silently change a higher-authority boundary.

New install steps must be idempotent and write install.state.json atomically
(temp file, fsync, rename). New configuration is typed; never bash-source it.
No control-plane polling; DEC-META-006 permits interactive log tail only.
No real libvirt import outside libvirt_ctl/real.py; no production mock import
outside the documented CI whitelist.

## Existing execution setup (commands are not A1 evidence)

Existing hooks live in .githooks. On an owner-approved Linux clone, after
reviewing those files, activate with git config core.hooksPath .githooks and
git config commit.template .gitmessage. Do not bypass hooks. Running project
commands, installing dependencies or committing triggers target-controlled
execution and requires the agreed OS sandbox.

Worktree cleanup follows verified merge: compare exact SHA and branches,
check git status and worktree locks; preserve active/dirty/unmerged work.
Archive superseded instructions is not a live checklist. Never read the
whole legacy backlog or loop-spec merely to start a brief.

## Existing unresolved owner decisions

Consult only relevant entries in ../needs-owner.md for hosted package domain,
code signing and Linux/KVM runner policy. No new policy is inferred here.
