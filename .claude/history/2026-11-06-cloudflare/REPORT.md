# CrossDesk security audit — INCOMPLETE

Reason: `platform_guard_interruption`. This is a partial standard-profile audit,
not a completed security review. The owner granted the earlier source/provider
consent and all four reconnaissance roles completed. A later platform safety
guard interrupted source-hunting coordination. The interrupted operation was
not retried, rephrased or routed through another agent/tool.

Source: `d761d6805be6e70a9a23b0276fad16b1b6e6c969`, clean original public
CrossDesk source. Scope: first-party host, guest, GUI/local IPC and release
controls; two explicit reference-material exclusions. No compatible prior JSON
ledger/findings was available. Provisional coverage IDs were retained when
reconnaissance expanded the deterministic plan. No global invocation budget was
set; per-call bounds and failed attempts remain in private transport receipts.

## Results and limits

There are **0 independently validated final findings**. Empty findings.json
means no candidate completed independent Phase3/Phase5 verification; it does
not mean the application is secure. No severity or confirmed exploit claim is
assigned to unvalidated ledger candidates. Both mandatory critics and final
verification remain unexecuted; there is no clean-coverage claim.

Coverage counts: {"candidate": 4, "covered": 19, "deferred": 31, "out_of_scope": 2}. All unresolved planned work is explicitly
deferred; four candidate units remain unresolved. Only already-accepted parent
ledger state was retained; raw unharvested payloads were not promoted.

The separate deterministic dependency audit and 94 selected synchronous tests
are in ../2026-11-06-security-audit.md. Full Python collection was blocked by
missing dependencies; Rust/Windows/real-VM validation was not performed.
Those receipts do not establish candidate-specific reproduction. No new PoC
or target execution was performed after the platform guard.

## Unvalidated ledger candidates

- `crossdesk/host/jitlite-parent-follows-guest-writable-symlink`
- `host/ipc/auth:stream-nonce-rebinding-unbounded-active-streams`
- `release.yml:sign-agent:unprotected-signing-on-tag-or-dispatch`

These identifiers are unresolved bookkeeping only, not security findings.
They require fresh independent source decisions and final record checks.

## Remaining work

Preserve the exact source/coverage identity. Resume only in an environment
that permits the remaining authorized review; do not bypass the platform guard.
Complete deferred units, immediate post-wave and distinct final-clean critics,
then fresh candidate and final-record verification. Any actual target check
requires the full offline OS sandbox and safe evidence promotion. Native Linux,
guest/VM and deployment observations remain separate unmet validation tasks.

Artifacts: run-metadata.json, architecture.md, coverage-ledger.json,
findings.json, FINDINGS-DETAIL.md, NEEDS-VALIDATION.md. Validators check structure
and state consistency only. The project's canonical ADP backlog/brief owns
remaining work; this ledger is audit accounting, not another product backlog.
