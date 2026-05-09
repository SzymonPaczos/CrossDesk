# CLAUDE.md

Auto-load list for Claude Code sessions in CrossDesk. The canonical
source of project knowledge is [AGENTS.md](AGENTS.md) — that's the
human-readable navigation map and coding ruleset, referenced from
README.md. This file just tells the agent harness which rule files to
load.

## Load these files

- @AGENTS.md — project navigation, coding rules, agent workflow,
  file boundaries.
- @.claude/rules/general.md — universal prohibitions, commit
  conventions, branch-per-agent rule, coordination protocol.
- @.claude/rules/backend.md — Python (host) + Rust (guest)
  path-specific rules.
- @.claude/architecture.md — stack snapshot (timestamp bumped by
  pre-commit hook so it lands in the commit, not as drift).
- @.claude/ignorefiles.md — dead code / generated artifacts manifest.
- @WORK_LOG.md — live "who's working on what" ledger; START/END
  protocol is in AGENTS.md "Agent workflow".

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
