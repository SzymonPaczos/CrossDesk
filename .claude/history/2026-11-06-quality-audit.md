# CrossDesk quality source audit — 2026-11-06

Task: ADP-2026-11-06-01, sole acceptance plan in ../task-briefs/ADP-2026-11-06-01.md.
Assessed application baseline: d761d6805be6e70a9a23b0276fad16b1b6e6c969
(fresh origin/main); A1 configuration is separately described in
../toolkit-adoptions/A1-review.md. Author role: CrossDesk adoption Builder,
source-fact collector; this is not an independent technical Reviewer verdict.

Status: bounded source review completed; runtime quality, fresh tests, mutation
runs, live integration and historical CI execution are NOT independently
verified. No project code, build, hooks, conftest, scanners or test was executed.
A2/A4/P5 remain Coordinator-owned. Do not read this report as a full product PASS.

## DELIVERY_REVIEW and PROCESS_DRIFT

The requested 21 calendar days are 2026-10-17 through 2026-11-06 inclusive.
`git log origin/main --since=2026-10-17T00:00:00+02:00
--until=2026-11-07T00:00:00+01:00` contains zero commits. The last baseline
commit is d761d68 on 2026-09-05. Uncommitted work, other machines, conversations,
agent sessions and the preserved 11-commit local branch are not included.
There is no basis here to infer hours, model cost or a three-week process stall.

A SEPARATE last-active 21-day window, 2026-08-16 through 2026-09-05, has:

| Source-history measure | Count |
|---|---:|
| All origin/main commits / non-merge commits | 30 / 18 |
| Non-merge commits touching application/domain paths | 5 |
| Non-merge commits touching tests/microbench paths | 5 |
| Non-merge commits touching gate/delivery code | 2 |
| Non-merge commits touching docs/process metadata | 18 |
| Docs/process-only commits | 11 |
| File touches: docs/process, application, tests, gates | 88, 9, 8, 2 |

Categories overlap. A file touch is per commit, not a unique file or time.
Application means host/src, guest, gui, proto or infra (including lockfiles);
tests means host/tests, nested tests or host/benches; gates means .githooks,
.github or scripts; remaining paths are docs/process. Many source commits also
bump architecture/ignorefile timestamps automatically. The numbers cannot
establish whether testing/documentation was excessive or valuable. Five source
commits include concrete launch/filesystem/auth fixes, a Rust CI repair and h2
refresh; two gate commits repair the pre-push scanner. These are observable
outputs, not a velocity or ROI score.

## Regression/TDD evidence: three deliberately selected samples

| Commit and source/tests | Useful behavior/counterexample | What RED evidence exists |
|---|---|---|
| a6efb19cbeea65ce6f0acb2cbcf69f67af2495c7 (2026-08-24), .githooks/pre-push and host/tests/test_pre_push_hook.py:137-237 | Committed secret removed only in working tree must still block; the reverse case must not block; stdin push range/new branch/deletion are distinct cases. This tests the artifact actually pushed, not just a regex helper. | Commit Gates text reports three new tests failing against the old hook and passing after, with three controls passing both. Tests and implementation land in the same commit. No separately persisted raw RED/green artifact was inspected; this audit did not rerun them. |
| e5d672bf32c8f55bf1018b1f9ccd495b8cf13b40 (2026-08-24), ipc/heartbeat.py and filesystem.py; host/tests/test_smoke_e2e.py:374-480 | Real-wire disconnect tests inspect validator cleanup. Waiting for a SECOND ping proves an authenticated pong was consumed; breaking at the first ping could pass vacuously. | Gates text explicitly reports that the first test survived removal of cleanup, then was corrected; removing cleanup reportedly fails each final sentinel. This is valuable mutation reasoning, but remains author-reported here. Current A0905-02 records missing nonce-rotation/error cleanup; ordinary disconnect success cannot close every exit path. |
| c4cb6e8866132c262c06b09f3939396ca45a7fff (2026-07-14, outside the statistics window), lifecycle/coordinator.py/dbus_listener.py; host/tests/test_lifecycle_coordinator.py:371-429 | One test measures event-loop progress during a slow libvirt call. Another requires FSM=SUSPENDED synchronously before the handler returns, while the libvirt half is deferred; making everything async would violate the data-loss boundary. | Gates text reports two targeted mutations failing (blocking call restored, FSM suspend deferred). Tests use a .3s stall/ticker and a .05s completion wait, so timing robustness still needs execution. No real system-bus host suspend was performed; PLAN #5 correctly remains owner/live-gated. |

