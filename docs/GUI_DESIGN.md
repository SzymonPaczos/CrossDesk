# GUI Design Reference

Brief for visual / icon design work on CrossDesk. Describes every
screen, current placeholder icons, and the intent behind each surface.

## App overview

| Property | Value |
|----------|-------|
| Framework | Qt 6 / QML via CXX-Qt (Rust bindings) |
| Default window | 800 × 600, resizable |
| Color palette | System palette — respects OS light / dark / system setting |
| Typography | System font throughout; 22px bold for major headings, 18px bold for step / pane headers, 16px bold for toolbar title, system default for body |
| Language | English + Polish (gettext + Qt `qsTr`) |

## Startup routing

- **No VM installed** → Manager opens, InstallWizard pushes on top immediately.
  Step 1 of the wizard has a **Back** button that returns to Manager.
- **VM already installed** → Manager opens directly.

---

## Screen 1 — Manager

The main app surface. Permanently visible as the base of the navigation
stack. Divided into a 180px fixed sidebar and a fluid content area.

### Toolbar (global)

Sits above both sidebar and content via `ApplicationWindow.header`.

| Element | Detail |
|---------|--------|
| Title label | "CrossDesk Manager" — 16px bold |
| Language switcher | ComboBox: `en` / `pl` — right-aligned |

### Sidebar

180px wide, `palette.alternateBase` background. Vertical list of
checkable `flat` buttons; the active pane is `checked`.

| Slot | Current icon | Label | Intent |
|------|-------------|-------|--------|
| 1 | 📊 | Dashboard | VM health overview |
| 2 | 🪟 | Apps | App catalog + launch |
| 3 | 💾 | Storage | JIT VirtioFS mounts |
| 4 | ⏻ | Lifecycle | Suspend / Resume / Destroy |
| 5 | 🩺 | Diagnose | Self-tests + doctor checks |
| 6 | 📜 | Logs | Structured log viewer |
| 7 | ⚙ | Settings | General / VM / Display / Advanced |
| 8 | ℹ | About | Version + credits |

**Icon design ask:** Replace each emoji with a monochrome SVG icon
(24 × 24) that works on both light and dark backgrounds.
A checked (active) sidebar button should use `palette.highlight`
as background — icons should remain legible over it.

### Pane 1 — Dashboard

Three frames arranged vertically (full width, scrollable):

**Status card**

```
● HEALTHY  [severity dot]   VM state: RUNNING    Uptime: 14m 02s
Heartbeat EWMA RTT: 1 ms    Consecutive misses: 0   Soft attempts: 0
```

Severity dot palette (current: Unicode circles — replace with SVG):

| State | Current glyph | Color intent |
|-------|--------------|--------------|
| ok | 🟢 | Green — system OK |
| warn | 🟡 | Amber — degraded / probing |
| critical | 🔴 | Red — hard-destroy / unrecoverable |
| unknown | ⚪ | Grey — no data / daemon not connected |

**Resources frame**

```
CPU    [████████░░░░░░░░░░░░]  12%
RAM    [██████████░░░░░░░░░░]  48%   2.0 GiB / 4.0 GiB
```

Progress bar labels use system font, small size.

**Recent activity frame**

Chronological list of formatted one-liners:
```
16:04  ✓ Notepad launched
16:01  ↻ Suspend → Resume cycle (1.7 s)
15:43  ✓ JIT mount: ~/Documents/spec.docx → Word, 12.4 s
```

**Quick actions row**

Three flat buttons at the bottom: "Launch app…" / "Suspend VM" /
"View logs".

### Pane 2 — Apps

**Curated apps grid** — 4 columns, 160 × 140 px cards:

```
┌──────────────┐
│   [icon area]│
│ Microsoft    │
│ Word         │
│ Office       │
│ ★★★★☆       │
│ [Launch]     │
└──────────────┘
```

Icon area is blank for now (app icons come from Windows registry scan
in Phase 4). Stars rendered as text (`★★★★☆`).

**Discovered apps section** — empty-state text when no registry scan
result available yet.

**Actions row**: "+ Add custom .exe" + "Refresh discovery".

### Pane 3 — Storage

Table of active JIT VirtioFS mounts:

