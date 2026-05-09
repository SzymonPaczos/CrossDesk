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
| What's in MVP v0.1.0? | `docs/MVP_SCOPE.md` |
| What's the week-by-week plan to MVP? | `docs/EXECUTION_PLAN.md` |
| Why this stack? | `docs/TECH_STACK.md` |
| What does the architecture look like? | `docs/GOALS.md` (vision) + `docs/TECH_STACK.md` (components) |
| How does distribution + updates look? | `docs/DISTRIBUTION.md` (visual) → `docs/PACKAGING.md` (deep-dive) |
| What's the security model? | `docs/THREAT_MODEL.md` |
| What's the roadmap? | `ROADMAP.md` (phases) + `docs/EXECUTION_PLAN.md` (sequenced) + `FOLLOWUPS.md` (action items) |
| Why X over Y? | `docs/DECISIONS.md` (ADRs `DEC-NNNN`) |
| What does the competition look like? | `docs/COMPETITION.md` + `docs/COMPARISON_WINAPPS.md` |
| Coding rules? | The "Coding rules" section below |
| How does an agent pick a task? | The "Agent workflow" section below |
| What can an agent change? | The "File boundaries" section below |
| Anything in `third_party/`? | `third_party/winapps/` — vendored for reference, AGPLv3, do not copy verbatim |

## Generic agent loadout (`.claude/`)

Stack-agnostic guardrails extracted from `universals.md` (kept in
the repo as a reference template). Auto-loaded by Claude Code via
`CLAUDE.md`:

- [.claude/rules/general.md](.claude/rules/general.md) — universal
  prohibitions, Conventional Commits, branch-per-agent rule,
  pointer to the `WORK_LOG.md` coordination protocol.
- [.claude/rules/backend.md](.claude/rules/backend.md) — Python
  (`host/**`) + Rust (`guest/**`) path-specific rules; proto-first
  RPC pattern; secrets / mTLS guidance.
- [.claude/architecture.md](.claude/architecture.md) — short stack
  snapshot; defers to this file's "Repository layout" for the full
  map. `Last Updated:` is bumped by the post-commit hook.
- [.claude/ignorefiles.md](.claude/ignorefiles.md) — generated
  artifacts and reference-only paths agents should not analyze.

The git hooks under `.githooks/` are activated per-clone; see the
"One-time setup per clone" block in [CLAUDE.md](CLAUDE.md).

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

## Agent workflow

When the user asks an agent to "work on the next task":

1. **`git pull --rebase origin main`** — see what other agents have
   already done or claimed.
2. **Read `WORK_LOG.md`** — scan "Active" entries. If your planned
   task is claimed by another agent (open START with no END), pick
   a different task. Scan "Recent" for relevant context that just
   landed.
