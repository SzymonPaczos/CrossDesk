# Post-1.0 ideas

Things we deliberately punt past v1.0 because the value/effort
ratio fits a "growth" version better than a "stability" one. Some
are genuine roadmap candidates; others are explicitly marzenia and
exist here so the idea isn't lost.

This file is **not** a prioritised list — it's a brainstorm with
sketches. Items get promoted into [FOLLOWUPS.md](../FOLLOWUPS.md)
or [EXECUTION_PLAN.md](EXECUTION_PLAN.md) when they earn a real
slot.

---

## Multi-VM

Run several Windows installs concurrently. Office VM (Win11 + Office
+ Polish lang pack), Legacy VM (Win7 + that one accounting app from
2003), Gaming VM (Win11 + GPU passthrough). RAIL apps from each VM
mix in the Linux desktop indistinguishably; user picks "Excel
(Office VM)" or "Excel (Legacy VM)" from the launcher.

**Why post-1.0:** changes the data model substantially. Single
`~/.config/crossdesk/vm.toml` becomes
`~/.config/crossdesk/profiles/<name>/vm.toml`; libvirt domain name
becomes `crossdesk-<profile>`; install state machine grows a
`profile` axis; FSM + Lifecycle Coordinator become per-profile.
Worth doing right, not bolting on.

**v1.0 prep:** all the above paths are already parameterised
where possible (e.g. `RealLibvirtController(domain_name=...)`). v1.x
just adds a profile loader.

---

## Cloud-synced settings + app catalog

Use GNOME Online Accounts / KDE Akonadi / iCloud to sync
`~/.config/crossdesk/` between machines. User installs CrossDesk on
their second laptop and sees the same app catalog, credentials,
preferences.

**Open questions:**
- Where does the cloud sync state live (IMAP folder? WebDAV?
  Tailscale ts.net? Self-hostable?).
- How do we handle credentials (KWallet sync is brittle).
- Multi-machine VM image sharing is too big — out of scope.

---

## Mobile companion app

Android + iOS app that talks to the host daemon over Tailscale's
ts.net. Lets the user:

- See VM status from phone
- Suspend / resume / restart
- View recent activity
- Receive HARD_DESTROY notifications
- Launch a Windows app remotely (would render via VNC on phone? or
  just queue for next time at desk?)

**Why post-1.0:** doubles the surface area. New gRPC client in
Kotlin + Swift, mobile UX patterns, push notifications via FCM /
APN. Big, separate project.

---

## Browser extension

WebExtension for Firefox/Chrome/Edge. Routes specific link patterns
through CrossDesk:

- `.docx` / `.xlsx` / `.pptx` direct downloads → open in Office
  via JIT mount of the cached file
- `ms-word://` / `ms-excel://` URI schemes (already shipped via
  `.desktop` handler; extension makes it nicer in-browser)
- Right-click image → "Open in Photoshop"
- Maybe even right-click selection → "Send to OneNote"

**Why post-1.0:** browser store reviews + per-browser packaging is
ongoing maintenance.

---

## App Store with one-click install

Curated catalog of "popular Windows apps you might want". Click
"Install Notepad++" → host runs PowerShell in the guest:

```powershell
Invoke-WebRequest -Uri "https://github.com/notepad-plus-plus/...installer.exe"
.\installer.exe /S
```

Then auto-generates `.desktop`. Crossover/Whisky already does this
(they call them "bottles"). We can do better because we're a real
Windows install — no Wine compatibility issues.

**Why post-1.0:** legal + security review. Auto-running installers
from URLs needs careful scrutiny. PolicyKit + signed manifests +
SHA-256 verification + per-app allowlist.

---

## Compatibility-rating submission

v1.0 ships `compatibility.json` as bundled data with display-only
ratings. Post-1.0 lets users submit:

```
You've used Photoshop CS24 for 47 hours.
How's it working?
[ ⭐⭐⭐⭐⭐ ]   [ Notes (optional): _________________ ]
              [ Submit anonymously ]
```

Aggregated server-side (similar to ProtonDB), redistributed in a
weekly catalog update.

**Privacy concern:** what data goes with the rating? VM Win version,
RAM allocation, GPU passthrough state — useful but identifying.
Opt-in, anonymous, hashed.

---

## Voice commands

"CrossDesk, open Excel." Whisper STT runs locally; intent matches
against app catalog; same code path as KRunner / launcher.

**Why post-1.0:** infrastructure cost (Whisper model is ~150 MB),
multilingual training, false-positive rate ("CrossDesk, open Excel"
matches anyone in the room). Fun feature, low priority.

---

## Power Mode toggle

