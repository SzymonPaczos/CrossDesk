# Needs Owner — batched decision ledger

The autonomous loop ([`loop-spec.md`](loop-spec.md)) parks here anything it
must not do alone: boundary-file edits, owner decisions, and changes whose
correctness needs human eyes. **Review in batches** (e.g. daily), decide,
and the loop resumes the unblocked work. Each item: framing + the loop's
recommendation. Resolving one = either you author the boundary edit, or you
reply "go with rec" and the loop drafts it for your final sign-off.

## Decisions (boundary-file edits / owner calls)

- [ ] **MVP_SCOPE #3 — FS rebalance.** Decided in conversation
  (2026-06-23): Stage B = v0.1.0 floor, Stage C (JIT-per-file) = post-1.0
  user-selectable mode. Needs the actual `docs/MVP_SCOPE.md` #3 edit.
  *Rec:* reword #3 to mandate Stage B (persistent virtio-fs, one scoped
  folder R/W) for v0.1.0; list C as a v0.1.x optional security mode.
- [ ] **FS exposure default.** "Max usefulness, no paranoia" (owner).
  *Rec:* default the Stage B share to the user's `~/Documents` R/W
  (covers open+save), with a one-flag "expose whole home" toggle. Confirm.
- [ ] **THREAT_MODEL honesty (pre-announce).** Ship reality diverges from
  the doc. *Rec:* add rows for the TCP-loopback transport (the AF_VSOCK
  "no listener to TA1" claim is false today) and the single-scoped-folder
  FS (C5 JIT-VirtioFS is aspirational); flip the real-`LogonUserW`
  residual-risk note. Owner authors (security boundary).
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
- [ ] **Semver label.** *Rec:* `0.1.0-alpha`, not "1.0-alpha" (the
  audience reads versions literally; "1.0" implies API stability).
- [ ] **Final go/no-go** for the public beta cut (after burn-in).

## Eyeball (loop captured evidence — you judge)

(loop appends: item · what to check · evidence path)

## Resolved

(move decided items here with the outcome + date)
