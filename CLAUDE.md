# CLAUDE.md

Auto-load list for Claude Code sessions in CrossDesk. The canonical
source of project knowledge is [AGENTS.md](AGENTS.md) — that's the
human-readable navigation map and coding ruleset, referenced from
README.md. This file just tells the agent harness which rule files to
load.

## Load these files

- @PLAN.md — **jedyny board „co dalej" do v0.1.0** (TERAZ / NEXT /
  LATER + 12 kryteriów akceptacji). Zaczynaj tu.
- @AGENTS.md — project navigation, coding rules, agent workflow,
  file boundaries.
- @.claude/rules/general.md — universal prohibitions, commit
  conventions, branch-per-agent rule, coordination protocol.
- @.claude/rules/backend.md — Python (host) + Rust (guest)
  path-specific rules.
- @.claude/rules/audit.md — weekly audit procedure (statyczna +
  głęboka warstwa; P0/P1/P2 definitions).
- @.claude/rules/decisions.md — META-decyzje (proces / workflow /
  layout); ADR `DEC-NNNN` żyją w `docs/DECISIONS.md`.
- @.claude/architecture.md — stack snapshot (timestamp bumped by
  pre-commit hook so it lands in the commit, not as drift).
- @.claude/ignorefiles.md — dead code / generated artifacts manifest.
- @.claude/backlog.md — post-MVP / parking (NIE board MVP — to jest
  PLAN.md). Długi ogon + kontekst techniczny.
- @.claude/status.md — bieżące breakages / partial implementations.
- @.claude/needs-owner.md — zaparkowane decyzje właściciela + drafty
  boundary (czeka na podpis).

WORK_LOG.md ceremony jest **wycofany** (2026-07-05) — nie ładuj, nie
dopisuj START/END. Historia: `git log` + `history/completed-work.md`.

## Audit reminder

Sprawdź `.claude/audit-log.md` przy starcie sesji — jeśli ostatni wpis
`## Audyt YYYY-MM-DD` jest >7 dni, zaproponuj cotygodniowy audyt
(skill `weekly-audit`, procedura `.claude/rules/audit.md`).

## One-time setup per clone

Hooks live under `.githooks/` and need activation after `git clone`:

```sh
chmod +x .githooks/pre-commit .githooks/pre-push .githooks/post-commit
git config core.hooksPath .githooks
```

The `core.hooksPath` setting is per-clone (lives in `.git/config`,
not tracked) — it must be re-run after every fresh clone.

## Why this layout

`AGENTS.md` is the entry point for human contributors and is referenced
from `README.md`. Rather than duplicate its contents into a separate
`CLAUDE.md`, this file is a thin shim that delegates. The
`.claude/rules/*` files are stack-agnostic guardrails extracted from
`universals.md` (kept in the repo as a reference template); they're
intentionally short so an agent can load them every session without
ceremony.
