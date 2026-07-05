# Needs Owner — batched decision ledger

The autonomous loop ([`loop-spec.md`](loop-spec.md)) parks here anything it
must not do alone: boundary-file edits, owner decisions, and changes whose
correctness needs human eyes. **Review in batches**, decide, and the loop
resumes. Resolving one = either you author the boundary edit, or you reply
"apply" and the loop applies the drafted text below for your final sign-off.

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

## Still open (boundary-file edits / owner calls)

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
- [ ] **▶ GREENLIGHT the P0 live-verify (the #1 remaining release blocker).**
  Everything host-side is now in place: the steady-state finalize is wired
  (`9ac1da1`), the daemon can drive real libvirt via
  `CROSSDESK_CONFIG__LIBVIRT__BACKEND=real` (`30579a6`). The last step is a
  *faithful* live run — daemon `backend=real` + a **fresh install** → agent
  Hello → finalize redefines to steady-state → `virsh destroy`+`create` boots
  the **disk** (not the ISO) → agent reconnects ≤90s. Closes #6, unblocks A3.
  **The catch:** it wants a fresh install, which **wipes the current milestone
  Windows install** (`crossdesk-win.qcow2`; a 30 GB `…milestone-bak.qcow2`
  backup exists). My incident-restored domain has a fresh nvram (no boot entry)
  so it's not a faithful vehicle. I have box autonomy but I'm **holding on the
  destructive install for your nod** given (a) the valuable existing install
  and (b) the recent accidental-undefine incident (Eyeball below). *Say go and
  I run it next iteration; or say "use the existing disk" and I'll attempt a
  boot-once-to-seed-nvram path instead.*
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

- **FS Save-dialog (whole `$HOME`):** when A5-live runs, confirm a Windows
  app's Save dialog lands in the Linux `$HOME` and the saved file appears
  host-side. Evidence path TBD (needs the live VM + GUI capture tools).

## Resolved

(move decided items here with the outcome + date)