These samples show meaningful regression design and attempts to defeat tests
that pass without exercising the defect. They do not prove RED preceded code,
that refactoring happened, that every test is useful, or that TDD is consistently
followed. Green suites, coverage and a commit narrative are different evidence.
For established regressions, keep a small failing behavior test, minimal fix and
simplification; for unknown external contracts, first bound a probe and compare
fake-provider assumptions with a real contract. No evidence supports adding a
universal coverage/mutation target or rewriting all tests around a new framework.

## Architecture and TASK_COMPLETENESS

There is useful separation: the host libvirt Protocol and real/mock adapters
(abstractions/libvirt.py:17, libvirt_ctl/real.py:93), generated proto boundary,
separate servicers and a synchronous FSM with a bounded async libvirt half.
Tests protect several cross-boundary failures rather than merely mirror helpers.
This is a sampled source assessment, not a review of every module/ADR.

Integration remains materially incomplete where PLAN already says so:

- Stage B: PLAN:53-83 describes absent guest provisioning/mount proof. The source
  agrees: installer/domain_xml.py:119-125 only supplies host-side shared-memory/
  virtiofs plumbing, while guest/crates/fs-mount/src/mount.rs:5-23 is explicitly
  a mock returning Mounted; agent-svc/src/filesystem.rs:59 calls it. No real
  WinFsp/viofs/VirtioFsSvc provisioner was found in the inspected infra/installer
  paths. This is NOT new proof that the live VM was inspected, nor a new claim
  that #3 is complete. Retain the existing PLAN Stage B task, no duplicate.
- PLAN:128 retains real suspend/resume acceptance and :135-137 retains package/
  README gaps. A mocked daemon, a native cargo check and a real Windows PE build
  are three different checks. Default backend remains mock unless explicitly
  selected real (daemon.py:182-188); a successful start with default config
  cannot certify Linux/libvirt operation.
- NEW low-impact process finding: PLAN:29-31 and NEXT:72-75 still list #2/#4/#8
  as upcoming, although the same PLAN table:125/:127/:131 and summary:137 mark
  them historical live-complete. The approved PLAN/backlog split is sound as a
  policy exception; conflicting state INSIDE PLAN can still send an agent to
  repeat finished work. QLT-2026-11-06-01 records reconciliation against evidence,
  without inferring that July's live result remains current in November.

## Test and CI blind spots (deduplicated, not a new parallel queue)

- In-process integration is valuable but conditional: test_smoke_inprocess.py:
  79-95 skips for missing PKI, missing Cargo/prebuilt agent or explicit opt-out.
  Current ci.yml:66-111 installs dependencies and runs pytest but contains no
  matching PKI generation step. Source review cannot establish how many tests
  actually skipped in a particular hosted run. Existing A0905-07 owns skip
  observers/producer-error inventory and mutation sampling; a green job alone
  does not prove this integration ran.
- Destructive real-libvirt tests require --live-libvirt (tests/conftest.py:12-37).
  The autouse guard at :40-61 intentionally blocks accidental real access.
  Keep that protection. The mock in-process harness also mocks FreeRDP; it
  verifies the wire/session behavior, not a real Windows desktop or RAIL window.
- Microbench is not fake user latency: bench_N1_1_cold_launch.py:1-15 explicitly
  describes metrics-recording overhead, and :38-47 measures Histogram.observe.
  The CI label is broad, so readers must distinguish that from the real ≤3s
  launch goal. perf-baselines.json has 11 positive numeric baselines; its text
  claims three measured July CI runs and a 20% threshold. This audit verified
  the source values, not those runs or current hardware variance. Existing
  backlog integration-benchmark/histogram work and PLAN live criteria remain.
