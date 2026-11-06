# Resume the INCOMPLETE CrossDesk security audit

This is a public, sanitized checkpoint, not a clean security report. Findings
is [] because no candidate reached independent validation; it does not mean
there are no vulnerabilities. Status remains incomplete and paused. Do not
resume remote model calls until the outstanding explicit source-payload and
model-destination consent is received. Both rejected recon-b launches executed
no process; changing launcher/transport/agent would not waive that restriction.

## Recorded source and retained work

Target: SzymonPaczos/CrossDesk, clean commit
 d761d6805be6e70a9a23b0276fad16b1b6e6c969; public Git tree
9403671f840725f2ada68f34ada959d0a707bfb8. The checkpoint does not assess a later
adoption branch/worktree. Recreate that clean source ref in a dedicated bounded
review environment, or explicitly compare changed source and plan revalidation
before changing the source identity in metadata. Preserve the original checkpoint.
Published metadata uses target="." relative to the reviewed repository root,
not this checkpoint directory. The resuming parent resolves the local absolute
target only in private runtime metadata; do not commit a machine-specific path.

Skill: project-installed .claude/skills/security-audit, toolkit 2026.11.07 at
879edc6f6fcf08762adcd1c34244c582bb690535 on the published toolkit feature branch
chore/project-adoptions-2026-11-06. Preserve its complete companions/license.
Do not install globally or silently substitute current main. The skill is the
workflow; it does NOT provide a universal run-audit command. Private host
launchers, credentials and transport transcripts are deliberately not bundled.

Completed: one structured recon-a result (recon-a-facts.json), after two private
failed recon-a calls. Retained: 478-word preliminary architecture and 19-unit
ledger (17 deferred first-party, 2 explicitly out of scope). Global invocation
budget was not set; requested per-call limit is 4 USD/240 s for claude-fable-5-1.
Reset deferred units to planned only as their blocker is resolved and the
parent intentionally schedules them; do not change them to covered from these
planning documents or from schema validation.

## Exact methods not started

1. RECONNAISSANCE.md Phase 1 Agent 1b: principals, authority, identity/authz,
   privilege/confirmation/revocation/fallback and visible versus deployed controls.
2. Phase 1 Agent 1c: every lower-trust entry surface, transformations/copies/sinks,
   limits and parallel paths. Phase 1 Agent 1d: safe offline fixture/build paths,
   prohibited fetch/publish operations, runtime visibility, sandbox and artifact
   promotion capabilities. All three must use the required independent bounded
   read-only CLI with a verified source packet, after consent. Read/Glob/Grep
   only; StructuredOutput is formatting, not filesystem authority.
3. Reconcile architecture and every deterministic unit/block map from all four
   baseline results. The current ledger is preliminary, not exhaustive coverage.
   No compatible prior JSON ledgers/findings existed; old prose is a clue only.
4. HUNTING.md Phase 2: focused source hunters for the accepted units, exact required
   prompt blocks and structured results, followed immediately by a fresh coverage
   critic. Standard profile also needs a distinct final-clean critic. No hunter
   wave or either critic has run. Do not silently cap or skip uncovered units.
5. VALIDATION-AND-REPORTING.md Phase 3: independently refute/validate each genuine
   candidate, then Phase 4 schema-shaped final records and both validators.
   Phase 5: separate fresh record verification for every confirmed and
   needs_validation record. No candidate or final verifier has run.
6. Phase 6: derive reports from independently decided records and actual coverage.
   The current Phase 6 files disclose interruption; they do not certify preceding
   methods. Update completion only after all required evidence is present.

The parent alone writes shared metadata/architecture/ledger/findings/reports.
Technical read-only tools must prevent out-of-packet reads before returning
content; post-hoc trace checks alone do not establish that boundary. Target
builds/tests/PoCs require real OS isolation, no external network, empty
allowlisted environment, read-only inputs/tools, scratch-only writes, resource
limits and trusted no-follow bounded artifact promotion. Neither a worktree
nor a CLI tool list is that execution sandbox. Missing evidence is a run gap;
it is not automatically a vulnerability finding or severity.

## Installed-skill commands

From this published checkpoint directory INSIDE the CrossDesk clone, resolve
the installed skill without any private host path:

```sh
project_root="$(git -c core.fsmonitor=false rev-parse --show-toplevel)"
skill_dir="$project_root/.claude/skills/security-audit"
cat "$skill_dir/SKILL.md"
cat "$skill_dir/TOOLKIT-INTEGRATION.md"
node "$skill_dir/validate-findings.cjs" findings.json
node "$skill_dir/validate-coverage-ledger.cjs" coverage-ledger.json
```

These are the skill's exact validation interfaces, not audit execution.
Read RECONNAISSANCE.md, HUNTING.md, VALIDATION-AND-REPORTING.md and all selected
companion blocks before their phases. A configured supported delegation/CLI
adapter must be reviewed separately; no portable source-export launcher is
included or implied by this checkpoint. Retain truthful reviewed SHA, real
source-read receipts, per-call limits and the required consent; never fabricate
an endpoint or use copied commands as authorization.

Both validators currently pass for 0 records and 19 units. That proves only
format/state invariants. Seventeen units remain deferred; the actual security
review, critics and independent validation described above remain unfinished.
