# CrossDesk GUI Plan — v1.0 vision

This document is the canonical design for the CrossDesk Manager UI
plus the desktop-environment integrations that make us feel native
on KDE Plasma and GNOME. It pairs with [V1_0_ROADMAP](#v10-roadmap)
which sequences the implementation week-by-week (Phases 6–9, Weeks
25–40).

Everything here is **plannable on macOS**: each native API touch
hides behind an abstraction (Protocol/trait) with a mock for
mock-driven testing per [CROSS_PLATFORM_DEV.md](CROSS_PLATFORM_DEV.md).
When the binary is compiled on Linux the Real implementation lights
up automatically — no source forking, no `#ifdef` thicket.

Long-term moonshots live in [POST_1_0_IDEAS.md](POST_1_0_IDEAS.md).

---

## Why this matters

WinApps' UX is "we don't have a GUI, you SSH and run shell scripts".
That's our biggest opening: we ship the same RAIL trick they invented
plus an actual desktop application that hides every libvirt detail
behind buttons a normal user can press.

The competitive landscape:

| Product | What they do well | Gap we fill |
|---|---|---|
| WinApps | RAIL forwarding, app catalog | No GUI, no security UX, permanent home share |
| Parallels Desktop | Coherence, slick wizard | Mac-only, $$$, closed-source |
| VMware Fusion | Unity, snapshots | Same as Parallels |
| GNOME Boxes | Friendly Linux UX | No RAIL, no Windows app catalog |
| virt-manager | Power-user depth, perf graphs | Raw libvirt, no app integration |
| Crossover/Whisky | Per-app sandboxes, ratings | Wine-based (no Office, no Adobe) |

CrossDesk Manager = WinApps' RAIL + Boxes' approachability +
virt-manager's depth + Tailscale's tray ergonomics + Crossover's
catalog. Nobody offers that combination today.

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────────┐
│  Linux desktop session                                      │
│                                                             │
│   ┌───────────────────┐  ┌──────────────────┐              │
│   │  System tray      │  │  Manager window  │              │
│   │  (KSNI / GShell)  │  │  (Qt6 QML, 8 px) │              │
│   └────────┬──────────┘  └─────────┬────────┘              │
│            │                       │                        │
│            └───────────┬───────────┘                        │
│                        │                                    │
│                        ▼                                    │
│            ┌────────────────────────┐                       │
│            │  Manager IPC client    │  (mgmt.proto over     │
│            │  (Rust + tonic)        │   AF_UNIX socket)     │
│            └────────────┬───────────┘                       │
│                         │                                   │
│  ───────────────────────┼─────────────────────────────────  │
│                         ▼                                   │
│            ┌────────────────────────┐                       │
│            │  crossdesk-host daemon │  (Python asyncio)     │
│            │  + management RPC      │                       │
│            └────────────┬───────────┘                       │
│                         │                                   │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          ▼  (existing channel: AF_VSOCK + mTLS)
                  ┌──────────────────┐
                  │  Windows guest   │
                  │  agent.exe       │
                  └──────────────────┘
```

**Key design decisions:**

- **Tray and Manager are one binary** (`crossdesk-gui`) but Tray can
  run headless (no main window). User closes the Manager → Tray
  stays. Quit only via Tray menu.
- **GUI ↔ daemon over AF_UNIX**, not the gRPC-mTLS channel that
  goes to the guest. Local IPC has no peer-cert overhead and lets
  us add commands like `Status()` / `ListMounts()` / `Launch()` /
  `RotateCredentials()` without touching the guest-facing proto.
- **Single source of truth for state** is the daemon. The GUI
  subscribes to `Status` stream and renders. Settings changes flow
  GUI → daemon → on-disk config; daemon then re-emits new state.
- **Dual-DE support** via integration abstractions; a build for
  Plasma plugs different concrete classes than a build for GNOME,
  but the manager UI itself is identical.

---

## Manager window — eight panes

The window is 800×600 by default, sidebar + main pane. Sidebar
shows pane names; main pane swaps content. Below, each pane in
detail — what's shown, what user can do, what data sources back it.

### 1. Dashboard (landing)

Default pane after `crossdesk install` finishes. Single-screen
overview so an operator can answer "is my Windows VM OK?" in one
glance.

```
┌── Status card ─────────────────────────────────────────────┐
│  ● HEALTHY                                Uptime: 14h 23m  │
│  Heartbeat RTT: 1.4 ms p50                                 │
│  Last HARD_DESTROY: never                                  │
│  AuthContext rejections: 0                                 │
│  Active mounts: 0                                          │
└────────────────────────────────────────────────────────────┘

┌── Resources ──────────┐  ┌── RAIL apps running ─────────┐
│  ▓▓▓▓░░░░  RAM 48 %   │  │  Notepad   PID 4214  60 MB   │
│  ▓▓░░░░░░  CPU 18 %   │  │  Excel     PID 5102  410 MB  │
│  ▓░░░░░░░  Disk 11 %  │  │                              │
└───────────────────────┘  └──────────────────────────────┘

┌── Recent activity (last 10) ───────────────────────────────┐
│  16:04  ✓ Notepad launched (request_id=abc12)              │
│  16:01  ↻ Suspend → Resume cycle (1.7 s)                   │
│  15:43  ✓ JIT mount: ~/Documents/spec.docx → Word, 12.4 s  │
│  15:42  ✓ JIT detach: spec.docx (LockReport: 0 handles)    │
│  ...                                                        │
└────────────────────────────────────────────────────────────┘

[ Launch app... ]  [ Suspend VM ]  [ Open Settings ]  [ Logs ]
```

**Backed by:** `mgmt.Status` streaming RPC. Updates push every
~500 ms (or on event); GUI doesn't poll.

### 2. Apps (catalog + launcher)

Card grid of registered Windows apps. Each card: icon, name,
compatibility badge, "Launch" button.

```
┌─ Built-in (15) ──────────────────────────────────────────┐
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │
│  │ Notepad │ │  Calc   │ │  Paint  │ │  cmd    │  ...    │
│  │   ⭐⭐⭐⭐⭐ │ │  ⭐⭐⭐⭐⭐ │ │  ⭐⭐⭐⭐⭐ │ │  ⭐⭐⭐⭐⭐ │         │
│  │ [Launch]│ │ [Launch]│ │ [Launch]│ │ [Launch]│         │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘         │
└──────────────────────────────────────────────────────────┘

┌─ Microsoft Office (5) ───────────────────────────────────┐
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │
│  │  Word   │ │  Excel  │ │ PowerP. │ │ Outlook │  ...    │
│  │  ⭐⭐⭐⭐☆  │ │ ⭐⭐⭐⭐⭐ │ │ ⭐⭐⭐⭐⭐ │ │ ⭐⭐⭐☆☆  │         │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘         │
└──────────────────────────────────────────────────────────┘

┌─ Discovered on this guest (47) ──────────────────────────┐
│  Auto-detected from registry. Click to add to launcher.  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │
│  │ Spotify │ │ VS Code │ │  Steam  │ │ AutoCAD │  ...    │
│  │   [+]   │ │   [+]   │ │   [+]   │ │   [+]   │         │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘         │
└──────────────────────────────────────────────────────────┘

[ + Add custom .exe ]  [ Refresh discovery ]
```

**Backed by:**
- Curated tier: `~/.local/share/crossdesk/apps/curated/*.toml` (vendored
  templates, ported from `third_party/winapps/apps/`).
- Discovered tier: `mgmt.ListDiscoveredApps()` RPC →
  daemon asks guest agent's `RegistryScannerService` (new RPC,
  Phase 8) to enumerate `HKLM\App Paths` + `Uninstall` + UWP +
  Chocolatey + Scoop shims.
- Compatibility ratings: bundled `compatibility.json` (community-
  curated; submission flow lands post-1.0).

**Launch flow:** Click → `mgmt.Launch(app_id, optional_file)` →
daemon orchestrates JIT mount (if file given) → spawns FreeRDP
RAIL via existing `rail_manager`.

### 3. Storage (JIT mount visualizer — unique differentiator)

WinApps doesn't have this because it permanently exposes `~`. Our
JIT-only design means we can show the user *exactly* what's mounted
right now, who's holding it, and what the recent history is.

```
┌── Active JIT mounts (1) ─────────────────────────────────┐
│  share-7f3e... → \\virtiofs\share-7f3e...                │
│    Host path:  ~/Documents/spec.docx                     │
│    App:        Word (PID 5102)                           │
│    Mounted:    1m 47s ago                                │
│    Open handles: 1   Pending writes: 0                   │
│    [ Force release (⚠ may cause data loss) ]             │
└──────────────────────────────────────────────────────────┘

┌── Recent mount history (last 24h) ───────────────────────┐
│  Time      Host path                  App      Duration  │
│  16:05:23  ~/Documents/spec.docx      Word     ongoing   │
│  15:43:11  ~/Pictures/diagram.png     Paint    23 s      │
│  14:12:08  ~/Reports/Q3.xlsx          Excel    14m 02s   │
│  12:30:55  ~/Source/main.c            VS Code  2h 14m    │
└──────────────────────────────────────────────────────────┘

┌── Statistics ─────────────────────────┐
│  Total mounts today:        17        │
│  Avg duration:              4m 22s    │
│  Path-traversal rejections: 0         │
│  ReleaseAck timeouts:       0         │
└───────────────────────────────────────┘
```

**Backed by:** `mgmt.ListMounts` stream + on-disk
`~/.local/state/crossdesk/mount_history.jsonl` (append-only).

### 4. Lifecycle (manual VM controls + FSM viz)

```
┌── VM controls ────────────────────────────────────────────┐
│  ● Running (HEALTHY)                                      │
│                                                            │
│  [ Suspend ]   [ Resume ]   [ Restart VM ]                │
│  [ Force HARD_DESTROY (⚠ may lose unsaved data) ]         │
│  [ Open Windows console (RDP fullscreen escape hatch) ]   │
└───────────────────────────────────────────────────────────┘

┌── FSM state graph ────────────────────────────────────────┐
│                                                            │
│      HEALTHY ──→ DEGRADED ──→ PROBING                      │
│       ●            ○             ○                         │
│       │                          │                         │
│       ▼                          ▼                         │
│      SUSPENDED                  SOFT_RECOVERY              │
│                                  │                         │
│                                  ▼                         │
│                                 HARD_DESTROY               │
│                                                            │
│  EWMA RTT: 1.4 ms     miss_count: 0     soft_attempts: 0  │
│                                                            │
│  [Live RTT graph: ◢ small sparkline last 60 s]             │
└───────────────────────────────────────────────────────────┘

┌── Auto-suspend ───────────────────────────────────────────┐
│  □ Suspend VM after 30 min of inactivity                  │
│  □ Always suspend on lid close                            │
│  ☑ Resume on launch attempt                               │
│  Threshold tuning: [Advanced ▼]                           │
└───────────────────────────────────────────────────────────┘
```

**Why FSM viz matters:** virt-manager shows raw libvirt states
(`running`, `paused`); we show our application-layer FSM. A user
seeing `DEGRADED` knows "heartbeat RTT is elevated, system is
watching" — not "should I be worried?".

**Backed by:** `mgmt.Status` stream contains FSM state +
RTT samples; QML chart renders sparkline from rolling 60-second
buffer.

### 5. Diagnose (`crossdesk doctor` integrated)

```
┌── Pre-flight check ──────────────────────────────────────┐
│  ✓ /dev/kvm                                              │
│  ✓ FreeRDP (xfreerdp 3.5.1)                             │
│  ✓ libvirt session                                      │
│  ✓ Disk space (147 GB free)                             │
│  ! D-Bus notifications (notify-send not on PATH)        │
│    → Install libnotify-bin: sudo apt install libnotify  │
│  ✓ mTLS PKI (CA + host + guest leaves present)          │
│  ✓ vsock kernel module loaded                           │
│                                                          │
│  [ Re-run ]   [ Export diagnostic bundle ]              │
└──────────────────────────────────────────────────────────┘
```

**Diagnostic bundle** = zip of `~/.local/state/crossdesk/` +
last 1000 lines of `journalctl --user -u crossdesk-host` +
`crossdesk doctor` output + redacted vm.toml (password masked).
Ready to attach to GitHub issues. Docker Desktop pioneered this
and it's worth gold for support.

### 6. Logs

Live-tail with severity filters, component filters, search box,
Follow toggle.

```
┌─ Filter: [All ▼] Component:[heartbeat ▼] [Search: ____] [Follow ☑] ┐
│                                                                     │
│  16:04:23 [info]    heartbeat_state_transition HEALTHY→DEGRADED    │
│  16:04:23 [warn]    heartbeat_graceful_shutdown_dispatched         │
│  16:04:24 [info]    heartbeat_state_transition DEGRADED→HEALTHY    │
│  16:04:30 [info]    rail_create hwnd=0x4321 title='Notepad'        │
│  ...                                                                │
└─────────────────────────────────────────────────────────────────────┘
```

**Backed by:** `journalctl --user -u crossdesk-host -f -o json`
piped through QML model. Color-coded by severity.

### 7. Settings (drawer-style; expand on demand)

```
┌── General ────────────────────────────────────────────┐
│  Language:  [Polski ▼]                                │
│  Theme:     [System ▼]   (Light / Dark)               │
│  Telemetry: [□ Enable anonymous usage stats]          │
└───────────────────────────────────────────────────────┘

┌── VM ─────────────────────────────────────────────────┐
│  Credentials:  [ Show ]  [ Rotate ]  [ Repair ]       │
│  Storage:      Use KWallet / gnome-keyring [ ☑ ]      │
│  Lean mode:    [ Enabled ]   (rebake VM image: opt-in)│
│  Network:      [NAT ▼]                                 │
└───────────────────────────────────────────────────────┘

┌── Display ────────────────────────────────────────────┐
│  HiDPI scale:  [Auto ▼]   (100 / 140 / 180 / Auto)   │
│  Multi-monitor placement: [☑ Enabled]                  │
│  Wayland-native RAIL: [□ (post-1.1 experimental)]      │
└───────────────────────────────────────────────────────┘

┌── Advanced (FSM tuning) ──────────────────────────────┐
│  miss_threshold:        [3 ▽▲]                        │
│  recovery_ticks:        [3 ▽▲]                        │
│  backoff_initial_secs:  [5.0 ▽▲]                      │
│  max_soft_attempts:     [3 ▽▲]                        │
│  [ Reset to defaults ]                                │
└───────────────────────────────────────────────────────┘
```

### 8. About

Version, build hash, license summary, link to docs, contributors.
Easter egg: scroll to bottom shows the Phase 4 SPOF passage from
[ROADMAP.md](../ROADMAP.md).

---

## Distro integrations

This is where v1.0 graduates from "nice app" to "feels native". Each
hook below is its own concrete class behind an integration trait,
with a Mac-friendly mock that does nothing so dev work continues.

### KDE Plasma 6

| Hook | Implementation | Mac mock |
|---|---|---|
| **KCM module** | `crossdesk-kcm.so` — Plasma 6 plugin loading our QML. Lives in System Settings → "Windows Apps". Same QML as Manager window's settings pane, wrapped in the KCModule API. | No-op; on Mac the Manager window's settings pane stands in. |
| **Dolphin Service Menu** | `infra/desktop/crossdesk-dolphin.desktop` with `Actions=`. Right-click on file → "Open with Windows app..." submenu. | Bundled but unwired on Mac. |
| **KRunner plugin** | `crossdesk-krunner.so` — KRunner V2 Plugin. User types `win <name>` → matches against app catalog → Enter launches. | Same QML "command palette" Ctrl+P inside Manager window. |
| **KWallet** | `keyring/kde.py` — uses `kwallet5-py3` or DBus directly. | `keyring/file.py` (current vm.toml stays as fallback everywhere). |
| **Plasmoid widget** | `crossdesk-plasmoid` package — desktop/panel widget, status dot + 5 most-recent apps. | No-op. |
| **System Tray (KSNI)** | `org.kde.StatusNotifierItem` proper. | macOS NSStatusItem (Mac actually has tray; nice to keep parity). |
| **Notification Center** | `org.freedesktop.Notifications` with KDE-specific actions (`replaces-id`, `urgency=critical` for HARD_DESTROY events). | NSUserNotification on Mac; logs only on headless. |

### GNOME

| Hook | Implementation | Mac mock |
|---|---|---|
| **Nautilus Extension** | Python plugin in `~/.local/share/nautilus-python/extensions/`. Right-click context menu mirrors Dolphin's submenu. | No-op. |
| **Search Provider** | `org.gnome.Shell.SearchProvider2` over D-Bus. Apps appear in Activities search. Manifest in `infra/desktop/`. | No-op. |
| **GNOME Shell extension** | `crossdesk@szymonpaczos.io` — vanilla GNOME doesn't show SNI tray, so we ship an extension that adds the indicator. | No-op. |
| **gnome-keyring (libsecret)** | `keyring/gnome.py` — `secretstorage` Python lib. | File fallback. |
| **Quick Settings tile** | Part of the GNOME Shell extension. Pull-down panel shows VM status with a toggle. | No-op. |

### Cross-DE (XDG)

| Hook | Implementation |
|---|---|
| **MIME registration** | Generated `.desktop` files declare `MimeType=application/vnd.openxmlformats-officedocument.wordprocessingml.document;...`. `xdg-mime default crossdesk-word.desktop application/...`. |
| **`org.freedesktop.portal.OpenURI`** | Daemon implements the portal so containerised apps (Flatpak Firefox) can open files in our Windows apps without escape. |
| **xdg-autostart** | `~/.config/autostart/crossdesk-tray.desktop` — tray launches on session start. |
| **PolicyKit** | `infra/policy/org.crossdesk.policy` — for actions needing root (libvirt domain create on first install). |
| **GApplication ID** | `io.crossdesk.Manager` for desktop file matching, recently-used, etc. |

### macOS dev environment

The Mac developer experience stays exactly what it is today: `cargo
run -p crossdesk-gui` opens the Qt window, all distro hooks are
stubbed mocks, all subprocess calls (notify-send, virsh, kwallet5)
are guarded by `shutil.which` and silently no-op when the binary
isn't available. The same source produces a Linux build that lights
up every integration.

---

## WinApps 90+ apps coverage

WinApps' edge over alternatives is its app catalog: 90+ pre-tested
`.desktop` files in `third_party/winapps/apps/` covering Office,
Adobe, Autodesk, engineering tools, accounting software, browsers,
and built-in Windows utilities.

**We can match this and exceed it via three tiers.**

### Tier 1 — Curated (~30 apps, vendored at v1.0)

Hand-picked best-tested apps with our wrapper. Each tier-1 entry has:

- Icon + display name + categories (translated EN+PL)
- Windows executable path
- Launch arguments
- MIME types it claims (so `.docx` → Word automatically)
- Compatibility rating (we test on hardware before shipping)
- Known-issues notes if any

Initial list mirrors the most-used WinApps entries:

```
Office:       Word, Excel, PowerPoint, Outlook, Access, OneNote, Teams
Adobe:        Photoshop, Illustrator, Premiere, Acrobat Reader
Browsers:     Edge, Internet Explorer
Dev:          PowerShell, cmd, regedit, Notepad++
Built-in:     Notepad, Calculator, Paint, Snipping Tool, Task Manager
Specialised:  AutoCAD (smoke-tested), Spotify, VS Code Win
```

Format: TOML in `infra/apps/curated/`, packaged with the wheel.
Loaded at first launch into `~/.local/share/crossdesk/apps/`.

### Tier 2 — Auto-discovered (~60+, runtime)

Guest-side scanner enumerates every install on the running VM.
Implemented as a new Rust crate `guest/crates/registry-scan/`.
Sources (matching WinApps' coverage and exceeding it):

| Source | Path | Apps captured |
|---|---|---|
| App Paths | `HKLM\Software\Microsoft\Windows\CurrentVersion\App Paths` | Things you can launch by name (`winword`, `excel`) |
| Uninstall | `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall` + `HKCU\...` | Everything with an installer entry |
| WOW6432Node | `...\Wow6432Node\...\Uninstall` | 32-bit apps on 64-bit Windows |
| UWP | `Get-AppxPackage` via PowerShell | Modern Windows apps (Calc, Photos, Sticky Notes) |
| Chocolatey | `choco list -lo` | Apps installed by power users |
| Scoop | `scoop list` | Same |
| Start Menu shortcuts | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\*.lnk` | Catch-all |

WinApps only does App Paths; we get all seven. Surfaced in the
Apps pane as "Discovered (47)" with a "+" to promote into the
launcher.

### Tier 3 — User-added (∞)

Drag-drop a `.exe` onto the Apps pane, or "Add custom" wizard:

```
┌── Add custom Windows app ─────────────────────────────────┐
│  1. Browse VM filesystem...    [ Choose .exe ]            │
│  2. Display name:              [ My Custom App ]          │
│  3. Icon:                      [ Auto-extract ☑ ]         │
│  4. Categories:                [ Office  Utility +  ]     │
│  5. Claim MIME types?          [ □ Set as default for ... │
│                                                            │
│  [ Cancel ]                              [ Add to catalog ]│
└───────────────────────────────────────────────────────────┘
```

Generates `.desktop` file + entry in `~/.local/share/crossdesk/apps/user/`.

---

## Tech architecture

### Build outputs

| Binary | Crate | Role |
|---|---|---|
| `crossdesk-gui` | `gui/crates/crossdesk-gui` | Manager window (Qt6 QML) |
| `crossdesk-tray` | `gui/crates/crossdesk-tray` (new) | Tray icon, headless-OK |
| `crossdesk-kcm.so` | `gui/crates/crossdesk-kcm` (new) | KDE System Settings plugin |
| `crossdesk-krunner.so` | `gui/crates/crossdesk-krunner` (new) | KDE KRunner plugin |
| Nautilus extension | `gui/extensions/nautilus/` (Python) | Right-click integration |
| GNOME Shell ext | `gui/extensions/gnome-shell/` (JS) | Tray + Quick Settings |
| `crossdesk` CLI | (existing in host package) | Imperative commands |
| `crossdesk-host` | (existing) | Daemon |

### IPC layer (mgmt.proto)

New proto file `proto/crossdesk/v1/mgmt.proto` (separate from
guest-facing protos so wire-format isolation stays clean):

```proto
service ManagementService {
  rpc Status(Empty) returns (stream StatusFrame);
  rpc ListApps(Empty) returns (stream AppEntry);
  rpc ListDiscoveredApps(Empty) returns (stream AppEntry);
  rpc ListMounts(Empty) returns (stream MountEntry);
  rpc Launch(LaunchRequest) returns (LaunchResponse);
  rpc Suspend(Empty) returns (Empty);
  rpc Resume(Empty) returns (Empty);
  rpc HardDestroy(Empty) returns (Empty);
  rpc RotateCredentials(Empty) returns (CredentialsResponse);
  rpc RunDiagnostics(Empty) returns (DiagnosticsReport);
  rpc ExportDiagnosticBundle(Empty) returns (DiagnosticBundle);
  rpc Settings(SettingsRequest) returns (Empty);
}
```

Bound to `~/.local/run/crossdesk-host.sock` (XDG_RUNTIME_DIR
fallback). No mTLS — Unix socket permissions (0600) are the
authentication mechanism. PolicyKit gates privileged actions
(HardDestroy, Settings.lean_mode_change).

### Cross-platform abstractions (new traits/Protocols)

Following the existing pattern (`LibvirtController`,
`FreeRDPInvocation`, `Notifier`, `Transport`):

```python
# host/src/crossdesk_host/integrations/keyring.py
class Keyring(Protocol):
    def get(self, key: str) -> Optional[str]: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> None: ...

# Real impls:
#   keyring/kwallet.py  — Linux+KDE
#   keyring/gnome.py    — Linux+GNOME (via secretstorage)
#   keyring/file.py     — fallback (~/.config/crossdesk/vm.toml, 0600)
#   keyring/mock.py     — in-memory for tests
```

```rust
// gui/crates/crossdesk-tray/src/integration/mod.rs
pub trait DesktopIntegration: Send + Sync {
    fn show_tray(&self) -> Result<()>;
    fn update_status(&self, state: VmState) -> Result<()>;
    fn show_notification(&self, n: Notification) -> Result<()>;
    fn register_search_provider(&self) -> Result<()>;
}

// Real:  KdeIntegration (KSNI + KCM hooks), GnomeIntegration (extension hooks)
// Mock:  NullIntegration (Mac dev)
```

Plus a couple of new ones for v1.0:

- `MimeRegistry` — registers MIME associations (xdg-mime / KDE / GNOME)
- `XdgPortal` — implements OpenURI portal
- `SearchProvider` — KRunner + GNOME Shell common interface
- `RegistryScanner` — talks to guest agent's new RPC

### Data flow examples

**User clicks "Launch Word" in Apps pane:**

1. QML `Apps.qml` emits `launch("word", null)` signal
2. Tray/window IPC client sends `Launch{app_id: "word"}` over Unix socket
3. Daemon's `ManagementServiceServicer.Launch` maps app_id to
   `AppLaunchSpec` + `FreeRDPConnectionSpec`
4. Daemon spawns FreeRDP via existing `RealFreeRDPInvocation`
5. Daemon emits `app_launched` event on `Status` stream
6. GUI updates dashboard "RAIL apps running" list

**User opens `~/Documents/spec.docx` from Dolphin:**

1. Dolphin invokes registered `.desktop` file
2. `Exec=crossdesk launch word %f`
3. CLI dispatches to daemon (it can talk to mgmt socket too)
4. Daemon: `validate_mount_path(spec.docx)` →
   `trigger_mount(parent_dir)` → wait for MountResult →
   `Launch(word, translated_path)`
5. Word opens in RAIL window with the file argument
6. Tray icon flashes briefly to confirm

---

## V1.0 roadmap

Sequenced like [EXECUTION_PLAN.md](EXECUTION_PLAN.md). Each week
states **acceptance** and the **Mac-friendly subset** so dev work
continues uninterrupted.

### Phase 6 — Manager window core (Weeks 25–28)

#### Week 25: tray + dashboard pane

- New crate `gui/crates/crossdesk-tray` with KSNI + Mac NSStatusItem
  abstractions (and a `Null` for headless CI).
- `crossdesk-gui` Manager window grows the sidebar; landing pane
  → Dashboard.
- `mgmt.proto` v1: `Status` stream + `ListApps` stream.
- Daemon: minimal `ManagementServiceServicer` with mock data on
  Mac (returns canned `Healthy` state + canned app list).
- 30+ tests for QML state machine + IPC client.

**Acceptance:** Mac dev can `cargo run -p crossdesk-gui` and see
a Dashboard with mock data; tray icon stub shows in Mac menubar.

#### Week 26: apps pane + lifecycle pane

- Apps pane card grid in QML.
- Lifecycle pane with FSM state graph (using existing FSM data
  via `Status` stream).
- Settings drawer skeleton (no logic yet, just UI).

**Acceptance:** All five "core" panes render; Suspend/Resume
buttons send correct RPCs (verified against mock daemon).

#### Week 27: storage + logs panes

- Storage pane with active mounts table + history.
- `mount_history.jsonl` append-only log on the daemon side.
- Logs pane: live tail QML model.
- Diagnose pane.

**Acceptance:** All eight panes functional; full pane test suite
passes; mock daemon drives every stream.

#### Week 28: i18n complete + theme switching

- `gui/crates/crossdesk-gui/i18n/` — full PL translations for every
  string in QML.
- Theme detector (KDE Plasma color scheme + GNOME color scheme +
  manual override in Settings).
- Polish formatting (numbers, dates, byte sizes).

**Acceptance:** Switching `LANG=pl_PL.UTF-8` shows fully Polish UI;
manual `LANG=en_US.UTF-8` shows English. Theme follows DE.

---

### Phase 7 — Distro integration (Weeks 29–32)

#### Week 29: KDE Plasma integration

- `crossdesk-kcm.so` Plasma 6 KCModule.
- `crossdesk-krunner.so` plugin (matches `win <name>` queries).
- KWallet keyring backend.
- Dolphin Service Menu `.desktop` file.
- Plasmoid skeleton (panel widget; full implementation v1.1).

**Mac-friendly:** all the above are conditionally compiled
`#[cfg(target_os = "linux")]` and the Mac dev binary just doesn't
include them; tests live in the same crates and run on Mac.

**Acceptance:** Linux KDE smoke test (post-hardware): KCM appears
in System Settings; KRunner shows app suggestions; KWallet stores
credentials; Dolphin right-click works.

#### Week 30: GNOME integration

- Nautilus extension Python plugin.
- GNOME Search Provider D-Bus service.
- gnome-keyring (libsecret) backend.
- GNOME Shell extension skeleton (tray indicator).

**Acceptance:** Linux GNOME smoke test: type "Word" in Activities,
app appears; right-click in Files works; tray indicator shows.

#### Week 31: cross-DE XDG hooks

- MIME registration on first launch.
- `org.freedesktop.portal.OpenURI` portal implementation in
  daemon.
- xdg-autostart for tray.
- PolicyKit policy file for privileged operations.
- GApplication ID + recently-used integration.

**Acceptance:** Opening a `.docx` from any GNOME / KDE / sandboxed
app routes through CrossDesk regardless of how it was invoked.

#### Week 32: notification center proper

- Replace `notify-send` shell-out with native `org.freedesktop.
  Notifications` D-Bus client (Rust dbus crate). Action buttons,
  inline replies (where supported), `urgency=critical` for
  HARD_DESTROY events.
- Recovery notifications: "VM was forcibly restarted. Click for
  details" → opens Diagnose pane with the relevant log section.

---

### Phase 8 — App catalog (Weeks 33–36)

#### Week 33: curated tier vendor

- `infra/apps/curated/*.toml` — 30 entries.
- Loader on first launch; populates `~/.local/share/crossdesk/apps/`.
- Translation strings PL+EN per app.

#### Week 34: registry scanner (guest-side)

- New Rust crate `guest/crates/registry-scan`.
- New RPC `RegistryScannerService.Enumerate(stream Empty) returns
  (stream DiscoveredApp)` in a new proto file `mgmt_guest.proto`.
- Sources: App Paths / Uninstall / WOW6432Node / UWP / Chocolatey /
  Scoop / Start Menu shortcuts.
- Icon extraction via `ExtractIconExW` (already in FOLLOWUPS;
  finally lands here).

#### Week 35: catalog browser UI

- Apps pane "Discovered" section consumes `ListDiscoveredApps`.
- Search box (filter by name).
- "Add to launcher" button → generates `.desktop` + persists to
  user tier.

#### Week 36: compatibility ratings (display only)

- Bundled `compatibility.json` per-app: stars + known-issues notes.
- Renders ⭐ in cards.
- Submission flow (community ratings) deferred to post-1.0.

---

### Phase 9 — v1.0 polish (Weeks 37–40)

#### Week 37: recovery diagnostics

- After every HARD_DESTROY, daemon writes
  `~/.local/state/crossdesk/recovery/<timestamp>/`:
  bundled logs, FSM transition log, last RAIL events, last JIT
  mounts. GUI surfaces these as "What just happened?" cards in
  Dashboard until user dismisses.
- Diagnostic bundle export.

#### Week 38: tutorial mode + first-launch experience

- After install, Dashboard shows interactive walkthrough:
  - "Tap to launch your first Windows app"
  - "Right-click any file in Files to open with a Windows app"
  - "Enable system tray for quick access"
- Onboarding cards dismissible, never re-shown after a successful
  app launch.

#### Week 39: docs + screenshots + community

- README polish for v1.0; tag-line update.
- Screenshots (Linux KDE + Linux GNOME + macOS dev).
- Demo GIF.
- Contribution guide for `compatibility.json` submissions.
- v1.0 release notes draft.

#### Week 40: tag v1.0

- All 12 MVP acceptance criteria + 8 v1.0 acceptance criteria
  re-verified on hardware.
- Tag, release, announce.

**v1.0 acceptance criteria** (in addition to v0.1.0's 12):

13. Tray icon shows VM status persistently across login sessions.
14. KDE System Settings → "Windows Apps" loads our KCM.
15. GNOME Activities search shows registered Windows apps.
16. `xdg-mime default crossdesk-word.desktop application/...` makes
    Word the default for `.docx`; double-click in Files just works.
17. Apps pane shows ≥30 curated apps + ≥1 discovered app.
18. KWallet / gnome-keyring stores VM credentials; vm.toml
    becomes optional.
19. HARD_DESTROY recovery: GUI surfaces "What happened?" card with
    one-click export of diagnostic bundle.
20. Polish UI is complete; non-English speaker can complete install
    and launch flow without seeing English.

---

## Mac dev environment guarantee

Throughout Phases 6–9, the Mac dev environment must:

- Compile `crossdesk-gui` and run it (Qt6 + cxx-qt).
- Run `pytest` and have all integration tests pass via mocks.
- Run `cargo test --workspace` and have all Rust unit tests pass.
- `crossdesk doctor` returns 0 or warns clearly about missing tools.
- Fresh-install simulation via `crossdesk install --dry-run`.

Anything Linux-specific (KSNI, KWallet, Dolphin extension, KCM,
KRunner, Nautilus, GNOME Shell, libvirt, FreeRDP binary,
notify-send proper) hides behind a trait/Protocol with a Null/Mock
implementation. The build system selects the right concrete
implementation via `cfg(target_os = ...)` for Rust and runtime
discovery for Python.

This is the same pattern that lets us today develop the heartbeat
FSM + RAIL command builder + path validation entirely on Mac and
trust they'll work on Linux.

---

## What this plan does *not* cover (post-1.0)

See [POST_1_0_IDEAS.md](POST_1_0_IDEAS.md). Highlights:

- Multi-VM (Office VM + Legacy VM + Gaming VM)
- Cloud-synced settings + app catalog
- Mobile companion app
- Browser extension for direct file-link routing
- "App Store" with one-click installs
- Compatibility-rating submission flow (currently display-only)
- Voice commands
- Power Mode (battery-aware throttling)
- Snapshot tab
- Recovery mode wizard with bug-report autosubmit
- Sandbox-per-session ephemeral VMs
- GPU passthrough toggle in UI (Phase 4.5 work)