3. **Find the current week** in `docs/EXECUTION_PLAN.md` (compare
   today's date to the week ranges).
4. **Pick the highest-priority unfinished item** in that week's
   "Items" list. P0 before P1 before P2.
5. **Cross-reference `FOLLOWUPS.md`** for additional context on the
   item (specific files to touch, dependencies, acceptance
   criteria).
6. **Append a START entry to `WORK_LOG.md`** "Active" section, then
   commit + push that one file directly to `main`. This is the only
   exception to the no-direct-main-push rule — see `WORK_LOG.md`
   "Protocol" for full rules and conflict resolution. If push is
   rejected because another agent claimed the same task, pick a
   different task.
7. **Create a short-named feature branch:** `feat/<task-keyword>`
   (e.g., `feat/transport-abstraction`, `feat/structlog-config`).
8. **Implement** the item against its acceptance criteria. Stay
   scoped — don't bundle unrelated refactors.
9. **Commit** on the feature branch with Conventional Commits.
   Reference the FOLLOWUPS section keyword in the commit message
   body so the linkage is searchable.
10. **Wait for the user to explicitly tell you to merge** before
    merging to `main`. Do not push the feature branch to origin or
    open PRs unless instructed.
11. **When the user says "merge"**: `git checkout main && git merge
    --no-ff <branch> -m "Merge branch '<branch>'"`. Then `git push
    origin main` only if the user says so. Delete the local branch
    (`git branch -d`) after merge.
12. **Update `docs/EXECUTION_PLAN.md`**: mark the item ✅ in this
    week's items list. If you discovered new work, add a one-line
    entry to `FOLLOWUPS.md` under the appropriate section.
13. **Move your `WORK_LOG.md` START entry to "Recent" and append a
    matching END entry**. Commit + push directly to main (same
    exception as step 6).

The user's preference is **local merges only for code**, no GitHub
PRs, no GitHub Issues. The exception is `WORK_LOG.md` — its START/END
entries are pushed directly so parallel agents see them in real
time. The only sources of truth for "what to do" are
`docs/EXECUTION_PLAN.md` (this week's work) and `FOLLOWUPS.md`
(everything queued); the source of truth for "what's happening right
now" is `WORK_LOG.md`.

## File boundaries

Agents may freely modify:

- Source code: `host/`, `guest/`, `gui/`, `infra/` (excluding files
  flagged below).
- Tests: anywhere under `host/tests/`, `guest/**/tests/`, etc.
- Build configs: `host/pyproject.toml`, `guest/Cargo.toml`,
  `gui/Cargo.toml`, lockfiles.
- `FOLLOWUPS.md` — for marking items complete or adding discovered
  work. Don't restructure the file without instruction.
- `docs/EXECUTION_PLAN.md` — for marking items ✅ as completed and
  for schedule updates after the user reviews.
- `WORK_LOG.md` — START / END entries per the protocol in step 6
  and step 13 of "Agent workflow". This file is the only one an
  agent may push directly to `main` without explicit user merge
  instruction.

Agents must NOT modify without explicit instruction:

- `docs/DECISIONS.md` — ADRs are the user's call. If a change is
  warranted, raise it with the user; the user decides and authors the
  ADR (or instructs the agent to draft).
- `docs/THREAT_MODEL.md` — security claims. Same as above.
- `docs/REQUIREMENTS.md` — F\*/N\* IDs are referenced from many
  places; renumbering or rewriting needs user approval.
- `docs/MVP_SCOPE.md` — scope changes are user decisions.
- `docs/GOALS.md` — vision is the user's call.
- `proto/**/*.proto` — wire-format changes propagate everywhere; user
  approval required.
- `ROADMAP.md` — phase definitions are the user's call.
- This file (`AGENTS.md`) — workflow conventions are the user's call.

When in doubt, ask the user before changing.

## Pending user-decision reminders

These are open questions the user has parked. Mention them in
relevant moments (don't spam every conversation, but do raise when
appropriate):

- **Domain name for hosted package repos** (deb / rpm). Currently
  the user doesn't have a domain beyond their personal one; thinking
  about it. *Reasonable cadence to ask: every ~4 weeks, or when work
  on packaging hosting comes up.* Last asked: 2026-05-07.
- **Code signing strategy** for `agent.exe` (Sigstore vs EV cert).
  Deferred per user as not-yet-justified. *Ask before v0.1.0 release
  packaging work begins.*
- **Self-hosted Linux+KVM CI runner** — gated on user acquiring a
  Linux machine. *Ask when hardware acquisition status changes.*

## What to read first as a new agent

If you are a Claude Code session, [CLAUDE.md](CLAUDE.md) auto-loads
the rule files under `.claude/rules/` for you. Read this file
(`AGENTS.md`) for project specifics, then in order:

1. This file.
2. `README.md` — pitch.
3. `docs/GOALS.md` — what we're trying to do.
4. `docs/MVP_SCOPE.md` — what's in v0.1.0.
5. `docs/EXECUTION_PLAN.md` — the week-by-week sequence.
6. `docs/TECH_STACK.md` — components and stack rationale.
7. `docs/THREAT_MODEL.md` — what we're defending against.
8. `FOLLOWUPS.md` — what's queued, prioritized.

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
