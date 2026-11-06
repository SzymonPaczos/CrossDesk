# CrossDesk audit integration

Read the complete ../skills/weekly-audit/SKILL.md and all its reference files.
Use audyt-naprawczy only for an explicitly assigned audit-with-repairs.
The toolkit copy/preflight is one evidence class: a stale, blocked or
in-progress toolkit adoption does not cancel review of independent product
scope. Record its nonzero exit and unresolved adoption; never label that PASS.

.claude/audit.sh continues independent static sections after toolkit preflight,
records its exit, and returns that nonzero exit after writing the section.
Its existing text-match counters are measurements, not scanner verdicts;
scanner errors/missing tools require raw exit/report evidence collected by the
Coordinator. Do not infer security from zero textual matches. A1 used only
bash -n, no scanners/tests/hooks on the host.

Context: ../agents/security-reviewer.md, ../decisions-register.md, CLAUDE.md,
docs/THREAT_MODEL.md, docs/DECISIONS.md and ../ignorefiles.md. Project boundaries
and accepted risks override generic examples. The Security Reviewer remains
read-only. Full ../skills/security-audit/SKILL.md is a separately orchestrated
Cloudflare audit; target-controlled code needs a real OS sandbox, no external
network, sanitized environment and resource/time limits. Missing controls are
needs_validation, without active reproduction on the host.

Record the full assessed SHA, raw evidence scope, missing checks, DELIVERY_REVIEW,
TASK_COMPLETENESS, PROCESS_DRIFT and CONTEXT. Findings route to PLAN (MVP) or
backlog (post-MVP/process) under DEC-META-009/010; do not duplicate acceptance
stages. No audit, production/VM operation or remediation starts merely because
these configurations were adopted.
