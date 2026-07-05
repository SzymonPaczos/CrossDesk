# CrossDesk Autonomous Loop — Operating Spec

Drive CrossDesk toward **v0.1.0 (full MVP)** with *supervised autonomy*.
Each iteration takes ONE unblocked unit of work end-to-end (implement →
test → gate → commit → merge) and **parks** anything that needs the owner
or the live box. This file is the prompt the loop runs every iteration —
identical on the Mac (hardware-free items only) and the Proxmox box
(hardware-free + live items).

Canonical context the loop re-reads each iteration: this file (for the
*algorithm + guardrails*), **[`PLAN.md`](../PLAN.md) for what to work on**
(the single v0.1.0 board — it supersedes the "Work queue" section below,
kept only for the 🟢/🔵 environment tags), [`needs-owner.md`](needs-owner.md),
and `status.md`.

## Per-iteration algorithm — two phases

**Phase 1 first: land every host-side / code item you can. Phase 2 (live
verify on the VM) runs only once Phase 1 is exhausted** (owner: "live verify
gdy uznasz że skończyłaś wszystko co mogłaś"). Rationale: code work is
deterministic and gate-checked; live-verify is flaky + destructive, so batch
it at the end rather than interleave.

### Phase 1 — code (repeat until no code item remains)

1. **Sync.** `git pull --rebase origin main`; re-read PLAN.md + status.md +
   needs-owner.md.
2. **Select** the top UNBLOCKED item: PLAN.md **TERAZ** front first, then
   **NEXT** top-down. Take the *host-side / testable* part of it now; defer
   its 🔲 live-verify to Phase 2.
   - 🟠 owner-gated / boundary → **draft + park** to needs-owner.md, skip.
3. **Branch** `feat|fix|chore/<topic>` from fresh `main`. One item, no
   drive-by refactors.
4. **Implement + Gate — all green, never `--no-verify`:**
   - host: `ruff check src/ tests/`; `mypy --strict src/`; `pytest`.
   - guest/gui if touched: `cargo check` + `cargo test --features
     agent-svc/mock` + `cargo clippy -- -D warnings`.
   - won't go green after a fair try → **park with the failure**, never merge red.
5. **Commit** (Conventional Commits + `Co-Authored-By` trailer; **no backticks
   in `-m`** — the shell command-substitutes them). **Merge** `--no-ff` into
   `main`, delete the branch, **push** (PUSH=ON).
6. **Record.** Update PLAN.md (mark done / move the TERAZ front) + status.md.
   Append one line to the Loop log. **No WORK_LOG** (ceremony retired).
7. **Repeat** until no host-side item remains, or the bound trips.

### Phase 2 — live verify on the box (once Phase 1 is exhausted)

8. For each 🔲 item whose code landed, exercise it on a real VM and capture
   evidence (log / screenshot to `/tmp/cd-evidence/`). Full box autonomy —
   `snapshot create` before a destructive step is prudent but not required.
9. If correctness needs human judgement (Save-dialog lands right, window looks
   right, install-not-frozen, BSOD) → capture the screenshot and **park to
   needs-owner.md "Eyeball"**; don't self-certify a subjective call.
10. **STOP** when the bound trips or nothing unblocked remains → emit a batched
    needs-owner summary (decisions to make, eyeball evidence to review).

## Parking (owner-gated / eyeball)

Never apply a boundary edit or owner decision. Draft the exact diff/text or
the decision framing into `needs-owner.md` under the right bucket, mark the
queue item ⏸, and move on. Boundary files (draft-and-park, never edit):
`proto/**`, `docs/{THREAT_MODEL,DECISIONS,REQUIREMENTS,MVP_SCOPE,GOALS}.md`,
`ROADMAP.md`, `AGENTS.md`.

## Guardrails

- Never `--no-verify`; never edit boundary files (draft → needs-owner).
- One item per branch; no drive-by refactors.
- **Bounds:** stop + report after a per-run token ceiling or **N=6 merged
  items**, whichever first. Don't run unbounded.
- **VM ops:** full autonomy on this box (owner: "może robić co chce na tym
  komputerze") — spin up / tear down / reinstall VMs freely, including
  `windows-guest`. `snapshot create` before a destructive step is prudent
  (the host has reset under load); not a hard gate.
- If unsure whether something is owner-gated → treat it as owner-gated and park.

## Toggles (owner set these 2026-07-05)

- **PUSH = ON** — loop pushes its own merges to `origin/main` after green gates.
- **ENV = box** — the live Linux+KVM box (TUF FX505DT; `windows-guest` live).
- **VM = full autonomy** — may reinstall / destroy any VM on this box.
- **LIVE-VERIFY = deferred** — Phase 2 only, after Phase 1 is exhausted.
- **EYEBALL = park** — capture evidence, park subjective sign-offs to needs-owner.
- **BOUND = 6 merged items** or the token ceiling, whichever first.

### Pre-decided owner calls (in effect — loop does NOT re-ask)

- **FreeRDP RDP cert policy = `ignore`** for the localhost / SLIRP path (our own
  guest, no MITM surface; real trust = mTLS gRPC + Windows cred). Loop may switch
  `rail_command.py` `cert_policy` default `tofu`→`ignore`; the matching
  `THREAT_MODEL` row is a boundary draft.
- **`agent.exe` code-signing = self-signed** publisher root CA for beta (already
  built); document "unsigned-to-the-world" honestly. Not a blocker.
- **Security §3c honesty** (THREAT_MODEL transport TCP-vs-AF_VSOCK + real
  LogonUserW residual-risk + VERSIONING capability promotion) is a **go/no-go
  gate for calling anything "beta"**, NOT a loop blocker — loop drafts it, owner
  authors/signs before the beta cut.

## Board — see PLAN.md

The former Work queue lived here; it is **superseded by [`PLAN.md`](../PLAN.md)**
(TERAZ / NEXT / LATER + the 12 acceptance criteria with live status). The loop
reads PLAN.md, not this section. Remaining **owner-gated** items (draft →
needs-owner, never apply): proto edits (app-discovery RPC) · repo-hosting domain
· REQUIREMENTS F-marker re-baseline · remaining THREAT_MODEL / VERSIONING honesty
· final go/no-go. FS-exposure default, semver label, MVP_SCOPE #3, FreeRDP cert,
and code-signing are already decided (Pre-decided calls above + `docs/DECISIONS.md`
DEC-0018).

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
- [2026-07-01 23:11] 0dc3424 (merged, pushed) fix(install) autounattend tools-drive — A7-live (owner authorized destructive). Root cause of the fresh-install agent never coming online: with two CD-ROMs, Windows assigns the install media to D: and the tools ISO to E:, but FirstLogonCommands hardcoded `D:\` — so every copy read from the Windows media (no agent/PKI) → service registered but STOPPED, System32\CrossDeskAgent.exe missing, C:\CrossDesk\pki empty (diagnosed live via `wmic logicaldisk`: D:=CCCOMA_X64FRE_PL-PL, E:=CROSSDESK). Fixed all 5 copies (orders 3,4,5,6,9) to scan D..I for the tools ISO's marker (CrossDeskAgent.exe) + stale D: comments in tools_iso.py. Gates green (ruff/mypy/tools_iso tests). **LIVE-VERIFIED ★★★:** full clean reinstall (fresh 64GB disk, rebuilt tools.iso with the fixed autounattend) — Windows installed unattended and the NT-service agent **auto-connected in ~12 min with ZERO manual steps** (Hello protocol_version=1 features=['rail.v1'] + filesystem + heartbeat + READY). THE A7-live acceptance: a fresh `crossdesk install` self-assembles a working agent. Corrects line 151's wrong assumption that the autounattend already did it right (A4 used a manual FixAgent.cmd, not the autounattend's own copies).
- [2026-07-01 23:12] 2ab10d1 (merged, pushed) fix(install) FreeRDP TOFU pin-clear — 2nd A7-live bug the clean reinstall surfaced: managed launch got verify_credentials_resolved status=1 (real LogonUserW in the fresh agent) but FreeRDP `/cert:tofu` deadlocked because the reinstall rotated the guest self-signed RDP cert and the stale pin read as a cert-CHANGE → unanswerable prompt (no stdin) → ERRCONNECT_TLS_CONNECT_FAILED. install now clears the pin on create_libvirt_domain; TOFU change-detection preserved for steady-state. 962 green. **Adversarial Workflow (11 agents)** reviewed both A7 fixes + audited the install path → 6 confirmed defects: caught a REAL non-hermetic test in my OWN TOFU fix (full-pipeline test was deleting the dev's real ~/.config/freerdp pin — fixed with autouse fixture + sentinel-verified) + 5 pre-existing issues now in backlog.
- [2026-07-01 23:15] (live, diagnosed) A7-live render-from-fresh-install — the RAIL window did NOT surface on first try: `LOGON_FAILED_OTHER` because AutoLogon(LogonCount=1) leaves an active crossdesk CONSOLE session and Win10 single-session blocks the RDP RemoteApp logon as the same user (A4/A6 worked because those had rebooted to a clean logon screen). Rebooting to clear it WEDGED the fresh guest at firmware (install ISO still boot order 1); destroy+start after ejecting the ISO recovered it. Diagnosed → fixed below. The audit found the SAME root cause auto-triggers a HIGH data-loss path (hard_destroy → reinstall) — backlog, **blocks A3**.
- [2026-07-01 23:20] 0bccb73 (merged, pushed) fix(install) console-session reboot — added a final FirstLogonCommand (order 21) `shutdown /r` so the AutoLogon console session is gone before the host connects. OS-initiated restart (clean, unlike the ACPI reboot that wedged the guest) boots to a clean logon screen where the agent (session 0) reconnects.
- [2026-07-01 23:22] 29ccea5 (merged, pushed) fix(install) OVMF cross-distro — `resolve_ovmf()` (env override → Debian/Fedora/Arch candidate list) so `defineXML` doesn't fail on non-Debian hosts; build_domain_xml stays pure. + bac8dfd doctor OVMF pre-flight check. Both from the A7 audit. 959 green.
- [2026-07-05 21:30] 9ac1da1 (merged, pushed) feat(install) steady-state finalize wiring — completes the P0 TERAZ front's host-side part: `installer/steady_state.py` persists the steady-state XML at `create_libvirt_domain` and the daemon redefines the domain to it on the first agent Hello via a new `ControlServiceServicer.on_session_ready` hook. Idempotent (`steady_state` step in install.state.json) + retries on a libvirt error. Daemon wires the hook ONLY for the real controller — running it against the mock would mark the step done without redefining anything, masking the data-loss path until A3 lands the real controller. 14 new tests; full suite 996 green; mypy --strict + ruff clean. Remaining on the front is now box-gated (= A3: swap the daemon's mock→real controller, which activates the finalize; + live-verify destroy+create boots the disk not the ISO). i18n .pot re-extracted (244ac8a, line-ref churn only).
- [2026-07-01 23:30] ★★★ (live) A7-live RENDER CLOSED — **pristine reinstall verified the WHOLE loop end-to-end**: `crossdesk install` → Windows unattended → agent auto-Hello #1 (~11min) → **order-21 auto-reboot → agent Hello #2 reconnect (~100s, console session cleared)** → `crossdesk launch notepad` → verify_credentials_resolved status=1 → RAIL → **Notepad renders as a native Linux window** (`wid title='Bez tytułu — Notatnik'` 1426×782, WM_CLASS RAIL/crossdesk-notepad, with `workdir:Z:\` + `/drive:CrossDesk,$HOME` whole-$HOME live). All 5 A7-live install fixes (drive-find, TOFU, test-hermeticity, console-session reboot, OVMF) verified on a clean install with ZERO manual steps. The console-session fix is LIVE-VERIFIED — the one open item is closed. (Note: the first post-reboot launch raced verify-creds — retry after settle rendered; a bounded post-install-wait, backlog, would smooth that.)
