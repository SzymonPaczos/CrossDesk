# CrossDesk security audit — INCOMPLETE

This is a partial standard-profile run, not a completed security audit or PASS.
Required independent source-payload/model-endpoint consent remains pending:
automatic approval review rejected recon-b twice BEFORE either model process
executed. No alternate transport/agent was used. The second rejection persisted
after public repository/tree-equality evidence and explicitly requires consent
for the payload and external destination. Coordinator has asked the user.

## Identity, scope and invocation accounting

Frozen clean source: d761d6805be6e70a9a23b0276fad16b1b6e6c969,
SzymonPaczos/CrossDesk. Standard profile, first-party host Python, guest Rust,
GUI/local IPC, release/packaging controls; vendored WinApps and frozen design
reference material are out of scope. No global invocation budget was set;
requested per-call cap is 4 USD/240 s, model claude-fable-5-1. Baseline recon-a-r2
completed after two preserved failed recon-a attempts. Recon-b/c/d, hunters,
post-wave critic, distinct final-clean critic and candidate/final verifiers
have NOT run in this continuation. Two approval-blocked launches are not model
invocations or evidence of source review.

No compatible prior JSON ledger/findings was available. Old prose audits are
clues, not carried confirmed findings, exclusions or complete prior coverage.
The required budget reserves remain explicit in run-metadata.json; the blocker
is approval/source confinement, not a fabricated spend cap.

## Security posture statement

There is no independently validated final finding in this run. Empty findings
means no candidate reached the required independent decision path; it does NOT
mean no vulnerability exists. Completed recon-a establishes product/entrypoint
facts only. Its transport PASS is structured research completion, not a target
security verdict. The architecture map is preliminary and later reconnaissance
may add or correct units.

Source-visible mechanisms include separate user-session host/Windows guest,
per-frame AuthContext/mTLS, an independent Unix management plane, sharing/token
controls and maintained signing/packaging paths. Their completeness was not
established by this interrupted run. Same-owner authority must not be confused
with another local user, compromised guest or lower-trust file/message input.
No deployed reachability, Windows identity, release provenance or live control
was probed or certified.

## Confirmed findings

None independently validated; no severity or exploit claim is assigned.
FINDINGS-DETAIL.md has no confirmed medium/high/critical reproduction.

## NEEDS VALIDATION

No schema-shaped vulnerability lead has completed independent candidate
validation, so none is presented as a needs_validation security finding.
NEEDS-VALIDATION.md records RUN-LEVEL gaps separately. Historical source clues
are not promoted to findings without tracing/verification.

## Coverage and controls

coverage-ledger.json has 17 deferred first-party units and 2 out-of-scope
reference units; covered 0, candidate 0, blocked 0. Deferred units preserve visible
management IPC, mTLS/per-frame/replay/stream paths, share/file/XML/RAIL state,
credentials/Windows FFI, GUI/installer, configuration and CI/release/package
boundaries. Their selected blocks are a resumable preliminary plan, not an
assertion of exhaustive material combinations. No hunter wave ran, so neither
mandatory standard-profile critic ran; no clean-coverage claim is made.

No target code was executed by this Parent. Coordinator supplied separate
OS-sandbox receipts for 94 selected CrossDesk tests; full host collection was
blocked by missing cached modules. That auxiliary test evidence is not a
candidate-specific local proof and is not mislabeled as a ledger local check.
Root-owned SCA/OSV/KEV/secrets work is separate and was not duplicated here.

Source packets exclude Git metadata and ignored/secret filenames. The adapter
checks tool paths in its final trace, but effective pre-read confinement must
also be established; a rejected outside-path trace after execution would not
by itself prove host data had never been read. Until consent and confinement
are resolved, no new remote source call will be made.

## Resumption and artifacts

Resume only after the required user response. Continue recon-b/c/d, complete
architecture/unit maps, then focused hunting, immediate and distinct final
critics, independent candidate decisions and fresh final record checks. Actual
candidate checks require the prescribed OS sandbox and safe artifact promotion.
The parent alone owns shared files. Validators prove format/state consistency,
not truth, completed coverage or target security.

Artifacts: run-metadata.json; architecture.md; coverage-ledger.json;
findings.json; approval-review.json; recon-a-facts.json;
FINDINGS-DETAIL.md; NEEDS-VALIDATION.md. Earlier failed recon attempts remain private and are not bundled. Their
counts are retained; no raw prompts, source packets or transport logs are published. Source/ref, scope and incomplete reason are explicit in metadata.

## Public checkpoint scope

This sanitized checkpoint includes curated recon-a facts, metadata and the
preliminary ledger, not private execution logs or an executable audit launcher.
The reviewed target is the recorded baseline commit, not a later adoption
commit. Private helper paths and model connection details are intentionally
absent. See resume.md for the installed skill procedure and validation commands.
Automatic approval rejected two source-egress launches before execution; the
auditing process remains paused pending the required explicit user response.
