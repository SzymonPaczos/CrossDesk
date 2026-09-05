# Needs Owner — batched decision ledger

The autonomous loop ([`loop-spec.md`](loop-spec.md)) parks here anything it
must not do alone: boundary-file edits, owner decisions, and changes whose
correctness needs human eyes. **Review in batches**, decide, and the loop
resumes. Resolving one = either you author the boundary edit, or you reply
"apply" and the loop applies the drafted text below for your final sign-off.

## Audit 2026-09-05 — current decision batch

- **Python support floor (A0905-06):** recommend Python **3.12+**, matching CI,
  rather than continuing the declared 3.9 floor (upstream EOL 2025-10-31).
  Local runtime is 3.14; this is a compatibility/documentation decision, not
  an assertion that the running daemon is on an unsupported interpreter.
  After approval, update packaging/runtime requirements and the relevant
  user-owned documentation together; verify installation and tests.
- **Server-side gate policy (A0905-08):** GitHub reports no effective main
  rules. Local hooks remain real gates, but a failed diff can skip them and
  CI is post-push. Choose explicit acceptance of the current local-first
  risk or required checks/ruleset compatible with the no-PR workflow.
  Existing first-party SHA-pinning and WARN-to-blocking choices are still
  open; they are not implicitly resolved by toolkit adoption.
- **Existing release decisions remain parked:** tag/go-no-go after burn-in,
  Arch packaging environment, public disclosure contact and package domain;
  app-discovery/proto and future GPU/peripheral threat boundaries need their
  own design decisions. Do not re-ask signing-for-beta, documents default,
  localhost RDP policy or the already authorized staged reinstall.

These decisions do not prevent read-only audit completion or preparation of
ordinary nonce/window/warning/gate corrections. Security-policy changes still
follow the boundary rules in AGENTS.md.

## Decided this session (2026-06-29) — drafts ready below

- [x] **FS exposure default = whole `$HOME` R/W.** Owner confirmed
  (2026-06-29), with the explicit heads-up that this exposes `~/.ssh` and
  `~/.config/crossdesk` (host mTLS private key + VM password) to the guest
  when sharing is enabled. Shipped (a0ca5ca): `shared_folder_scope` default
  `home`; `documents` / `custom` available for a narrower surface. Boundary
  docs drafted below (DEC-0018, THREAT_MODEL rows, DEC-META-006, MVP_SCOPE).
- [x] **MVP_SCOPE #3 — FS rebalance.** Stage B = v0.1.0 floor, Stage C
  (JIT-per-file) = post-1.0 user-selectable mode. Draft edit below (§1).
- [x] **THREAT_MODEL honesty (pre-announce).** Reality diverges from the doc
  (whole-`$HOME` FS, real `LogonUserW`, TCP-loopback dev transport). Draft
  rows below (§3). You author/sign the security boundary.
- [x] **Semver label = `0.1.0-alpha`.** Owner confirmed (2026-06-29). Apply
  when the release/versioning surfaces are touched.

## Z adopcji toolkitu 2026-07-12 — do decyzji (DEC-META-008)

Adopcja fali toolkitu 2026-07-11 wykonana (polecenie właściciela
2026-07-12; szczegóły w `rules/decisions.md` DEC-META-008). Cztery
punkty wymagają Twojego podpisu:

- [ ] **D-007 — profil CI: potwierdź hybrydowy.** Stan faktyczny: hosted
  GitHub Actions (repo publiczne — `ci.yml`, `security.yml`, `release.yml`)
  + local-first mirror (pre-push lustrzy pipeline). *Rec:* potwierdź
  hybrydę jako formalną odpowiedź D-007; dopiszę status do DEC-META-008.
- [ ] **Ratchet trybu raportowego → blokada.** Dwa nowe gate'y działają
  jako WARN: (a) trailery `Intent`/`Task-Ref`/`Gates` w `commit-msg`,
  (b) preflight świeżości audytu (>7 dni) w `pre-push`. Konwencja
  (`change-provenance.md` §5, `rules-as-gates.md` §3) przewiduje 1–2
  tygodnie trybu raportowego, potem decyzja o blokadzie. *Zapytam
  ponownie ~2026-07-26.*