- Bandit and Semgrep execution statuses are explicitly swallowed by || true in
  security.yml:87 and :145; QML is advisory at ci.yml:188. Zizmor and dependency
  checks have different failure policy. Do not infer scanner PASS from overall
  CI green. A0905-05 already owns scanner status/metric parsing and baseline
  policy; A0905-08 owns server-side merge gates. No workflow policy was changed.
- Python floor >=3.9 in host/pyproject.toml:8 differs from tested/typechecked 3.12
  in ci.yml:54 and pyproject:91. This is already A0905-06 (owner compatibility
  decision), with environment reproducibility under A0905-09/lockfile debt.
- Pre-push checks the first ref and can fall back to working-tree content when
  materialization fails (pre-push:58-80/:132-139). Existing A0905-04 and backlog
  TOP own this. Passing the current selected tests is not proof of fail-closed
  operation under Git errors, multi-ref pushes or missing scanner executables.

Existing A0905-02/04/05/06/07/08/09 and PLAN acceptance gaps were found already
tracked; they are not reopened under new IDs. Their previous severity or
historical exploit claims were not independently revalidated here. The single
new quality item is QLT-2026-11-06-01; adding it is not implementation permission.

## CONTEXT and audit limit

A1 reduced always-loaded file bytes from 318218 to 12283 (AGENTS 896); this measures
file input, not actual token use, money or long-session recall. One durable ADP
brief keeps all stages, with A1 evidenced and A2/A3/A4/P5 independently open.
This source report supplies A3 facts; Coordinator must reconcile the exact A3
acceptance scope before marking an end-to-end/runtime quality stage complete.
No historical evidence from the user's other unnamed project was available,
so no cause or auditor blame is assigned to that reported three-week incident.

## Scanner offline/source acceptance facts

No scanner was invoked here. Cargo install metadata identifies cargo-audit
0.22.1/cargo-deny 0.19.5; executable version/help acceptance and report freshness
still belong to Coordinator in a trusted empty working directory/runtime.

| Scanner | Static accepted-input/offline facts | Limit for this handoff |
|---|---|---|
| cargo-audit 0.22.1 | Upstream pinned parser has --file existing Cargo.lock, --db, --no-fetch, --json. An explicit existing lock avoids locate_or_generate; --no-fetch suppresses advisory DB fetch. | Existing hook does not pass these. Use a prepared advisory database and OS network restriction; do not use --stale to conceal old data. No --no-yanked option exists in this version's parser. [Pinned parser](https://raw.githubusercontent.com/rustsec/rustsec/cargo-audit/v0.22.1/cargo-audit/src/commands/audit.rs). |
| cargo-deny | Official common options document --offline and --locked (or --frozen), plus --metadata-path to consume supplied cargo metadata instead of invoking cargo metadata by default. | Cached crates/index/advisory data are still required; offline data can be old. Validate installed 0.19.5 syntax separately. [Common options](https://embarkstudios.github.io/cargo-deny/cli/common.html). |
| pip-audit | Installed parser and upstream docs support --disable-pip --no-deps with a fully pinned requirements input, plus --cache-dir and --osv-url. This avoids pip resolution, not advisory-network access. | No generic --offline flag was found in the installed parser. Cache is not a network guarantee; --dry-run skips auditing. Default -r can resolve/install untrusted packages; do not run it on the host. [Usage/security model](https://github.com/pypa/pip-audit#security-model). |
| gitleaks / Bandit | Existing hook uses local history/content scan and AST-oriented SAST respectively; neither requires target application startup. | Git configuration, trusted scanner/plugins and source/config scope still require control. This is not a tested binary/network/coverage attestation. Gitleaks full-history synthetic fixtures need precise evidence-based exceptions, never broad path suppression. |

A CLI flag is not a sandbox. No scanner is a universal CVE exploit runner;
SCA matches inventory/advisories, while active tests and full Cloudflare audit
have separate accepted scope and technical isolation. Source-only results do
not certify exploit absence. Coordinator retains raw reports outside the
tracked instruction corpus and binds final evidence to the actual reviewed SHA.
