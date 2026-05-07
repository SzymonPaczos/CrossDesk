# Agent work log

Append-only coordination log so parallel agents don't step on each
other. Read this **before** picking a task. Update it **at start**
and **at end** of work. The user reads it to know what's happening.

## Format

Each entry is a single line:

```
[ISO-8601 timestamp] STATE · agent: <agent-id> · branch: <branch> · task: <task-keyword> · note: <one-line context>
```

States:

- **START** — agent claims a task; no matching END yet.
- **END** — agent finished (success, blocked, or aborted) — `note`
  must say which.
- **NOTE** — non-claim status update mid-work (rare; only for
  long-running tasks).

`agent-id` is whatever identifies the agent run (`claude-code`,
`cursor`, `aider`, plus a session UUID or short tag if multiple
runs are in flight on the same machine).

## Protocol

**Before picking a task:**

1. `git pull --rebase origin main` (so you see other agents' claims).
2. Scan "Active" below — if your planned task has an open START
   without a matching END, **pick a different task** or wait.
3. Scan "Recent" for context on what just landed (in case your
   planned task depends on it).

**At start:**

1. Append a START entry to "Active" below.
2. `git add WORK_LOG.md && git commit -m "chore(work-log): START
   <task-keyword>"` on `main` directly (this single file is the
   exception to the "no direct main commits" rule because it is
   coordination metadata, not code).
3. `git push origin main`. If push is rejected because someone else
   pushed first, `git pull --rebase` and retry. If the conflict is on
   their START entry for the same task, **pick a different task**.
4. Then proceed to your normal feature branch and implementation work.

**At end (success, failure, or blocked):**

1. Move your START entry from "Active" to "Recent" and append a
   matching END entry below it. Include the result in `note`:
   `result: success → merged as <sha>`, `result: blocked on <thing>`,
   `result: aborted, see <issue/conversation>`.
2. `git commit -m "chore(work-log): END <task-keyword>"` on `main`.
3. `git push origin main`. Same conflict-resolution as START.

The push of the work-log entry happens **independently of the
feature branch's merge** — START is pushed at the beginning, END is
pushed at the end, regardless of whether the feature branch itself
has merged. This is the only file an agent may push to `main` without
explicit user instruction; everything else still requires the user
to say "merge".

## Single-machine concurrency

If two agent sessions run on the same machine sharing the same
working tree, they see the same file system but may interleave reads
and writes. The git-push race protocol above resolves cleanly when
both push to origin. If neither pushes (e.g., user is running both
locally without internet), they should at minimum both
`cat WORK_LOG.md` before adding their entry, and prefer separate
branches so file contents don't clobber.

If the user explicitly wants two agents on the same task (rare —
e.g., two angles on a hard problem), the agents should use different
branch names and the user merges by hand later.

## Active

<!-- Currently in flight. Move to Recent on completion. -->

(none)

## Recent

<!-- Newest first. Trim entries older than ~30 days into RELEASE_NOTES
     or just delete; this log is operational, not historical. -->

- [2026-05-07 22:30] END · agent: claude-anthropic-conversation · branch: feat/build-config-lean-and-mock-features · task: build-config-lean-mock-features · note: result: success → merged as cb4a23f
- [2026-05-07 22:15] END · agent: claude-anthropic-conversation · branch: feat/pre-agent-setup · task: pre-agent-setup · note: result: success → merged as b8abc71 (CI workflow + MVP_SCOPE + EXECUTION_PLAN + agent workflow rules)
- [2026-05-07 21:00] END · agent: claude-anthropic-conversation · branch: feat/gpu-decision · task: gpu-passthrough-decision · note: result: success → merged as a9c1f5f (DEC-0009)