- [ ] **Polityka atrybucji AI (kadencja miesięczna, pierwsza: 2026-07-12).**
  Zaktualizowany skill audytu każe raz w miesiącu ponawiać pytanie: czy
  chcesz włączyć oznaczanie udziału AI w commitach
  (`AI-Contribution: none|assisted|generated`)? Dziś obowiązuje D-006 =
  **bez atrybucji** (spójne z rewrite'em historii 2026-07-07). Odpowiedź
  (także „nie zmieniamy") zapiszę w `rules/decisions.md` z datą.
- [ ] **Hook `UserPromptSubmit` maksymalizacji promptów (§9.3).** *Rec:*
  NIE wdrażać — wstrzykiwane co prompt przypomnienie „czekaj na zielone
  światło" koliduje z autonomiczną pętlą (`loop-spec.md`) i trybem
  „merge po zielonych bramkach". Jeśli wolisz mieć — powiedz, dodam do
  `settings.json`.
- [ ] **`WORK_LOG.md` — archiwizacja.** DEC-META-003 (plik w roocie)
  oznaczona jako wycofana (ceremonia umarła 2026-07-05). *Rec:*
  `git mv WORK_LOG.md .claude/history/2026-07-05-work-log.md` — czysty
  root, git pamięta. Powiedz „przenieś", a wykonam.

## §8 — ✅ ROZSTRZYGNIĘTE 2026-07-14: opcja (a) + cała fala workflow

**Właściciel podpisał: „wykonaj falę + merge".** Pętla wykonuje całość i merguje
po zielonych bramkach; właściciel czyta diff post-hoc.

- **(a) wybrane:** przywracamy triggery `push` + `pull_request` + `schedule`
  (poniedziałki) w `security.yml` — repo jest publiczne (Actions darmowe), więc
  `AGENTS.md:64-69` staje się **prawdziwe bez edycji boundary**. Wariant (b)
  (przepisanie AGENTS.md na „manual-only") odpada.
- **Fala** (backlog P1 „CI / supply chain 2026-07-12") autoryzowana w tym samym
  podpisie: SHA-pinning third-party `uses:` + digest semgrep, top-level
  `permissions:` w `ci.yml`/`compat-matrix.yml`, `persist-credentials: false`,
  `.github/dependabot.yml`.
- **Konsekwencja dla granic:** `.github/**` **przestaje być boundary** dla pętli
  (zapisane w [`loop-spec.md`](loop-spec.md) toggles). Nadal jest **security
  code** — bramkowane `zizmor`em (dziś 40× `unpinned-uses` → cel 0) i raportowane
  w trailerze `Gates:`. Kolejka: `loop-spec.md` Faza A, item **A2**.

## §9 — FS defaults: rewizja DEC-0018 → drabina scope'ów — ✅ APPLIED 2026-07-19

Owner "apply" 2026-07-19 → landed on `feat/fs-documents-default`: **DEC-0019**
added to `docs/DECISIONS.md` (DEC-0018 marked *Amended by*); boundary docs
updated (`MVP_SCOPE.md` #3 + Phase-5/FS line, `THREAT_MODEL.md` §C5 row I +
security-claim #2, `PLAN.md` #3 row + NEXT + summary); code: `peripherals.py`
scope default `home`→`documents` + `home_scope_warning()`, `management.py`
`_jitlite_flags` + `_launch` wiring (per-launch parent-dir `/drive:` overrides
the persistent scope, keeps other peripheral flags) + loud home-scope launch
warning. Tests: new default/opt-in/warning + JIT-lite share/skip/override
(65 pass in the two files; full suite green). Gates: ruff + mypy --strict clean.
Sign-off boxes below kept for the record. **Owner still authors the exact
THREAT_MODEL security wording if they want to refine my applied draft.**

Owner decision (conversation 2026-07-19, thesis-driven): the *mechanism* of
DEC-0018 stays (opt-in share, `scope = home|documents|custom`); what changes is
the **default** and the posture. Ladder: (1) default `documents` + **JIT-lite**
(per-launch rdpdr share of the opened file's parent dir, dies with the app
session), (2) `home` stays as an explicit opt-in behind a loud warning naming
`~/.ssh` + the mTLS key, (3) Stage C JIT-per-file remains the post-1.0
tight-isolation mode. Rationale discussed: whole-`$HOME` R/W default collapses
the G4 trust boundary — guest *write* to `$HOME` = host code execution
(dotfiles/autostart/`~/.local/bin`), guest *read* = `~/.ssh` + VM password
exfiltration; same exposure class as VirtualBox shared-folders (abused by
Ragnar Locker/Maze). `documents`+JIT-lite keeps the UX (Save → `Z:` →
Documents) while honoring the original "on-demand sharing, no persistent home
mapping" commitment (B1).

Say **"apply §9"** and I land the whole batch (ADR + boundary edits + code
branch). Sign-off items:

- [x] **DEC-0019 draft** (insert at top of `docs/DECISIONS.md`):

      ## DEC-0019: FS share default narrows to `documents`; whole-$HOME becomes a loud opt-in; JIT-lite ships in v0.1.0

      **Date:** 2026-07-19 · **Status:** active · **Amends:** DEC-0018

      Sharing remains opt-in (`shared_folder_enabled` default OFF) and the
      DEC-0018 mechanism/staging is unchanged. When sharing is enabled, the
      default scope becomes **`documents`** (was `home`). `home` remains
      available as an explicit opt-in accompanied by a loud CLI/GUI warning
      naming the exposure: the guest gains R/W over `~/.ssh`,
      `~/.config/crossdesk` (host mTLS key + VM password), and writable
      dotfiles/autostart — i.e. guest compromise escalates to host-user code
      execution. Additionally v0.1.0 ships **JIT-lite**: launching an app
      with a file argument ("Open with Notepad") shares only the file's
      parent directory for that RAIL session (per-launch rdpdr `/drive:`);
      the share ends when the app session ends. Stage C JIT-per-file
      (`ReleaseAck`) stays post-1.0 as the tight-isolation mode.

      **Why:** a whole-`$HOME` R/W *default* collapses the G4 trust boundary
      through the filesystem while the control plane keeps per-frame auth —
      an inconsistent security posture, and the same exposure class as
      always-on VM shared folders. The `documents` default + JIT-lite
      preserves the intended UX at negligible security cost.

- [x] **Code (gated on the ADR):** `peripherals.py` scope default
  `"home"` → `"documents"`; loud warning path when `scope = home`; JIT-lite
  wiring (launch `file_path` → parent-dir `/drive:` for that session) +
  tests. Non-boundary, lands on one branch with the docs.
- [x] **§7a (MVP_SCOPE #3) draft superseded** — replace the pending §7
  wording with:

      3. With file sharing enabled, a Windows app can open and save files
         under the configured share (v0.1.0 default scope: `documents`); a
         `.txt` opened via "Open with Notepad" is shared per-launch
         (JIT-lite: the file's parent directory only, for the lifetime of
         that app session). Whole-`$HOME` is an explicit, warned opt-in.
         (Stage C JIT per-file mount/detach = post-1.0.)

- [x] **THREAT_MODEL §3a/§3b re-word** (you author): residual risk should
  now read "default `documents`; `home` opt-in raises risk to High (host
  code-exec via writable dotfiles), mitigated by explicit warning".
- [x] **PLAN.md #3 note** — after sign-off I update the criterion row
  (⚠️ boundary → resolved by DEC-0019) and the NEXT "FS Stage B live" line.

## Still open (boundary-file edits / owner calls)

- [ ] **#12 packaging install-test — blocked on environment + first release tag (loop 2026-07-25, C6).**
  The AUR PKGBUILD and agent bundling are done and host-side sound (`af8fd76`
  tested the `_resolve_tools_inputs` packaged-dir contract; I re-confirmed all
  five `install -D` sources exist in-tree). But the *actual* "install from the
  package" acceptance test can't run here: this box is **Ubuntu 26.04**, so there
  is no `makepkg`/`pacman`, and the PKGBUILD's `source=` fetches
  `github.com/.../archive/v0.1.0.tar.gz` — a tag that **does not exist**. So #12
  needs two things I won't do autonomously: **(a)** an Arch host or a clean Arch
  chroot to run `makepkg -si`, and **(b)** the first tagged `v0.1.0` release so
  there's a tarball to source (also the trigger for the `sha256sums=('SKIP')` →
  pin in backlog C-1). Both are owner calls — tagging a release is the beta
  go/no-go you've kept for yourself. *Rec:* decide the release-tag timing; if you
  want #12 proven before then, point me at an Arch chroot and I'll run
  `makepkg -si` against a `--holdver` local checkout.

- [ ] **Ratchet: hash-pin GitHub's OWN actions too? (surfaced by A2, `05653c7`).**
  The wave pinned every **third-party** action to a SHA (that was your sign-off's
  scope) and encoded the convention in `.github/zizmor.yml`: `actions/*` and
  `github/*` may stay on a major tag, everything else must hash-pin. That policy
  is doing real work — running zizmor with `--no-config` reports **33 High**
  findings, all of them first-party actions on `@v4` / `@v5` / `@v3`.
  `.claude/rules/ci-cd.md` §2 (the convention we adopted from the toolkit) says
  to pin these too: *"Każde zewnętrzne `uses:` przypnij do pełnego 40-znakowego
  commit SHA, **również akcje GitHub**."* So today the repo knowingly diverges
  from its own rule for 13 `uses:` lines.
  *Rec:* **do it** — a compromised `actions/checkout@v4` tag is not more far-fetched
  than a compromised `dtolnay/rust-toolchain@stable`, and dependabot keeps SHA pins
  fresh as long as the version comment stays on the line. Cost: a noisier diff and
  13 more pins to bump. Say "pin first-party" and the loop lands it + flips the
  zizmor policy to a blanket `hash-pin` (then the gate is 0 findings with **no**
  exception, which is a much stronger floor). Say "keep the tags" and I'll record
  the divergence as an explicit exception in `ci-cd.md` so the audit stops
  re-raising it.
- [ ] **Delete the 17 merged stale `origin/*` branches? (A3, 2026-07-14).** All 17
  are fully merged into `main` (verified with `git branch -r --merged`), so they
  carry nothing `main` doesn't already have and deleting them is recoverable by
  re-pushing the SHA. I did **not** do it: it mutates the shared remote and you
  never asked for it (a mass-cancel of CI runs in the same session was correctly
  blocked for the same reason). Say "clean the branches" and I'll delete exactly
  the merged ones and print the list first. The two unmerged ones
  (`origin/chore/handoff-transfer`, `origin/feat/get-metrics-rpc`) stay.
- [ ] **Proto edit — app-discovery RPC.** `ListDiscoveredApps` /
  registry-scan guest→host channel needs a `proto/**` change. *Rec:*
  approve a `RegistryScannerService` so installed apps + Start-menu/Desktop
  shortcuts mirror into native Linux launchers.
- [ ] **REQUIREMENTS F-marker re-baseline.** F1.1/F2.1/F5.1 are marked ❌
  but work live; F6.1 (JIT VirtioFS) is genuinely not built. Boundary file
  → owner approves the re-mark.
- [x] **Code-signing strategy for `agent.exe` — DECIDED 2026-07-05: self-signed
  for beta.** Self-signed publisher root CA installed into the guest (already
  built); document "unsigned-to-the-world" honestly. Not a release blocker. EV /
  Sigstore revisited post-beta if distribution demands it.
- [ ] **Repo-hosting domain (deb/rpm).** Open since 2026-05-07. Blocks the
  apt/dnf repos in milestone D.
- [ ] **ISO acquisition + Windows licensing stance.** *Rec:* "bring your
  own ISO + your own license" in README/wizard (drop auto-download); state
  the licensing/legal expectation plainly to a Linux-forum audience.
- [x] **FreeRDP RDP cert policy — DECIDED 2026-07-05: `ignore`.** A daemon-spawned
  FreeRDP has no stdin, so any cert rotation (Windows update, expiry) deadlocks
  the launch on an unanswerable TOFU prompt. The RDP endpoint is `localhost:3389`
  SLIRP-forwarded to OUR OWN guest (no MITM surface; real trust = mTLS gRPC +
  Windows cred). Loop may switch `rail_command.py` `cert_policy` default
  `tofu`→`ignore` for the localhost path. The matching `docs/THREAT_MODEL.md`
  row is a boundary draft (owner authors).
- [ ] **A7-live adversarial-audit findings (2026-07-01).** 6 confirmed defects
  in `backlog.md` P0 "A7-live install-path findings". The one needing owner
  awareness: **[P0-latent] `hard_destroy` → Windows REINSTALL / data-loss** —
  the heartbeat-FSM auto-recovery boots the install-ISO (still boot-order-1 for
  the VM's whole life) and can silently reinstall over the disk. Latent today
  (daemon uses mock-libvirt) but **A3 must not wire the real LibvirtController
  into lifecycle until the steady-state-XML finalize lands.** Not a boundary
  edit — flagged so it's on the go/no-go radar.
- [x] **▶ P0 live-verify — GREENLIT 2026-07-14 (owner: „pełny destrukcyjny
  cykl").** The loop now owns the whole sequence; it is Phase B of
  [`loop-spec.md`](loop-spec.md): `uninstall --force` (closes #10) → fresh
  `install` (re-verifies #1, and yields the *faithful* domain: fresh nvram,
  install-ISO still boot-order-1) → daemon `backend=real` → agent Hello fires
  `on_session_ready` → `finalize_steady_state` redefines to steady-state →
  `virsh destroy` → recovery `create` must boot the **disk, not the installer**
  → agent reconnects ≤90 s. **Closes #6, unblocks A3.** Wipes the current
  milestone install by design.
  **Safety net (done 2026-07-14):** the 30 GB `…milestone-bak.qcow2` was moved
  to `~/crossdesk-backups/` — it had been sitting *inside* the state dir that
  `uninstall()` `rmtree`s (`uninstall.py:112`), so the destructive cycle would
  have deleted the backup along with the install. Verified outside before B1.
  **Abort rule:** if the recovery `create` boots the **ISO**, the loop STOPS and
  reports — that is the data-loss path itself, not something to retry blind.
- [ ] **Final go/no-go** for the public beta cut (after burn-in).
- [x] **`docs/GOALS.md` whole-$HOME alignment — APPLIED 2026-07-05** (owner
  "apply"). §5 landed: G4 row, advantages row, Vision annotation, closing line.
  `.claude/architecture.md` FS-drift (Storage + Non-goals) fixed in the same pass.
- [x] **`AGENTS.md` — WORK_LOG ceremony retired + PLAN.md added — APPLIED
  2026-07-05** (owner "apply"). §6 landed: Agent-workflow rewritten (no
  START/END push), File-boundaries updated, nav table + What-to-read-first add
  PLAN.md, Repository-layout host tree refreshed (5→22 subpackages).
- [x] **`docs/MVP_SCOPE.md` reality fixes — APPLIED 2026-07-05** (owner "apply").
  §7 landed: #3 JIT→Stage B, #7 macOS→Linux, timeline → PLAN.md pointer.

## Boundary drafts — pending owner (2026-07-05)

### §5 — `docs/GOALS.md` whole-$HOME reality alignment

The factual claims (G4, advantages row) are now wrong for the shipped default;
the Vision para + closing line are aspirational (Stage C JIT-per-file) — your
call whether to keep them as the north-star or annotate. Recommended: fix the
two factual rows, annotate the aspirational ones.

(5a) **G4** — CURRENT:

    | G4 | Treat the Windows VM as a strict trust boundary; per-frame authentication, no full-`$HOME` exposure. | See `docs/THREAT_MODEL.md`. Enforced by per-frame `AuthContext` + JIT VirtioFS. |

PROPOSED:

    | G4 | Treat the Windows VM as a strict trust boundary; per-frame authentication; file sharing opt-in (default off). | See `docs/THREAT_MODEL.md`. Enforced by per-frame `AuthContext`. When sharing is on, the v0.1.0 default scope is the whole `$HOME` (DEC-0018); `documents`/`custom` narrow it; Stage C JIT-per-file is the eventual tight-isolation mode. |

(5b) **Advantages row** (line ~64) — CURRENT:

    | Just-in-time VirtioFS | WinApps `\\tsclient\home` | Per-file mounts, not whole-`$HOME` exposure; detached after `ReleaseAck` |

PROPOSED:

    | Opt-in staged file share | WinApps always-on `\\tsclient\home` | Sharing is opt-in (default off) and stage-able; Stage C JIT-per-file (mount only the opened file, detach after `ReleaseAck`) is the eventual tight-isolation mode. WinApps' mount is always-on and whole-$HOME. |

(5c) **Vision para** (lines ~14-15) — aspirational (Stage C). Owner style call:
keep as north-star, or append a one-liner that the v0.1.0 default is an opt-in
whole-$HOME share and the per-file-vanishing mount is the post-1.0 Stage C mode.

(5d) **Closing line** (~95) "per-frame authentication and JIT filesystem." —
same call: "JIT filesystem" is Stage C; either keep as vision or reword to
"per-frame authentication and an opt-in staged filesystem share."

### §6 — `AGENTS.md`: retire the WORK_LOG ceremony + add PLAN.md (tracking simplification 2026-07-05)

Owner retired the WORK_LOG START/END ceremony (solo owner + one agent). The
agent-editable side is done (WORK_LOG.md banner, `rules/general.md`, `CLAUDE.md`,
`loop-spec.md`, `status.md`, `backlog.md`, memory). `AGENTS.md` is a boundary
file, so these edits are drafted for your sign-off — say "apply" and I land them:

- **"Agent workflow" steps 6, 10–13** — delete the WORK_LOG START/END push-to-main
  steps. New shape: pull → read `PLAN.md` → pick top item → branch → implement →
  gates green → merge (→ push if PUSH=ON). No WORK_LOG commits.
- **"File boundaries"** — remove the `WORK_LOG.md` "only file an agent may push to
  main" exception line (no longer used).
- **Navigation table + "What to read first"** — add a top row: **`PLAN.md` — the
  single v0.1.0 board (what to do next)**; demote `.claude/backlog.md` to
  "post-MVP parking". Point "how does an agent pick a task" at `PLAN.md` instead
  of `EXECUTION_PLAN.md`.
- **"Repository layout" drift** (separate long-standing item): lists 5 subdirs
  under `host/src/crossdesk_host/`, actual = 22. Fix while in the file.

### §7 — `docs/MVP_SCOPE.md`: reality fixes (audit 2026-07-05)

Three drifts, boundary file → your sign-off. Drafts:

(7a) **Acceptance criterion #3 self-contradiction.** In-scope (lines 30-33) says
Stage B (persistent whole-$HOME) is the v0.1.0 floor per DEC-0018; acceptance #3
(lines 108-110) still requires a **JIT** mount "detached after the file is
closed" (= Stage C, moved post-1.0). CURRENT #3:

    3. Right-clicking a `.txt` file in a file manager and choosing "Open with
       Notepad" opens the file in Notepad through a JIT VirtioFS mount; the
       mount is detached after the file is closed.

PROPOSED #3:

    3. With file sharing enabled, a Windows app can open and save files under
       the configured share (v0.1.0 default: the whole `$HOME` via persistent
       virtio-fs, Stage B / DEC-0018); a `.txt` opened via "Open with Notepad"
       lands in the running Notepad. (JIT per-file mount/detach = Stage C, post-1.0.)

(7b) **Acceptance criterion #7 — dead macOS matrix.** Mac was vacuumed
(Mac→Ubuntu move). CURRENT: "CI is green on macOS + Ubuntu matrix; cross-compiled
`agent.exe` builds." PROPOSED: "CI is green on the Linux (Ubuntu) matrix;
cross-compiled `agent.exe` builds." (Drop macOS; keep NG1 note that Mac is
build-correctness-only if you want it referenced.)

(7c) **"Estimated timeline" (lines 146-160)** — assumes hardware not yet arrived,
targets 2026-10/11. Hardware is live, Phases 1–4 done. PROPOSED: replace the
week-by-week estimate with a pointer to `PLAN.md` (live board), or a one-line
"remaining scope tracked in PLAN.md; date depends on P0 hard_destroy + live
verification passes."

## Boundary drafts — ✅ APPLIED 2026-07-01 (owner sign-off)

Applied to the boundary files after the owner's "apply" sign-off: §1
MVP_SCOPE Phase-5 line, §2 DEC-0018, §3a/§3b THREAT_MODEL rows, §4 as
**DEC-META-007** (DEC-META-006 was already taken by the CLI file-tail
exception). §3c (transport wording + LogonUserW residual-risk /
VERSIONING capability promotion) is left for the owner to author. The
exact text applied is below for the record.

### §1 — `docs/MVP_SCOPE.md` Phase 5 / FS line

CURRENT:

    - **Phase 5** — JIT VirtioFS (per-file mount/detach with `ReleaseAck`)

PROPOSED:

    - **Phase 5 / FS** — Stage B persistent virtio-fs share (one configured
      mount, default the whole `$HOME` R/W) is the v0.1.0 floor; Stage C
      JIT-per-file mount/detach with `ReleaseAck` is a post-1.0,
      user-selectable tight-isolation mode.

### §2 — `docs/DECISIONS.md` new DEC-0018 (insert at top, newest-first)

    ## DEC-0018: FS share defaults to the whole $HOME (Stage B); JIT-per-file is post-1.0

    **Date:** 2026-06-29 · **Status:** active

    CrossDesk file sharing ships in stages. v0.1.0 ships Stage A (FreeRDP
    rdpdr `/drive:` redirect) plus the Stage B host-side plumbing (persistent
    virtio-fs `<filesystem>` device + shared memfd backing). When sharing is
    enabled (opt-in; `shared_folder_enabled` defaults OFF), the default
    exposure scope is the **whole `$HOME` R/W** (`shared_folder_scope =
    "home"`), chosen for maximum usefulness — the Windows app's Open/Save
    reaches anything the user has. `documents` (`~/Documents` only) and
    `custom` (one explicit folder) scopes narrow the surface.

    The whole-$HOME scope means the Windows guest can read/write everything
    under `$HOME`, including `~/.ssh` and `~/.config/crossdesk` (the host
    mTLS private key and the VM password). This is an accepted trade-off for
    a single-user, same-trust-domain VM (the same-user threat is already out
    of scope per THREAT_MODEL §C7). Stage C (JIT-per-file VirtioFS — mount
    only the directory of the file being opened) remains the eventual
    tight-isolation mode, post-1.0 and user-selectable.

    **Supersedes** the "reject the static `\\tsclient\home` whole-$HOME
    mount" stance in `docs/COMPARISON_WINAPPS.md` §7 / DEC-META-005:
    CrossDesk's share differs (opt-in + stage-able) but reaches a comparable
    scope by default, so the prior blanket rejection no longer applies.

### §3 — `docs/THREAT_MODEL.md` reality-alignment edits

(3a) §C5 row I — CURRENT:

    | **I** | TA2 reads files outside the JIT mount | Cross-mount escape | Mount surface is exactly one directory at a time | Low |

PROPOSED:

    | **I** | TA2 reads files outside the configured share | Cross-mount escape | Mount surface is one configured share; the v0.1.0 default is the whole `$HOME` R/W (DEC-0018). Per-file JIT isolation (Stage C) is post-1.0 | Medium |

(3b) Security-claims list, item 2 — CURRENT:

    2. Never expose the user's `$HOME` to the Windows guest beyond the
       single file the user is actively opening.

PROPOSED:

    2. File sharing is opt-in (default off). When enabled, the configured
       scope is reachable R/W by the guest; the v0.1.0 default scope is the
       whole `$HOME` (DEC-0018), including `~/.ssh` and `~/.config/crossdesk`.
       The `documents` / `custom` scopes narrow this; Stage C JIT-per-file is
       the eventual single-file mode.

(3c) Two further alignments you author (no exact diff — your security call):
  - **Transport (C1 row D / TA1):** the dev/bring-up transport is TCP
    loopback on `127.0.0.1` (DEC-0017 dev path), not AF_VSOCK yet. The "no
    external listener" property still holds (loopback only), but reword so it
    doesn't imply AF_VSOCK is wired today.
  - **`auth.verify-credentials.v1`:** the credential check is now a real
    `LogonUserW` (guest Stage 4 shipped), not a mock — flip any
    "planned / mock" residual-risk note to "real `LogonUserW` wired". (Also
    promote the capability planned→stable in `docs/VERSIONING.md` if you
    agree.)

  **Update 2026-07-14 (A8):** `README.md` and `.claude/architecture.md` now state
  the transport truthfully — AF_VSOCK is the *decided* transport (DEC-0017), while
  the shipped bring-up path is loopback TCP via the `transport.bind_kind` seam.
  `docs/THREAT_MODEL.md` is now the **only** doc still describing AF_VSOCK as the
  live channel, so the gap is no longer hidden, it is isolated to one boundary file
  waiting on you. (Also corrected a mis-citation both files carried: DEC-0017 settles
  AF_VSOCK vs AF_HYPERV and says nothing at all about a TCP path.)

### §4 — `.claude/rules/decisions.md` new DEC-META-006

    ## DEC-META-006 — whole-$HOME FS default supersedes the DEC-META-005 skip

    **Data:** 2026-06-29 · **Status:** aktywna

    DEC-META-005 listuje „Static `\\tsclient\home` mount — security
    regression vs JIT VirtioFS" wśród pozycji skip-on-purpose. DEC-0018
    (docs/DECISIONS.md) czyni whole-$HOME **domyślnym** zakresem Stage B
    (decyzja właściciela 2026-06-29). Mechanizm różni się od always-on
    WinApps (nasz share jest opt-in i etapowalny), ale zakres jest
    porównywalny. Pozycja DEC-META-005 dla tego itemu jest **zastąpiona**.

    **Jak stosować:** audyt nie raportuje whole-$HOME jako naruszenia
    DEC-META-005.

## Eyeball (loop captured evidence — you judge)

- **⚠️ Loop touched the live `windows-guest` VM by accident (2026-07-05) — no
  data loss, restored.** While adding the uninstall confirmation (`427b15e`), I
  changed a pre-existing CLI test (`test_uninstall_keep_config_preserves_vm_toml`)
  to pass `--force`, which made it run the *real* `uninstall_cmd._resolve_libvirt_ctl()`
  → `RealLibvirtController.undefine()` against `qemu:///session`. That
  **undefined the `windows-guest` domain definition** (destroy + undefine +
  NVRAM). **The disk was NOT touched** — `undefine()` deliberately omits
  `REMOVE_ALL_STORAGE`, so `~/.local/state/crossdesk/crossdesk-win.qcow2` (29 GB,
  the installed Windows) plus the `…milestone-bak.qcow2` (30 GB) are intact.
  **What I did:** (1) fixed the test to inject a `LibvirtControllerMock` so the
  suite never touches real libvirt; (2) added an autouse conftest guard
  (`13c765f`) that makes any accidental real-libvirt connection fail loudly for
  the whole suite; (3) **restored `windows-guest`**: redefined it (defined, off)
  from a **steady-state** XML pointing at the intact disk (disk `sda` boot
  order 1, both CD-ROMs ejected) — so a `virsh start` boots the installed
  Windows, not the installer. This also **live-verified the P0 steady-state XML**
  (item #1): real libvirt's `defineXML` accepted it and the boot config is
  disk-first. **Your call:** nothing to fix (disk safe, domain back, better shape
  than before). If you'd rather it be defined differently or started, say so; the
  remaining P0 live-verify (actually `start` it → boots disk + agent reconnects)
  is still open.

- **#5 suspend/resume — 5-minute owner runbook (loop 2026-07-25, C5 parked).** The
  loop cannot self-drive this: the coordinator subscribes to
  `org.freedesktop.login1.Manager.PrepareForSleep` on the **system bus** (can't be
  spoofed without root), `rtcwake` needs root (`sudo -n` prompts here), and any real
  suspend freezes the box the agent runs on — so no autonomous session can trigger
  *and* observe it. The mechanism is already sentinel-tested (A5 `c4cb6e8`). To close
  #5, with the daemon `backend=real` up and the agent connected (a fresh guest boot
  brings it online):
  1. `journalctl --user -u ... ` or tail the daemon log; note the FSM is HEALTHY.
  2. Real sleep + auto-wake: `sudo rtcwake -m mem -s 90` (or just close the laptop
     lid, wait, reopen).
  3. After resume, grep the daemon log for the sleep window: **expect** a
     `lifecycle` suspend line + FSM `SUSPENDED`, **and NO `HARD_DESTROY` / no
     `virsh destroy`** during the sleep, then a resume line and the agent still
     connected. A false HARD_DESTROY = the FSM escalated across the sleep = fail.
  Screenshot/log to `/tmp/cd-evidence/` and it's done. *Rec:* run it right after the
  next reinstall while the guest is fresh and connected.

- **FS Save-dialog (whole `$HOME`):** when A5-live runs, confirm a Windows
  app's Save dialog lands in the Linux `$HOME` and the saved file appears
  host-side. Evidence path TBD (needs the live VM + GUI capture tools).

## Resolved

- [x] **Audit-2026-07-07 boundary drafts B-1 + B-2 — APPLIED 2026-07-07**
  (owner signed "apply" interactively during remediation planning; drafts
  lived in `.claude/history/2026-07-07-remediation.md` §3, never parked here).
  B-1: `AGENTS.md:102` "22 subpackages" → **20** (measured, `__pycache__`
  excluded). B-2: `docs/REQUIREMENTS.md` gained **F4.4** (`transport.
  bind_kind`), **F4.5** (`libvirt.backend`), **F6.4** (`shared_folder_*`,
  DEC-0018) — owner chose markers **🔄 for all three** (honest ✅ flips ride
  the open "F-marker re-baseline" item above, one batch).
