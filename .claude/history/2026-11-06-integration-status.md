# Adoption integration status — 2026-11-06

A1 configuration is accepted within the scope of the JSON static receipt.
This is an adoption in progress, not an application release or full gate PASS.
Toolkit source: published review branch chore/project-adoptions-2026-11-06,
2026.11.07 at 879edc6f6fcf08762adcd1c34244c582bb690535 (toolkit PR46).
No production application source was modified. BootControl alone has a
changed audit-wrapper regression test, executed as 10mock cases in isolation.
Whole adopted skill directories match this source byte for byte. Security
Reviewer retains its complete local domain extension after the exact current
master prefix. Old override lock hashes intentionally preserve their original
baseline; they are not an undisclosed mismatch or rewritten provenance.

A2 remains OPEN. Native workers really dispatched and returned to Coordinator
for this task, but copied runtime/collector/local-gate templates do not establish
project start/resume/result/merge integration, fast/slow refill/restart behavior,
permission enforcement or post-merge cleanup. CrossDesk's approved default
multi-agent-inactive exception is preserved; no new always-on daemon or hook
was activated. Linux follow-up must demonstrate these behaviors against the
reviewed final revision before closing A2.

A3 source/Git review is in 2026-11-06-quality-audit.md. The independent execution
receipt in 2026-11-06-security-audit.md adds bounded tests with limitations;
it does not convert missing application/Linux/real-Polkit evidence to PASS.

A4 remains OPEN. Cloudflare checkpoint under 2026-11-06-cloudflare/ is explicitly
INCOMPLETE. Automatic approval review rejected further Claude/Fable source
review calls and requires explicit owner source-to-provider consent. No further
call was routed through a different agent/tool. Local exact-version advisory
checks and secret/SAST candidates remain distinct from validated app exploits.

P5 publication state is tracked in the canonical ADP brief and GitHub branch/PR.
No main merge, deployment, actual boot/ESP/libvirt mutation or gate bypass is
part of this handoff. Active failed gates must remain failures. The adoption
record stays Status: in-progress and toolkit-sync check exits 1 because A2/A4
are open. The helper fragment-link bug is fixed at the pinned source.
