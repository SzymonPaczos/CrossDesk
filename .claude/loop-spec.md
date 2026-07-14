# CrossDesk Autonomous Loop — Operating Spec

Drive CrossDesk to **v0.1.0** with supervised autonomy. One iteration = **one**
queue item, taken end-to-end (implement → gate → commit → merge → push → record).
The `/loop` prompt re-reads this file every iteration: it is the algorithm, the
guardrails, and the queue. The board it serves is [`PLAN.md`](../PLAN.md).

Re-read each iteration: this file · [`PLAN.md`](../PLAN.md) (the v0.1.0 board) ·
[`needs-owner.md`](needs-owner.md) (parked decisions) · [`status.md`](status.md)
(known breakages).

## Toggles (owner-set — current)

| Toggle | Value | Set |
|--------|-------|-----|
| PUSH | **ON** — merge, then `git push origin main`, after green gates | 2026-06-29 |
| ENV | **box** — the live Linux+KVM machine; `windows-guest` lives here | 2026-07 |
| DESTRUCTIVE P0 | **GREENLIT** — the Phase B cycle below is authorized | 2026-07-14 |
| WORKFLOWS | **GREENLIT** — the loop may change `.github/**` and merge it | 2026-07-14 |
| EYEBALL | **park** — capture evidence; subjective sign-offs go to needs-owner | 2026-07-05 |
| BOUND | queue drained · an item fails its gates twice · the box wedges | — |

### Pre-decided owner calls — do NOT re-ask

- **FreeRDP RDP cert policy = `ignore`** on the localhost / SLIRP path (our own
  guest, no MITM surface; real trust = mTLS gRPC + the Windows credential).
- **`agent.exe` signing = self-signed** publisher root CA for beta; document
  "unsigned-to-the-world" honestly. Not a release blocker.
- **FS default = whole `$HOME`** (DEC-0018); sharing itself stays opt-in / off.
- **Semver label = `0.1.0-alpha`.**
- **THREAT_MODEL §3c honesty** (TCP-loopback vs AF_VSOCK; real `LogonUserW`) is a
  go/no-go gate for calling anything "beta" — **not** a loop blocker. Draft, park.

## Per-iteration algorithm

1. **Sync.** `git pull --rebase origin main`; re-read this file, PLAN.md,
   needs-owner.md, status.md.
2. **Select** the top queue item that is not ⏸. Exactly **one**.
3. **Branch** `feat|fix|chore|docs|test/<topic>` from a fresh `main`. One item per
   branch; no drive-by refactors.
4. **Implement + gate — green or park; never `--no-verify`:**
   - host: `ruff check src/ tests/` · `mypy --strict src/` · `pytest`
   - guest / gui, if touched: `cargo check` · `cargo test` · `cargo clippy -- -D warnings`
   - workflows, if touched: `zizmor` + a YAML parse
   - Won't go green after a fair try (**two** attempts) → **park it with the
     failure text** and take the next item. Never merge red.
5. **Commit.** Conventional Commits subject — the `commit-msg` hook **blocks** a
   malformed one — plus the provenance trailers from
   [`change-provenance.md`](rules/change-provenance.md): `Intent:` / `Task-Ref:` /
   `Gates:` (the hook WARNs when they are missing).
   **No AI attribution** — no `Co-Authored-By`, no `AI-Contribution` (D-006).
   Never put backticks in `git commit -m` (the shell command-substitutes them).
6. **Merge** `--no-ff` into `main`, delete the branch, **push** (PUSH=ON).
7. **Verify the server-side gate.** `gh run list --branch main` for the merge
   commit; wait for CI + Security audit to complete. **The local gates are a
   mirror, not the truth** — they run on a box that has OVMF, libvirt and Qt
   installed, so they can be green while CI is red. They were, for a week
   (`2fdff19`: a test resolved UEFI firmware off the real filesystem, passing here
   and failing on every bare runner). **A red `main` is the next item, ahead of
   the queue** — `ci-cd.md` §1.1: fix or revert before piling on.
8. **Record.** PLAN.md (mark done / move the front) · status.md if a partial
   changed · one line in the Loop log below. No WORK_LOG — the ceremony is retired.