| Column | Example |
|--------|---------|
| Share | spec.docx |
| App | Microsoft Word |
| Handles | 1 |
| Pending writes | 0 B |
| Mounted | 00:04:17 |

Empty state: "No active mounts."

### Pane 4 — Lifecycle

Suspend / Resume / Hard Destroy buttons with confirmation dialogs
(Phase 6 stubs — dialogs not yet implemented).

### Pane 5 — Diagnose

Self-test result list:

```
✓  kvm_device
✓  freerdp       xfreerdp 3.5.1
✓  libvirt
⚠  notify-send   notify-send not on PATH
```

Status icons: ✓ (ok) / ⚠ (warn) / ✗ (fail). Replace with SVG icons
sized to 16 × 16.

"Run diagnostics" button triggers re-check.

### Pane 6 — Logs

Scrollable, monospace-font log viewer. Each line: timestamp +
`[level]` + message. Level colour coding:
- `[info]` → default text
- `[warn]` → amber
- `[error]` → red

Controls: --since filter, --component selector, follow-mode toggle.

### Pane 7 — Settings

**General section**
- Language: ComboBox ("Auto" / "English" / "Polish")
- Theme: ComboBox ("System" / "Light" / "Dark")
- Send usage telemetry: CheckBox

**VM section**
- Credentials: Show / Rotate / Repair buttons
- Lean mode: CheckBox (reduces host RAM footprint)

**Display section**
- HiDPI scaling: ComboBox ("Auto" / "100%" / "140%" / "180%")

**Advanced section** *(placeholder — FSM tuning)*

### Pane 8 — About

CrossDesk version, protocol version, agent version (when daemon
connected), license (GPL-3.0-or-later), link to project homepage.

---

## Screen 2 — Install Wizard

Pushed on top of Manager. Four steps navigated via an inner StackView.
Outer container is a `Page` with title "Install Windows VM".

### Step 1 — Installation media

```
Step 1 of 3 — Installation media

Choose the Windows installation ISO…

[/path/to/windows.iso              ] [Browse…]

[Back]                               [Next ▶]
```

- "Back" → dismisses wizard, returns to Manager
- "Next" enabled only when a path is selected

### Step 2 — VM identity

```
Step 2 of 3 — VM identity

VM name: [CrossDesk-Win                        ]
Admin username: [crossdesk                     ]
Admin password: [●●●●●●●●                      ]

[◀ Back]                             [Next ▶]
```

### Step 3 — Resources

```
Step 3 of 3 — Resources

vCPUs:  [2 ▲▼]
RAM:    [4 GiB ▲▼]
Disk:   [64 GiB ▲▼]

[◀ Back]                          [Install ▶]
```

### Progress view

Indeterminate progress bar + status label ("Downloading…",
"Installing…", "Configuring agent…", "Done"). "Close" button
appears on completion and pops back to Manager.

---

## Icon deliverables summary

| Context | Count | Size | Format |
|---------|-------|------|--------|
| Sidebar navigation | 8 | 24 × 24 | SVG |
| Status severity dot | 4 | 12 × 12 | SVG (or coloured circle component) |
| Diagnose check result | 3 (ok / warn / fail) | 16 × 16 | SVG |
| App placeholder | 1 | 64 × 64 | SVG |
| CrossDesk app icon | 1 | 512 × 512 + 1024 | SVG + PNG set |

All SVGs should use `currentColor` so they inherit the QML `color`
property and adapt to light / dark palette automatically.

## Color semantics

No custom color constants currently — everything uses Qt's system
`palette` object:

| Role | QML expression | Usage |
|------|---------------|-------|
| Background | `palette.window` | Main pane background |
| Sidebar | `palette.alternateBase` | Sidebar background |
| Accent / active | `palette.highlight` | Active sidebar button |
| Body text | `palette.windowText` | Regular text |
| Dim / hint | `palette.placeholderText` | Subtitles, empty-state text |
| Severity green | (hardcoded `#4caf50` or system-colored SVG) | ok dot |
| Severity amber | (hardcoded `#ff9800` or system-colored SVG) | warn dot |
| Severity red | (hardcoded `#f44336` or system-colored SVG) | critical dot |
| Severity grey | (hardcoded `#9e9e9e` or system-colored SVG) | unknown dot |

Severity colors are the only place where hardcoded colors may be
needed — everything else follows the system palette.
