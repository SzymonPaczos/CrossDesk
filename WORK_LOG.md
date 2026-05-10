# Agent work log

Append-only coordination log so parallel agents don't step on each
other. Read this **before** picking a task. Update it **at start**
and **at end** of work. The user reads it to know what's happening.

## Format

Each entry is a single line:

```
[ISO-8601 timestamp] STATE · agent: <agent-id> · branch: <branch> · task: <task-keyword> · note: <one-line context>
```

States:

- **START** — agent claims a task; no matching END yet.
- **END** — agent finished (success, blocked, or aborted) — `note`
  must say which.
- **NOTE** — non-claim status update mid-work (rare; only for
  long-running tasks).

`agent-id` is whatever identifies the agent run (`claude-code`,
`cursor`, `aider`, plus a session UUID or short tag if multiple
runs are in flight on the same machine).

## Protocol

**Before picking a task:**

1. `git pull --rebase origin main` (so you see other agents' claims).
2. Scan "Active" below — if your planned task has an open START
   without a matching END, **pick a different task** or wait.
3. Scan "Recent" for context on what just landed (in case your
   planned task depends on it).

**At start:**

1. Append a START entry to "Active" below.
2. `git add WORK_LOG.md && git commit -m "chore(work-log): START
   <task-keyword>"` on `main` directly (this single file is the
   exception to the "no direct main commits" rule because it is
   coordination metadata, not code).
3. `git push origin main`. If push is rejected because someone else
   pushed first, `git pull --rebase` and retry. If the conflict is on
   their START entry for the same task, **pick a different task**.
4. Then proceed to your normal feature branch and implementation work.

**At end (success, failure, or blocked):**

1. Move your START entry from "Active" to "Recent" and append a
   matching END entry below it. Include the result in `note`:
   `result: success → merged as <sha>`, `result: blocked on <thing>`,
   `result: aborted, see <issue/conversation>`.
2. `git commit -m "chore(work-log): END <task-keyword>"` on `main`.
3. `git push origin main`. Same conflict-resolution as START.

The push of the work-log entry happens **independently of the
feature branch's merge** — START is pushed at the beginning, END is
pushed at the end, regardless of whether the feature branch itself
has merged. This is the only file an agent may push to `main` without
explicit user instruction; everything else still requires the user
to say "merge".

## Single-machine concurrency

If two agent sessions run on the same machine sharing the same
working tree, they see the same file system but may interleave reads
and writes. The git-push race protocol above resolves cleanly when
both push to origin. If neither pushes (e.g., user is running both
locally without internet), they should at minimum both
`cat WORK_LOG.md` before adding their entry, and prefer separate
branches so file contents don't clobber.

If the user explicitly wants two agents on the same task (rare —
e.g., two angles on a hard problem), the agents should use different
branch names and the user merges by hand later.

## Active

<!-- Currently in flight. Move to Recent on completion. -->

- [2026-05-09 20:55] START · agent: claude-code · branch: docs/distribution-overview · task: distribution-overview · note: new docs/DISTRIBUTION.md — visual entry for packaging+update flow (5 formats, release pipeline, dual-layer update apt/dnf/yay/nix/pip vs crossdesk upgrade RPC, Flatpak/Snap/AppImage rejection contrast). Adds 1 nav row to AGENTS.md, 1 cross-ref line to PACKAGING.md. Doc-only, no code.

## Recent

- [2026-05-10 11:14] START · agent: claude-code · branch: feat/verify-credentials-rpc · task: verify-credentials-stage-1 · note: P0 unblocked by user (FOLLOWUPS:928-935 + 985-994). Stage 1 of 3: proto edit (VerifyCredentialsRequest as ServerFrame variant + VerifyCredentialsResult as ClientFrame variant — payload-variant approach because guest is gRPC client not server) + guest mock impl with cfg-gated real-Windows scaffold + guest session.rs wiring. Stages 2-3 follow: host-side VerifyCoordinator + servicer refactor; rail_manager gate + CLI vm credentials check/repair.
- [2026-05-10 11:42] END · agent: claude-code · branch: feat/verify-credentials-rpc · task: verify-credentials-stage-1 · note: result: success → merged as c3e314c (proto edit + guest credentials.rs with 8 unit tests + session.rs handler dispatch). Side-effect: regenerated all *_pb2.py/.pyi stubs from current grpc_tools/mypy-protobuf versions (formerly stale). Gates: cargo test workspace 33/33, clippy clean -D warnings, mypy --strict 91 source files clean, pytest 401/401.

- [2026-05-09 17:09] END · agent: claude-code · branch: (multiple) · task: autonomous-weeks-6-through-23 · note: result: success → batched merges of feat/{heartbeat-adaptive-broadcast, lifecycle-suspend-resume, week8-rail-command, week9-rail-manager, week10-rail-polish, week11-notifications-multimonitor, week12-microbench, week13-hello-handshake, install-pipeline, phase5-virtiofs, release-packaging}. Phases 3-5 complete in code; install pipeline + CLI + doctor + uninstall scaffolded; AUR PKGBUILD + Nix flake landed. Hardware-gated items clearly labeled 🚧 across EXECUTION_PLAN. 263 tests pass; mypy --strict 70 source files clean. Week 24 (tag v0.1.0 + AUR/Nix/PyPI publish) intentionally not executed — user-decision actions.
- [2026-05-09 16:07] END · agent: claude-code · branch: feat/heartbeat-fsm-wire · task: heartbeat-fsm-stage-2 · note: result: success → merged (servicer wired to FSM; old inline state machine removed; structlog logging; pytest 157/157)
- [2026-05-09 15:42] END · agent: claude-code · branch: feat/heartbeat-fsm · task: heartbeat-fsm-stage-1 · note: result: success → merged as df8363c (watchdog/{ewma,fsm,__init__}.py + 19 unit tests; mypy --strict 46 files clean; pytest 157/157)
- [2026-05-09 15:18] START · agent: claude-code · branch: feat/heartbeat-fsm · task: heartbeat-fsm-stage-1 · note: Week 5 P0 pulled forward (no hardware needed for FSM correctness). Stage 1 of 3: pure FSM module under host/src/crossdesk_host/watchdog/ — State enum, EWMA RTT calc, exponential backoff, transitions HEALTHY→DEGRADED→PROBING→SOFT_RECOVERY→HARD_DESTROY per heartbeat.proto. No wiring to ipc/heartbeat.py yet (Stage 2). Unit tests cover every transition with mocked time.

<!-- Newest first. Trim entries older than ~30 days into RELEASE_NOTES
     or just delete; this log is operational, not historical. -->

- [2026-05-09 15:02] END · agent: claude-code · branch: chore/tidy-plan-docs · task: tidy-plan-docs · note: result: success → merged as bf676b0 (5 plan/status files refreshed: 3× "Today" bump to 2026-05-09, FOLLOWUPS meta-claim removed, ROADMAP translated PL→EN with ✅ Phase 1)
- [2026-05-09 14:57] START · agent: claude-code · branch: chore/tidy-plan-docs · task: tidy-plan-docs · note: refresh stale "Today: 2026-05-07" markers (EXECUTION_PLAN, MVP_SCOPE, INSTALL_WIZARD_PLAN) → 2026-05-09; remove obsolete "sections still to be expanded" claim in FOLLOWUPS:105-110; translate ROADMAP.md PL→EN preserving Foundation/Proof/SPOF structure + ✅ Phase 1
- [2026-05-08 22:32] END · agent: claude-code · branch: chore/bootstrap-claude-architecture · task: bootstrap-claude-architecture · note: result: success → merged as ac0fe11 (8 new files + AGENTS.md & .gitignore updates; universals.md tracked with 7-item enrichment). mypy --strict and cargo check --workspace both pass.
- [2026-05-08 22:10] START · agent: claude-code · branch: chore/bootstrap-claude-architecture · task: bootstrap-claude-architecture · note: extract universals.md templates into .claude/rules/{general,backend}.md + .claude/{architecture,ignorefiles}.md + .githooks/{pre-commit,pre-push,post-commit} + thin CLAUDE.md shim; overlay only — keep AGENTS.md/WORK_LOG.md/THREAT_MODEL.md as canonical
- [2026-05-07 22:30] END · agent: claude-anthropic-conversation · branch: feat/build-config-lean-and-mock-features · task: build-config-lean-mock-features · note: result: success → merged as cb4a23f
- [2026-05-07 22:15] END · agent: claude-anthropic-conversation · branch: feat/pre-agent-setup · task: pre-agent-setup · note: result: success → merged as b8abc71 (CI workflow + MVP_SCOPE + EXECUTION_PLAN + agent workflow rules)
- [2026-05-07 21:00] END · agent: claude-anthropic-conversation · branch: feat/gpu-decision · task: gpu-passthrough-decision · note: result: success → merged as a9c1f5f (DEC-0009)
