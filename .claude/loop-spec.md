# CrossDesk Autonomous Loop — Operating Spec

Drive CrossDesk toward **v0.1.0 (full MVP)** with *supervised autonomy*.
Each iteration takes ONE unblocked unit of work end-to-end (implement →
test → gate → commit → merge) and **parks** anything that needs the owner
or the live box. This file is the prompt the loop runs every iteration —
identical on the Mac (hardware-free items only) and the Proxmox box
(hardware-free + live items).

Canonical context the loop re-reads each iteration: this file, the
**Work queue** below, [`needs-owner.md`](needs-owner.md), `backlog.md`,
`status.md`, and memory `v010_release_plan`.

## Per-iteration algorithm

1. **Sync.** `git pull --rebase` if a remote is in play; re-read the
   context files above.
2. **Select** the highest-priority queue item that is UNBLOCKED *for this
   environment*:
   - 🟠 owner-gated / 👁 eyeball → never implement; if it's top priority,
     **draft + park** (see Parking) and skip.
   - 🔵 needs-box → skip unless running on the Proxmox/KVM box.
   - pick the first 🟢 (any host) or 🔵 (box only) item.
3. **Branch** `feat|fix|chore/<topic>` from `main`.
4. **Implement**, scoped to that item only. No bundled refactors.
5. **Gate — all green, never `--no-verify`:**
   - host: `ruff check src/ tests/`; `mypy --strict src/`; `pytest`
     (signal-method timeout). The *only* acceptable red is the known
     order-dependent `test_transport_mock` — and only if it passes solo.
   - guest/gui if touched: `cargo check` + `cargo test --features
     agent-svc/mock` + `cargo clippy -- -D warnings`.
   - if gates won't go green after a fair attempt: **park the item** with
     the failure, never merge red.
6. **Commit** (Conventional Commits + the `Co-Authored-By` trailer).
7. **Merge** `--no-ff` into `main` locally; delete the branch. **Do NOT
   push** (owner pushes) unless the push toggle below is ON.
8. **Live-verify** (box only, when applicable): exercise the change on a
   real VM; capture evidence (log / screenshot). If correctness depends on
   human judgement (UX, "does it look right"), park to `needs-owner.md`
   under Eyeball.
9. **Record.** Update the Work queue (mark ✅ / add discovered work),
   `status.md`, and append one line to the Loop log.
10. **Repeat.** STOP when no unblocked item remains for this environment →
    emit the batched needs-owner summary.

## Parking (owner-gated / eyeball)

Never apply a boundary edit or owner decision. Draft the exact diff/text or
the decision framing into `needs-owner.md` under the right bucket, mark the
queue item ⏸, and move on. Boundary files (draft-and-park, never edit):
`proto/**`, `docs/{THREAT_MODEL,DECISIONS,REQUIREMENTS,MVP_SCOPE,GOALS}.md`,
`ROADMAP.md`, `AGENTS.md`.

## Guardrails

- Never `--no-verify`; never push unless the toggle says so; never edit
  boundary files.
- One item per branch; no drive-by refactors.
- **Bounds:** stop + report after a per-run token ceiling or N=8 merged
  items, whichever first. Don't run unbounded.
- **VM ops** (box only): `snapshot create` before risky steps. The
  data-loss invariant (real `LibvirtController` refuses to start without
  the suspend listener) is already enforced in `daemon.py`.
- If unsure whether something is owner-gated → treat it as owner-gated and
  park.

## Toggles (owner sets these)

- **PUSH:** `ON` — owner present on the live box (2026-06-29); loop pushes its
  own merges to `origin/main` after green gates.
- **ENV:** `box` — running on the live Linux+KVM box (TUF FX505DT; `windows-guest`
  VM live). Both 🟢 and 🔵 items are in play.

## Work queue (v0.1.0)

Tags: 🟢 hardware-free (any host) · 🔵 needs-box · 🟠 owner-gated · 👁 eyeball.
Priority top-to-bottom within each tier.

