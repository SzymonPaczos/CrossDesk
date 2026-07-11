# General Rules

Universal prohibitions and conventions that apply across the whole
repo, regardless of language or layer. For project navigation,
file boundaries, and the agent workflow, read [AGENTS.md](../../AGENTS.md).

## Absolute prohibitions

- **No hardcoded data as a substitute for empty state.** If a UI or
  CLI surface has no real data to show, render an explicit empty
  state (e.g., "No applications registered yet") — never fake
  numbers, fake comments, or sample names.
- **No placeholder text shipped as code.** "Coming soon", "TBD",
  "Wizard step 3 here" baked into UI strings is drift. Either
  implement the surface or render an empty state explaining the
  current limitation.
- **No "✅ done" for mocks.** In `ROADMAP.md`,
  `docs/EXECUTION_PLAN.md`, and `.claude/backlog.md`, "✅ done" means
  *runs against real inputs end-to-end*. A mock or dead-code stub is
  not done — mark it explicitly (e.g., `🚧 mock` or `[~PARTIAL]` in
  the backlog).
- **No client-side AI/LLM features without owner approval.** Cost,
  latency, and prompt-injection surface area make this a
  cross-cutting decision, not an implementation detail. Raise it
  before writing the call site.
- **No `--no-verify` on git commits or pushes** unless the owner
  explicitly says so. Hooks fail for a reason — fix the reason.
- **No `git push --force` to `main`.** Force-pushing to feature
  branches you own is fine; rewriting shared history is not.
- **No `*.mock` imports from production code.** Modules under
  `host/src/crossdesk_host/**/mock.py` and `guest/crates/**/src/**`
  feature-gated to `mock` are test-only. Production code must
  reach the abstraction Protocol (e.g.
  `crossdesk_host.abstractions.libvirt.LibvirtController`) and
  let the call site decide which implementation to instantiate.
  Enforced by a CI grep gate in `python-host` (whitelist:
  subpackage `__init__.py` re-exports +
  `daemon.py`'s Phase 3 dev-default). Adding a new bad import
  needs a matching `.claude/backlog.md` entry explaining why.

## Communication & work

- **Conventional Commits** (`feat:`, `fix:`, `chore:`, `refactor:`,
  `docs:`, `test:`, `style:`). Enforced (blocking on subject format)
  by the `commit-msg` hook since 2026-07-12.
- **Change provenance** (adopted 2026-07-12, DEC-META-008): a
  non-trivial commit's body carries `Intent`, `Task-Ref` and `Gates`
  trailers per [`change-provenance.md`](change-provenance.md); template
  in `.gitmessage`. Currently report-mode — the `commit-msg` hook WARNs
  on missing trailers, does not block. No AI attribution
  (`Co-Authored-By` / `AI-Contribution`) per toolkit D-006.
- **Write it down first, then continue.** Any non-trivial task
  discovered outside the current scope goes onto the board
  IMMEDIATELY — v0.1.0 work to [`PLAN.md`](../../PLAN.md), post-MVP to
  [`backlog.md`](../backlog.md) (unclear priority → its `Inbox`
  section) — without waiting for the owner to ask. Deduplicate first.
  Recording a task is not permission to start it.
- **Terse engineering tone.** Diff > narrative. Avoid trailing
  summaries when the user already sees the diff.
- **Stage long tasks.** Break a multi-hour task into 3–5 stages,
  `/clear` between stages, persist intermediate state to `PLAN.md` /
  `.claude/backlog.md` items (WORK_LOG.md ceremony retired 2026-07-05).
- **Language: English.** Code, comments, commit messages, and
  in-repo docs are English. UI strings ship as English plus Polish
  via `docs/I18N.md` (gettext + Qt `tr`).

## Branch-per-agent rule

Every agent session works on its own feature branch. Never push
commits onto a branch that another agent (or another conversation)
is also using, unless the owner explicitly asked for shared work.

- Naming: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`,
  `docs/<topic>`. Keep `<topic>` short.
- New session = new branch from a freshly-rebased `main`. Do not
  branch from another agent's feature branch.
- Mixing two agents' commits on one branch blocks selective merge —
  either everything ships together or you cherry-pick with
  conflicts. Separate branches = separate diffs = clean review.

Branch-per-agent still applies whenever more than one session runs at
once (parallel Claude runs, worktrees).

## Coordination protocol — WORK_LOG ceremony RETIRED (2026-07-05)

The old `WORK_LOG.md` START/END ledger (pushed to `main` per session) was
multi-agent coordination. Project = owner + one agent → retired. No agent
pushes START/END to `main` anymore.

- **What to do** → [`PLAN.md`](../../PLAN.md) (the single v0.1.0 board).
- **State / breakages** → [`.claude/status.md`](../status.md).
- **What shipped** → `git log` + [`.claude/history/completed-work.md`](../history/completed-work.md).

If two sessions ever run at once, still use separate branches (above) and
say so to the owner; the heavy push-to-main ledger isn't coming back.

## Don't

- **Premature abstraction.** Three similar lines beats a factory.
  Wait for the fourth.
- **Defensive code for impossible scenarios.** Trust internal
  callers. Validate only at system boundaries (gRPC servicer
  entry, libvirt response parsing, user CLI input).
- **Comments that explain *what*.** Names already say what.
  Comments are for *why* — a hidden constraint, a subtle invariant,
  a workaround for a specific bug. If removing the comment wouldn't
  confuse a future reader, don't write it.
- **Backwards-compat shims.** `_unused` renames, `// removed`
  comments next to deleted code, re-exports kept "just in case".
  If something is unused, delete it; if a callsite needs updating,
  update it.
- **Bundling refactors into bug fixes.** Fix the bug, ship the fix.
  Refactor in a separate diff if it's worth doing.
