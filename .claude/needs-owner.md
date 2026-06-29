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
- [ ] **Code-signing strategy for `agent.exe`.** Sigstore vs the
  self-signed osslsigncode that's implemented vs EV. Blocks release
  packaging. *Rec:* self-signed publisher root CA installed into the guest
  (already built) for beta; document "unsigned-to-the-world" honestly.
- [ ] **Repo-hosting domain (deb/rpm).** Open since 2026-05-07. Blocks the
  apt/dnf repos in milestone D.
- [ ] **ISO acquisition + Windows licensing stance.** *Rec:* "bring your
  own ISO + your own license" in README/wizard (drop auto-download); state
  the licensing/legal expectation plainly to a Linux-forum audience.
- [ ] **Final go/no-go** for the public beta cut (after burn-in).

## Ready-to-apply boundary drafts (owner sign-off → "apply")

Exact text the loop will apply on your word (or paste it yourself). Boundary
files — never applied without sign-off.

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

- **FS Save-dialog (whole `$HOME`):** when A5-live runs, confirm a Windows
  app's Save dialog lands in the Linux `$HOME` and the saved file appears
  host-side. Evidence path TBD (needs the live VM + GUI capture tools).

## Resolved

(move decided items here with the outcome + date)
