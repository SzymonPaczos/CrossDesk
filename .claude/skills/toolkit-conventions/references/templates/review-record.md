# Review: <commit SHA>

**Task-Ref:** <TASK-ID / issue / task brief>
**Reviewed revision:** <full commit SHA>
**Reviewer identity:** <human / independent agent run / required check URL>
**Acceptance source:** <path or URL>
**Diff range:** <base...head>

## Deterministic evidence

- <command/check URL + result>

## Findings

- <severity + file:line + reproduction, or `none`>

## Security

`PASS | NOT_TRIGGERED <reason> | ACCEPTED_RISK <decision-id> | BLOCKED`

## Discovered tasks

`recorded <backlog refs> | none`

## Verdict

`PASS | NEEDS_WORK | BLOCKED`

<!--
Prefer an immutable PR review/check-run. For a local-only flow, the owner or
integration role persists this record; the Builder must not author approval
of its own commit. A verdict is invalid after the reviewed SHA changes.
-->
