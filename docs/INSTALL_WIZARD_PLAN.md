# Install Wizard Plan — first-launch UX

Today: **2026-05-07**.
Phase: **Phase 4 (UX)** — first-run flow that takes a fresh CrossDesk
install from "user just launched the app" to "Windows app running as a
native Linux window".

This document is the design and implementation plan for the install
wizard. It defines the screens, the background work each screen
orchestrates, the deferred items, and the new decisions that need to be
recorded in `docs/DECISIONS.md` before implementation begins.

Source material:
- `docs/PARALLELS_INSTALLER_REFERENCE.md` — UX teardown of Parallels
  Desktop's installer (14 phases, ~17 screens). We borrow what works,
  drop what's friction, and improve what's broken.
- `docs/DECISIONS.md` DEC-0001 (Windows password lifecycle), DEC-0002
  (zero telemetry), DEC-0008 (distribution via deb/rpm/AUR/NixOS/PyPI),
  DEC-0009 (GPU passthrough = Phase 4.5).
- `docs/MVP_SCOPE.md`, `docs/EXECUTION_PLAN.md` — phase boundaries.

---

## 1. North star

Parallels takes 14 phases / ~17 screens to deliver a working Windows
guest. CrossDesk delivers the same outcome in **5 screens** by
exploiting four advantages:

1. **`unattended.xml`** — entire Microsoft Setup + OOBE + Windows EULA
   collapse into zero user-facing screens.
2. **Linux-native distribution** — package manager (deb/rpm/AUR/NixOS,
   per DEC-0008) installs the app, replacing Parallels' .app installer
   chrome (~6 screens at Parallels).
3. **Zero account requirement** (DEC-0002 — zero telemetry, zero
   phone-home) — no sign-up screen, no trial banner, no marketing
   page.
4. **Single permission surface** — Linux: ask once for KVM/USB/audio
   with one explanation, vs Parallels' three sequential macOS native
   permission dialogs.

Anti-goals — patterns we explicitly will not adopt from Parallels:

- Telemetry checkbox pre-selected as opt-in (Parallels `f_0010` —
  dark pattern).
- Mandatory online account during install (Parallels `f_0215`).
- Trial banner at end of install (Parallels `f_0240`).
- Black "loading" screens with no progress label (Parallels
  `f_0150..f_0175` — multiple minutes of dead air).
- Success page rendered in the *guest's* browser (Parallels `f_0260`).
- `cmd.exe` flashes mid-install (Parallels `f_0145` — looks like
  malware to a non-technical user).

---

## 2. Flow overview

| # | Screen | Borrowed from Parallels | Key delta vs Parallels |
|---|---|---|---|
| 1 | Welcome | f_0001 splash | One screen, not four. EULA in `postinst`, not wizard. |
| 2 | OS source picker | f_0050 tile chooser | 3 tiles, not 8. No free-Linux tiles (we run on Linux). No macOS. |
| 2a | Microsoft Windows EULA | none (Parallels skips it via Setup) | Express path only. Per DEC-0014: user accepts MS terms before any download. |
| 3 | Configuration | new — Parallels has no equivalent single-page config | Express-mode defaults, no edition choice, no GPU toggle, no password field. |
| 4 | Install progress | f_0150..f_0175 (improved) | Real "step N of M" with sublabel + ETA. No black screen. |
| 5 | First-app prompt | none — Parallels stops at empty Windows | Optional .exe install / Microsoft Store / skip. Native Linux notification. |

Background tasks (no user-facing screen) covered in §4.

---

## 3. Screen-by-screen specification

### Screen 1 — Welcome

**Trigger:** first launch of `crossdesk` GUI when state-store reports
zero configured guests.

**Content:**
- Title: *"Witaj w CrossDesk"* / "Welcome to CrossDesk".
- One-sentence value statement: "Run Windows applications as native
  Linux windows."
- Hero illustration (TBD asset).

**Actions:**
- Primary: **Continue** (advances to Screen 2).
- Quit / window close — exits. App will show this screen again on next
  launch until a guest is configured.

