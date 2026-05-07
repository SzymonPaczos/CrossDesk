# Project goals & non-goals

What CrossDesk is for, what it explicitly is not, what success looks
like, and where our advantage and disadvantage sit relative to the
field.

## Vision

A Linux user opens their Wayland or X11 desktop, types
`crossdesk launch word`, and a Microsoft Word window appears next to
their Firefox and VS Code — same compositor, same window manager, same
task switcher, same window decorations. The Windows VM running it is
invisible: no visible desktop, no RDP client window, no shell to log
into. Files open in Word land via a per-file mount that the user never
sees and that vanishes the moment Word is done with them.

The cost of running a Windows app is the cost of running a VM —
nothing more — and the user never has to think about the VM.

## Primary goals

| # | Goal | Measurable when |
|---|------|-----------------|
| G1 | Run any Windows desktop application as a native Linux window. | RAIL window class matches the WM's grouping; Alt-Tab treats it like any native app. |
| G2 | Onboarding from zero install to first app launched in ≤2 minutes user-attended time. | `time crossdesk install && crossdesk launch notepad` returns successfully; wall-clock can be 15-25 min unattended. |
| G3 | Run the host as a regular user — no daemon root, no privileged container. | `ps -eo user,comm \| grep crossdesk` shows the user, never root. |
| G4 | Treat the Windows VM as a strict trust boundary; per-frame authentication, no full-`$HOME` exposure. | See `docs/THREAT_MODEL.md`. Enforced by per-frame `AuthContext` + JIT VirtioFS. |
| G5 | Survive the long tail: VM crashes, network changes, suspend/resume, partial installs all recover deterministically. | Adaptive heartbeat FSM (Phase 3) walks PROBING → SOFT_RECOVERY → HARD_DESTROY without data loss. |

## Non-goals

| # | What we deliberately don't do | Why |
|---|------------------------------|-----|
| NG1 | macOS host runtime support. | Apple Silicon: no AF_VSOCK, no native KVM, no native libvirt. Code-correctness yes, runtime no. |
| NG2 | Linux-on-Windows (the WSL2 direction). | Different problem. WSL2 already exists. |
| NG3 | Non-VM execution (Wine / CrossOver / Bottles). | Different paradigm with different strengths and limits. We deliberately use a real VM. |
| NG4 | Multi-user shared VM. | Single Linux user, single Windows VM. Adding sharing breaks our credential model and threat model. |
| NG5 | Headless / server / kiosk deployments. | We assume an interactive Linux desktop with a logged-in user. |
| NG6 | Docker / Podman backends. | Architectural — see `docs/DECISIONS.md` DEC-0003. |
| NG7 | Shipping pre-installed Windows VMs. | License + hosting cost. We help users download official Microsoft ISOs. |
| NG8 | Activation key management. | The user owns their Windows licensing. |

## Success criteria

| Axis | Target |
|------|--------|
| Onboarding (user-attended) | ≤2 min from `crossdesk install` to walking away |
| Onboarding (wall-clock) | 15-25 min including Windows install on a typical NVMe + 8-core host |
| Cold app launch (post-install, post-VM-boot) | ≤5 s p50, ≤10 s p99 from `crossdesk launch` to visible window |
| Heartbeat round-trip (steady state) | <100 ms p50, <250 ms p99 |
| Host process resident memory | <100 MB excluding child processes |
| Idle VM memory (Lean) / (full Win11 Pro) | ≤800 MB / ≤1.2 GB with virtio-balloon |
| Recovery from forced VM kill | <30 s to next successful `launch` |

These are also captured machine-readably in `docs/REQUIREMENTS.md`
under N1 (performance budgets).

## Our advantages — defend these

| Advantage | vs | Why we win |
|-----------|----|------------|
| `qemu:///session` user libvirt | WinApps Docker mode | No privileged daemon, direct `$WAYLAND_DISPLAY` access, no sudo install step |
| `AF_VSOCK` + mTLS + per-frame `AuthContext` | WinApps RDP-over-TCP | Skips the network stack; replay defense independent of TLS |
| Just-in-time VirtioFS | WinApps `\\tsclient\home` | Per-file mounts, not whole-`$HOME` exposure; detached after `ReleaseAck` |
| Type-checked async | WinApps 1993-line bash | Compile-time correctness, testability, refactor safety |
| Zero-touch `autounattend.xml` bootstrap | virt-manager + manual install | Reproducible from-zero VM rebuild |
| Heartbeat FSM with explicit recovery states | WinApps "exit and retry" | Survives transient stalls; surfaces hard failures |
| Per-frame authentication context | TLS-only RDP | Defends against CID collision, replay, even with TLS layer compromise |

## Our disadvantages — accept and mitigate

| Disadvantage | Mitigation |
|--------------|------------|
| WinApps has 5+ years of polish, ~10k★, 91 community-tested apps | Vendor their app catalog (license-permitting) and inherit the tribal knowledge — see `docs/COMPARISON_WINAPPS.md`. |
| WinApps's `docker compose up` is genuinely faster than our libvirt setup today | `crossdesk install` one-command bootstrap with auto-ISO download closes most of this gap. |
| Our stack (Python + Rust + Qt + gRPC + VSOCK + libvirt) is more pieces than `bash + freerdp` | Type checking + tests pay back the complexity. `AGENTS.md` helps human and AI contributors navigate. |
| No Mac runtime (only build/test) | Documented as NG1; CI matrix proves Mac builds work. |
| Pre-MVP — nothing to demo | Foundational layers (transport, FSM) are correct-by-construction even before integration testing. |
| GPL-3.0 vs WinApps AGPLv3 means we can't directly copy code | Re-implement logic, not source. Documented in `docs/DECISIONS.md`. |

## Where we sit in the design space

CrossDesk is a high-trust, single-user, security-first Windows-app
forwarder for Linux desktops. Closest neighbors:

- **WinApps** — same goal, different stack, looser security model.
- **Cassowary** — abandoned; closer to WinApps' approach.
- **Wine / CrossOver / Bottles** — different paradigm (no VM); better
  for some apps (especially older games), worse for the cases where
  Microsoft / Adobe enforce real-Windows execution.
- **WSL2 / WSLg** — opposite direction (Linux on Windows host); not
  relevant to our user.
- **Direct virt-manager + RDP** — what advanced users do today by
  hand. CrossDesk is essentially "this, automated, with per-frame
  authentication and JIT filesystem."

Full landscape in `docs/COMPETITION.md`.