### 🟢 Hardware-free (loop does these now)
1. **A2b — per-install PKI.** Install step mints a unique CA + guest leaf
   per install (today it reads one static shared dev keypair). `host/`
   installer + `generate_mtls` integration. P0 security.
2. **README ISO honesty.** Drop the false "auto-download Win11 ISO" claim →
   "bring your own ISO via `--iso-path`"; fix the status banner. (README is
   not a boundary file. The matching `REQUIREMENTS.md` F-marker re-baseline
   is 🟠 — park it.)
3. ✅ **B — diagnostics/logging.** Opt-in telemetry/crash-report path
   (host-side, default OFF); turn install/CLI failures into actionable
   recovery messages instead of raw tracebacks. *(2026-06-29: CLI
   last-resort handler + redacted opt-in crash report; i18n .pot regen
   deferred — gettext absent on box.)*
4. ✅ **A5-host — FS Stage B host-side.** `<filesystem driver='virtiofs'>` +
   memfd shared-memory in `domain_xml.py`; typed config for exposure scope.
   *(2026-06-29: virtio-fs domain device + memfd + scope home|documents|custom,
   default **whole $HOME** per owner confirmation. install_cmd wiring + the
   User Shell Folders redirect for virtio-fs land with A5-live.)* Live mount
   is 🔵.
5. ✅ **A7-logic — install idempotency.** Atomic state file; clean up a
   half-created libvirt domain on failure; wire `doctor` pre-flight. Real
   install execution is 🔵. *(2026-06-29: persist last_error + re-run doctor
   on resume; the atomic state / domain cleanup were already in place.)*
6. ✅ **D — packaging scaffolding.** Bundle `agent.exe` into the wheel /
   PKGBUILD `build()`; fix `flake.nix` missing runtime deps. Signing + repo
   domain are 🟠. *(2026-06-29: `_resolve_tools_inputs` packaged
   `/usr/share/crossdesk` fallback + AUR cross-builds/installs agent.exe;
   flake.nix deps were already fixed overnight.)*
7. ✅ **A1-config — CI runner wiring.** Self-hosted runner workflow YAML +
   re-enable CI auto-triggers. Runner stand-up itself is 🔵 (Proxmox).
   *(2026-06-29: linux-kvm-smoke wired to `[self-hosted, linux, kvm]`; CI
   auto-triggers were re-enabled overnight.)*

### 🔵 Needs the box (loop does these on Proxmox)
- **A3** enable the real `LibvirtController` + lifecycle FSM recovery live
  (gated on A2 — done).
- **A4** NT-service agent live (survives window-close/disconnect/reboot) +
  `sc failure` auto-restart; answer the session-0 cross-session
  `LogonUserW` token question.
- **A5-live** virtio-fs mount verify (WinFSP + VirtioFsSvc); Save dialog
  lands in the Linux folder.
- **A6-live** a second non-Notepad app renders; peripherals e2e
  (audio/clipboard/printer) on the NT-service agent.
- **A7-live** the 7-step install actually drives an install; `uninstall` +
  `doctor` live.
- **A1-standup** self-hosted runner on Proxmox; `linux-kvm-smoke` real.
- **M5** burn-in matrix (≥2 Windows × ≥2 distro × cycles) + real N1
  measurements.

### 🟠 Owner-gated (loop drafts → `needs-owner.md`, never applies)
MVP_SCOPE #3 rebalance · THREAT_MODEL edits · proto edits (discovery RPC) ·
code-signing strategy · repo domain · ISO/licensing legal stance · FS
exposure default · semver label · REQUIREMENTS F-marker re-baseline ·
final go/no-go.

### 👁 Eyeball (loop captures evidence → owner judges)
Save-dialog folder correctness · window appearance · install-not-frozen
UX · guest BSOD / failure UX.

## Loop log

(append one line per merged item: `[iso-ts] <sha> <topic> — <result>`)

