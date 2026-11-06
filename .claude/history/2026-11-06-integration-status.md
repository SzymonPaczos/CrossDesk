# Final adoption/integration status — 2026-11-06

A1 configuration and scoped A3 source/Git audit are accepted. The adoption
record stays Status: in-progress; A2/A4 are OPEN. toolkit-sync check exits 1
because adoption is unfinished, not because the fragment-link helper defect
remains. Published review source 879edc6f6fcf08762adcd1c34244c582bb690535,
version 2026.11.07, toolkit PR46; source is not toolkit main.

Whole adopted skill directories match the pinned source. Security Reviewer
retains the exact current master prefix and complete project domain extension.
No production Rust/Python or Cargo lockfile remediation was performed.
BootControl alone changes the audit-wrapper meta-test and warning link; its
10 mock cases passed. Old override lock hashes intentionally retain provenance.

## A2 — real partial runtime proof

See 2026-11-06-runtime-proof.md and JSON. Actual Fable sessions, per-attempt
run IDs, typed provider session handles, main persistence/ACK and genuine slot
refill were measured. Native_task_id remains null: no native background-task
API/chat-push capability was claimed. Backend 1 second polling did not imply
1 second main-chat delivery; measured delivery/persistence was about 58 seconds.
Boot controller live restart preserved the same session/run without redispatch;
Cross completed-state resume was replay/dedup only. Boot SLOW malformed JSON
remained BLOCKED despite CLI exit 0; main acknowledged the result, not success.

The strict cached Docker image lacks real ps, so deterministic Builder/merge,
timeout and cleanup proof remains BLOCKED before accepted task execution.
No tool shim, dependency installation, extra image or resource relaxation was
used. The configurable refactor is kept only as a reference candidate under
../reference/a2-on-demand, with metadata/syntax guards and no provider end-to-end
validation after refactoring. It was not installed as an active project feature.
No daemon, startup hook, global skill or always-on swarm was activated.

## A4 — explicit incomplete security audit

Owner explicitly approved public source to Claude/Anthropic Fable; the earlier
consent checkpoint is historical. A separate platform safety guard interrupted
Phase 2 coordination in both projects. No retry/rephrasing/alternate route was
used after the guard. Current reason: platform_guard_interruption.

This project's retained units: {"candidate": 4, "covered": 19, "deferred": 31, "out_of_scope": 2}.
There are 0 independently validated final findings. Unvalidated candidates stay
ledger-only, without severity or promotion into findings.json. Both mandatory
critics and independent Phase3/Phase5 verification are unfinished. Structural
validator PASS is not a clean security result. Exact phase/scope/gaps are in
2026-11-06-cloudflare/REPORT.md and its JSON metadata/ledger.

The separate 2026-11-06-security-audit.md records exact-version OSV/CISA checks,
secret-pattern candidates and bounded tests. Cross 94 selected synchronous tests
passed; full collection remains blocked by missing modules. No actual Rust,
Windows guest, real Polkit/firmware/libvirt or complete native acceptance ran.
These facts never become a candidate-specific reproduction or full audit PASS.

## Publication and remaining work

Linux instructions: ../linux-handoff.md. The canonical ADP brief/backlog keeps
A2/A4 open with concrete gaps. Publication is WIP/draft, without merge/release.
Owner granted one CrossDesk WIP publication with pre-push exception; it does
not mean its full Linux/scanner gates passed or authorize a permanent bypass.
Boot's original hooksPath was unset; nothing was disabled for its publication.
