# AGENTS.md — CrossDesk

An agent with a task brief follows that brief and its exact files. Do not
load the whole PLAN, backlog, decision register or historical instructions.
An agent without a brief starts at CLAUDE.md.

Use your own branch. Merge/push/production require owner authorization.
Never bypass hooks, force-push main, expose secrets or execute untrusted
project code on the host outside the agreed OS sandbox.

Owner approval is required for technical ADRs, threat model, requirements,
MVP scope/goals, proto wire format and ROADMAP changes. Preserve libvirt,
AF_VSOCK/mTLS/per-frame AuthContext and DEC-0019 sharing defaults.
Canonical instructions: CLAUDE.md; brief-specific domain contracts must be
included in the brief. AGENTS.md is a pointer, not a second workflow.
Codex Builder preamble: .claude/templates/codex-builder/preamble.md
(A2 runtime activation remains pending).