- [2026-06-29 12:45] 244b12b B diagnostics — CLI friendly last-resort errors + opt-in crash reports; 937 host tests green, 3-lens review clean; i18n .pot regen pending gettext on box.
- [2026-06-29 13:40] 2bb2b88 A7-logic — install state machine records last_error + re-runs doctor pre-flight on resume; 943 green; self-reviewed (low-risk polish).
- [2026-06-29 13:30] a0ca5ca A5-host — FS Stage B host-side (virtio-fs domain device + memfd + exposure scope, default whole $HOME); merged after 3-lens review (applied abs-path + dup-tag validation + invalid-scope test) + owner confirmed whole-$HOME knowing it exposes ~/.ssh + ~/.config/crossdesk to the guest; 947 green.
- [2026-06-29 14:00] ae4943e chore(deps) — bump anyhow 1.0.102→1.0.103 (RUSTSEC-2026-0190) in guest+gui; unblocked the pre-push cargo-audit gate.
- [2026-06-29 14:20] 5c404b9 D packaging — `_resolve_tools_inputs` /usr/share/crossdesk fallback + AUR installs agent.exe; 957 green; self-reviewed.
- [2026-06-29 14:35] 8851262 A1 CI — linux-kvm-smoke wired to [self-hosted, linux, kvm] (YAML only; runner stand-up is 🔵); YAML validated.
- [2026-07-01 01:35] (live) BASELINE RENDER re-verified on the box post-batch — `xfreerdp3` RAIL renders Windows Notepad as a native Linux X window (`Bez tytułu — Notatnik` 1426×782, WM_CLASS crossdesk-notepad, Map State IsViewable). Screenshot: /tmp/cd-evidence/notepad-window.png. GUI capture tooling working (`import -window`) for the A5-live eyeball. Boundary edits applied on owner sign-off (DEC-0018 etc.); i18n .pot regenerated.
- [2026-07-01 02:30] (live) A5-LIVE Stage A VERIFIED (owner eyeball: "teraz się udało") — whole-$HOME share maps (`net use Z: \\tsclient\CrossDesk` → whole $HOME accessible), and a Windows app's Save dialog lands in the Linux $HOME. Working lever = process CWD `workdir:Z:\` (drive letter; Notepad ignores the redirect + a raw UNC CWD). Guest diagnostic also uncovered a REAL product bug → 12cae84.
- [2026-07-01 02:40] 12cae84 fix(installer) drive_map reg-quote — `/d "Z:\"` let reg.exe (C-runtime argv) swallow `/f`, so the Documents/Desktop redirect stored `Z:" /f` and never applied (the long-standing "Save dialog → System32"). Doubled the trailing backslash; 958 green. Found live.
- [2026-07-01 19:21] (live) ★★ A4 NT-SERVICE AGENT FULLY VERIFIED — the whole CrossDesk stack works end-to-end on real HW. Fresh agent.exe cross-built; installed as the `CrossDeskAgent` service (owner ran FixAgent.cmd elevated — RemoteApp can't show the UAC secure-desktop prompt, so used desktop-mode FreeRDP). Proven: (1) connects (mTLS Hello/READY, protocol_version=1, 3 planes); (2) survives RDP disconnect (connection ESTAB after the desktop session closed = session-0 persistence); (3) survives a hard reset (start=auto → auto-reconnect in ~32s, new port); (4) full managed launch: `crossdesk launch notepad` → daemon → `verify_credentials_resolved status=1` (real LogonUserW in the service) → FreeRDP RAIL spawn with `workdir:Z:\` + `/drive:CrossDesk,$HOME` (A5-host code live) → Notepad renders. Evidence: /tmp/cd-evidence/managed-notepad.png. Finding: the June-1 install left the service registered but binary+env missing (old autounattend); current autounattend does it correctly. #1 stability beta-blocker resolved.
- [2026-07-01 19:25] (live) A6 second app — `crossdesk launch mspaint` (managed) → verify-credentials → RAIL → **Microsoft Paint renders** (full ribbon, native Linux window), alongside Notepad (multi-app: two Windows apps as separate native windows at once). Evidence: /tmp/cd-evidence/managed-paint.png. Deferred this session: A7-live real install (destructive — owner chose non-destructive), M5 burn-in, peripherals (audio/clipboard default-off + RAIL-connect-risky per handoff).
