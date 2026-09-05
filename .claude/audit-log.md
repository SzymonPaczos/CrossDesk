# Audit Log

Newest audit first. Format: each run dopisuje sekcję `## Audyt YYYY-MM-DD` na górę.

## Audyt 2026-09-05

**Verdict: FAIL — confirmed security/reliability defects and vulnerable local
Python dependencies.** No new independently demonstrated P0 VM escape. This
is an audit report, not a repair or release approval.

```text
AUDITED_REVISION: 8c173e01b57f4edcbec661df7003dc24767ace01
BRANCH: chore/audit-toolkit-current (based on chore/toolkit-update)
TOOLKIT_VERSION: 2026.09.05; check PASS; one declared CrossDesk specialization
DIFF_RANGE_OR_SCOPE: 3205027..8c173e0 (28 commits, 11 merges), plus current
 guest-to-host invariants, test baseline, delivery controls and unmerged
 origin/chore/audit-toolkit-2026-08-20 findings; no blind merge
PREVIOUS_AUDIT: 2026-08-23, 3205027122b599f84a982d7185658e91d604a9ae (13 days)
THREAT_MODEL_VERSION: ddbd34d97ef0fbcc728897d8bf3c65a534b09417; DEC-0019
SECURITY_REVIEW: FAIL — independent security_current, exact SHA above
RED_TEAM: FINDINGS — independent redteam_current, exact SHA above
DOCS_SOURCE: official Python devguide, cryptography changelog and maintainer
 advisory through web browsing; installed versions measured from local tools
DEPENDENCY_CURRENCY: REPORT — vulnerable/stale installed Python environment;
 declared Python 3.9 floor is upstream EOL, actual runtime is supported 3.14
SAST: Bandit 1 MEDIUM scanner finding (not a proven exploit); zizmor 3 INFO;
 Semgrep/CodeQL not installed locally, prior CI evidence explicitly separate
CODE_HEALTH_DELTA: n/a (no delta tooling); manual full-diff and invariant review
BACKLOG_WRITE: A0905-01..09 recorded/deduplicated; owner batch in needs-owner.md
EXCLUSIONS_OR_NA: no live KVM/Windows, suspend, reinstall, release/packaging,
 restore drill or stress/OOM test; no fresh local buf/qmllint/gitleaks/CodeQL/
 Semgrep; GUI test run timed out in earlier attempt (not counted as PASS)
```

### Measured checks and evidence provenance

| Check | Result / interpretation |
|---|---|
| Toolkit preflight + contrib | PASS; local audit file delegates to complete master skill, so contrib's heading difference is not a missing checklist |
| `bash .claude/audit.sh` at audited SHA | Exit 0; raw counters are unreliable in several fields, corrected below; not accepted alone as scanner-success evidence |
| `cd host && .venv/bin/pytest -q --cov=crossdesk_host --cov-report=term --cov-report=json:... -ra` | **1087 passed, 3 skipped, 29 warnings, 58.50 s**; **5714/7134 statements = 80.0953%**; configured floor 75% passes |
| Skip inventory | 1 needs xorriso; 2 destructive libvirt tests require explicit opt-in; no live domain was touched |
| `ruff check src/ tests/` / `mypy --strict src/` | PASS; 0 findings / 126 source files |
| Guest check, host tests, Windows-target clippy | Earlier same-day direct commands exit 0; guest runner summed **37 passing tests**. `git diff --quiet d56108c HEAD -- host guest gui proto infra .github .githooks` proves identical inputs; results reused, not represented as new runs |
| GUI check/clippy | Direct same-day checks pass on identical source; GUI tests timed out, not passed |
| Rust dependency scans | Direct fresh `cargo audit --deny warnings` / `cargo deny check --hide-inclusion-graph`: exit 0 both workspaces; 274 guest / 106 GUI packages; deny has **24 / 2 duplicate warnings**, not vulnerabilities |
| Python dependency scan | Fresh isolated pip-audit scanner, `--path host/.venv/lib/python3.14/site-packages`: exit 1 with **7 unique advisory IDs across 3 packages**; repeated IDs deduplicated. Editable crossdesk-host not on PyPI, skipped explicitly |
| `bandit -c host/pyproject.toml -ll -r host/src -f json` | Exit 1: **B314 MEDIUM**, `libvirt_ctl/real.py:80` XML parse. Input path reviewed; no independent malicious XML entry beyond already accepted whole-home write demonstrated |
| `zizmor --format json .github/workflows` | 3 Informational results (2 template expressions, 1 action-style finding), no blocking findings under project policy; first-party tag exception still owner-pending |
| Gate regression evidence | Current canonical template: **6/6**; existing pre-push tests pass (same-day adoption evidence). Those tests do not cover the missing-base/worktree-error paths found here |
| Negative verification | In an isolated `git archive HEAD host` tree, `test_release_ack_with_wrong_token_is_refused` exits 0 on fixed code, exits 1 after disabling only the token comparison. Working source untouched |
| Provenance | All 17 non-merge commits in the reviewed range contain Intent/Task-Ref/Gates; no AI attribution trailer introduced |

Commands and raw evidence: `/tmp/crossdesk-audit-current/` (current static,
coverage JSON/test log, pip-audit JSON, pip-check, tiny boundary checks,
fixed/mutated sentinel logs); `/tmp/crossdesk-audit-2026-09-05/` (same-day
unchanged-input Rust/SAST evidence); `/tmp/crossdesk-toolkit-update/` (gate
checks). Tool versions measured: Python 3.14.4, ruff 0.15.15, mypy 2.1.0,
cargo 1.98.0, zizmor 1.27.0. Reproduction summaries below are retained here
because temporary evidence directories are not permanent archives.

