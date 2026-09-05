# CrossDesk audit integration

The canonical procedure is [weekly-audit](../skills/weekly-audit/SKILL.md),
including both files under its `references/` directory. Load that procedure
for every audit; do not maintain a second checklist here. For an explicitly
requested audit with repairs, use [audyt-naprawczy](../skills/audyt-naprawczy/SKILL.md).

Before scanners, run `bash .claude/toolkit-check.sh`; `.claude/audit.sh` does
this automatically. A failed preflight stops the run without changing the
audit log. Source selection and project overrides are recorded in
[DEC-META-009](decisions.md).

CrossDesk-specific review context lives in
[security-reviewer.md](../agents/security-reviewer.md), `AGENTS.md`,
`docs/THREAT_MODEL.md`, `docs/DECISIONS.md`, and the known mock/generated
exclusions in [ignorefiles.md](../ignorefiles.md). Project boundaries and
previous owner decisions override generic examples from the toolkit.

The static script is only the measurement layer. Preserve scanner errors and
raw evidence; do not infer a successful scan from a zero text-match count.
A report requires the independent Security Reviewer and the risk-triggered
Red Team prescribed by the skill. Record scope, exact SHA, missing checks and
findings in `audit-log.md`; deduplicate work into PLAN (MVP) or backlog
(post-MVP), with owner decisions in `needs-owner.md`.

No application/VM changes or new security policy are implied by running an
audit. No audit is started merely by updating its tools or checking sync.