```
┌── Power Mode ─────────────────────────────────────────────┐
│  ○ Performance  (full CPU, full RAM, GPU passthrough on)  │
│  ◉ Adaptive     (scale based on activity, default)        │
│  ○ Battery      (cap CPU 25%, balloon RAM aggressively,   │
│                  suspend on inactivity, GPU off)          │
└───────────────────────────────────────────────────────────┘
```

Affects: libvirt vCPU pinning, virtio-balloon driver targets, FSM
miss_threshold (more lenient on battery), GPU device hot-attach
state, RAIL frame rate cap.

**Why post-1.0:** needs upower/UPower D-Bus integration + hot
reconfig of running VM (some libvirt knobs only apply on next
domain start). Big enough to deserve its own design doc.

---

## Snapshot tab

Backup the running VM, restore on demand. Wraps `virsh snapshot-create`
+ external storage targets.

```
┌── Snapshots ──────────────────────────────────────────────┐
│  current state       (live)                               │
│    │                                                       │
│    ├── Daily        (auto, 7 days)                         │
│    │     2026-05-09  6.2 GB                                │
│    │     2026-05-08  6.2 GB                                │
│    │     ...                                               │
│    │                                                       │
│    └── Manual                                              │
│          before-office-update  4.1 GB    [Restore][Delete] │
│                                                            │
│  [ + Create snapshot now ]                                 │
└───────────────────────────────────────────────────────────┘
```

**Why post-1.0:** disk consumption planning + GUI for managing
snapshot tree + integration with backup tools (Pika, Vorta, BorgBase).

---

## Recovery mode wizard with bug-report autosubmit

After HARD_DESTROY:

```
┌── What just happened? ────────────────────────────────────┐
│  CrossDesk's heartbeat watchdog couldn't recover the VM   │
│  via graceful shutdown, so it forced a restart at 16:04.  │
│                                                            │
│  At the time:                                              │
│    Active app:    Word (PID 5102)                          │
│    Open file:     ~/Documents/spec.docx                    │
│    FSM history:   HEALTHY → DEGRADED (3 misses) →          │
│                    PROBING (5 misses) → SOFT_RECOVERY      │
│                    (3 attempts) → HARD_DESTROY             │
│                                                            │
│  Suggested cause: VM ran out of RAM. Try:                  │
│    [ Increase RAM allocation to 6 GB ]                     │
│    [ Enable Lean mode ]                                    │
│                                                            │
│  Help us improve CrossDesk:                                │
│    [ Send anonymous bug report ]   [ Dismiss ]             │
└───────────────────────────────────────────────────────────┘
```

The "anonymous bug report" auto-uploads a redacted diagnostic
bundle to a community endpoint (Sentry-like). Privacy-reviewed
contents only.

---

## Sandbox-per-session ephemeral VMs

Like Windows Sandbox: every `crossdesk launch` spawns a fresh VM,
runs the app, destroys the VM on close. Maximum isolation.

**Tradeoffs:** boot latency (~10–30 s vs <1 s for warm RAIL), no
persistent state (no settings, no recent files), much higher RAM
churn. Useful for "I want to run this sketchy `.exe` without
trusting it."

**Implementation hint:** snapshots + clone + quick boot
(`virsh start --reset-nvram` style). Could share base disk
read-only across sessions.

---

## GPU passthrough toggle in UI

Phase 4.5 work (per [DEC-0009](DECISIONS.md)) but framed for the
GUI here. Settings:

```
┌── Display & GPU ──────────────────────────────────────────┐
│  GPU acceleration:                                        │
│    ◉ Off (default; software rendering)                    │
│    ○ NVIDIA RTX 4070 (Tier 1, hot-attachable)             │
│    ○ Looking Glass (single-GPU hot-switch, advanced)      │
│                                                            │
│  ⚠  Enabling GPU passthrough requires VFIO setup. CrossDesk│
│     can configure this; you'll be prompted for sudo.      │
│                                                            │
│  [ Run GPU compatibility check ]                          │
└───────────────────────────────────────────────────────────┘
```

A "Run compatibility check" button shells to `lspci -nnk` + IOMMU
group enumeration, surfaces results in a friendly form. Catches
"shared IOMMU group" footguns before user commits.

---

## Command palette (VS Code-style)

`Ctrl+P` globally inside Manager (and via KRunner outside) opens:

```
┌────────────────────────────────────────────┐
│ > _                                        │
│   Launch Notepad                          ↩│
│   Launch Excel                            ↩│
│   Suspend VM                              ↩│
│   Show recent activity                    ↩│
│   Open ~/Documents/spec.docx in Word      ↩│
│   ...                                      │
└────────────────────────────────────────────┘
```

Fuzzy-matched, ranked by recent use. "Open <file> in <app>" entries
generated dynamically from recently-used files in `~/Documents` etc.

---

## "Quake" overlay