**CI is separate evidence:** latest hosted Security audit succeeded
[2026-08-31 on d56108c](https://github.com/SzymonPaczos/CrossDesk/actions/runs/33399559497);
CI succeeded [2026-08-26 on d56108c](https://github.com/SzymonPaczos/CrossDesk/actions/runs/32956833921).
There is no hosted run for this unpushed audit SHA. CodeQL, Semgrep, gitleaks
and Rust/Python scanner jobs succeeded then; Semgrep/Bandit commands use
`|| true`, so job success is not a zero-findings assertion.

### Findings and remediation order

1. **P1 A0905-09 — stale/vulnerable installed Python environment.**
   `cryptography 48.0.0` is installed; source requires `>=49.0.0`, installed
   crossdesk-host metadata still says `>=41.0`. Thus `pip check` misleadingly
   passes against stale installed metadata. pip-audit reports four unique
   cryptography advisories: `PYSEC-2026-3554`, `PYSEC-2026-3553`,
   `PYSEC-2026-3552`, `GHSA-537c-gmf6-5ccf`; two for pip 26.1.1:
   `PYSEC-2026-196`, `PYSEC-2026-3721`; one for setuptools 82.0.1:
   `PYSEC-2026-3447`. Runtime-library findings and installation-tool findings
   are different exposure surfaces. Do not claim reachable exploitation of
   every advisory: CrossDesk does not call all affected APIs. Recreate from
   current source, select patched dependencies and rerun SCA/tests. The
   [maintainer changelog](https://cryptography.io/en/latest/changelog/)
   identifies security fixes through 50.0.0; the
   [wheel OpenSSL advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-537c-gmf6-5ccf)
   distinguishes upstream wheels from source builds.
2. **P1 A0905-01 — home-sharing warning is erased.** `management.py:541`
   logs `warning=home_warning`; `redaction.py:176-188` drops its field/text.
   Actual configured logger + `PeripheralsConfig(... scope='home')` emitted
   `warning: <redacted>` in a tiny standalone process. The only production
   consumer does not deliver the warning elsewhere. Restore user-visible
   disclosure required by DEC-0019 without weakening secret redaction.
3. **P1 A0905-02 — unbounded nonce state and incomplete teardown.**
   `auth.py:80-105` treats each new nonce as a fresh sequence. Channels retain
   only the first for teardown. Coordinator's two 16-byte nonces in one
   fingerprint-valid context left one entry after first-nonce removal;
   independent Red Team's three-nonce case left two. A valid ShareChannel
   frame followed by fingerprint rejection leaves one entry because awaiting
   the failed consumer at `filesystem.py:83` bypasses cleanup at :88.
   Bind nonce/ownership to RPC lifetime, enforce length/count bounds, guarantee
   error/cancel cleanup. **Authenticated guest required; no mTLS bypass.**
4. **P1 A0905-03 — unbounded guest window state.** `control.py:239-240`
   dispatches to `rail_manager.py:103-113,230`; it retains arbitrary unique
   HWNDs, titles and icon bytes before icon-store validation. Manager survives
   stream close. Red Team's three tiny CREATED events retained three entries
   and invalid PNG bytes; no memory stress test was attempted. Bound count/
   aggregate bytes before storage and reclaim session state on disconnect.
5. **P1 A0905-04 — pre-push can silently skip all gates.** Its `git diff`
   process substitution (:103-109) loses the command's failure status. Red
   Team's tiny temporary repository with a missing remote-base object emitted
   `fatal: bad object` then exited **0**, claiming no changes. Failed worktree
   creation (:132-138) also falls back to mutable checkout (source evidence).
   Fail closed with fetch/retry instructions; add both fault-injection tests.
   Existing multi-ref/advisory-path limitations remain separate residuals.
6. **P1 A0905-05 — audit report counts can claim false success.** Current
   raw script said Bandit 0 despite JSON MEDIUM=1; counted **254** Python
   test files including venv instead of **97 tracked project files**; selected
   previous audit **July 22 / 45 days** instead of **August 23 / 13 days**.
   Scanner errors are discarded. Generated static table was replaced with
   this corrected report; no change to audit.sh was made by this audit.
7. **P1 A0905-06 — public Python support claim needs owner choice.**
   `requires-python >=3.9` includes upstream-EOL Python 3.9. Official
   [Python status](https://devguide.python.org/versions/) gives EOL
   **2025-10-31**. Actual local 3.14 and CI 3.12 are supported; no actual EOL
   running interpreter was found, so this is a support-contract P1 rather
   than an asserted live-runtime P0. Recommend a 3.12 floor and aligned docs.
8. **P2 A0905-07 — incomplete suite-quality controls**, detailed below.
9. **P2 A0905-08 — server-side gate policy unresolved.**
   `gh api repos/SzymonPaczos/CrossDesk/rules/branches/main` returned `[]`;
   legacy branch protection returned 404. Local hooks are real controls,
   but no server-required check protects main; Actions is post-push. Owner
   should choose explicit local-first acceptance or a compatible ruleset,
   without silently replacing the no-PR workflow.

Security Reviewer rated warning/nonce/window findings HIGH; Red Team rated
resource and gate findings MEDIUM conditional on authenticated guest/local
ref failure. Coordinator uses **P1** for remediation ordering; severity is
not conflated with unauthenticated reachability. Teardown is grouped with
nonce lifecycle rather than counted twice.

### Previous-report reconciliation

- `1243070` root-home JIT guard and `1adf106` minted-token/XML-quoting fixes
  are present; token sentinel above demonstrates a meaningful regression test.
- `e5d672b` fixes ordinary close; error exits and changing nonce remain open.
- The unmerged August 22 warning/nonce/window findings were verified and
  deduplicated into A0905-01/02/03, not imported blindly.
- `steady-state.xml` is writable/trusted, but both reviewers found no separate
  default-scope entry path after the root-home fix. Explicit home R/W already
  accepts host-user execution. Keep D2/D3 hardening, do not advertise a newly
  proven P0; child-path denylisting cannot filter a whole ancestor share.
- FreeRDP password argv observation lacks runtime cross-UID exposure proof;
  same-user malicious Linux process remains out of scope. No new confirmed
  password-exposure finding is asserted.
- Existing guest-redial, Stage-B provisioning, end-to-end launch metric,
  first-launch race, packaging/tag, SECURITY.md and Python lockfile tasks
  remain open; no duplicate feature tasks added. PLAN's old TERAZ and trailing
  summary still contradict its own completed criteria; reconcile during loop
  preparation. Existing signed decisions are not reopened.

### Test-quality baseline (new checklist, all properties assessed)

`test-baseline: 1 partial(plan) 2 partial(plan) 3 partial(plan) 4 corrected
5 pass 6 partial(plan) 7 partial(plan) 8 n/a(SQL) 9 n/a(SQL) 10 partial(plan)
11 partial(plan) 12 partial(plan) 13 pass(sample) 14 missing(plan)`

| # | Evidence / follow-up in A0905-07 |
|---|---|
| 1 | RPC errors are generally explicit; `management.py:534-536` silently falls back to no peripheral flags on config failure. No producer/error-state inventory |
| 2 | Real-wire mTLS/auth failure tests and token rejection pairs exist; not a complete producer inventory |
| 3 | Skips are named in runner output; no automated observer preventing loss of each optional lane |
| 4 | Runner counts above; original script mixed installed-package files with project tests, corrected and filed A0905-05 |
| 5 | Coverage floor 75 has measured 78% baseline comment; microbench measured baselines + 20% regression sentinel documented in existing work |
| 6 | Real hook file tested; missing-base/worktree failure and audit parser failures remain uncovered |
| 7 | Bandit skips, zizmor first-party exception and ignorefiles reviewed; expiry/review policy not systematic |
| 8 | No shared SQL database: database-writer lane requirement n/a. Temp paths and autouse real-libvirt guard protect default suite, with explicit destructive opt-in; no live run here |
| 9 | No SQL query variant surface: n/a; guest-driver/live-transport gaps tracked independently |
| 10 | CI pytest has no retry mask; no fresh repeated-run flake study, plan measured baseline before flake changes |
| 11 | FSM tests use injected clocks, but autopause/libvirt-async tests also use timed sleeps; migrate synchronization case by case |
| 12 | Gate fixture tests assert return/output; no complete inventory/nonempty anchor for every enumerating parser |
| 13 | Existing Hypothesis path, version parse/negotiation and EWMA properties; sampled actual fixtures; no universal coverage claim |
| 14 | Manual token mutation pair passes; no configured/measured mutation-tool pilot. Add pilot without invented score threshold |

### Deep-review coverage and limits (26-point checklist)

1 security: independent reviews above; 2 producers/slop: GUI progress and
catalog/recovery stubs explicitly listed in ignorefiles, not newly labelled
shipped; 3 tests: baseline table; 4 architecture: PLAN/cadence/count drift;
5 dead code: excluded known scaffolds, no speculative removals; 6 decisions:
DEC-0019 warning broken, known home opt-in preserved; 7 toolkit/docs: current
check PASS, official sources available; 8 gates: real-file negative evidence;
9 supply chain: SCA and lockfile gap; 10 delivery: hosted/local policy above;
11 provenance: trailers verified, existing no-attribution decision preserved;
12 disclosure: existing SECURITY.md/contact task open; 13 duplicate/empty
state: known catalog ratings/mock producer gaps remain explicitly deferred;
14 hygiene: no stash/prunable worktree, 97 tracked host test files, no
suspicious PII/backup filename hits outside reference vendor tree, git about
37 MiB versus guest build cache 8.8 GiB (not repository-history bloat), old
rescue/dependabot branches remain triage work; 15 currency: Python/SCA above;
16 deploy: no running hosted production, release review remains separate;
17 canonical artifact: proto is wire source, public tag/package evidence
not yet available; 18 restore: **not exercised**, no backup restoration claim;
19 external oracle: independent runtime/advisory sources, no civic-data
count domain; 20 DoD: PLAN has 8 live criteria, remaining live/owner gates
not self-certified; 21 security tools: configured vs advisory vs absent
explicit above; 22 negative test: token pair verified in isolated tree;
23 review: local-only project workflow preserved; 24 pipeline topology:
read master `ci-pipeline-architecture.md` §11/11a (not copied during audit);
25 defects: actionable reproductions/dedup recorded; 26 swallowed failures:
audit counters and config fallback covered above, no new historical timestamp
or identity-counter bug established.

### Next decisions and execution boundary

`needs-owner.md` now has a current batch: Python floor; server-gate policy;
existing release/environment/disclosure and later wire/security decisions.
The recommended initial repair queue is environment SCA → warning/nonce/
window bounds → hook/audit-report integrity, then reconcile the MVP/live
queue. This audit changes only report/backlog/decision-parking documents.
No production patch, VM operation, release, merge or push was performed.

---

## Audyt 2026-08-23

**Git:** `3205027` on `main`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 126 files)
- pytest collected: 1067
- bandit medium/high: 0
- servicer direct blocking libvirt/fs calls (want 0): 0

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 25
- gui cargo-deny issues: 2
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf: n/a
- .proto files: 5

**QML (`gui/`)**

- qmllint: n/a

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 0
- test files (python): 254
- #[test] annotations (rust): 85

**Drift & meta**

- architecture.md Last Updated: 2026-07-25 (29d ago)
- META decisions (status: aktywna): 8
- ADR DEC-NNNN total: 18

**Security**

- gitleaks: n/a (use `CROSSDESK_FULL_AUDIT=1 git push` for history scan)

**Cadence**

- previous audit: 2026-07-12 (42d ago)

### Nagłówek raportu (skill weekly-audit, Krok 3)

```
AUDITED_REVISION: 3205027122b599f84a982d7185658e91d604a9ae
DIFF_RANGE_OR_SCOPE: 2026-07-22..HEAD — 14 commitów, WSZYSTKIE docs/chore
  (parking pętli C4/C5/C6, sync toolkitu, backlog TOP). Jedyny nie-doc plik:
  .claude/toolkit.lock. Zero zmian kodu produkcyjnego.
PREVIOUS_AUDIT: 2026-07-22 (b0ecdc0) — 32 dni (audyt zaległy; próg 7 dni)
TOOLS: bash .claude/audit.sh (ruff/mypy --strict/bandit/cargo-deny/cargo-audit/
  clippy — wszystkie zielone poza cargo-deny 25/2 = duplikaty otel);
  zizmor 1.27.0 lokalnie; agenty security-reviewer + red-team (niezależne konteksty).
EXCLUSIONS_OR_NA: buf / qmllint / gitleaks = n/a lokalnie (brak narzędzi na boxie;
  CI je pokrywa). Krok 00 (toolkit-sync check) + Krok 05 (porównanie masterów) =
  DEGRADED — ~/DevProjects/claude-toolkit NIE ISTNIEJE na tym boxie.
THREAT_MODEL_VERSION: docs/THREAT_MODEL.md (bez zmian w oknie)
SECURITY_REVIEW: PASS — 1× MEDIUM (F-1 JIT-lite whole-$HOME bypass DEC-0019),
  1× NOTE (F-2 AuthValidator stream-leak), 1× NOTE śledzony (SEC-01). Zero CRITICAL/HIGH.
RED_TEAM: FINDINGS — A = F-1 (potwierdzony niezależnie, MEDIUM);
  B = ShareChannel token-authz + nieescapowany libvirt XML (LOW dziś / latent-MEDIUM
  przy Stage B). Recovery/reinstall P0 zweryfikowany JAKO ZAMKNIĘTY (finalize_steady_state).
BACKLOG_WRITE: recorded — 3 nowe (F-1, Finding B, F-2) do backlog.md; P0 pre-push
  i persystencje (SEC-01, SECURITY.md, lockfile, toolkit-DEGRADED) już śledzone.
```

### Warstwa głęboka (osąd agenta)

**Charakter okna:** czysto dokumentacyjne — 14 commitów, zero kodu produkcyjnego
(potwierdzone: jedyny nie-`.md` to `.claude/toolkit.lock`). Powierzchnia
bezpieczeństwa niezmieniona; findingi to realne wady istniejące od wcześniej,
odsłonięte przez adwersaryjny przegląd, plus persystencje.

**P0**
- **Gate `pre-push` — antywzorzec A1 NADAL nienaprawiony** (backlog TOP, 32 dni).
  Hook liczy zmiany z *working tree* (`git diff …origin/$DEFAULT_BRANCH...HEAD` +
  czyta pliki z dysku, l. 52/63/222…), nie z pushowanego commita odtworzonego przez
  `git worktree add --detach`, i nie czyta refów ze stdin. Lipcowy `1b9c6f1` załatał
  tylko word-splitting (NUL-array), nie rdzeń A1. Dowód domknięcia
  (`test-gates.sh → 6/6`) **niewykonalny** — toolkit nieobecny.

**P1**
- **[NOWE — F-1 / Red-Team A, MEDIUM, dwa agenty niezależnie]** JIT-lite dzieli
  **całe `$HOME`** dla pliku leżącego w korzeniu `$HOME` (`~/x.txt`), po cichu,
  **bez** ostrzeżenia `home_scope_warning` DEC-0019, i **nawet przy
  `shared_folder_enabled=False`**. `management.py:452` woła `_jitlite_flags`
  bezwarunkowo; `parent_share_path(~/x.txt)` = `Path.home()` (`path_validation.py:104`);
  kontrakt „caller must re-validate" z docstringu niespełniony. Gość → R/W do `~/.ssh`
  + klucz mTLS + hasło VM → eksfiltracja + host code-exec. Kolaps granicy G4, którego
  DEC-0019 miał bronić. **Blokuje kryt. #3 (FS Stage B live).** Zweryfikowane w kodzie.
- **[NOWE — Red-Team B, LOW dziś / latent-MEDIUM przy Stage B]** `ShareChannel`:
  `_token_ok` (`filesystem.py:128`) waliduje **tylko długość** 32B — zero autoryzacji,
  brak `share_id in active_shares`; `attach/detach_virtiofs` (`real.py:255/277`) budują
  device XML nieescapowanym f-stringiem z `share_id`/`host_path`. Sink dziś nieosiągalny
  (`trigger_mount` bez produkcyjnego callera → `_attached` puste), ale **musi paść przed
  Stage B** (kryt. #3). Zweryfikowane w kodzie.
- **[persystencja] SEC-01** — kanarek `gitleaks-action` v3.0.0 (`security.yml:48`) nadal
  niezweryfikowany jako fail-closed. Bez zmiany SHA/dowodu — status bez zmian.
- **[persystencja] Krok 00 + Krok 05 DEGRADED** — toolkit nieobecny na boxie → kanoniczna
  procedura (toolkit-sync check, porównanie masterów) niewykonalna. Decyzja właściciela:
  sklonować toolkit czy uznać kopie za samodzielne mastery.

**P2 / NOTE**
- **[NOWE — F-2, NOTE]** `AuthValidator._active_streams` rośnie bez ograniczeń dla
  heartbeat i filesystem — `remove_stream` wołane tylko w `control.py:291`, brak w
  blokach `finally` `heartbeat.py`/`filesystem.py`. Resource-leak proporcjonalny do
  reconnectów (atakujący musi przejść mTLS → nie ścieżka eksploitu).
- `cargo-deny` guest 24→**25** (+1) — duplikaty tranzytywne otel (znane, Tech-debt).
- Brak `SECURITY.md` (repo publiczne, brak kanału disclosure) — persystencja od 07-12.
- Brak lockfile'a Pythona (`ci-cd.md` §3) — persystencja.
- `audit.sh` raportuje „previous audit 2026-07-12" zamiast 2026-07-22 — quirk detekcji
  kadencji (czyta zły wpis/marker).
- Trzy lokalne gate'y cicho `n/a` (buf/qmllint/gitleaks) — CI pokrywa, lokalnie fałszywy
  komplet.

**Zamknięte / czyste (zweryfikowane):**
- **Recovery/reinstall P0 ZAMKNIĘTY** — `finalize_steady_state` na pierwszym Hello
  (`control.py:221`) redefiniuje domenę disk-boot=1/CD-ejected przed kolejną ramką;
  recovery = idempotentny `start()`, nie `hard_destroy`; gość nie sfałszuje
  `EVENT_STOPPED_DESTROYED`. (Red Team.)
- **zizmor job JEST w CI** (`security.yml:154`) — item A6 z 2026-07-22 domknięty.
- Per-frame AuthContext na **wszystkich 3** servicerach (fingerprint+nonce+seq per ramka);
  timeouty (libvirt 30s + pula 4 wątków, heartbeat `wait_for`); supply-chain hardening
  (brak `pull_request_target`, `permissions: contents:read`, `persist-credentials:false`,
  third-party SHA-pinned, pwn-request guard); sekrety gitignored; Rust `unsafe` z `// Safety:`.
- Provenance: commity robocze mają `Intent`; **atrybucja AI = 0** (D-006 OK); No-Docker OK;
  integralność referencyjna docs OK; `main` w pełni wypchnięty; `.git` 35M bez bloatu.

**SECURITY_REVIEW verdict:** PASS (wiąże SHA 3205027). **RED_TEAM:** FINDINGS (2).
Ratchet (Krok 4): brak nowych zamrożeń — findingi czekają na decyzję właściciela;
zizmor-w-CI już zratchetowany w poprzednim oknie.

---

## Audyt 2026-07-22

**Git:** `b0ecdc0` on `main`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 126 files)
- pytest collected: 1067
- bandit medium/high: 0
- servicer direct blocking libvirt/fs calls (want 0): 0

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 24
- gui cargo-deny issues: 2
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf: n/a
- .proto files: 5

**QML (`gui/`)**

- qmllint: n/a

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 0
- test files (python): 254
- #[test] annotations (rust): 84

**Drift & meta**

- architecture.md Last Updated: 2026-07-22 (0d ago)
- META decisions (status: aktywna): 8
- ADR DEC-NNNN total: 18

**Security**

- gitleaks: n/a (use `CROSSDESK_FULL_AUDIT=1 git push` for history scan)

**Cadence**

- previous audit: 2026-07-06 (16d ago)

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

### Warstwa głęboka (agent)

```text
AUDITED_REVISION: b0ecdc0866f0995a7e429b255cf39247a8756101
DIFF_RANGE_OR_SCOPE: e07028f..b0ecdc0 (fala merge'ów dependabota + sprzątanie) + pełne repo dla checklisty stałej
PREVIOUS_AUDIT: 2026-07-12 (`7b66676`)
TOOLS: bash .claude/audit.sh · zizmor 1.27.0 · mypy --strict (126 plików) · pytest 1064 passed/3 skipped · cargo check --workspace (guest+gui) · cargo test (gui) · cargo deny · cargo audit · cargo tree -d · gh run list
EXCLUSIONS_OR_NA: buf, qmllint, gitleaks — brak narzędzi na tym boxie (audit.sh raportuje `n/a`, NIE zero); SAST (semgrep/CodeQL) tylko w CI — run „Security audit" na `main` = success
THREAT_MODEL_VERSION: docs/THREAT_MODEL.md @ b0ecdc0 (bez zmian w tym zakresie)
SECURITY_REVIEW: PASS (1× MEDIUM → backlog, 2× NOTE; `.claude/agents/security-reviewer.md`, niezależny kontekst)
RED_TEAM: NOT_DUE 2026-07-12 (miesięczna kadencja; auth/secrets/deploy bez zmian merytorycznych)
BACKLOG_WRITE: recorded — backlog.md „Tech debt" (2 wpisy, `15f4618` + `558604f` + `b0ecdc0`)
```

**Kontekst:** audyt zbiegł się z falą merge'ów — 13 z 17 gałęzi dependabota
weszło do `main`, 4 odrzucone. Ocena dotyczy stanu PO tej fali.

#### Co potwierdzone jako zdrowe

- **Zgodność z decyzjami** — bez naruszeń. Brak `Dockerfile`/`compose.yaml`
  (DEC-0003); żaden z 10 `while True` nie jest pollingiem (blokujący event-loop
  libvirt, keepalive `sleep(3600)`, chunked hashing, plus zatwierdzony wyjątek
  DEC-META-006); w drzewie git tylko `generate_mtls.sh`, zero liści PKI; zero
  importów `*.mock` z produkcji; 0 TODO/FIXME w `src`.
- **Provenance** — wszystkie 6 nietrywialnych commitów tej fali ma komplet
  `Intent`/`Task-Ref`/`Gates`. Atrybucja AI: **0 trafień** (D-006 trzyma).
  Commity bota i revert bez trailerów — zgodnie z wyjątkiem konwencji.
- **Triggery workflowów zgadzają się z dokumentacją** — `security.yml` ma
  realnie `push` + `pull_request` + `schedule` (pn 06:17 UTC), czyli
  `AGENTS.md:64-69` mówi prawdę (naprawione w fali 2026-07-14, tu tylko
  re-weryfikacja).
- **zizmor po 5 bumpach akcji: 16 findings, 0 high / 0 medium / 0 low** —
  bez regresji względem stanu sprzed fali.
- **CI jako niezależny sędzia** — run na `main` (`29887625451`) = **success**,
  „Security audit" = success. Failure mają dokładnie te dwie gałęzie, które
  odrzuciłem ręcznie (`prost-types-0.14.4`, `tonic-build-0.14.6`) — ocena
  agenta i CI zgodne, niezależnie.

#### P1

1. **Bump otel rozdwoił stack gRPC w agencie Windows.** `opentelemetry`
   0.27→0.32 przeciągnął tranzytywnie **drugi** `tonic` i **drugi** `prost`:
   `cargo tree -i tonic@0.14.6` pokazuje `opentelemetry-otlp 0.32 → observability
   → agent-svc`, a `guest cargo-deny issues` skoczyło **16 → 24** (wszystko
   `duplicate`, zero podatności). Efekt zmierzony: `agent.exe` waży
   **5 664 256 B** wobec **5,2 MB** zapisanego w `PLAN.md` #7 (2026-07-14) —
   ok. **+9%** za opcjonalny eksporter, którego domyślnie nikt nie włącza.
   Do 2026-07-21 otel 0.27 używał **tego samego** `tonic 0.12` co my, więc
   rozjazd powstał dziś. Opcje: (a) revert obu merge'ów otel — najtańsze, OTLP
   jest opt-in; (b) zrobić sprzężoną migrację prost/tonic 0.14 (i tak jest w
   backlogu) i zejść do jednego stacku; (c) świadomie zaakceptować.
   *Rekomendacja: (b), a jeśli migracja nie rusza w tym tygodniu — (a).*
2. **Ścieżka OTLP nie ma ŻADNEGO testu — a właśnie ją przepisałem.**
   `build_otlp_layer` (`guest/crates/observability/src/lib.rs:59`) przeszedł
   breaking-change API (`SdkTracerProvider`, `Resource::builder`, batch exporter
   bez jawnego runtime'u). W całym crate'cie jest **jeden** `#[test]` i testuje
   writer JSON, nie ten kod. Inwariant DEC-0002 („zero telemetry by default")
   nie ma **żadnego** strażnika regresji — dziś opiera się wyłącznie na tym,
   że ktoś przeczyta `std::env::var(OTLP_ENV_VAR).ok()?`. Fix jest tani: test
   asertujący `None` przy nieustawionym i przy pustym `OTEL_EXPORTER_OTLP_ENDPOINT`.
3. **`architecture.md` i `README.md` wciąż obiecują whole-`$HOME` jako default
   — DEC-0019 zmienił to trzy dni temu.** Kod: `shared_folder_scope` = **`documents`**
   (`config/peripherals.py:180`). Dokumentacja: `.claude/architecture.md:29`
   i `:67` oraz `README.md:47` i `:120` mówią „the whole `$HOME` (DEC-0018)”;
   `.claude/loop-spec.md:29` i `:172` powtarzają to jako stan bieżący (wpisy
   dziennika z datami są historyczne i zostają). `README` jest user-facing —
   mówi użytkownikowi, że włączenie sharingu wystawia cały katalog domowy,
   co jest nieprawdą od `ddbd34d`. To dokładnie ta klasa driftu, którą
   `needs-owner.md` §9 zamknął dla plików boundary, ale nie objął tych czterech.

#### P2

4. **7 gałęzi `ratunek/stash-*` na `origin` ma 73 dni.** Wszystkie z 8-10 maja;
   diff względem `main` to niemal same usunięcia (starsze snapshoty), więc
   prawdopodobnie nie trzymają nic unikalnego — ale nikt tego nie potwierdził
   i nie wygasają. Do triażu i skasowania albo do jawnego „zostają, bo X".
5. **Krok 5 audytu jest dziś niewykonalny — mastera toolkitu nie ma na tym
   boxie.** `~/DevProjects/claude-toolkit` **nie istnieje** (został na MacBooku).
   Skill `weekly-audit` i `.claude/rules/audit.md` odsyłają do
   `NEW-PROJECT.md §9.2` jako kanonicznego źródła, a cały `.claude/rules/`
   opisuje się jako „kopie masterów z toolkitu" — od teraz nie ma z czym
   porównywać. Status kroku: **DEGRADED**. Decyzja właściciela: sklonować
   toolkit na ten box, czy uznać kopie w repo za samodzielne mastery i
   wyciąć odwołania.
6. **Trzy warstwy gate'ów cicho nie działają lokalnie:** `buf` (proto),
   `qmllint` (QML), `gitleaks` (sekrety) raportują `n/a`. `.claude/rules/ci-cd.md`
   §1 mówi wprost: „Ciche `skip` jest awarią gate'a". CI je pokrywa, więc to
   nie jest dziura w merge'u — ale lokalny pre-push daje fałszywe poczucie
   kompletu. To samo dotyczy `zizmor` (jest lokalnie, **nadal nie ma joba w CI**
   — item A6).
7. **Nadal brak `SECURITY.md` i lockfile'a Pythona.** Oba znane z audytu
   2026-07-12, oba bez ruchu. Przy publicznym repo brak kanału disclosure
   robi się coraz trudniejszy do obrony.

#### NOTE (bez akcji)

- `pytest collected` 1040 → **1067**; test files 254; `#[test]` (rust) 84.
  Wzrost z DEC-0019 (JIT-lite + scope), nie z tej fali.
- `guest cargo-deny 24` to **wyłącznie** `duplicate`; `cargo audit` = **0 vulns**
  w obu workspace'ach.
- Sprzątanie gałęzi: `origin` 31 → 13. GitHub sam skasował zmergowane gałęzie
  dependabota (auto-delete), więc lista „do usunięcia" z `needs-owner.md`
  domknęła się przy okazji.

#### Security Review — findings (niezależny kontekst, verdict PASS)

- **SEC-01 · MEDIUM · `security.yml:48` — major bramki sekretów bez potwierdzenia,
  że jest fail-closed.** `gitleaks-action` 2.3.9 → **3.0.0**. Ta akcja ma
  historię trybu, w którym kończy się kodem 0 mimo trafień (brak licencji dla
  organizacji = cichy no-op). Attack path: sekret trafia do historii → jedyna
  serwerowa bramka historii przechodzi na zielono → merge do `main` na repo
  **publicznym**. Lokalny mirror w `pre-push` jest warunkowy
  (`command -v gitleaks`), więc na maszynie bez gitleaksa nie łapie nic.
  Zamknięcie jest tanie i konkretne: **kanarek** — gałąź z syntetycznym kluczem
  w formacie łapanym przez gitleaks, push, oczekiwany job **czerwony**. Zielony
  = bramka jest fail-open i bump trzeba cofnąć.
- **SEC-02 · NOTE → ZAMKNIĘTE w tym audycie.** Reviewer (bez sieci) nie mógł
  potwierdzić pary SHA↔tag dla dwóch pinów, w tym tego, który dopisałem ręcznie.
  Sprawdzone `git ls-remote`: `gitleaks-action` v3.0.0 = `e0c47f4f…` ✅;
  `action-gh-release` v3.0.1 to **tag anotowany** — `refs/tags/v3.0.1` wskazuje
  obiekt `2bb465e9…`, a rozwinięty `refs/tags/v3.0.1^{}` = **`718ea10b…`**,
  czyli dokładnie nasz pin ✅. Komentarz `# v3.0.1` jest prawdziwy.
- **SEC-03 · NOTE.** Majory `upload-artifact` v7 / `download-artifact` v8:
  Actions **ignorują nieznane `with:` bez błędu**, więc gdyby major przemianował
  `if-no-files-found: error`, ochrona przed pustym artefaktem znika po cichu.
  Ścieżki exploitu nie ma (jest zapasowe `fail_on_unmatched_files: true`,
  `release.yml:267`), ale domyka to jeden dry-run `workflow_dispatch` przed
  pierwszym tagiem — i tak jest w kolejce jako C-1.
- **Potwierdzone jako zdrowe przez reviewera:** `permissions` nigdzie nie
  rozszerzone (top-level `contents: read` ×4, podniesienia punktowe; job z
  sekretem podpisującym **nie** ma `contents: write`); `persist-credentials:
  false` na wszystkich 13 checkoutach; polityka `.github/zizmor.yml` pokrywa
  YAML-e 1:1 po bumpach; floory pip **powyżej** wszystkich znanych łatek
  (żaden bump nie obniżył flooru); DEC-0002 utrzymane po porcie OTLP (bramka
  na zmiennej środowiskowej + `Err` → `None`, zero `unwrap` na tej ścieżce);
  boundary files (`proto/**`, THREAT_MODEL, DECISIONS) **nietknięte**;
  materiał z transferu nie wszedł do gita.
- **Uwaga operacyjna reviewera (nie finding):** jeśli nagranie
  `pararelInstaltionProcessVideo.mov` kiedyś trafi do publikacji — pokazuje
  żywą instalację, więc warto przejrzeć kadry pod kątem hasła VM.

---

## Audyt 2026-07-12

**Git:** `7b66676` on `chore/toolkit-adoption`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 126 files)
- pytest collected: 1040
- bandit medium/high: 0
- servicer direct blocking libvirt/fs calls (want 0): 0

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 16
- gui cargo-deny issues: 2
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf lint findings: 0
- buf format diff lines: 0
- .proto files: 5

**QML (`gui/`)**

- qmllint warnings: 0

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 0
- test files (python): 233
- #[test] annotations (rust): 84

**Drift & meta**

- architecture.md Last Updated: 2026-07-12 (0d ago)
- META decisions (status: aktywna): 8
- ADR DEC-NNNN total: 17

**Security**

- gitleaks worktree findings: 0

**Cadence**

- previous audit: 2026-07-05 (7d ago)

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

### Warstwa głęboka (agent, 2026-07-12)

Pierwszy audyt po adopcji fali toolkitu 2026-07-11 (DEC-META-008). Wykonany na
macOS dev-box — live-checki boxa Linux+KVM (real libvirt, VirtioFS, perf)
niedostępne, więc warstwa statyczna jest host-side-only (co i tak pokrywa cały
stack: Python/Rust/proto/QML/sec). Deep-layer pełna: Security Reviewer +
Red Team w niezależnych, read-only kontekstach z master-definicji.

```text
AUDITED_REVISION: 7b6667681780bf014737039bbe6bb4b33272a033
DIFF_RANGE_OR_SCOPE: f6a8574..HEAD (poprzedni udokumentowany audyt 2026-07-07;
  wpis „2026-07-06" nagłówkuje SHA 13df5d1 nierozwiązywalny po rewrite historii
  2026-07-07 — patrz NOTE niżej). 62 pliki: kod prod = host/ Python + CI/hooks/
  docs, zero zmian guest/ Rust.
PREVIOUS_AUDIT: 2026-07-06 (audit.sh) / deep-layer 2026-07-07
TOOLS: audit.sh (ruff 0 / mypy --strict 0 across 126 / pytest 1040 collected /
  bandit med+high 0 / cargo check+clippy 0 / buf 0 / qmllint 0 / gitleaks
  worktree 0); zizmor (uvx, 86 findings: 42 High / 26 Med — supply-chain
  workflowów); semgrep dostępny lokalnie; agent Security Reviewer + Red Team.
EXCLUSIONS_OR_NA: live libvirt/VirtioFS/perf/suspend (box-gated, nie ten mac);
  zizmor niezainstalowany na stałe (odpalony przez uvx jednorazowo).
THREAT_MODEL_VERSION: docs/THREAT_MODEL.md @ HEAD (bez zmian w oknie).
SECURITY_REVIEW: PASS (1× NOTE — libvirt_call default executor; brak
  CRITICAL/HIGH/MEDIUM). Zmiany kodu w oknie = wyłącznie hardening obronny
  (deadline libvirt, walidacja guest-input na granicy WindowIconStore, sekrety
  born-0600, redakcja `/p:`, pwn-request guard w ci.yml).
RED_TEAM: FINDINGS (1× HIGH: mutowalne tagi third-party w ścieżce release/sign
  → podpisany malware do userów, latentne do 1. release; 1× LOW: pre-push
  secret-gate bypass przez word-splitting). Guard self-hosted KVM (4ad3d21)
  potwierdzony szczelny; zero pull_request_target; brak expression injection
  z tekstu PR; brak cache/reusable-workflow surface.
BACKLOG_WRITE: recorded — P1 „CI / supply chain 2026-07-12" (security.yml
  manual-only vs AGENTS.md claim, SHA-pinning+Red-Team-HIGH, dependency bot,
  pre-push word-split bypass), P2 (SECURITY.md, status.md branch-drift, handoff
  refs, python lockfile, libvirt_call executor, zizmor, timestamp-bump NOTE);
  needs-owner §8 (AGENTS.md claim + workflow-wave sign-off) + 5 pkt DEC-META-008.
```

**Zgodność z decyzjami: CZYSTA.** No-Docker (brak Dockerfile/compose);
No-polling (0 nowych `while True` w oknie; DEC-META-006 `_tail_file` jedyny
wyjątek); proto nietknięte; seam libvirt szczelny (`import libvirt` tylko w
`libvirt_ctl/real.py`); brak leaf-certów w git (`infra/certs/` = tylko
`generate_mtls.sh`); brak atrybucji AI od rewrite'u 2026-07-07 (D-006 trzyma).
DEC-META-008 (ta adopcja) spójny — nowe rule-files dolinkowane, hooki
przetestowane, role audytowe skonkretyzowane.

**Slop / dead-code:** bez nowych. Świadome `🚧 mock` / Phase-deferred stuby
udokumentowane w `ignorefiles.md` + `status.md` (drive_map, iso_downloader
ScrapeBackend, recovery/, catalog ratings, fs-mount mocks) — nadal uzasadnione.

**Drift:** `status.md` opisuje `feat/resilience-logging` i Etap A
`feat/fs-drive-letter` jako „NIE merged", a kod JEST w main (`rail_supervisor.py`
@ `0f31d52`, `drive_map.py` @ `688b2a7`) → P2. `AGENTS.md` security-sweep claim
rozjeżdża się z manual-only `security.yml` → needs-owner §8.

#### P0 — brak

#### P1 (4 grupy → backlog „CI / supply chain 2026-07-12")
1. **[Red Team HIGH]** mutowalne tagi third-party w release/sign (podpisany
   malware; latentne do 1. tagowanego release).
2. **[SEC/docs]** `security.yml` manual-only, AGENTS.md twierdzi „always runs".
3. **[supply-chain]** brak SHA-pinu third-party (zizmor 42 High) + brak
   dependency bota.
4. **[Red Team LOW]** pre-push secret-gate word-splitting bypass.

#### P2 (porządkowe → backlog + status.md refresh)
SECURITY.md (repo publiczne bez disclosure); status.md branch-drift; wiszące
`handoff.md` refs; host bez python-lockfile; `libvirt_call` współdzielony
executor (NOTE Security Review); zizmor nie w CI; top-level `permissions:` +
`persist-credentials:false` (zizmor Med).

#### NOTE
- pre-commit bumpuje `Last Updated:` w architecture/ignorefiles — toolkit
  2026-07-11 uznaje to za kłamiący sygnał świeżości; świadoma decyzja opcja(b)
  z maja, do potwierdzenia.
- Stare SHA w audit-log (np. `13df5d1`) nie rozwiązują się po rewrite historii
  2026-07-07 — historyczne, bez akcji.

**Skille/MCP (§5+§7):** `weekly-audit` zaktualizowany do mastera 2026-07-11 w
ramach TEJ adopcji; role `security-reviewer`/`red-team` skopiowane. Brak
`.mcp.json` (bez zmian). Dalsza synchronizacja masterów = osobny Builder-commit
(Krok 5 skilla), nie część tego read-only audytu.

---

## Audyt 2026-07-06

**Git:** `13df5d1` on `main`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 125 files)
- pytest collected: 1014
- bandit medium/high: 0

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 16
- gui cargo-deny issues: 3
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf: n/a
- .proto files: 5

**QML (`gui/`)**

- qmllint: n/a

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 0
- test files (python): 249
- #[test] annotations (rust): 84

**Drift & meta**

- architecture.md Last Updated: 2026-07-06 (0d ago)
- META decisions (status: aktywna): 7
- ADR DEC-NNNN total: 17

**Security**

- gitleaks: n/a (use `CROSSDESK_FULL_AUDIT=1 git push` for history scan)

**Cadence**

- previous audit: 2026-06-12 (24d ago)

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

### Warstwa głęboka (agent, 2026-07-07)

Okno: `bf38110..13df5d1` (2026-06-12 → 2026-07-05, ~114 commitów pętli
autonomicznej). Cztery równoległe przeglądy (bezpieczeństwo / slop+dead-code /
testy / architektura+decyzje); wszystkie P1 zweryfikowane ręcznie w aktualnych
plikach przed raportem.

**Zgodność z decyzjami: CZYSTA.** No-polling zweryfikowane per-site (wszystkie
`while True:` event/stream-driven; jedyny sleep-poll to zatwierdzony
DEC-META-006 `_tail_file`). Proto nietknięte. Wszystkie edycje boundary files
(`7d8720b`, `34bc3d3`) pokryte zapisanymi podpisami właściciela w
`needs-owner.md`. Seam libvirt szczelny (`import libvirt` tylko w
`libvirt_ctl/real.py`); mock-importy w prod tylko na whiteliście. Brak Dockera,
brak leafów certów w git.

**Suita testowa:** 1013 passed / 1 uzasadniony skip / 0 fail (44,5 s).
Hermetyczność istotnie poprawiona w oknie: guard anti-real-libvirt (`13c765f`)
zweryfikowany jako szczelny (autouse, jedyny choke-point `_connect`), izolacja
FreeRDP-config i peripherals-config domknięta. Negatywne testy mTLS
(`test_mtls_handshake.py`) napędzają realny handshake TLS z poprawnym
dyskryminatorem (UNAVAILABLE ≠ UNIMPLEMENTED) — wzorcowe. Testy finalize
kodują kontrakt anti-data-loss (retry zostawia krok nieoznaczony).

**cargo-deny (16 guest + 3 gui):** wyłącznie `warning[duplicate]` (zdublowane
wersje transitive crates) + 1 `advisory-not-detected` (stale ignore, P2 niżej).
Nie-security.

**Skille/MCP (§8):** brak `~/DevProjects/claude-toolkit` na tym boxie (nic do
synchronizacji); brak `.mcp.json`. Bez zmian.

#### P0 — brak

#### P1 (5)

1. **[SEC] Hasło VM w plaintext w logu daemona.**
   `freerdp/real.py:133` loguje pełny argv FreeRDP (z `/p:<hasło>` z
   `rail_command.py:139`) na INFO → tee do rotującego pliku
   `~/.local/state/crossdesk/logs/` (0644). Redakcja
   (`observability/redaction.py`) jest value-blind (matchuje nazwy kluczy
   `password|secret|token`, nie wartości) → nie łapie. Lokalne konto czyta log →
   RDP na `localhost:3389` → pełna kontrola guesta (+ whole-$HOME share =
   `~/.ssh`). Obala 0600-ochronę `vm.toml`. (Linia logu sprzed okna —
   `986d523` 2026-05-07 — ale sweep `a211087` deklarował pokrycie security,
   które ta dziura falsyfikuje.) Fix: redakcja `/p:...` przed logiem +
   rozważyć 0600 na pliku logu.
2. **[SEC] `autounattend.prepared.xml` z realnym hasłem world-readable.**
   `cli/install_cmd.py:229-231` — `write_text()` bez 0600, plik trwa w
   state-dir. Kontrast: `vm.toml` 0600 z repair-path, tools ISO 0600 przez
   `mkstemp` — ta jedna kopia sekretu odstaje. Fix: `os.open(..., 0o600)`.
3. **[SEC] Blokujące wywołania libvirt na event-loopie bez deadline'u.**
   `ipc/control.py:220-221` (`on_session_ready()` w async handlerze) →
   `finalize_steady_state` → `real.py` `defineXML`/`_connect`; analogicznie
   `ipc/heartbeat.py:274` `hard_destroy()`. Uzbrojone dopiero przez A3 seam
   (`30579a6` + `9ac1da1`). Zwisający libvirtd przy pierwszym Hello = zamrożony
   cały daemon (3 plany + heartbeat + D-Bus listener), bez timeoutu. Łamie
   `.claude/rules/backend.md` („libvirt event-loop deadlines — pick one").
   Fix: `run_in_executor` + `asyncio.wait_for` wokół każdego wywołania real
   controllera osiągalnego z servicerów.
4. **[SLOP] Daemon nie loguje wybranego backendu libvirt przy starcie.**
   `daemon.py:131-138` — selekcja mock/real bez żadnej linii logu; jedyny ślad
   mocka to per-operacyjne `[LIBVIRT MOCK]` — czyli dopiero przy zdarzeniu
   lifecycle, dokładnie wtedy gdy rozróżnienie mock/real decyduje o losie VM.
   Fix: 1 linia `logger.info` przy selekcji (warning dla mocka).
5. **[TESTY] Gałąź mock→`on_session_ready=None` bez testu.**
   `daemon.py:186-189` — guard „finalize na mocku maskowałby data-loss" (P0
   z PLAN.md) egzekwowany wyłącznie inline w `serve()`; refactor mógłby go
   cicho odwrócić i żadna bramka tego nie złapie. Fix: wyciągnąć selekcję do
   testowalnego helpera + 2 testy (mock→None, real→finalize).

#### P2 (14)

1. **[SEC]** PKI write-then-chmod race — `installer/pki.py:76-84`: klucz
   istnieje z umask-perms między `write_bytes` a `chmod(0o600)`. Fix:
   `os.open` z 0600 od razu.
2. **[SEC]** Guest-controlled `icon_png` zapisywane bez walidacji do icon
   theme (`display/window_icon.py` `offer`/`_apply`) — powierzchnia ataku na
   host-side dekodery obrazów (gdk-pixbuf itd.). Defense-in-depth: sygnatura
   PNG + cap rozmiaru.
3. **[SEC]** `linux-kvm-smoke` (ci.yml) — label-gate bez guardu same-repo →
   pwn-request na self-hosted runner. Dziś teoretyczne (runner nie istnieje);
   przed postawieniem dodać `head.repo.full_name == github.repository`.
4. **[SEC]** PKGBUILD `sha256sums=('SKIP')` — tarball bez integralności
   buduje `agent.exe` trafiający do każdego guesta. Pin przy release.
5. **[SLOP]** Stale wpis w `ignorefiles.md`: `DBusNotifier._send_sync` nie
   jest już no-opem (realny `dbus_next` call) — wpis do usunięcia/aktualizacji.
6. **[SLOP]** `installer/drive_map.py` — 0 production callers (tylko testy),
   nieza rejestrowany w `ignorefiles.md` → przyszłe audyty będą re-flagować.
   Zarejestrować albo wpiąć.
7. **[SLOP]** Drift PLAN.md (#10) + backlog.md: twierdzą, że uninstall
   `--force`/confirm „zostaje" — a jest shipped (`427b15e`,
   `cli/uninstall_cmd.py:30-56`).
8. **[TESTY]** Brak marker-gated testu integracyjnego dla destrukcyjnych
   ścieżek `RealLibvirtController` (box-gated; live-verify dziś wyłącznie
   manualny — dodać przy P0 live-cycle, żeby #6 zostało regression-guarded).
9. **[ARCH]** `architecture.md` „Transport: gRPC over AF_VSOCK" — brak
   wzmianki o shipped seamie `bind_kind=auto|tcp|vsock` (wszystkie żywe
   milestone'y szły po tcp).
10. **[ARCH]** AGENTS.md „22 subpackages" vs realne 20 (boundary → owner).
11. **[ARCH]** REQUIREMENTS.md nie dokumentuje `bind_kind` /
    `libvirt.backend` / `shared_folder_*` (wzorzec new-config wymaga wpisu;
    boundary → draft do needs-owner).
12. **[ARCH]** `uninstall.py:111-115` ręcznie deriwuje state/config-dir
    zamiast `installer/state.py::default_state_file()` — dwie niezależne
    derywacje tej samej ścieżki.
13. **[ARCH]** 2 commity `i18n:` poza Conventional Commits (`chore(i18n):`).
14. **[DEPS]** Stale ignore `RUSTSEC-2026-0202` w `gui/.cargo/audit.toml`
    (`advisory-not-detected`) — do usunięcia.

**Obserwacje bez akcji:** `_keepalive()` striplikowany w 3 plikach lifecycle
(dokładnie na progu reguły „wait for the fourth"); `logs_cmd.py:610` 1 Hz
queue-wakeup w `--follow` (pre-window, powierzchnia DEC-META-006); duplikaty
cargo-deny (transitive, kosmetyka).

**Werdykt:** 114 commitów pętli bez ani jednego P0 i bez złamania decyzji;
hermetyczność testów netto lepsza niż przed oknem. Wspólny wątek P1:
hasło VM chronione w 1 z 3 miejsc spoczynku, a świeżo uzbrojona ścieżka
real-libvirt nie ma jeszcze dyscypliny deadline'ów, której wymagają własne
reguły projektu. Decyzja właściciela: co naprawiamy.

---

## Audyt 2026-07-05

**Git:** `5d87d2d` on `main`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 126 files)
- pytest collected: 971
- bandit medium/high: 0

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 16
- gui cargo-deny issues: 4
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf: n/a
- .proto files: 5

**QML (`gui/`)**

- qmllint: n/a

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 0
- test files (python): 244
- #[test] annotations (rust): 84

**Drift & meta**

- architecture.md Last Updated: 2026-07-02 (3d ago)
- META decisions (status: aktywna): 7
- ADR DEC-NNNN total: 17

**Security**

- gitleaks: n/a (use `CROSSDESK_FULL_AUDIT=1 git push` for history scan)

**Cadence**

- previous audit: 2026-05-31 (35d ago)

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

### Warstwa głęboka (osąd agenta)

Metoda: 3 równoległe agenty (bezpieczeństwo+decyzje / slop+backend /
testy+architektura+dead-code); kluczowe *nowe* znaleziska zweryfikowane
ręcznie greppem+odczytem (event-loop subprocess, puste pakiety, brak
timeoutu, drift). Statyczna warstwa wzorowa (ruff/mypy/bandit/clippy/
cargo-audit = 0; cargo-deny spadł 24→16 guest, 15→4 gui; 0 TODO w src).

**Ogólna ocena:** zdrowy, zdyscyplinowany projekt. Rdzeń produktu
zweryfikowany na żywo (A7-live: świeży `crossdesk install` → agent
auto-online → Notepad/Paint jako natywne okna Linuksa, zero ręcznych
kroków). Bezpieczeństwo: 0 P0/P1 — per-frame AuthContext na wszystkich
3 planes, mTLS `require_client_auth`, tokeny kryptograficzne
(uuid4/secrets), abstrakcje respektowane, brak sekretów w git, decyzje
(No-Docker / No-polling / whole-$HOME) niezłamane. Slop niski, Manager
GUI ma uczciwe empty-state.

**P0 (standing — nie nowe, ale otwarte i blokujące):**
- **`hard_destroy` → REINSTALACJA Windows / utrata danych — BLOKUJE A3.**
  Install-ISO jest `boot order=1` przez całe życie VM; heartbeat-FSM
  auto-recovery robi `destroy()`+`create()` → bootuje install-ISO →
  autounattend reinstaluje Windows na dysku, bez człowieka. Latentny dziś
  (daemon=mock-libvirt). Realny `LibvirtController` NIE MOŻE wejść do
  lifecycle zanim nie wyląduje steady-state-XML finalize (eject ISO,
  disk boot=1, flaga „installed"). `backlog.md` P0 + `needs-owner.md`.

**P1 (nowe w tym audycie):**
- **Blokujący `subprocess.run` na pętli asyncio daemona.** `control.py:220`
  woła `rail_manager.handle_rail_event()` synchronicznie w pętli async
  `_consume_session`; ścieżka CREATED→`WindowIconStore.offer`→
  `_refresh_caches` (`display/window_icon.py:139`) odpala 2× `subprocess.run
  (timeout=15)` → do ~30s zamrożenia CAŁEJ pętli (heartbeat FSM, filesystem
  plane, wszystkie streamy) przy każdym oknie z ikoną. Komentarz
  `rail_manager.py:126` „never blocks event handling" jest fałszywy dla
  sync subprocess. Ryzyko: distortion timingu heartbeat-FSM → false-positive
  recovery. Fix: `asyncio.to_thread`/`run_in_executor`. (Pokrewne, mniejsze:
  `SubprocessNotifier.notify` `subprocess.run(timeout=2.0)` z heartbeat/rail
  na pętli.)
- **Brak negatywnych testów mTLS-handshake (named critical path).** Każdy
  test z `require_client_auth=True` pokrywa tylko happy-path; brak testu
  odrzucenia cert untrusted/wrong-CA/expired ani hostname-mismatch na
  warstwie TLS. Fingerprint-pinning (app-layer) pokryty. Znany w
  `backlog.md` Tech-debt; podniesiony do P1 bo audit.md §4 nazywa to
  MUST-cover.

**P2 (nowe):**
- `update_mime_database` (`integrations/mime.py:120`) `subprocess.run` **bez
  `timeout=`** → potencjalny wieczny hang (łamie backend.md „infinite hangs
  are bugs"; kontrast: `window_icon.py:139` ma timeout=15).
- Dwa martwe puste pakiety: `virtiofs/__init__.py` + `wayland/__init__.py`
  (0 bajtów, 0 importerów) — do usunięcia; nie w ignorefiles.
- Phase-9 scaffoldy z 0 prod-callerami, nie w ignorefiles: `recovery/`
  (`bundle`/`snapshot`; `ExportDiagnosticBundle` zwraca `zip_payload=b""`
  zamiast wołać `export_bundle`), `catalog/ratings.py` + `catalog/user_apps.py`
  (`ListApps` używa inline hardcoded listy). Wire albo dodać do manifestu.
- GUI install-wizard ma fejkowy silnik postępu (`wizard/progress.rs`
  `INSTALL_STEPS` hardcoded + `ProgressView.qml` Timer, nie woła `host/`).
  Udokumentowany jako mock w `gui/README.md`, ALE `ignorefiles.md`
  „Security / placeholder UI" mówi „(none currently)" → manifest drift.
  Eskaluje do P1 jeśli GUI kiedyś prezentowane jako funkcjonalne.
- `.claude/architecture.md` drift: „Just-in-time VirtioFS… no permanent
  home-dir mount" (`:25`) i „No permanent host-dir exposure to the guest"
  (`:62`) sprzeczne z shipowanym default whole-$HOME R/W (DEC-0018/
  DEC-META-007). architecture.md jest agent-editable → fix; `:62` mirroruje
  `GOALS.md` (boundary — tylko flaga).

**P2 (potwierdzone znane / nity):**
- fs-mount mocki (`fs-mount/src/flush.rs` `mock_generate_release_ack`→1024,
  `mock_generate_lock_report`→0 handles) wołane BEZ `#[cfg(feature=mock)]`
  z realnego filesystem-plane agenta (`agent-svc/src/filesystem.rs`) →
  placeholder trafia do prod-builda. Phase-5, ale schować za feature.
  (backlog Tech-debt — stan bez zmian.)
- AuthContext `traceparent` (proto) bez wzmianki w THREAT_MODEL — advisory,
  non-security-bearing (`auth.py` traktuje malformed jako non-fatal); 1 linia
  do THREAT_MODEL.
- Znane/tracked (nie do naprawy tu): AGENTS.md „Repository layout" 5 vs 22
  podkatalogi (boundary), autopause↔LifecycleCoordinator duplikat kolejności
  suspend („merge when third caller arrives").

**Testy:** krytyczne ścieżki (AuthValidator rejection ×3 planes, FSM
transitions z backoff, `test_smoke_inprocess` real-agent boundary) mocne
i asertywne; jedyna realna luka = negatywny mTLS-handshake (P1 wyżej).
Skips wszystkie uzasadnione (env/HW-gated), 0 xfail, 0 `assert True`.

**Decyzja właściciela:** czeka na akceptację listy → pozycje do
`backlog.md`.

---

## Audyt 2026-06-12

**Git:** `8f266bb` on `feat/usability-shared-fs`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff: n/a (not on PATH)
- mypy: n/a
- pytest: n/a
- bandit: n/a

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 24
- gui cargo-deny issues: 15
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf: n/a
- .proto files: 5

**QML (`gui/`)**

- qmllint: n/a

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 0
- test files (python): 234
- #[test] annotations (rust): 84

**Drift & meta**

- architecture.md Last Updated: 2026-06-09 (3d ago)
- META decisions (status: aktywna): 6
- ADR DEC-NNNN total: 16

**Security**

- gitleaks: n/a (use `CROSSDESK_FULL_AUDIT=1 git push` for history scan)

**Cadence**

- previous audit: 2026-05-23 (20d ago)

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

### Korekta warstwy statycznej (venv niedostępny dla audit.sh)

Skrypt nie widzi `host/.venv` — wartości policzone ręcznie z aktywowanym venv:

- ruff: **8 błędów, wszystkie w `host/tests/`** (3× I001 import-sort, 1× F401 unused
  import `test_heartbeat_boot_probe.py:20`, 3× E402 `test_lifecycle_coordinator.py:148-151`);
  5 auto-fixable
- mypy --strict: **0 błędów (121 plików)**
- pytest: **870 passed, 2 skipped, 36.9s**
- cargo-deny "issues" 24/15 = wyłącznie warningi `duplicate` (transitive windows-*
  crates) + 8× `license-not-encountered` (licencje w allowliście nieużywane przez
  graf zależności) — zero błędów, kosmetyka konfiguracji deny.toml

### Warstwa głęboka (4 równoległe przeglądy: bezpieczeństwo / slop / testy / architektura+decyzje)

**1. Bezpieczeństwo — czysto.** Per-frame `verify_auth_context` na każdej ramce
wszystkich 3 płaszczyzn (control.py:253, filesystem.py:46, heartbeat.py:205);
mTLS leaves poza git tree (`git ls-files infra/certs` → tylko generate_mtls.sh);
wszystkie bloki `unsafe` w guest/ mają `// Safety:`; spawn FreeRDP przez
list-argv (brak shell injection); walidatory shared-folder (pusta/względna
ścieżka, separatory w nazwie share, mkdir-fail → drop drive+workdir) działają
i są przetestowane.

**2. Slop — werdykt: to NIE jest AI slop.** Zero hardcoded danych udających
realne; zero "Coming soon"/TBD w src; wszystkie zaślepki (sleep_sync,
ScrapeBackend, fs-mount mocks, control.py:149 pid=9999) jawnie opisane i
zarejestrowane w ignorefiles.md/status.md; status.md uczciwie raportuje
PORAŻKI (A1 workdir UNC→System32); komentarze to "why", nie "what"; milestone'y
"LIVE-verified" mają pokrycie w realnych commitach. Jedyny znany wyjątek:
`mock_generate_release_ack` wołany bez cfg-gate z `agent-svc/filesystem.rs:98`
— już w backlogu (Tech debt).

**3. Testy — mocne na ścieżkach krytycznych.** AuthValidator rejection paths
(3 tryby × 3 płaszczyzny), FSM watchdog (wszystkie przejścia + backoff cap),
VerifyCoordinator (korelacja, timeout, trace), nowe gardy peripherals
(empty-path, relative-path, mkdir-fail — pokryte po adversarial review),
WindowIconStore (expect/offer/TTL). Znane luki bez zmian: mTLS cert-pinning
failure-modes (backlog), CLI semver snapshot (backlog). **Brak progu coverage
w pyproject** mimo deklarowanych 78% — kandydat na ratchet.

**4. Architektura/decyzje — zgodne.** No-Docker (DEC-0003) ✅; no-polling —
jedyny `while True: sleep` to zatwierdzony wyjątek `_tail_file` (DEC-META-006),
reszta to event-driven `await` ✅; brak `import libvirt` poza real.py ✅; brak
edycji proto na branchu ✅; layering config→display→ipc respektowany w nowym
kodzie ✅; brak dead code poza pozycjami z ignorefiles.md. Fałszywy alarm
odrzucony w weryfikacji: stdlib `logging.getLogger` w window_icon.py to
celowy wzorzec projektu (udokumentowany w heartbeat.py:67,
verify_coordinator.py:39, rail_manager.py:44 — caplog + configure_logging
timing), nie drift.

### Lista P0/P1/P2

**P0:** brak.

**P1:** brak nowych. (Istniejące w backlogu bez zmian stanu: fs-mount mock
cfg-gate, mTLS failure-mode testy, NT-service agent, zombie xfreerdp reaper.)

**P2 (nowe):**
1. **ruff 8 błędów w testach** — I001/F401/E402, 5 auto-fixable
   (`ruff check --fix tests/`); pre-commit gate najwyraźniej nie obejmuje
   `tests/` albo wersja ruff dryfuje vs CI.
2. **Brak coverage ratchet** — pyproject.toml nie ma `fail_under`; baseline
   ~78% znany → zamrozić podłogę (np. 75) zgodnie z regułą ratchet.
3. **audit.sh nie aktywuje `host/.venv`** — sekcja Python raportuje n/a;
   dodać `source host/.venv/bin/activate` fallback do skryptu.
4. **deny.toml: 8× license-not-encountered** — przyciąć allowlistę licencji
   do faktycznie występujących (kosmetyka).

**Cadence:** poprzedni audyt 2026-05-23 (20 dni) — powyżej 7-dniowego rytmu.

**Ratchet (zamknięte tego samego dnia, decyzja właściciela, branch
`chore/audit-p2-fixes`):** wszystkie 4 P2 naprawione — (1) `fd1365e` ruff
0 błędów + `c04769b`/`e0f73c9` bramki pre-push i CI rozszerzone na `tests/`;
(2) `e0f73c9` coverage floor `fail_under=75` (baseline 77.74%) uzbrojony
przez `--cov` w CI; (3) `31c8198` audit.sh widzi host/.venv (ruff/mypy/
pytest/bandit przestają raportować n/a); (4) `b754b42` deny.toml allowlisty
przycięte do faktycznie występujących licencji (`cargo deny check licenses`
→ "licenses ok" w guest+gui).

---

## Audyt 2026-05-31

**Git:** `73c6141` on `main`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 118 files)
- pytest collected: 804
- bandit: n/a

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 1
- gui cargo check warnings: 2
- gui clippy errors (-D warnings): 1
- cargo-deny: n/a
- cargo-audit: n/a

**Proto (`proto/`)**

- buf: n/a
- .proto files: 5

**QML (`gui/`)**

- qmllint: n/a

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 0
0
- test files (python): 214
- #[test] annotations (rust): 79

**Drift & meta**

- architecture.md Last Updated: 2026-05-24 (20604d ago)
- META decisions (status: aktywna): 5
- ADR DEC-NNNN total: 15

**Security**

- gitleaks: n/a (use `CROSSDESK_FULL_AUDIT=1 git push` for history scan)

**Cadence**

- previous audit: 2026-05-23 (20604d ago)

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

### Warstwa głęboka (agent — workflow, 17 agentów, fan-out + adwersarialna weryfikacja)

Pierwszy audyt na świeżym Linux+KVM boxie (po pełnym bootstrapie dev-env + runtime).

**Sprostowania warstwy statycznej (artefakty świeżego boxa, nie defekty kodu):**
- `guest clippy errors: 1` — błędne. `cargo clippy --workspace -- -D warnings` exit 0; guest **czysty**. Liczba w automacie to przeciek z gui / cold-build.
- `gui cargo check warnings: 2` + `gui clippy errors: 1` — to **porażka builda `cxx-qt 0.7.3`**, bo brak Qt6-dev + szybkiego linkera (mold/lld/gold) na tym boxie. Luka dev-env (do bootstrapu: `qt6-base-dev qt6-declarative-dev mold`), nie kod.
- `architecture.md … 20604d ago` + `previous audit … 20604d ago` — **bug `audit.sh`**: `date -j -f` (BSD/macOS) nie parsuje na Linuksie → epoch 0. Realnie poprzedni audyt 2026-05-23 (8 dni temu).
- bandit / cargo-deny / cargo-audit / buf / qmllint / gitleaks = `n/a` (niezainstalowane lokalnie) → pokrycie audytu zawężone (CI je pokrywa).
- Stray `0` po linii TODO/FIXME (l.38-39) — drobny double-print w `count_lines` na pustym wejściu.

**Fan-out:** 8 surowych znalezisk → **4 confirmed, 4 dropped** + 1 od krytyka kompletności.

**Confirmed:**
- **[P1] Polling** `host/src/crossdesk_host/cli/logs_cmd.py:492` (`_tail_file`) — `while True: … await asyncio.sleep(0.25)`. Łamie regułę „No polling" (AGENTS.md „Coding rules"). Docstring uzasadnia (unika zależności inotify/kqueue), ale **brak zatwierdzonego wyjątku** w `decisions.md` / `docs/DECISIONS.md`. → decyzja właściciela: zatwierdzić wyjątek i udokumentować, ALBO przepisać na inotify (`asyncio.add_reader` na fd inotify).
- **[P2] Hardcoded `1024`** `guest/crates/fs-mount/src/flush.rs:31` — `total_bytes_written: 1024` w `mock_generate_release_ack()`, wołane bezwarunkowo z `agent-svc/src/filesystem.rs:98` (bez cfg-gate). Znany Phase-5 stub (`status.md` „Mock virtiofs handlers"); nowy kąt = **feature-gate** by nie trafiał do prod-builda.
- **[P2] Empty `icon_png`** `guest/crates/rail-bridge/src/events.rs:71` — `icon_png: vec![]` (Phase 4 placeholder), osiągalne z `windows.rs:117`. Ikony okien zawsze puste do Phase 4.
- **[P2] Drift `AGENTS.md:102-108`** — „Repository layout" listuje 5 podkatalogów `crossdesk_host/`, faktycznie 23 (m.in. `cli/`, `doctor/`, `abstractions/`, `lifecycle/`, `filesystem_ctl/`…). **AGENTS.md = boundary file** → zmiana wymaga zgody właściciela.
- **[P2] Brak `// Safety:`** (krytyk) `guest/crates/registry-scan/src/windows_impl.rs:266` — `display_name.unwrap()` bez komentarza, mimo że ten sam plik używa `// Safety:` poprawnie (l.246/260). Infallible (None → early-return l.245), ale łamie regułę backendu „unwrap/expect wymaga komentarza".

**Dropped (poprawnie — false positives wychwycone przez weryfikację):**
- Phase-5 mocki wołane bezwarunkowo — udokumentowane (`status.md`, `EXECUTION_PLAN.md` Week 18).
- `[mock]` marker w MountResult detail — intencjonalny.
- test-credsy `crossdesk`/`test123` — za `#[cfg(test)]` / `--features mock`, nieobecne w prod-buildzie.
- `TraceContext::is_valid()` „dead" w Rust — realnie używane po stronie hosta (`observability/trace_ctx.py:167`), świadoma symetria API host↔guest.

**Luki / rekomendacje procesowe (krytyk kompletności):**
- Brak automatycznego grep-gate na `import libvirt` poza `*real.py` — dziś tylko dyscyplina reviewera. Kandydat na ratchet (analogicznie do mock-import-gate, FOLLOWUPS:269).
- Brak testów failure-mode mTLS (cert-pinning / hostname-validation); `AuthValidator` pokrywa rejection paths, ale nie scenariusze mTLS-specific.
- `DEFAULT_HOST_ENDPOINT 127.0.0.1:50051` (`agent-svc/src/planes.rs`) — dev-default czytany z env w runtime; brak checklisty pre-prod.

### Lista P0/P1/P2 (do decyzji właściciela)

- **P0:** brak.
- **P1:** Polling `logs_cmd.py:492` — wymaga rozstrzygnięcia (zatwierdzić wyjątek vs przepisać na inotify).
- **P2:**
  1. feature-gate Phase-5 mocków `fs-mount` (`flush.rs:31` hardcoded 1024).
  2. `rail-bridge/events.rs:71` empty `icon_png` (Phase 4 — już na liście followups RAIL).
  3. `AGENTS.md:102-108` layout drift (boundary — zgoda właściciela na edycję).
  4. `// Safety:` na `windows_impl.rs:266`.
  5. `audit.sh` `date -j` → port na GNU `date -d` (tooling).
  6. grep-gate `import libvirt` poza `*real.py` (ratchet).
  7. testy failure-mode mTLS.

**Werdykt:** kod produktowy zdrowy — 0 P0, 1 P1 (polling, wymaga tylko decyzji), reszta to świadomie odroczone stuby i porządki. Adwersarialna weryfikacja odrzuciła 4/8 surowych znalezisk jako false-positives.

---

## Audyt 2026-05-23

**Git:** `f2ff03c` on `chore/adopt-claude-toolkit`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 117 files)
- pytest collected: 783
- bandit medium/high: 0

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 26
- gui cargo-deny issues: 15
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf lint findings: 0
- buf format diff lines: 0
- .proto files: 5

**QML (`gui/`)**

- qmllint warnings: 0

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 1
- test files (python): 207
- #[test] annotations (rust): 79

**Drift & meta**

- architecture.md Last Updated: 2026-05-20 (3d ago)
- META decisions (status: aktywna): 5
- ADR DEC-NNNN total: 15

**Security**

- gitleaks worktree findings: 0

**Cadence**

- previous audit: 2026-05-23 (0d ago)

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

---

## Audyt 2026-05-23

**Git:** `ba357af` on `chore/adopt-claude-toolkit`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 117 files)
- pytest collected: 783
- bandit medium/high: 0

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 26
- gui cargo-deny issues: 15
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf lint findings: 0
- buf format diff lines: 0
- .proto files: 5

**QML (`gui/`)**

- qmllint warnings: 0

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 1
- test files (python): 207
- test files (rust): 1

**Drift & meta**

- architecture.md Last Updated: 2026-05-20 (3d ago)
- META decisions (status: aktywna): 0
0
- ADR DEC-NNNN total: 15

**Security**

- gitleaks worktree findings: 0

**Cadence**

- previous audit: none yet

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

### Warstwa głęboka (agent review)

Pierwszy bieg po adopcji konwencji `claude-toolkit`. Zakres jak w
`.claude/rules/audit.md`. **TL;DR: codebase jest dobrze utrzymany —
0 P0, 0 P1 z nowych findings. Tylko 5 pozycji P2 (kosmetyka).**

#### Bezpieczeństwo
- **mTLS leaves w git history:** zweryfikowane greppem `git log --all
  --diff-filter=A -- 'infra/certs/'` — **NIGDY** nie były tracked. Tylko
  `generate_mtls.sh` ma historię. Komentarz w `.gitignore` jest stale i
  wprowadza w błąd (P2 niżej).
- **`gitleaks` worktree:** 0 findings.
- **`bandit -ll`:** 0 medium/high.
- **gRPC servicers:** `AuthValidator` (117 LOC w `ipc/auth.py`)
  enforces per-frame check via async `verify_auth_context`. Touch
  boundary per AGENTS.md — nie modyfikowane.

#### Slop / hardcoded data udające realne
- `ipc/control.py:141` zwraca `process_id=9999` jako placeholder
  z dokumentowanym komentarzem ("keeps the proto contract honest").
  Reachable tylko przez Phase 4 stub `cli/launch_cmd.py`, który też
  jest stubem. Świadome + dokumentowane.
- Hardcoded UI strings: 0 znalezionych (brak `Anna Kowalska`,
  `Lorem ipsum`, `John Doe` itp. w `host/src` i `gui/`).
- `palette.placeholderText` w QML to nazwa koloru Qt theme, nie UI
  string.

#### Backend
- **0 `while True: sleep()` polling.** Wszystkie `while True` (9
  hits w `host/src`) są await-driven: `asyncio.sleep`,
  `asyncio.Event.wait`, file `read()` chunked do EOF.
- **0 swallowed errors bez justyfikacji.** Wszystkie 10 hits
  `except Exception:` mają albo:
  - re-raise po cleanup (atomic write pattern w `atomic_write.py`,
    `user_apps.py`, `keyring/file_backend.py`, `credentials.py:112`)
  - explicit best-effort comment + log/notification call
    (`launch_cmd.py` z `nosec B110`, `rail_manager.py:127` z
    `logger.exception` + `notify_rdp_drop`)
  - dokumentowany "swallow silently — failed notification mustn't
    take down daemon" (`notifications.py:60`)
- **gRPC + HTTP timeouts:** AuthValidator enforces `_token_ok` +
  per-stream nonce. Server-side timeouts: gRPC server `add_secure_port`
  use default timeout-on-shutdown. Client-side: nie znaleziono
  bezpośrednich `aiohttp.ClientSession` w `host/src/` (ISO downloader
  jest mock-stub Phase 5).

#### Testy
- **783 pytest tests collected** (.5s wall — fast suite).
- **79 Rust `#[test]` annotations** across 11 plików w `guest` + `gui`
  (audit.sh policzył tylko 1 — bug regexu, P2 niżej).
- Strong coverage na krytycznych ścieżkach: `AuthValidator`,
  `LifecycleCoordinator` (7 nowych testów hibernation 2026-05-19),
  `HeartbeatServiceServicer.Channel` (boot_probe + missed-prepare
  heuristic + suspend/resume propagation), `RailManager` (26 tests
  na out-of-order events).
- Mock contract tests (`MockFilesystemController` 13, `MockLibvirt`
  per-method failure injection) — boundary fidelity.

#### Architektura
- **Abstrakcje respektowane:** `libvirt` importowany tylko w
  `libvirt_ctl/real.py` (10 funkcji + 1 type-only przy module-top).
  Brak `import libvirt` poza tym plikiem.
- **`*.mock` imports zgodne z policy:** 2 hits — `daemon.py:43`
  (Phase 3 dev-default, dokumentowany) + `filesystem_ctl/__init__.py:14`
  (subpackage re-export, whitelisted). CI grep gate aktywne.
- **DEC-0003 (no Docker):** ✓ brak Dockerfile / compose.yaml.
- **DEC-0005 (mock-driven):** ✓ Protocol abstrakcje + mock impls
  potwierdzone.
- **DEC-0006 (structured logging + trace):** ✓ `structlog` +
  `trace_ctx` + `traceparent` w `common.proto`.
- **`.claude/architecture.md` Last Updated: 2026-05-20** — 3d ago.
  Adoption commits z dziś nie bumpnęły bo `core.hooksPath` w tym
  clone'ie wskazuje na `.git/hooks/` (default), nie na
  `.githooks/`. Aktywacja per-clone (zob. CLAUDE.md "One-time setup").
  P2 niżej.

#### Dead code (weryfikacja heurystyk)
Wszystkie potencjalnie martwe pozycje wykryte greppem są DOKUMENTOWANE
w `.claude/ignorefiles.md` lub komentarzem w pliku:
- `iso_downloader.py::ScrapeBackend` — Phase 5 placeholder
  (ignorefiles.md).
- `watchdog/sleep_sync.py` — Phase 7 stub (ignorefiles.md).
- `cli/launch_cmd.py` — Phase 4 RAIL stub (ignorefiles.md).
- `guest/crates/registry-scan/src/windows_impl.rs:30` — Phase 8 TODO
  (App Discovery, backlog P0).
- `notifications.py::DBusNotifier._send_sync` — Phase 7 stub, ale
  **brak w ignorefiles.md** (P2 niżej, dodać po następnym commicie).

#### Zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`
- **15 ADR DEC-NNNN** w `docs/DECISIONS.md`. Wyrywkowa kontrola:
  DEC-0003 ✓, DEC-0005 ✓, DEC-0006 ✓.
- **5 META decyzji DEC-META-001..005** w `.claude/rules/decisions.md`
  (audit.sh nie policzył przez bug regexu, P2).
- 0 wykrytych regresji łamiących aktywną decyzję.

#### Skille / MCP
- `~/DevProjects/claude-toolkit/skills/` ma 1 skill (`weekly-audit`).
  Skopiowany do `.claude/skills/weekly-audit/SKILL.md` w tym commicie.
- **MCP:** brak `.mcp.json` w repo. Nic do sprawdzenia.

#### P0 / P1 / P2 z tego biegu

**P0:** żadnych. Codebase jest czysty pod kątem bezpieczeństwa,
swallowed errors, hardcoded data, decision violations.

**P1:** żadnych. Wszystkie partial / hardware-gated pozycje są już
udokumentowane w `.claude/status.md` lub `.claude/backlog.md`.

**P2 (kosmetyka — wszystkie meta o samej infrze audytu, nie o
codebase):**

1. **`audit.sh` regex bug — META decisions count.** Linia 144
   audit.sh: `grep -cE '^- \*\*DEC-META-[0-9]+'` nie matchuje
   bo nagłówki w `.claude/rules/decisions.md` są w formacie
   `^## DEC-META-NNN`. Fix: zmień regex na `^## DEC-META-[0-9]+`.
   Też wyciekło stray `0` w output (`||` fallthrough). Cel: liczyć
   poprawnie + bez "0\n0" stray output.
2. **`audit.sh` Rust test count bug.** Linia 113:
   `find guest gui -path '*/tests/*'` znajduje tylko integration
   test files. Unit testy w `mod tests` blocks (79 hits via
   `grep -rE '^\s*#\[(test|tokio::test)' --include='*.rs'`) nie są
   zliczone. Fix: zamień find na grep.
3. **`.gitignore` stary komentarz o mTLS keys.** Linie 67-69
   sugerują że `infra/certs/{ca,host,guest}.{key,crt}` są w git
   history — zweryfikowane: **nigdy nie były**. Tylko
   `generate_mtls.sh` był tracked. Komentarz wprowadza w błąd
   (sugeruje rotację + `git filter-repo` które są niepotrzebne).
   Fix: usuń lub przepisz komentarz na "files MUST never be
   tracked; rotate locally via generate_mtls.sh".
4. **`.claude/ignorefiles.md` brakuje wpisu** dla
   `notifications.py::DBusNotifier._send_sync` (Phase 7 stub
   landed wcześniej). Mały drift — dodać entry żeby vulture /
   dead-code audit nie raportował.
5. **Post-commit hook nie aktywny w tym clone'ie.**
   `core.hooksPath = .git/hooks` (default), nie `.githooks/`.
   Skutek: `.claude/architecture.md` + `.claude/ignorefiles.md`
   `Last Updated:` stamps drift względem realnego stanu repo.
   Aktywacja per-clone (`git config core.hooksPath .githooks`) jest
   udokumentowana w CLAUDE.md, ale brak automatycznej weryfikacji.
   Opcje: (a) dodać do `audit.sh` check że hooks są aktywne +
   ostrzeżenie; (b) po prostu uruchomić aktywację teraz; (c) zostawić
   bez zmian (user-clone responsibility per CLAUDE.md).

Audytu nie kończy żaden P0/P1 — wszystkie pozycje są albo
porządkowe (P2) albo już są w `backlog.md` / `status.md`.

---

