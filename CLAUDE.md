# CrossDesk

Canonical project instructions. Linux Python host controls a Windows Rust
NT-service guest through libvirt (`qemu:///session`) and gRPC/AF_VSOCK with
mTLS and per-frame AuthContext. FreeRDP RAIL renders native windows.

## Work and acceptance

- Follow the assigned brief. Read the relevant record, never the whole backlog.
- Preserve the approved board split (DEC-META-009/010): PLAN.md is the MVP
  board; .claude/backlog.md holds post-MVP and cross-cutting process work.
  The current adoption has ONE plan: ADP-2026-11-06-01 in that backlog and
  .claude/task-briefs/ADP-2026-11-06-01.md. Links elsewhere do not duplicate it.
- Record accepted work before continuing. A topic change keeps every unfinished
  stage, next action and blocker. Partial stages cannot close the whole task.
- Use a separate branch per worker. Inspect original changes before deletion;
  remove a worktree only after verified integration, preserving dirty, locked,
  active or unmerged work. No hook bypass. Merge/push need owner authorization.
- No fabricated data, mock completion, shipped placeholders, secrets or raw
  conversations. Authored project code/docs/commits are English; unmodified
  tracked vendor conventions/skills retain their source language.
- Read .claude/status.md only for affected known issues; owner decisions are
  parked in .claude/needs-owner.md. WORK_LOG START/END remains retired.

## Boundaries

Technical ADRs in docs/DECISIONS.md, docs/THREAT_MODEL.md, requirements,
MVP scope/goals, proto wire format and ROADMAP require explicit owner approval.
Keep Docker/Podman out of the backend; no control-plane polling (DEC-META-006
allows interactive log tail only). Sharing defaults off and to documents;
whole-home sharing is explicit warned opt-in (DEC-0019).

## Procedures on demand

- Domain/build/navigation: .claude/conventions/project-workflow.md and
  path-scoped .claude/rules/backend.md.
- Audit: .claude/conventions/audit.md; full weekly-audit skill and references.
- Repairs: audyt-naprawczy and plan-naprawy skills, only for the assigned scope.
- Delivery/review: petla-dostarczenia; conventions/backlog-contract.md,
  multi-agent-delivery.md, test-evidence.md and test-execution-economy.md.
- CI/security/dependencies: conventions/ci-cd.md, security-verification-gates.md,
  dependency-currency.md and local-gate-orchestration.md.
- Full META register: .claude/decisions-register.md (lookup the relevant ID).
  Generic procedures are under .claude/conventions/; project decisions win.

## Roles, controls and adoption state

Existing profile is hybrid: GitHub Actions ci.yml/security.yml/release.yml
plus local hooks; production/rollout procedures remain reference-only and no
production operation is implied. Formal runner policy stays parked as before.
Conventional Commit subjects block; Intent/Task-Ref/Gates remain WARN and no
AI attribution is added (DEC-META-008). Local reviews/merges do not require PRs
or GitHub Issues. Per-clone hook activation is a separate setup step.

Full multi-agent delivery remains inactive by default; an explicit owner swarm
request enables scoped parallel work for that task, not a permanent policy
change. Security Reviewer remains independent/read-only (Read/Grep/Glob),
weekly and risk-triggered; .claude/agents/security-reviewer.md preserves the
CrossDesk checklist. Cloudflare security-audit is a separate full audit skill:
active code/tests/scanners/PoCs require real OS sandbox, no external network,
sanitized environment and limits; unavailable controls mean needs_validation.
Never grant broad Bash to the read-only reviewer.

Toolkit source/version and per-file provenance: .claude/toolkit.lock and the
in-progress adoption record. A1 copied/configured artifacts do not prove A2
integration, A3 quality, A4 security or P5 publication. The known local audit
script preflight behavior needs independent integration review; stale toolkit
copies are a finding, not a reason to abandon independent product auditing.
