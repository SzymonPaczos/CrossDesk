> REVIEW CANDIDATE ONLY. A2 remains OPEN. This refactored adapter has syntax,
> metadata-prepare and six guard checks; provider end-to-end after refactoring
> and Git lifecycle/cleanup in the required isolated environment are unverified.
> It is kept under reference, with no startup hook or active project integration.
> The prior live-session proof used the private predecessor, not this final file.
> On Linux verify real `ps`, the pinned CLI/toolkit and all stated controls first.

# On-demand toolkit adapter — CrossDesk

This workflow is inactive until explicitly invoked for ADP-2026-11-06-01/A2. It creates no hook, daemon, scheduled task or default swarm. Existing project decisions remain authoritative. It supports the accepted read-only reconnaissance graph, not arbitrary Builder permissions or application delivery.

Prerequisites: Python 3.9+, Git, the explicitly trusted toolkit root matching all profile SHA256s, and the validated Claude CLI release. An owner-consent JSON must bind this project, exact committed source SHA and exact model. State, raw traces and receipts must stay outside every source checkout. CLI updates or toolkit changes require explicit revalidation; do not bypass a binding failure.

Manual preparation, after reviewing profile and source consent:

```sh
python3 .claude/reference/a2-on-demand/toolkit-on-demand.py prepare \
  --project-root . --toolkit-root /path/to/trusted-toolkit \
  --state-dir /path/to/private/a2-state \
  --profile .claude/reference/a2-on-demand/a2-readonly.json \
  --source-sha d761d6805be6e70a9a23b0276fad16b1b6e6c969 --model claude-fable-5-1 \
  --consent-file /path/to/private/owner-consent.json \
  --task-ref ADP-2026-11-06-01/A2 --authorize-task
```

Run `python3 .claude/reference/a2-on-demand/toolkit-on-demand.py run --state-dir /path/to/private/a2-state` as a scoped task. After controller interruption use `resume`; never prepare over existing state. The graph has capacity two and each node has one attempt. A blocked result stays blocked; any repair/retry needs an explicit reviewed decision. Source is a clean Git clone at the accepted SHA, not the current dirty worktree. Only the master read-only adapter exports committed regular source, with Read/Glob/Grep, safe-mode/restricted and no MCP/customizations. No application code or tests run on the host through this adapter. Target tests and deterministic Git fixtures still require the strict OS/container sandbox.

An actual delegated observer must run `watch --state-dir ... --consumer main --poll-seconds 1 --shortest-worker-seconds 5 --max-wait 30`, forward every result to the main harness, then renew watching. The command returns at the first event, not batch end. The observer/main must persist result plus all remaining accepted stages, then use `ack --state-dir ... --consumer main --through CURSOR`. Ack is receipt, not acceptance or backlog closure. `events` and `status` are read-only control-plane operations; `resume` reconciles durable attempts instead of launching completed work again.

Each attempt's private session-handle.json binds `runtime_run_id`, `node_id`, `reviewed_sha` and real `provider_session_id` from Claude's init event. `handle_kind=claude_cli_session` is a conversation/session handle; `native_task_id` remains null because no native background-task API is used. No arbitrary chat-push capability is claimed. Claude --bg/agent-view and its supervisor are intentionally not activated.

The model's exit 0/success does not imply PASS. Original master adjudication and independent acceptance must verify JSON/report schema, source SHA, required reads, model/tools and complete process cleanup. Malformed prose is BLOCKED, as observed in the BootControl negative case. No parser repair or silent retry is applied.

Source review, result receipt and deterministic merge/cleanup are separate evidence categories. The adapter itself neither imports provider commits nor runs Git merge/push or deletes arbitrary worktrees. Integration/cleanup use the trusted runtime and only its owned, clean, confirmed-integrated worktrees. Real native-provider timing was measured on frozen public source; deterministic fixture workers must never be described as provider CLI workers.

Raw prompts/transcripts, runtime environment, credentials, home paths and private artifact locations never enter project history. Publish only sanitized source/proof hashes, measured outcomes/limits and pending stages.

CrossDesk DEC-META-009/010 and the inactive-by-default multi-agent exception remain unchanged. This explicit ADP task is not consent for always-on orchestration.