**No EULA in this screen.** EULA is shown once in the package
postinstall script (`debian/postinst`, RPM scriptlet) per DEC-0008's
distribution model.

**Out of scope:** "Import existing CrossDesk machine" tile — deferred,
see §5.

---

### Screen 2 — OS source picker

**Borrowed from:** Parallels `f_0050` — large tile design, single
primary "Continue" footer.

**Tiles** (three, not eight):

| Tile | Subtitle | What it triggers |
|---|---|---|
| **Install Windows 11** *(recommended)* | "Download from Microsoft, configure automatically." | Express path → Screen 3 with Pro edition fixed. |
| **From ISO file** | "Use a Windows or Linux ISO you already have." | File picker → detect guest OS → Screen 3 (manual mode if Windows non-Pro detected; advanced fields enabled). |
| **Reserved (deferred)** | — | "Import existing CrossDesk machine" — see §5; not rendered in MVP. |

**Why no Ubuntu/Fedora/Debian/Kali tiles** (Parallels has these): our
host **is** Linux. Surfacing free Linux distros as guest-OS choices is
absurd. If a user wants nested Linux they pick "From ISO".

**Why no macOS:** out of scope for CrossDesk (legal + technical).

**Footer:** "Help" (left), "Back" (centre, returns to Screen 1),
"Continue" (right, primary, disabled until tile selected).

**Express path → Screen 2a (EULA) → Screen 3.** "From ISO" path
skips Screen 2a (user already accepted Microsoft's terms when they
obtained the ISO) but goes through edition validation below before
reaching Screen 3.

#### "From ISO" — edition validation *(per DEC-0015)*

After the user picks an ISO, CrossDesk inspects it (`ei.cfg`,
`install.wim` index) and classifies the edition:

- **Pro-class** (Pro, Pro for Workstations) → proceed to Screen 3,
  manual mode with edition pre-selected.
- **Enterprise-class / Education** → proceed to Screen 3, manual
  mode.
- **Home-class** (Home, Home N, Home Single Language, Home in S
  Mode) → **block** with the modal below. Home is rejected because
  it ships no RDP server, which CrossDesk requires.

**Home-detected modal:**

- Heading: *"Windows 11 Home nie jest zgodny z CrossDesk"* /
  *"Windows 11 Home is not compatible with CrossDesk"*
- Body: *"Home nie zawiera serwera Remote Desktop, którego CrossDesk
  używa do wyświetlania aplikacji Windows jako okien Linuksa.
  Wspierane są Pro, Enterprise i Education."*
- Buttons:
  - **Download Windows 11 Pro from Microsoft** (primary) — switches
    to express path → Screen 2a EULA → Screen 3 with Pro fixed.
  - **Cancel** — returns to Screen 2.
- **No "install anyway" option.**

A non-Windows ISO (Linux distro) detected via "From ISO" goes
through a parallel manual-mode path that is beyond the scope of this
plan; track in the Linux-guest workstream.

---

### Screen 2a — Microsoft Windows EULA *(express path only)*

Per **DEC-0014**. Inserted between Screen 2 and Screen 3 only when
the user picked "Install Windows 11" tile.

**Content:**
- Heading: *"Microsoft Software Licence Terms — Windows 11"*.
- Scrollable text area with the EULA bundled in the CrossDesk release
  (version-tagged against the Windows release we install — e.g.
  Windows 11 24H2 → bundled 24H2 EULA).
- Below the text: link *"Read the latest version online"* → opens
  Microsoft's live EULA URL in the host browser.
- Acceptance checkbox: *"I have read and agree to the Microsoft
  Software Licence Terms"*. **Not pre-checked.**

**Actions:**
- **Decline** — returns to Screen 2.
- **Accept and continue** — primary, disabled until checkbox set.
  Advances to Screen 3 and triggers ISO download in the background
  (so the download is already in flight while the user fills in
  Screen 3).

**Audit:** acceptance is logged to
`~/.local/state/crossdesk/eula-acceptance.log` with timestamp,
user, EULA version, SHA256 of the bundled text. Local-only; never
transmitted (DEC-0002).

---

### Screen 3 — Configuration