9. **Stop the iteration.** One item per iteration; do not chain.

**Owner-gated or boundary?** Never apply it. Draft the exact diff (or the decision
framing) into `needs-owner.md`, mark the item ⏸, take the next one. Boundary files:
`proto/**` · `docs/{THREAT_MODEL,DECISIONS,REQUIREMENTS,MVP_SCOPE,GOALS}.md` ·
`ROADMAP.md` · `AGENTS.md`. `.github/**` is **no longer** boundary (greenlit
2026-07-14) — but it is security code: gate it with `zizmor` and say so in `Gates:`.

## Queue — v0.1.0 (ordered; work it top-down)

Phase A is deterministic code. Phase B is the one sanctioned destructive cycle.
Phase C is live work on the guest Phase B leaves behind. **Do not start Phase B
until Phase A is drained** — bank the code first, so a wedged box costs nothing.

### Phase A — code / CI (no VM)

- **✅ A1 · pre-push secret-gate bypass — DONE `1b9c6f1` (2026-07-14).** The diff is
  now read NUL-delimited into an array (+ a `changed_match` helper); `SECRET_HITS` /
  `QML_HITS` became arrays too. 3 regression tests in
  `host/tests/test_pre_push_hook.py`, sentinel-verified against the old hook.
- **✅ A2 · CI / supply-chain wave — DONE `05653c7` (2026-07-14).** Triggers restored
  (AGENTS.md's claim is now true, no boundary edit); all 4 third-party actions +
  the semgrep image hash/digest-pinned; top-level `permissions: contents: read` on
  all four workflows; `persist-credentials: false` on all 13 checkouts; least
  privilege un-inverted in `security.yml` (SARIF-only jobs) and `release.yml`
  (publish-only write); `.github/dependabot.yml` + `.github/zizmor.yml` added.
  **zizmor: 86 findings (42 high) → 16 (0 high/medium/low).** ⏸ Parked for the
  owner: ratchet first-party `actions/*` / `github/*` to hash-pin too (= the 33
  findings the policy currently allows).
- **✅ A2b · RED MAIN CI (inserted, not planned) — DONE `2fdff19` (2026-07-14).**
  Restoring the CI triggers immediately exposed that `main` had been **red since
  2026-07-07** (6 consecutive runs) while every local gate was green: the install
  full-pipeline test resolved OVMF firmware off the real filesystem, so it passed
  on this box (has the `ovmf` package) and failed on every bare runner. Fixed with
  a fourth autouse isolation fixture + a guard test that empties the distro
  candidate lists. **This is why step 7 above now exists.**
- **✅ A3 · tracking honesty — DONE (2026-07-14).** Three branches were described
  as "NIE merged" while their code sits in `main` — verified with
  `git merge-base --is-ancestor`, not by eye (`e15cf2b`, `0f31d52`, `1986295` /
  `9afb465` / `688b2a7`). The dangling `handoff.md` §2.7/§2.8 citations pointed at
  a file dropped from the tree in `709363b`; the content was **recovered from
  `7f656fc`** into `.claude/history/2026-06-12-fs-stage-ab-plan.md` and every
  reference re-pointed. ⏸ Parked: deleting the 17 merged `origin/*` branches
  mutates the shared remote — owner's call (needs-owner.md).
- **A4 · `libvirt_call` executor** (audit P2 / Security Review NOTE).
  `libvirt_ctl/aio.py` offloads onto the *shared default* executor; a saturated pool
  starves every other `run_in_executor` on the daemon. Give it a dedicated
  `ThreadPoolExecutor` + a saturation test (N > pool_size blocked calls must not
  starve an unrelated call).
- **A5 · C-3: lifecycle blocks the event loop** (backlog Tech-debt; **prerequisite
  for C5**). `lifecycle/coordinator.py` `suspend()`/`resume()` block on the D-Bus
  PrepareForSleep path. It was deliberately excluded from the deadline-bound libvirt
  work because the coordinator mutates FSM state — this needs a thread-safety design,
  not a mechanical `libvirt_call` wrap. Must land before #5 is verified on `real`.
- **A6 · `zizmor` on the box** (audit P2). Install it (uvx / pipx) so A2 has a real
  gate rather than an eyeball; consider a job in `security.yml`.
- **A7 · destructive-path integration test** (backlog C-2 — its trigger, the P0
  greenlight, just fired). A `live_libvirt` pytest marker (deselected by default)
  driving `define_and_start` → `redefine_steady_state` → `hard_destroy` → `undefine`
  on a **throwaway** domain (never `windows-guest`) with `XDG_*` pointed at a temp
  dir. This is what makes criterion #6 regression-guarded instead of a one-off.
- **A8 · README quick-start (#11), the text.** Rewrite it against what actually
  ships. The real "from zero to a window" run is C7.

### Phase B — the sanctioned destructive cycle (closes #6 and #10; re-verifies #1)

**Step 0 — the safety net.** The milestone backup was moved out of the state dir on
2026-07-14 (`~/crossdesk-backups/crossdesk-win.milestone-bak.qcow2`, 30 GB) because
`uninstall()` `rmtree`s the entire state dir (`uninstall.py:112`) and would otherwise
delete it. **Verify it is still outside the state dir before B1.** If not, move it.

- **B1 · `uninstall --force` live (#10).** Real removal via the real CLI: domain
  destroy + undefine (NVRAM), disk, state, config, `.desktop`. Capture the report.
- **B2 · fresh `install` (#1 re-verify).** `crossdesk install --iso-path
  ~/Downloads/Win10_22H2_Polish_x64v1.iso --locale pl-PL`. Zero-touch; the agent's
  Hello should land in ~12 min. This is the **faithful** domain the P0 needs — fresh
  nvram, install-ISO still at `boot order=1`.
- **B3 · P0 finalize + recovery (#6).** Daemon with
  `CROSSDESK_CONFIG__LIBVIRT__BACKEND=real` and `bind_kind=tcp`: the first Hello fires
  `on_session_ready` → `finalize_steady_state` redefines the domain (disk `boot=1`,
  both CDs ejected) → `virsh destroy` → recovery `create` must boot the **disk, not
  the installer** → the agent reconnects **≤ 90 s**. Evidence to `/tmp/cd-evidence/`.
  **This is the last real v0.1.0 blocker.** If it boots the ISO, **STOP** — that is
  the data-loss path itself. Report it; do not retry blind.

### Phase C — live, on the guest Phase B leaves behind

- **C1 · #4** heartbeat RTT p50 < 20 ms — the harness exists; produce real numbers.
- **C2 · #2** `launch notepad` → native window, ≤ 3 s p50 (formal measurement).
- **C3 · #8** microbench vs the baselines.
- **C4 · #3** FS Stage B live — virtio-fs mount (whole `$HOME` default, DEC-0018);
  a Windows Save dialog must land in the Linux `$HOME`. Subjective → screenshot and
  **park to Eyeball**.
- **C5 · #5** suspend/resume with no false HARD_DESTROY (needs A5).
- **C6 · #12** packaging — build the AUR PKGBUILD and install from it.
- **C7 · #11** README quick-start — the real "from zero to a window" run.
- **C8 · M5** burn-in — ≥ 2 Windows × cycles, to catch flakes.

⏸ **Owner-gated (draft + park; never apply):** proto edits (app-discovery RPC) ·
REQUIREMENTS F-marker re-baseline · THREAT_MODEL §3c + VERSIONING capability
promotion · MVP_SCOPE #3 / #7 re-definition · `SECURITY.md` (public-facing) · the
Python lockfile direction (uv vs pip-tools) · repo-hosting domain · the final beta
go/no-go.

## Guardrails

- **Never** `--no-verify`. Never merge red. Never edit a boundary file.
- **The only sanctioned destructive VM operation is Phase B**, in order, after
  Step 0. Anything else destructive → park it. `windows-guest` is not a test
  fixture: the autouse conftest guard (`13c765f`) that blocks real libvirt inside
  the suite stays, and destructive integration tests run against a **throwaway**
  domain with temp `XDG_*`.
- Subjective correctness — did the Save dialog land in the right place, does the
  window look right, is the install frozen, is that a BSOD — is **not** self-certified.
  Screenshot to `/tmp/cd-evidence/` and park to needs-owner "Eyeball".
- Any non-trivial task discovered outside the current item goes on the board
  **immediately** (v0.1.0 → PLAN.md; post-MVP → backlog.md; unclear → its `Inbox`)
  before continuing. Recording it is not permission to start it.
- If the newest `## Audyt` in `audit-log.md` is more than 7 days old, propose the
  `weekly-audit` skill instead of taking a queue item.
- Unsure whether something is owner-gated? Then it is. Park it.

## Stop and report

Stop when the queue is drained, an item fails its gates twice, or the box wedges.
Then emit one batched report: what merged (SHAs), what each live item actually
proved (with evidence paths), what is parked in needs-owner and why, and the
refreshed 12-criteria table in PLAN.md.

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
- [2026-07-06 00:50] (live, Phase 2, non-destructive) A3-SEAM SMOKE-VERIFIED on the box — ran the daemon with `CROSSDESK_CONFIG__LIBVIRT__BACKEND=real` + `bind_kind=tcp` for a bounded 6s: D-Bus `dbus_listener_subscribed` (suspend-protection passed with the REAL controller, not mock) → "Server is running. Awaiting connections." → graceful `daemon_shutting_down`. **Non-destructive**: libvirt isn't called at daemon startup, so `windows-guest` stayed defined-off (unchanged), no mock lines logged. Proves the daemon side of the P0 is live-ready — the config-selectable real backend (`30579a6`) constructs RealLibvirtController + passes `_assert_suspend_protection` + binds the server on the live box. The ONLY remaining P0 piece is the destructive install→Hello→finalize→destroy+create-boots-disk cycle (owner greenlight pending). Evidence: /tmp/cd-real-daemon.log.
- [2026-07-05 23:35] (audit, no code merge) security-coverage + fs-mount sweep — two audits, both concluded no clean code action: (1) **mTLS/AuthValidator coverage is SOLID** — `test_mtls_handshake.py` drives a real handshake asserting no-cert/wrong-CA/expired rejected at TLS; `test_auth_validator.py`+`test_security_edges.py`+`test_auth_rejection_paths.py` cover pinning/nonce/sequence per-plane → the backlog "missing mTLS failure-mode tests" item was STALE, corrected it (positive signal for the beta go/no-go). (2) **fs-mount placeholder-in-prod is REAL but deferred** — `agent-svc/filesystem.rs` calls `mock_generate_release_ack` (hardcoded `total_bytes_written:1024`) unconditionally in the spawned JIT-VirtioFS plane (post-1.0, dormant today); a clean cfg-gate is fiddly cross-crate work that risks the guest build/clippy, and I can't fully verify the Windows target here → left tracked (backlog Tech-debt), not touched. Host-side v0.1.0 backlog is now largely drained; biggest lever (P0 live-verify) awaits owner greenlight.
- [2026-07-05 23:10] af8fd76 (merged, pushed) test(install) `_resolve_tools_inputs` packaged-dir contract (#12) + README honesty — audited `packaging/aur/PKGBUILD`: all referenced files exist, `[[bin]] name = "agent"` → `agent.exe` matches install, hatchling backend matches makedepends → #12 host-side genuinely sound (no false-done). Added the missing test for the aggregator the install calls (agent+CA+autounattend resolve from `/usr/share/crossdesk`; each-missing → named `_StepFailed`). 4 tests, 1013 green. Also fixed a README stale pointer: it sent users to the FROZEN `docs/EXECUTION_PLAN.md` as "the v0.1.0 week-by-week" → now points at `docs/MVP_SCOPE.md` (EXECUTION_PLAN noted frozen). NOTE for owner: README top-line still says transport is "over gRPC on AF_VSOCK" — same overstatement as needs-owner §3c (live path is TCP-SLIRP); left for the owner to fix coherently with THREAT_MODEL.
- [2026-07-05 22:50] 30579a6 (merged, pushed) feat(daemon) config-selectable libvirt backend — the A3 seam: daemon no longer hard-codes LibvirtControllerMock. New `LibvirtConfig` (backend = mock|real, default mock → unchanged dev/CI behaviour; domain_name) selected in `daemon.py`; `CROSSDESK_CONFIG__LIBVIRT__BACKEND=real` drives the real qemu:///session domain, which auto-activates the on_session_ready steady-state finalize + real heartbeat recovery (`_assert_suspend_protection` still fail-closes without the D-Bus listener). 4 config tests; suite 1009 green. Remaining P0 live-verify (run daemon backend=real on a *faithful* domain → finalize → destroy+create boots disk) is box-gated — my incident-restored windows-guest has a fresh nvram (no boot entry) so it's not a faithful boot-test vehicle; a fresh install is.
- [2026-07-05 22:35] (live, Phase 2) #9 doctor + #2 uninstall-wiring VERIFIED on the box — `crossdesk doctor` = **exit 0**, 10/10 checks OK (cpu_virt svm / kvm / vsock / qemu 10.2 / freerdp / ovmf / libvirt / disk 135GB / config / vm_creds); bad host (`CROSSDESK_OVMF_CODE` bogus) → `ovmf [fail]` + **exit 1**. Both halves of #9 → ✅ live. Also `crossdesk uninstall --dry-run` on the real CLI lists `libvirt_domain: would destroy + undefine` FIRST + files, exit 0 (item #2 wiring confirmed end-to-end; stopped at dry-run — real undefine would destroy windows-guest). Objective, no eyeball, no VM mutation.
- [2026-07-05 22:20] 13c765f (merged, pushed) test: block accidental real-libvirt in the suite — autouse conftest guard patches `RealLibvirtController._connect` to raise, so no unit test can touch `qemu:///session`. WHY: while adding uninstall `--force` (`427b15e`), my edit to a pre-existing CLI test hit REAL libvirt and undefined the live `windows-guest` domain (disk INTACT — `undefine()` omits REMOVE_ALL_STORAGE). Fixed the test to inject a mock, added this guard (verified it bites), and RESTORED windows-guest by redefining it as steady-state (off, disk boot=1, CDs ejected) from the intact 29GB disk — which also **live-verified item #1's steady-state XML** (real `defineXML` accepts it). Parked full incident + restore for owner awareness → `needs-owner.md` "Eyeball". Suite 1005 green.
- [2026-07-05 22:05] 427b15e (merged, pushed) feat(uninstall) destructive-confirm + --force — uninstall now prompts y/N before wiping the VM + mTLS keys + vm.toml (losing vm.toml = losing Windows access); `--force` skips for scripts, `--dry-run` never prompts, EOF/OSError stdin = "no". Also hardened CLI-test isolation (mock controller). 6 tests. NOTE: surfaced the real-libvirt incident above.
- [2026-07-05 21:50] 8261a35 (merged, pushed) feat(uninstall) libvirt domain teardown — closed a real host-side gap: `crossdesk uninstall` removed .desktop/ISO/state/config but NEVER touched the libvirt domain (uninstall.py's own comment claimed it was "wired into the CLI layer" — it wasn't), so #10 "clean removal" was a false "kod gotowy". Added `LibvirtController.undefine()` (destroy-if-running + `undefineFlags(NVRAM)`; idempotent) on real+mock; `uninstall()` takes an optional controller and removes the domain FIRST (before the state-dir rmtree that holds its disk); domain error is recorded without aborting file cleanup. No `REMOVE_ALL_STORAGE` — it would risk deleting the user's own Windows ISO (file-backed CD-ROM source). 5 new tests; full suite 1000 green. Remaining #10: live-verify + optional `--force`/confirm (backlog). i18n .pot re-extracted (a1a3691, line-refs only).
- [2026-07-05 21:30] 9ac1da1 (merged, pushed) feat(install) steady-state finalize wiring — completes the P0 TERAZ front's host-side part: `installer/steady_state.py` persists the steady-state XML at `create_libvirt_domain` and the daemon redefines the domain to it on the first agent Hello via a new `ControlServiceServicer.on_session_ready` hook. Idempotent (`steady_state` step in install.state.json) + retries on a libvirt error. Daemon wires the hook ONLY for the real controller — running it against the mock would mark the step done without redefining anything, masking the data-loss path until A3 lands the real controller. 14 new tests; full suite 996 green; mypy --strict + ruff clean. Remaining on the front is now box-gated (= A3: swap the daemon's mock→real controller, which activates the finalize; + live-verify destroy+create boots the disk not the ISO). i18n .pot re-extracted (244ac8a, line-ref churn only).
- [2026-07-01 23:30] ★★★ (live) A7-live RENDER CLOSED — **pristine reinstall verified the WHOLE loop end-to-end**: `crossdesk install` → Windows unattended → agent auto-Hello #1 (~11min) → **order-21 auto-reboot → agent Hello #2 reconnect (~100s, console session cleared)** → `crossdesk launch notepad` → verify_credentials_resolved status=1 → RAIL → **Notepad renders as a native Linux window** (`wid title='Bez tytułu — Notatnik'` 1426×782, WM_CLASS RAIL/crossdesk-notepad, with `workdir:Z:\` + `/drive:CrossDesk,$HOME` whole-$HOME live). All 5 A7-live install fixes (drive-find, TOFU, test-hermeticity, console-session reboot, OVMF) verified on a clean install with ZERO manual steps. The console-session fix is LIVE-VERIFIED — the one open item is closed. (Note: the first post-reboot launch raced verify-creds — retry after settle rendered; a bounded post-install-wait, backlog, would smooth that.)
- [2026-07-14 20:06] 1b9c6f1 (merged, pushed) fix(hooks) A1 pre-push secret-gate bypass — the hook iterated `for f in $CHANGED_FILES` unquoted; verified empirically that `git diff --name-only` prints a spaced path UNQUOTED, so it word-split, every fragment failed `[ -f ]`, and a file holding a real secret was **never scanned** (this grep is the only secret gate when gitleaks is absent — and gitleaks is NOT installed on this box). Read the diff NUL-delimited into an array + a `changed_match` helper; the same split hit the console.log / print / qmllint loops and the `SECRET_HITS` / `QML_HITS` accumulators (space-joined then re-split) → arrays too. 3 regression tests (`host/tests/test_pre_push_hook.py`) driving the real hook in a temp repo with a real `origin/HEAD`. **Sentinel-verified**: the spaced-filename test FAILS on the old hook (output shows the scanner printing "hardcoded secrets ..." and walking straight past the file) and passes on the fixed one; the plain-filename and clean-file tests pass on both, isolating the defect. Gates: ruff clean, mypy --strict 126 files, pytest 1031 passed / 1 skipped, bash -n OK.
- [2026-07-14 20:35] 05653c7 (merged, pushed) ci(security) A2 CI/supply-chain wave — closed the 2026-07-12 audit's whole CI front on the owner's 2026-07-14 sign-off. (1) **security.yml triggers restored** (`push` + `pull_request` + Monday `schedule`): it had been `workflow_dispatch`-only since the 2026-05-20 billing freeze while `AGENTS.md:64-69` claimed it ran on every push/PR/weekly — the repo is public now, so Actions are free and the claim was made TRUE rather than rewritten down (option (a) of needs-owner §8; no boundary edit needed). (2) **Every third-party action hash-pinned**: `dtolnay/rust-toolchain` ×5 → `4be7066…c30`, `bufbuild/buf-setup-action` → `a47c93e…a99` (v1.50.0), `gitleaks/gitleaks-action` → `ff98106…0c7` (v2.3.9), `semgrep/semgrep` image → digest `sha256:59fbed…66e`. This was the Red Team HIGH: `rust-toolchain@stable` (a movable branch ref) runs in `release.yml`'s `build-agent`, whose artifact `sign-agent` Authenticode-signs with the REAL publisher cert → a compromised tag ships signed-by-us malware. The file's own header comment claimed it was already pinned — comment↔YAML drift, now true. (3) **Least privilege**: top-level `contents: read` on all 4 workflows, `persist-credentials: false` on all 13 checkouts, and two INVERTED grants fixed — `security.yml` handed `security-events: write` to all 5 jobs (now only the 2 that upload SARIF) and `release.yml` handed `contents: write` to the job holding the signing secret (now only `publish-release`). (4) `.github/dependabot.yml` (4 ecosystems, 5-day cooldown, minor/patch grouped; security updates bypass cooldown) + `.github/zizmor.yml` making the pinning convention machine-checkable. **Gates: zizmor 1.27.0 — 86 findings (42 High) → 16 (0 High / 0 Medium / 0 Low, 3 informational). All 6 YAML files parse. Policy proven load-bearing: `--no-config` regresses to 33 High** (= the first-party actions the convention deliberately allows on tags → parked for the owner). Note: dependabot cannot auto-bump `dtolnay/rust-toolchain` (branch-based, no semver tags) — bump by hand; documented in `dependabot.yml`.
- [2026-07-14 20:55] 2fdff19 (merged, pushed) fix(test) A2b RED MAIN CI — **the most valuable find of the run, and it was an accident**: restoring the CI triggers in A2 immediately surfaced that `main` had been RED since 2026-07-07 (6 consecutive runs: d0f6723, 721675b, cafbfa1, db6251f, a2a16b9, f361bde) with **nobody watching**, because every local gate was green. Root cause: `test_full_pipeline_with_iso_defines_and_starts_domain` drives the REAL `install_cmd.run()` → `create_libvirt_domain` → `resolve_ovmf()`, which probes the distro's UEFI firmware paths on the real filesystem. This box has the `ovmf` package; a bare GitHub runner does not → `FileNotFoundError` → pipeline returns 1 → `assert 1 == 0`. Introduced by `29ccea5` (OVMF cross-distro resolution, 2026-07-01) and **invisible locally by construction**. Fix: a fourth autouse isolation fixture in the module (joining `_state_in_tmp`, `_mock_libvirt`, `_isolate_freerdp_config` — that last one exists for the SAME class of bug, so this is the second time this repo has shipped a test that reaches real system state) pointing `CROSSDESK_OVMF_CODE/VARS` at fixture files, plus a guard test that empties the distro candidate tuples to simulate a bare runner. **Sentinel**: with the fixture neutered the guard test fails with CI's exact error while the ORIGINAL test still passes on this box — a precise demonstration of why the red survived a week. Gates: ruff clean, mypy --strict 126, and pytest run with CI's OWN invocation (`pytest -q --cov`) → 1043 passed / 1 skipped. **Ratchet**: loop-spec step 7 now requires checking `gh run list --branch main` after every push — local gates are a mirror, not the truth.
- [2026-07-14 21:15] (merged, pushed) docs A3 tracking honesty — the state files were lying about the code. Three branches (`feat/resilience-logging`, `feat/fs-drive-letter`, `feat/usability-shared-fs`) were written up as "NIE merged" while their code has been in `main` all along; I verified each with `git merge-base --is-ancestor` and by locating the actual symbols rather than trusting the note (`e15cf2b` workdir, `0f31d52` rail_supervisor, `1986295`+`9afb465`+`688b2a7` Stage A, `configure_logging(log_file=)` in `observability/log.py` — my first grep looked in `logging.py` and found nothing, which would have let me replace one false claim with another). The dangling `handoff.md` §2.7/§2.8 citations pointed at session-scratch dropped from the tree in `709363b` — but the content was NOT lost: `7f656fc` still holds the 430-line version, so the FS Stage A/B execution plan is now recovered and tracked at `.claude/history/2026-06-12-fs-stage-ab-plan.md`, with every reference in `status.md`/`backlog.md` re-pointed. Zero dangling links remain. **Step 7 satisfied**: main's CI + Security audit both went **success** on `b37f07d` — the first green main since 2026-07-07, confirming the OVMF fix on a real runner and not just here. ⏸ Parked for the owner: deleting the 17 merged `origin/*` branches (mutates the shared remote; a mass-cancel of CI runs earlier this session was correctly blocked by the permission classifier for the same class of reason — I did not work around it).
