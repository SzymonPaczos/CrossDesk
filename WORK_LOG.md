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

- [2026-05-10 15:25] END · agent: claude-code · branch: feat/code-signing · task: code-signing-self-trusted · note: result: success → merged as a53ac77 (full PKI bootstrap script + osslsigncode signing wrapper + autounattend FirstLogonCommands cert import + Defender exclusion + docs/CODE_SIGNING.md + 5/5 PKI smoke tests; private keys/PFX gitignored, public root CA committed). Gates: pytest 428/428, mypy --strict 93 source files clean, cargo check + clippy -D warnings workspace clean.
- [2026-05-10 14:50] START · agent: claude-code · branch: feat/code-signing · task: code-signing-self-trusted · note: User-approved (I+II) — self-signed publisher PKI for agent.exe + autounattend installs root CA into guest Cert:\LocalMachine\Root + Defender exclusion for C:\CrossDesk\. Zero annual cost; only works because agent.exe never leaves our orchestrated guest VM.
- [2026-05-10 15:24] END · agent: claude-code · branch: feat/trace-propagation-completion-v3 · task: trace-propagation-completion · note: result: success → merged as a33bc0e (Agent A's branch; heartbeat servicer switched to stdlib logger; VerifyCoordinator.verify mints fresh root TraceContext per call; 2 new smoke tests asserting trace_id appears on each plane + per-call uniqueness).
- [2026-05-10 15:23] END · agent: claude-code · branch: chore/threat-model-credential-drift · task: threat-model-credential-drift · note: result: success → merged as dc1c61d (THREAT_MODEL.md C7 row for credential-drift attack vector with 🚧 mock coverage marker; user-approved option a).
- [2026-05-10 15:22] END · agent: claude-code · branch: feat/tooling-cargo-deny-buf-lint · task: tooling-cargo-deny-buf-lint · note: result: success → merged as 05bdae8 (Agent B's branch; deny.toml tightened sources unknown→deny; proto/buf.yaml STANDARD lint + breaking FILE; CI proto job dropped `|| true`).

- [2026-05-10 11:53] START · agent: claude-code · branch: feat/trace-context-completion · task: trace-propagation-completion · note: P0 follow-up to DEC-0006. Investigation: guest already injects traceparent on all 3 planes (planes.rs:88-108), host TraceContextInterceptor is mounted server-wide so it covers control+heartbeat+filesystem automatically. Gaps: heartbeat servicer used module-level structlog facade (factory cached pre-configure_logging, never received per-call stream/contextvars); VerifyCoordinator server-initiated path had no trace binding; test coverage was control-only.
- [2026-05-10 14:35] END · agent: claude-code · branch: feat/trace-propagation-completion-v3 · task: trace-propagation-completion · note: result: success → branch feat/trace-propagation-completion-v3 pushed at ed42a88, ready for user merge. (Original branch name `feat/trace-context-completion` was force-overwritten on origin by another agent's racing push despite no-force-push rule; recreated under -v3 suffix.) Heartbeat servicer switched to stdlib logger (matches control.py + filesystem.py); VerifyCoordinator.verify() mints fresh root TraceContext per call, binds + clears around the await; two new smoke tests assert (a) trace_id appears on log lines from EACH plane component and matches the agent's minted ID, (b) two consecutive verify calls produce distinct trace_ids on their dispatch logs. Gates: mypy --strict 92 files clean, pytest 410/410, cargo check workspace clean, cargo test workspace clean (--features agent-svc/mock), clippy -D warnings clean. No proto edits, no THREAT_MODEL touches.

- [2026-05-10 12:30] START · agent: claude-code · branch: feat/tooling-cargo-deny-buf-lint · task: tooling-cargo-deny-buf-lint · note: FOLLOWUPS:199 (P1 buf.yaml lint+format) + FOLLOWUPS:223 (P2 cargo deny rule). Investigate existing guest/deny.toml + gui/deny.toml (already landed); finalise proto/buf.yaml lint+breaking rules; remove `|| true` from .github/workflows/ci.yml proto job; run buf format + buf lint where tooling available. Tooling-only, no code semantics changes. (`buf` not installed locally — will document gap; cargo-deny 0.19.5 available.)
- [2026-05-10 14:10] END · agent: claude-code · branch: feat/tooling-cargo-deny-buf-lint · task: tooling-cargo-deny-buf-lint · note: result: success → pushed as 93d2d5c (NOT merged — left for user review per worktree-agent protocol). Tightened guest/+gui/ deny.toml: sources unknown-* warn→deny, English headers, per-section policy comments, ignore-entry rationale. Finalised proto/buf.yaml: STANDARD lint minus COMMENT_* (matches existing block-header style), `breaking: FILE` (stricter than `WIRE_JSON` floor), inline note explaining no buf.gen.yaml. CI proto job: dropped `|| true` from `buf lint` + `buf format --diff --exit-code`, renamed to "Proto lint + format". Gates: cargo deny check PASS on guest+gui; cargo check --workspace PASS on guest; mypy --strict PASS (93 files); YAML validates. `buf` is not installed locally so `buf lint`/`buf format` are CI-first; rule names referenced (STANDARD, COMMENT_*, FILE) are valid v2 identifiers per buf docs.
- [2026-05-10 12:30] START · agent: claude-code · branch: feat/verify-credentials-rail-gate · task: verify-credentials-stage-3 · note: Stage 3 of 3 (Stages 1+2 merged as c3e314c + 8a2dab1). Wires VerifyCoordinator into RailManager.spawn_rail (gate before FreeRDP) and adds CLI subcommands `crossdesk vm credentials check` (read-only, doctor-friendly) + `crossdesk vm credentials repair` (interactive prompt + atomic vm.toml write); doctor integration. Stage 4 (real LogonUserW + THREAT_MODEL update) deferred to post-hardware.
- [2026-05-10 12:55] END · agent: claude-code · branch: feat/verify-credentials-rail-gate · task: verify-credentials-stage-3 · note: result: success → merged as 47e8e77 (installer/credentials.py extended with health_check + repair_permissions + verify_with_guest mapping; new display/session_starter.spawn_rail_with_auth_check gate raising AuthHealthCheckFailed with repair_hint; CLI `vm credentials check` + upgraded `repair`; doctor probe check_vm_credentials added to DEFAULT_CHECKS; 18 new tests). Gates: pytest 426/426, mypy --strict 93 source files clean, cargo check workspace clean.
- [2026-05-10 11:42] START · agent: claude-code · branch: feat/verify-credentials-host · task: verify-credentials-stage-2 · note: Stage 2 of 3 (Stage 1 merged as c3e314c). Host-side: new VerifyCoordinator (request_id correlation map + asyncio.Future plumbing), refactor ControlServiceServicer.OpenSession to support server-initiated ServerFrames via outbound asyncio.Queue, route incoming ClientFrame.verify_credentials_result to coordinator.deliver(). Smoke test extension exercising __inject_ok__ + __inject_bad__ end-to-end through in-process harness. Stage 3 (rail_manager gate + CLI vm credentials check/repair) follows.
- [2026-05-10 11:14] START · agent: claude-code · branch: feat/verify-credentials-rpc · task: verify-credentials-stage-1 · note: P0 unblocked by user (FOLLOWUPS:928-935 + 985-994). Stage 1 of 3: proto edit (VerifyCredentialsRequest as ServerFrame variant + VerifyCredentialsResult as ClientFrame variant — payload-variant approach because guest is gRPC client not server) + guest mock impl with cfg-gated real-Windows scaffold + guest session.rs wiring. Stages 2-3 follow: host-side VerifyCoordinator + servicer refactor; rail_manager gate + CLI vm credentials check/repair.
- [2026-05-10 12:15] END · agent: claude-code · branch: feat/verify-credentials-host · task: verify-credentials-stage-2 · note: result: success → merged as 8a2dab1 (VerifyCoordinator with request_id correlation + ControlServiceServicer.OpenSession refactored to consume-task + outbound-queue pattern + 6 unit tests + e2e smoke test exercising live Rust agent through __inject_ok__ / __inject_bad__). Gates: pytest 408/408, mypy --strict 92 source files clean, cargo check workspace clean.
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