This is a **new** screen — Parallels splits these decisions across
multiple wizard pages. We collapse to one.

**Express mode** (entered from "Install Windows 11" tile):

| Field | Default | User can change? |
|---|---|---|
| Windows edition | **Pro** (fixed — DEC-NNNN below) | No in express; yes post-install via `changepk.exe`. |
| Language | Detected from `$LANG` (`pl_PL` → Polish, etc.) | Yes, dropdown of supported locales. |
| Windows username | `crossdesk` (per DEC-0001) | **No** — DEC-0001 mandates a fixed account name. |
| Windows password | Random, generated at install | **No** — DEC-0001 mandates auto-generation; field hidden. |
| RAM | `min(host_ram / 2, 16 GB)` | Yes, slider. |
| Disk | 64 GB dynamic (qcow2) | Yes, slider 32–256 GB. |
| GPU passthrough | **Not present** — DEC-0009 defers to Phase 4.5 | Available later in Machine Settings. |

**Manual mode** (entered when "From ISO" detects a non-Pro Windows
edition, or when user later toggles "Advanced" — TBD whether toggle
exists in MVP):
- Edition picker: Home / Pro / Enterprise (only editions detected on
  ISO).
- Other fields identical to express.

**Footer summary line** (the bit Parallels skips that we add): show the
host-impact summary above the Continue button:
> *"Will download 4.5 GB. Will use up to 64 GB disk. Estimated 30 min
> install time."*

This is the moment where the user can opt out informed.

**Footer:** "Help", "Back", **"Install"** (primary).

---

### Screen 4 — Install progress

**The screen Parallels does worst** (`f_0150..f_0175` — minutes of
black with a window-chrome spinner only). Our delta is the entire
point of this section.

**Layout:**
- Heading: *"Installing Windows 11"*.
- **Step indicator**: "Step 4 of 7: Configuring Windows (unattended)".
  Steps are real labelled phases, not byte percentages:
  1. "Downloading Windows ISO from Microsoft"
  2. "Verifying ISO checksum"
  3. "Provisioning libvirt domain"
  4. "Configuring Windows (unattended)"
  5. "Installing virtio drivers"
  6. "Configuring RAIL host integration"
  7. "Finalising"
- **ETA**: "About 12 minutes remaining" — recomputed every 30 s from
  observed throughput.
- **Sublabel** under the step: live string from the work being done,
  e.g. "Applying unattended.xml…", "Mounting virtio-win.iso…".
- **"Show details" disclosure** (collapsed by default): expands
  installer / libvirt / QEMU log tail for power users.
- **"Show VM console" toggle** (off by default): when on, embeds the
  guest framebuffer. Off prevents the `cmd.exe`-flash effect that made
  the Parallels recording look malware-ish (`f_0145`); on serves
  power users debugging an install.
- **Cancel** button (secondary, grey — not primary blue, fixing the
  Parallels affordance inversion from `f_0085`). Confirmation modal:
  "Cancel and remove partial install?"

**On success:** auto-advances to Screen 5 once final step completes
and a smoke-test RPC to the guest succeeds.

**On failure:** modal with last 50 log lines, "Retry" / "Report issue"
/ "Quit" actions. Failure cleanup is automatic (per §4.1 cleanup
logic).

---

### Screen 5 — First-app

Parallels stops at "empty Windows desktop in Edge welcoming the user
to a marketing page". CrossDesk's value proposition is RAIL apps — so
this is where we differentiate.

**Content:**
- Heading: *"Windows is ready. Install your first app?"*
- Three quick actions (cards / buttons):

| Action | Behaviour |
|---|---|
| **Pick a `.exe` from this computer** | Host file picker → file copied to guest → installer invoked via RAIL → resulting installed app auto-registered as a CrossDesk RAIL app. |
| **Open Microsoft Store** | Microsoft Store launched as a RAIL window in the host. User installs there. |
| **Skip for now** | Closes wizard. App lives in host taskbar / system tray; user can launch RAIL apps later from Settings. |

**Native Linux notification** sent in parallel with this screen:
> *"CrossDesk is ready. Click to manage."*

