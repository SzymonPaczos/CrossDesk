# MVP scope (v0.1.0)

What ships in the first release. Everything else is post-MVP.

## Decision

**MVP = pełny end-to-end flow including JIT VirtioFS** (Phases 1–5 all
done). One concrete sentence:

> A user runs `crossdesk install` on a fresh Linux host, walks away,
> comes back ~20 minutes later, runs `crossdesk launch notepad`, and
> a Notepad window appears on their Wayland or X11 desktop. They
> right-click a `.txt` file in their file manager, choose "Open with
> Notepad", and the file opens in the running Notepad — through a
> just-in-time VirtioFS mount that detaches when Notepad closes.

Everything in that sentence must work for v0.1.0.

## In scope (must work for v0.1.0)

### From the original 5 phases

- **Phase 1** — VM bootstrap + NT service ✅ already done
- **Phase 2** — Transport: gRPC over `AF_VSOCK` with mTLS and
  per-frame `AuthContext`
- **Phase 3** — Control Session FSM + adaptive heartbeat (HEALTHY →
  DEGRADED → PROBING → SOFT_RECOVERY → HARD_DESTROY)
- **Phase 4** — RAIL display integration (FreeRDP RAIL with
  per-window events; X11 baseline acceptable)
- **Phase 5** — JIT VirtioFS (per-file mount/detach with
  `ReleaseAck`)

### From cross-cutting follow-ups

- **`crossdesk install`** one-command bootstrap with auto-ISO
  download (Fido-style scrape; `--iso-path` manual fallback)
- **VM credential management** (`show`, `rotate`, `set`, `repair`
  with two-phase commit host+guest)
- **Critical Windows registry tweaks** for RDP RAIL (RDPApps.reg
  contents)
- **Path translation** for file arguments (`$HOME` → guest mount path
  → guest-visible path)
- **MS Office URL scheme handler** (`ms-word://`, `ms-excel://`)
- **Basic `.desktop` file generation** for at least one test app
  (Notepad)
- **Cross-platform test scaffolding** (transport, libvirt, FreeRDP
  abstractions with mocks; CI matrix with Mac + Linux)
- **Structured JSON logging** with trace ID propagation
- **In-memory metrics** + `crossdesk metrics` RPC
- **Performance budget enforcement** in CI (microbench harness with
  baselines)
- **Versioning handshake** (`Hello` message + N-1 minor compat
  matrix)
- **Lifecycle: D-Bus suspend/resume coordination** with FSM
- **systemd user service** unit
- **Integer i18n setup** (gettext + Qt tr scaffolding; English +
  Polish strings for the install flow at minimum)
- **Lean profile** as opt-in `--lean` (the install can produce a
  smaller Win11 image)
- **`crossdesk doctor`** pre-flight check
- **`crossdesk uninstall`** clean removal

### Distribution at MVP

At least one packaging format ready for early adopters:
- **AUR PKGBUILD** — easiest target, technical audience
- **NixOS flake** — already structurally adjacent to winapps' flake
- **PyPI host module** — for developers
- (deb/rpm: post-MVP, gated on hosting infrastructure decision)

## Explicitly out of scope at v0.1.0 (post-MVP)

These have FOLLOWUPS items but won't ship at v0.1:

- **GPU passthrough** (Phase 4.5 / post-MVP P0 per DEC-0009)
- **Looking Glass integration** (post-Phase 4.5)
- **Software-rendering compatibility matrix per app** (post-Phase 4.5)
- **App discovery** from Windows registry (powerful but not gating)
- **MS Office and Adobe MIME-type-derived `.desktop` files** beyond a
  hand-curated minimum
- **Wayland-native RAIL** (XWayland fallback acceptable)
- **Multi-monitor polish** (basic single-monitor required;
  multi-monitor at MVP-quality is acceptable but not extensively
  tested)
- **HiDPI auto-detection** beyond a static `--scale` flag
- **Rich clipboard** (text-only at MVP)
- **Drag-and-drop**
- **Microphone**, **camera**, **smartcard**, **printer**, **USB**
- **`crossdesk vm snapshot`**, **`crossdesk upgrade`**,
  **`crossdesk export-state`**
- **deb/rpm packaging** (gated on hosting infrastructure)
- **Code signing** (any form — not justified at MVP)
- **Translations beyond English + Polish**
- **Hardware-smoke CI runner** (self-hosted, gated on availability of
  a Linux+KVM machine)

## Acceptance criteria for "MVP done"

A v0.1.0 release happens when **all of the following are true**:

1. `crossdesk install` on a fresh Arch / Fedora / Ubuntu host
   completes within 25 minutes wall-clock and 2 minutes
   user-attended time (per N1.7).
2. `crossdesk launch notepad` produces a native Linux window within
   ≤3 s p50 (per N1.1a).
3. Right-clicking a `.txt` file in a file manager and choosing
   "Open with Notepad" opens the file in Notepad through a JIT
   VirtioFS mount; the mount is detached after the file is closed.
4. Heartbeat round-trip is <20 ms p50 (per N1.2).
5. Suspending the host laptop with the VM running, then resuming,
   leaves the VM working with no false-positive HARD_DESTROY (per
   `docs/LIFECYCLE.md` strategy).
6. Killing the VM (`virsh destroy` while running) and re-running
   `crossdesk launch notepad` recovers within ≤90 s (per N1.6a).
7. CI is green on macOS + Ubuntu matrix; cross-compiled `agent.exe`
   builds.
8. Performance microbenchmarks pass against committed baselines.
9. `crossdesk doctor` returns 0 on a properly configured host;
   surfaces clear errors on misconfigured hosts.
10. `crossdesk uninstall` cleanly removes the install with no
    leftover libvirt domain or `.desktop` files.
11. README has a quick-start that works for a typical Linux user
    without external help.
12. At least one Linux package format installs without manual
    file-by-file copying.

If any of those fail, it's not MVP yet. If all pass, ship v0.1.0.

## Why this scope

- **Phase 5 included** because JIT VirtioFS is one of CrossDesk's
  core differentiators (vs. WinApps's static `\\tsclient\home`); a
  v0.1 without it shows architecture but not the security claim.
- **`crossdesk install` included** because the WinApps onboarding
  competition (`docker compose up`) is real and we need to match
  the simplicity.
- **GPU passthrough excluded** because it requires real hardware,
  significant scope, and Phase 4.5 / post-MVP P0 commitment per
  DEC-0009 is the agreed-on plan.
- **Wayland-native, multi-monitor polish excluded** because XWayland
  fallback works and polishing native Wayland upstream is a
  multi-release effort.

## Estimated timeline

Detailed week-by-week in `docs/EXECUTION_PLAN.md`. High level:

- ~4 weeks: Mac vacuum work (cross-platform scaffold, observability,
  Phase 2 polish)
- ~3-4 weeks: Phase 3 FSM (after Linux+KVM hardware arrives)
- ~5-6 weeks: Phase 4 RAIL
- ~3-4 weeks: install pipeline + crossdesk install end-to-end
- ~3-4 weeks: Phase 5 VirtioFS
- ~2-3 weeks: integration + polish + i18n + doctor + uninstall

Total: ~5-6 months from 2026-05-09 → MVP target around
**2026-10 / 2026-11**, depending on hardware-arrival date and
whether categories run in parallel.