Press F12 (configurable) anywhere on the desktop → drops a
translucent panel from the top of the screen with current Windows
apps + their RAM usage. Click an app name to focus its RAIL window.
Esc dismisses.

Inspired by Quake/CS:GO console. Power-user shortcut for
"what's running and where's my Word window?".

---

## Per-app workspace targeting

Each registered Windows app can be configured to always open on a
specific Linux workspace / desktop:

```
┌── Word configuration ─────────────────────────────────────┐
│  Open on workspace: [ 3 (Documents) ▼ ]                   │
│  Window placement:  [ Centered on monitor ▼ ]             │
│  Frame style:       [ Native (let WM decide) ▼ ]          │
└───────────────────────────────────────────────────────────┘
```

Means user can have a "Coding" workspace with VS Code on Linux + a
"Writing" workspace where Word always lands. Big productivity win.

---

## Diagnostic bundle "second opinion"

Diagnostic bundle export already exists in v1.0. Post-1.0: an
opt-in "send to community" flow where the bundle is uploaded to a
public dashboard (similar to Bugzilla but issue-friendly). Other
users can search "I have the same problem".

---

## Per-app GPU acceleration

Once Phase 4.5 GPU passthrough lands, expose per-app:

```
Photoshop:    GPU on  (always)
Word:         GPU off (default)
AutoCAD:      GPU on  (when launched)
```

Hot-swap GPU device between RAIL sessions. Hard problem (libvirt
device hot-detach races) but if we crack it, it's the most
power-efficient story for Windows VFIO.

---

## "Why is this slow?" diagnostic bot

Heuristic + ML hybrid that watches:

- FSM transition history
- RTT distribution
- RAM/CPU utilisation
- Active RAIL apps
- Recent JIT mounts

And surfaces actionable suggestions:

> Edge prebuilds icons in the background — disable to save 18% idle
> CPU. [ Apply ]

> Word has been hot for 4 hours; consider closing if you're not
> using it (saves ~410 MB RAM).

> Your virtio-balloon target is conservative; bumping max_memory
> by 1 GB may eliminate the recent OOM events.

---

## Telemetry dashboard for the operator

Opt-in telemetry feed that the operator sees on their *own*
dashboard (not phoned home anywhere unless explicitly enabled).

Charts: 7-day FSM transition counts, JIT mount durations, RAIL app
heat map, RTT histogram, memory pressure over time. Quantified-self
for your VM.

---

## Tutorial mode v2

v1.0's tutorial mode is a one-shot walkthrough. Post-1.0 adds:

- Interactive challenges ("Try opening this `.docx` we just dropped
  into your Documents folder")
- Tips of the day in tray
- Discovery hints ("You haven't tried KRunner yet. Press Alt+Space
  and type 'win'.")

Onboarding is forever.

---

## Plasma 6 / GNOME 47 specific polish

Once we're solidly v1.0, we can lean into newer DE features:

- Plasma 6's modern QML controls + improved KCM API
- GNOME 47's accent color sync
- Wayland color management (HDR Office documents in 2027? lol)

---

## Internationalisation beyond EN+PL

v1.0 ships English + Polish. Community translations are a natural
post-1.0 expansion:

- Spanish, German, French (large Linux user bases)
- Japanese (sizable Wine/CrossOver community)
- Russian (active Linux communities)
- Right-to-left support for Arabic / Hebrew

`weblate.org` self-hosted + GitHub actions for `.po` import/export.

---

## Code signing

Sigstore for the Linux binary; EV cert (or Sigstore-on-Windows when
Microsoft adopts it) for `agent.exe` so Windows SmartScreen doesn't
flag every install.

Currently deferred per AGENTS.md "pending user-decision reminders"
as not-yet-justified at MVP. Becomes more relevant when packaged
release artifacts hit Microsoft Store / Chocolatey.

---

## Self-hosted package repos

Currently AUR + Nix flake + PyPI cover v0.1.0. Post-1.0 considers:

- deb hosted (apt.crossdesk.io or similar)
- rpm hosted (Copr / OBS)
- Flatpak (was deferred as overkill but worth re-evaluating once
  tray + KSNI integration is solid; Flatpak's portal model fits)
- Snap (lower priority; Ubuntu-only audience)

Domain decision pending per AGENTS.md "pending user-decision
reminders".

---

## Hardware-smoke CI runner

Self-hosted Linux + KVM box that runs the integration test suite
against real hardware on every push. Currently gated on user
acquiring a Linux machine.

---

## "Operator mode" for shared deployments

Deployment scenario: small office, one Linux server, multiple
employees access shared Windows app set via thin clients. Operator
mode adds:

- Multi-user RAIL session multiplexing
- Per-user credentials in keyring
- Audit log of who launched what
- Resource quotas per user

Adjacent to xrdp territory but with our RAIL niceties on top.