This replaces Parallels' mid-guest Edge-rendered welcome page
(`f_0260`) — we never rely on the guest's browser to communicate with
the host user.

---

## 4. Background tasks (no user-facing screens)

### 4.1 Orphan cleanup at startup *(new requirement)*

**Trigger:** every cold start of the CrossDesk GUI, before Screen 1.

**Metadata schema** (resolves former §7 open question):

The libvirt domain XML carries a CrossDesk-namespaced metadata block
written at `virsh define` time, before the first `virsh start`:

```xml
<metadata>
  <crossdesk:install xmlns:crossdesk="urn:crossdesk:metadata:v1">
    <state>incomplete</state>
    <created-at>2026-05-07T14:32:18Z</created-at>
    <wizard-version>0.1.0</wizard-version>
  </crossdesk:install>
</metadata>
```

**Lifecycle of `<state>`:**
- `incomplete` — set at `virsh define`, before any boot.
- `installed` — set after `unattended.xml` Setup completes and the
  guest reaches a usable login state (signalled by `virtio-serial`
  ping from the guest agent shipped in `<FirstLogonCommands>`).
- `ready` — set after the **first successful RAIL launch** — i.e.
  the first time the host RAIL launcher establishes an RDP RAIL
  channel and renders at least one Windows window on the host.
  Until `ready`, orphan cleanup considers the guest a candidate
  for removal even if Windows finished installing.

The `incomplete → installed → ready` progression means a guest is
only "real" once it has demonstrably worked end-to-end. This is
deliberately stricter than "Windows finished installing" because a
guest that boots but cannot serve RAIL is not useful and should not
survive an interrupted setup.

**Cleanup logic:**
1. List libvirt domains matching `crossdesk-*` prefix.
2. Read each domain's `crossdesk:install/state` metadata.
3. **Orphan** = domain in state `incomplete` *or* `installed` *and*
   in libvirt status `shut off` *and* not currently being installed
   by another CrossDesk process (PID lock at
   `~/.local/state/crossdesk/install.lock`).
4. **Orphan disk** = qcow2 file in `~/.local/share/crossdesk/disks/`
   with no corresponding domain.
5. **Action:** **automatic cleanup** — `virsh undefine` the domain,
   delete the qcow2, append to
   `~/.local/state/crossdesk/cleanup.log`. **No user prompt** (per
   DEC-0011).
6. **Repeat-offender heuristic:** if the same orphan name reappears
   more than 3 times in a rolling week, surface a non-blocking
   notification: *"CrossDesk repeatedly cleaned up failed installs;
   consider reporting an issue."*

**Why "ready" requires a successful RAIL launch, not just install
completion:** an end-to-end RAIL launch exercises the full stack
(RDP server present, network reachable, guest agent responsive,
RAIL channel handshake). A guest that installs but fails RAIL is
not a usable CrossDesk guest, so we do not promote it to `ready`
and the next cold start will sweep it.

**Real (non-orphan) VMs** are domains in state `ready` — they are
never touched by cleanup.

### 4.2 Microsoft ISO download

**Source:** Microsoft directly. We do **not** operate a CrossDesk
CDN (per user directive 2026-05-07).

**Behaviour:**
- Use the documented Media Creation Tool / consumer download URLs.
  Implementation needs to handle Microsoft's geography-based
  redirects and signed-URL expiry (URLs typically valid ~24 h).
- Cache to `~/.cache/crossdesk/iso/` keyed by
  `windows-{version}-{arch}-{lang}.iso`. Reuse on subsequent
  installs without re-download.
- Verify SHA256 against Microsoft's published hash before mounting
  (display "Verifying ISO checksum" as Step 2 of the progress
  indicator).
- If Microsoft's URL discovery fails, surface a clear error pointing
  to "From ISO" path with a link to Microsoft's official download
  page.

**Open question:** legality of automated ISO retrieval from Microsoft.
Captured in §6.

### 4.3 Unattended.xml generation

Generated at the start of Step 3 ("Provisioning libvirt domain") from
a template. Inputs: language, RAM, disk size, generated password
(per DEC-0001 with `gpedit` lockdown of password change). Output:
mounted as a virtual floppy / second ISO so Windows Setup picks it up
automatically during first boot.

