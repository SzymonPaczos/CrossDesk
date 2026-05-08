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
  `docs/EXECUTION_PLAN.md`, and `FOLLOWUPS.md`, "✅ done" means
  *runs against real inputs end-to-end*. A mock or dead-code stub is
  not done — mark it explicitly (e.g., `🚧 mock`).
- **No client-side AI/LLM features without owner approval.** Cost,
  latency, and prompt-injection surface area make this a
  cross-cutting decision, not an implementation detail. Raise it
  before writing the call site.
- **No `--no-verify` on git commits or pushes** unless the owner
  explicitly says so. Hooks fail for a reason — fix the reason.
- **No `git push --force` to `main`.** Force-pushing to feature
  branches you own is fine; rewriting shared history is not.

## Communication & work

- **Conventional Commits** (`feat:`, `fix:`, `chore:`, `refactor:`,
  `docs:`, `test:`, `style:`). The pre-push hook does not enforce
  format, but reviewers do.
- **Terse engineering tone.** Diff > narrative. Avoid trailing
  summaries when the user already sees the diff.
- **Stage long tasks.** Break a multi-hour task into 3–5 stages,
  `/clear` between stages, persist intermediate state to
  `WORK_LOG.md` notes or `FOLLOWUPS.md` items.
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

The full multi-agent workflow (WORK_LOG START/END entries pushed
directly to `main`, conflict resolution, etc.) is in
[AGENTS.md](../../AGENTS.md) "Agent workflow" steps 6–13.

## Coordination protocol

`WORK_LOG.md` (not `.claude/active-work.md`) is the canonical
ledger of "who is working on what right now":

1. **Before first `Edit`/`Write`** in a session, read the "Active"
   section of `WORK_LOG.md`. If your planned scope overlaps an open
   START entry, pick a different task or ping the owner.
2. **At session start**, append a START entry per the format in
   `WORK_LOG.md` "Format". Commit and push directly to `main`
   (this single file is the documented exception to no-direct-main
   pushes).
3. **At session end** (success, blocked, or aborted), move the
   START entry to "Recent" and append a matching END entry with
   `result: success → merged as <sha>` / `result: blocked on …` /
   `result: aborted, …`.
4. **Stale entries (>24h with no progress).** Don't unilaterally
   delete another agent's entry — ask the owner first.

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
