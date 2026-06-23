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

- **PUSH:** `OFF` — loop merges to local `main` only; owner pushes.
- **ENV:** `mac-hardware-free` — set to `proxmox-box` when running there.

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
3. **B — diagnostics/logging.** Opt-in telemetry/crash-report path
   (host-side, default OFF); turn install/CLI failures into actionable
   recovery messages instead of raw tracebacks.
4. **A5-host — FS Stage B host-side.** `<filesystem driver='virtiofs'>` +
   memfd shared-memory in `infra/launch-vm.py`; extend the User Shell
   Folders redirect generator; typed config for exposure scope (Documents
   default + whole-home toggle). Live mount is 🔵.
5. **A7-logic — install idempotency.** Atomic state file; clean up a
   half-created libvirt domain on failure; wire `doctor` pre-flight. Real
   install execution is 🔵.
6. **D — packaging scaffolding.** Bundle `agent.exe` into the wheel /
   PKGBUILD `build()`; fix `flake.nix` missing runtime deps
   (pydantic/tomli/pycdlib/opentelemetry). Signing + repo domain are 🟠.
7. **A1-config — CI runner wiring.** Self-hosted runner workflow YAML +
   re-enable CI auto-triggers. Runner stand-up itself is 🔵 (Proxmox).

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