This is what skips Microsoft Setup (~`f_0125`), OOBE (~`f_0140`), and
Windows EULA (~`f_0190`) entirely.

### 4.4 Password lifecycle and surfacing

Per **DEC-0001** (lifecycle) and **DEC-0013** (storage, surfacing,
desktop copy).

**Authoritative storage** (read by the auth health-check and RAIL
launcher): `~/.config/crossdesk/vm.toml` mode `0600`.

**Desktop copy — always written**, not just as fallback:
`<xdg-DESKTOP-dir>/crossdesk-windows-password.txt` mode `0600`,
resolved per locale via `xdg-user-dirs` (Polish → `~/Pulpit/`,
English → `~/Desktop/`). The file carries a plaintext header
inviting the user to move or delete it once they've stored the
password somewhere safe. It is written **once at install** and not
auto-refreshed on subsequent password mutations — we do not own
files on the user's desktop.

**User communication on first install — both channels:**
1. **Modal at Screen 4 → Screen 5 transition** showing the password
   once with a copy-to-clipboard button and the paths to *both*
   `vm.toml` and the desktop copy. Modal is non-dismissable until
   acknowledged.
2. **Native Linux notification** in parallel:
   *"Windows password saved to <desktop-path>"*. Notifications are
   ephemeral and distro-dependent; the modal is the load-bearing
   channel.

**Fallback when desktop is unresolvable** (no `xdg-user-dirs`,
read-only home): skip the desktop copy and surface the `vm.toml`
path in both modal and notification with a warning that the
desktop copy could not be written. The auth health-check still
works regardless.

---

## 5. Decisions recorded in `DECISIONS.md`

All six entries below live in `docs/DECISIONS.md`. This section is a
pointer; the canonical text lives in DECISIONS.md.

- **DEC-0010** *(2026-05-07)* — Express install fixes Windows edition
  to Pro. Manual mode (via "From ISO") shows detected editions;
  post-install edition switch lives in Machine Settings.
- **DEC-0011** *(2026-05-07)* — Orphan cleanup is automatic at GUI
  cold start, no user prompt; repeat-offender heuristic catches
  silent bugs.
- **DEC-0012** *(2026-05-07)* — Windows ISO always pulled from
  Microsoft directly; no CrossDesk CDN. Local cache, SHA256 verified,
  signed-URL re-resolution per attempt.
- **DEC-0013** *(2026-05-07)* — Password authoritative copy at
  `~/.config/crossdesk/vm.toml` (per DEC-0001); a discoverable copy
  is **always written** to the user's desktop
  (`crossdesk-windows-password.txt` mode 0600); surfacing on first
  install via modal + native notification (both).
  **Amends DEC-0001 §2.**
- **DEC-0014** *(2026-05-07)* — Microsoft Windows EULA shown
  in-wizard (Screen 2a) before any ISO download on the express path.
  Bundled snapshot, explicit checkbox, no pre-check. Audit log
  local-only.
- **DEC-0015** *(2026-05-08)* — Windows Home is rejected as a guest
  edition. ISO-supplied Home triggers a blocking modal redirecting
  to Pro; no override path. Pro / Pro for Workstations / Enterprise
  / Enterprise LTSC / Education are accepted.

---

## 6. Deferred / explicitly out of scope for MVP

| Item | Why deferred | Surface in UI? |
|---|---|---|
| Import existing CrossDesk machine (qcow2/raw/OVF) | Adds OVF parsing, libvirt domain XML import, conflict resolution. | **No** — not even as disabled tile (per user directive 2026-05-07). Add when ready. |
| Manual-mode toggle in express path | Express → manual switch adds complexity for a minority case. | Manual mode is reachable via "From ISO" path; no separate toggle in MVP. |
| GPU passthrough toggle in wizard | Per DEC-0009, GPU passthrough = Phase 4.5. | Available in Machine Settings post-install, not in wizard. |
| Windows Home guests | Per DEC-0015, Home lacks the RDP server CrossDesk requires. | ISO-supplied Home triggers a blocking redirect-to-Pro modal. Never installed. |
| macOS guest | Out of CrossDesk scope. | Not present. |
| Free Linux distro tiles (Ubuntu/Fedora/Debian/Kali) | Host is Linux; redundant. | Not present. Users can use "From ISO" with their own image. |
| Microsoft account creation in OOBE | Skipped via `unattended.xml`. Local account `crossdesk` only. | Never shown. |

---

## 7. Open questions / cross-cutting

All originally-open questions were resolved on 2026-05-07 and
2026-05-08; resolutions are folded into the relevant sections above
and into DEC-0010 through DEC-0015. This section retains the
resolutions for traceability.

### 7.1 Windows Home guests — **rejected** *(resolved 2026-05-08)*

Resolved by **DEC-0015**. Home does not ship an RDP server, so a
Home guest cannot serve RAIL. The wizard blocks Home with a
redirect-to-Pro modal; no override path. Implementation lives in §3
Screen 2 "From ISO — edition validation".

### 7.2 Notification persistence — accepted as-is *(resolved)*

Linux notification persistence varies by distro and notification
daemon. DEC-0013 accepts this inherent variability: the notification
is best-effort; the modal and the desktop file copy are the
load-bearing surfaces. A persistent in-app banner in the main window
pointing the user at their password is **deferred** post-MVP —
revisit if first users report difficulty finding the password.

---

## 8. Acceptance criteria (Phase 4 MVP)

A user with a fresh Linux install and a working CrossDesk package can:

- [ ] Launch CrossDesk; see Screen 1 within 2 s of click.
- [ ] Reach Screen 4 (install in progress) in ≤ 4 clicks from Screen 1
      using express path (Continue → Tile → Install).
- [ ] See a real "Step N of 7" indicator with sublabel changing at
      least once per step throughout the install.
- [ ] Reach Screen 5 in ≤ 35 minutes on reference hardware (TBD spec)
      with a 1 Gbps network.
- [ ] Receive both a modal and a native notification with the Windows
      password location.
- [ ] Optionally install a `.exe` from Screen 5 and see it appear as a
      RAIL app in the host taskbar.
- [ ] Cancel mid-install (Screen 4 cancel) and on next launch, see no
      orphan domain or qcow2 (automatic cleanup verified).
- [ ] Quit before clicking any tile on Screen 2; on next launch, see
      Screen 1 again (no half-state).

---

## 9. Implementation sequencing

Sequencing is governed by `docs/EXECUTION_PLAN.md` (Phase 4 weeks).
This plan does not duplicate that schedule; it provides the design
contract that Phase 4 implementation work refers to.

Suggested work breakdown (mapped to feature branches `feat/wizard-*`):

1. `feat/wizard-shell` — Qt6/QML shell, navigation, Screen 1, Screen
   2 (no install logic yet).
2. `feat/wizard-config` — Screen 3 with all defaults, validation,
   summary footer.
3. `feat/wizard-orphan-cleanup` — §4.1 standalone (testable without
   full install pipeline).
4. `feat/wizard-iso-download` — §4.2 with cache, checksum, Microsoft
   URL resolver.
5. `feat/wizard-unattended` — §4.3 template + libvirt domain
   provisioning.
6. `feat/wizard-progress` — Screen 4 with step indicator, ETA,
   sublabel feed.
7. `feat/wizard-password-surfacing` — §4.4 modal + notification +
   desktop fallback.
8. `feat/wizard-first-app` — Screen 5 with .exe path and Microsoft
   Store launch.
9. `feat/wizard-acceptance` — end-to-end test fixtures meeting §8.

Items 3, 4, 5 are independent and can run in parallel after item 1.
Item 7 depends on 5 (it triggers from the install pipeline). Item 6
depends on 5. Item 8 depends on 6.

---

## 10. Living document

Update this plan when:
- A proposed DEC in §5 is accepted, rejected, or modified
  (cross-link to the accepted DEC ID).
- A deferred item from §6 enters scope.
- An open question in §7 is resolved.
- Acceptance criteria in §8 evolve as Phase 4 progresses.

Roll forward with each Phase 4 commit that touches the wizard.
