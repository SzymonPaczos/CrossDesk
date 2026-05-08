# Design decisions

Architectural decisions with rationale, alternatives considered, and a
note on when to reconsider. Add new entries at the top. Mark superseded
decisions with **Superseded by:** linking to the newer entry; do not
delete history.

---

## DEC-0015: Windows Home is not a supported guest edition

**Status:** Accepted — 2026-05-08
**Owner:** install wizard / Phase 4
**Related:** `docs/INSTALL_WIZARD_PLAN.md` §3 Screen 2; DEC-0010
(Pro fixed in express install)

### Context

Windows 11 Home does not include the RDP **server** — only the RDP
client. CrossDesk's architecture connects from the Linux host to the
guest's RDP server to deliver RAIL apps. A Home guest installs
successfully but cannot serve any RAIL app: Screen 5 of the wizard
and every subsequent app launch would fail.

Third-party workarounds exist (RDP Wrapper most notably) but:
- are unsupported by Microsoft;
- regularly break across Windows cumulative updates;
- trigger malware-detection false positives in the guest;
- tie our reliability to a third-party project we do not control.

When a user supplies a Windows Home ISO via "From ISO", three
options exist: (a) silently install Home and let the user discover
the broken state, (b) warn but permit override, or (c) refuse the
edition and redirect to Pro.

### Decision

**Windows Home is rejected as a guest edition. No override path.**

When ISO detection identifies a Home-class edition, the wizard shows
a blocking modal before Screen 3:

- Heading: *"Windows 11 Home is not compatible with CrossDesk"*
- Body: *"Home does not include the Remote Desktop server, which
  CrossDesk uses to display Windows applications as Linux windows.
  Pro, Enterprise, and Education editions are supported."*
- Two buttons:
  - **Download Windows 11 Pro from Microsoft** (primary, switches
    to express path → Screen 2a EULA → Screen 3 with Pro fixed)
  - **Cancel** (returns to Screen 2)

There is **no "install Home anyway"** option.

**Edition matrix:**

| Edition | Detected as | Wizard behaviour |
|---|---|---|
| Home | Home-class | Blocked. Modal redirects to Pro. |
| Home N | Home-class | Blocked. |
| Home Single Language | Home-class | Blocked. |
| Home in S Mode | Home-class | Blocked. |
| Pro | Pro-class | Accepted. |
| Pro for Workstations | Pro-class | Accepted. |
| Enterprise | Enterprise-class | Accepted. |
| Enterprise LTSC | Enterprise-class | Accepted. |
| Education | Education-class | Accepted. |

The express path (DEC-0010) is unaffected — it pulls Pro from
Microsoft regardless of any Home consideration.

### Alternatives considered

- **Allow override with warning.** Rejected: a predictably broken
  state that the user clicks past once and then carries forward as a
  support burden. The support load of "I clicked past the warning,
  now nothing works" outweighs the autonomy of allowing the click.
- **Implement RDP Wrapper integration.** Rejected per the third-
  party caveats above. Not appropriate for a project that promises
  reliable behaviour.
- **Silently substitute Pro when Home detected.** Rejected: the user
  picked their ISO deliberately; substituting without consent is
  overreach. The blocking modal is the consent surface.
- **Allow Home for non-RAIL use cases.** Out of scope for MVP.
  CrossDesk is a RAIL product; non-RAIL guests would be a separate
  guest-mode workstream and can revisit Home at that time.

### When to reconsider

- Microsoft adds the RDP server to Home edition (extremely unlikely;
  this is a Pro/Enterprise differentiator established for a decade).
- A vendor-supported, licence-clean RDP-server alternative becomes
  available for Home.
- A non-RAIL guest mode enters scope and Home becomes meaningful in
  that mode. At that point this DEC splits per guest-mode.

---

## DEC-0014: Microsoft Windows EULA shown in-wizard before ISO download

**Status:** Accepted — 2026-05-07
**Owner:** install wizard / Phase 4
**Related:** `docs/INSTALL_WIZARD_PLAN.md` §3 Screen 2/3, §4.2;
DEC-0012 (Microsoft as ISO source)

### Context

DEC-0012 fixed Microsoft as the source for Windows ISOs and relies on
public consumer download URLs. Two adjacent concerns remain:
1. **Legal posture.** CrossDesk programmatically retrieving Microsoft
   media and provisioning a Windows guest needs the user — not us —
   to be the party accepting Microsoft's licensing terms. Otherwise
   we operate as redistributor without licence.
2. **`unattended.xml`** skips the in-Windows EULA acceptance screen
   that Setup normally renders during first boot (`f_0190` in the
   Parallels reference). The EULA must be presented somewhere — if
   not by Setup, then by us.

Combining these: present Microsoft's Windows EULA in the wizard,
require explicit user acceptance, and only then trigger the ISO
download. The user is the party accepting; the unattended flow stays
unattended.

### Decision

1. **Express Windows path only.** When the user picks "Install
   Windows 11" on Screen 2, the wizard inserts an EULA step
   immediately after Screen 2 and before Screen 3 (Configuration).
2. **EULA content** is bundled with the CrossDesk release as a static
   text/RTF file shipped in the package, version-tagged against the
   Windows release we install (Windows 11 24H2 → bundle 24H2 EULA
   text). A `Read latest online` link points to Microsoft's current
   live URL.
3. **Acceptance UI:**
   - Heading: *"Microsoft Software Licence Terms — Windows 11"*.
   - Scrollable text area (full EULA).
   - Below the text: explicit checkbox *"I have read and agree to
     the Microsoft Software Licence Terms"*. **No pre-check.**
   - Footer buttons: **Decline** (returns to Screen 2),
     **Accept and continue** (advances to Screen 3, disabled until
     checkbox set).
4. **Audit trail:** acceptance is logged to
   `~/.local/state/crossdesk/eula-acceptance.log` with timestamp,
   user, EULA version, and the SHA256 of the bundled EULA text.
   This is local-only — it is **not** transmitted anywhere
   (DEC-0002).
5. **"From ISO" path is exempt.** Users who supply their own ISO
   already accepted Microsoft's terms when they obtained it; the
   wizard does not re-prompt.

### Alternatives considered

- **No EULA in wizard, rely on Setup's EULA screen.** Rejected:
  `unattended.xml` skips Setup's EULA, so it is never shown.
- **Show EULA on first launch of CrossDesk.** Rejected: a user who
  never installs Windows (e.g. CrossDesk for an existing imported
  guest, post-MVP) would still see Microsoft's EULA, which is
  irrelevant to them. Tying it to the express Windows path is
  cleaner.
- **Live EULA fetch from Microsoft.** Rejected for MVP: introduces a
  network dependency before any download starts, and the EULA URL
  changes with Microsoft's site. Bundled snapshot + "read latest
  online" link is more reliable.

### When to reconsider

- Microsoft changes its licensing model (e.g. requires online
  acceptance via a Microsoft account before download).
- Bundled EULA text drifts more than one Windows release behind the
  ISO version we actually pull.
- Legal review concludes that the bundled-snapshot approach is
  insufficient and live fetch is required.

---

## DEC-0013: Windows password storage, surfacing, and desktop copy

**Status:** Accepted — 2026-05-07
**Owner:** install pipeline / credential management
**Related:** `docs/INSTALL_WIZARD_PLAN.md` §4.4; **amends** DEC-0001
(Windows password lifecycle)

### Context

DEC-0001 fixed the storage location for the auto-generated Windows
password at `~/.config/crossdesk/vm.toml` mode `0600`. It did not
specify how the user is informed where the password is stored after a
successful install, nor what happens when the primary path is
unwritable.

The install wizard (`docs/INSTALL_WIZARD_PLAN.md` Screen 4 → Screen 5
transition) is the natural surfacing point. Beyond surfacing: the
config-dir location is hidden from non-technical users, and Linux
notifications are ephemeral. A discoverable copy of the password —
on the desktop of the user who created the guest — is worth the
modest extra exposure: the user already has read access to that
config file, and the desktop copy gives them an obvious place to look
weeks later when they've forgotten where it was.

### Decision

1. **Primary location** is unchanged from DEC-0001:
   `~/.config/crossdesk/vm.toml` mode `0600`. This is the
   authoritative copy that the auth health-check (DEC-0001 §5) and
   RAIL launcher read from.
2. **Desktop copy is always written**, not only as a fallback:
   `<xdg-DESKTOP-dir>/crossdesk-windows-password.txt` mode `0600`,
   on every fresh install. (Polish locale → `~/Pulpit/`, English →
   `~/Desktop/`, etc., resolved via `xdg-user-dirs`.) Header text:
   > *"This file is a copy of the password CrossDesk generated for
   > your Windows machine. The authoritative copy lives in
   > ~/.config/crossdesk/vm.toml. You can move or delete this file
   > once you've saved the password somewhere safe."*
3. **Surfacing on first install** uses **both** channels:
   - **Modal** at the Screen 4 → Screen 5 transition showing the
     password once (with a copy-to-clipboard button) plus the
     paths to *both* the config file and the desktop copy. Modal
     is non-dismissable until acknowledged.
   - **Native Linux notification** in parallel:
     *"Windows password saved to <desktop-path>"*. Notifications are
     ephemeral and distro-dependent — the modal is the load-bearing
     channel.
4. **Fallback when desktop is unresolvable** (no `xdg-user-dirs`,
   read-only home): skip the desktop copy and surface the
   config-file path in both modal and notification with a warning
   noting the desktop copy was not written.
5. **Password mutation events** (re-install, manual rotation post-
   MVP) refresh `vm.toml` immediately. The desktop copy is **not**
   automatically refreshed — it is written once at install and left
   for the user to manage. We do not own files on the user's desktop
   after creation.

### Alternatives considered

- **Desktop copy only as fallback.** Original framing of this
  decision earlier in the same conversation. Rejected in favour of
  always-write because the discovery problem (config dir is hidden,
  notifications are ephemeral) exists regardless of whether the
  primary path succeeded.
- **OS keyring (Secret Service / KWallet / GNOME Keyring).** Rejected
  for MVP: cross-distro packaging and behaviour differences outweigh
  the benefit at this stage. Revisit when keyring access is worth a
  separate workstream.
- **Notification only, no modal.** Rejected: notifications are
  ephemeral and distro-dependent.
- **Modal only, no desktop copy.** Rejected: a modal acknowledged and
  forgotten leaves the user hunting in `~/.config/` weeks later.

### Supersedes / amends

Amends **DEC-0001** §2 by extending its storage clause with a desktop
copy on every install plus a user-surfacing protocol. DEC-0001 §1
(account name), §3 (gpedit lockdown), §4 (no expiration), and §5
(auth health-check) are unchanged. The auth health-check continues to
read from `vm.toml`, never from the desktop copy.

### Security trade-off

The desktop copy increases blast radius slightly: anyone with brief
shoulder-surf access to the user's machine can read it. The mitigation
is the explicit header inviting the user to delete or relocate the
file. We judge the discoverability benefit (users know where the
password is) outweighs the marginal exposure (someone with desktop
access already has access to the config dir too — both at mode 0600
under the same `$HOME`).

### When to reconsider

- A real OS keyring integration becomes worth the cross-distro
  packaging cost.
- User research shows desktop clutter from this file is friction.
- Security review escalates the desktop-copy exposure ahead of the
  discoverability benefit.

---

## DEC-0012: Windows ISO sourced from Microsoft, no CrossDesk CDN

**Status:** Accepted — 2026-05-07
**Owner:** install pipeline
**Related:** `docs/INSTALL_WIZARD_PLAN.md` §4.2; DEC-0002 (zero
telemetry, zero phone-home)

### Context

The install wizard needs a Windows ISO to provision a guest. Two
options:
1. Pull directly from Microsoft's public consumer download URLs each
   install (with local cache).
2. Operate a CrossDesk-hosted CDN that mirrors Microsoft's ISOs.

Option 2 buys faster downloads (potentially) and reliability against
Microsoft URL churn, at the cost of operating infrastructure, paying
egress, taking on legal exposure for redistributing Microsoft media,
and introducing a CrossDesk-hosted dependency that conflicts with
DEC-0002's "no phone-home" posture.

### Decision

**Always pull from Microsoft directly.** No CrossDesk CDN.

- Local cache at `~/.cache/crossdesk/iso/`, keyed by
  `windows-{version}-{arch}-{lang}.iso`. Reused on subsequent
  installs without re-download.
- SHA256 verified against Microsoft's published hash before mounting.
- Microsoft's URLs are signed and short-lived (~24 h); the
  implementation re-resolves the URL on each download attempt and
  does not persist signed URLs.
- If URL discovery fails, the wizard falls back to a clear error
  pointing the user at the "From ISO" path with a link to
  Microsoft's official download page.

### Alternatives considered

- **CrossDesk CDN.** Rejected per above (cost, legal, trust, conflicts
  with DEC-0002).
- **BitTorrent / P2P delivery.** Rejected: introduces an external
  dependency the user did not consent to, and Microsoft's hashes are
  the trust anchor regardless of transport.

### When to reconsider

- Microsoft's public download path becomes locked behind sign-in (it
  is not today for consumer Windows 11 ISOs).
- User research shows non-trivial download failure rates from
  Microsoft's CDN that a co-located CrossDesk mirror would solve.
- Legal review concludes that a signed mirror under licence is
  feasible and cheaper than direct downloads at scale.

---

## DEC-0011: Orphan cleanup is automatic, not prompted

**Status:** Accepted — 2026-05-07
**Owner:** install pipeline / GUI startup
**Related:** `docs/INSTALL_WIZARD_PLAN.md` §4.1; DEC-0002 (no
telemetry — no signal to detect repeat-offender bugs)

### Context

When a CrossDesk install is interrupted (user cancels mid-install,
process killed, host reboots, etc.), it can leave behind: a libvirt
domain in `shut off` state with our `crossdesk-*` prefix, and / or
an orphan qcow2 file in `~/.local/share/crossdesk/disks/`. These
artefacts must be cleaned up before the next install attempt, both
to free resources and to prevent name collisions.

The question is whether to clean them silently or prompt the user.

### Decision

**Automatic cleanup at GUI cold start, before the wizard renders.**

1. List libvirt domains matching `crossdesk-*` prefix.
2. Cross-reference against the state-store
   (`~/.config/crossdesk/state.toml` or equivalent).
3. **Orphan domain** = domain with our prefix, not in state-store, in
   `shut off` state, with `install-incomplete: true` metadata
   (written at the start of every install, cleared on success).
4. **Orphan disk** = qcow2 in our managed disks directory with no
   corresponding domain.
5. **Action:** `virsh undefine` the domain, delete the qcow2, log to
   `~/.local/state/crossdesk/cleanup.log`. **No user prompt.**
6. **Repeat-offender mitigation:** if the same orphan name reappears
   more than 3 times in a rolling week, surface a non-blocking
   notification: *"CrossDesk repeatedly cleaned up failed installs;
   consider reporting an issue."* This catches silent bugs without
   per-install prompt fatigue.

### Alternatives considered

- **Prompt user every time.** Rejected: a user who abandoned an
  install is not in a state to make an informed cleanup choice; the
  prompt is friction without benefit. Real (non-orphan) VMs are
  identifiable via state-store membership and are never touched.
- **Prompt on first orphan, then remember preference.** Rejected: the
  added complexity (preference UI, clearing it, etc.) is not worth it
  vs the simple repeat-offender heuristic.
- **Lazy cleanup (delete only when the next install would collide).**
  Rejected: leaves disk space tied up indefinitely, and surfaces the
  failure later when it's harder to diagnose.

### When to reconsider

- The metadata tag (`install-incomplete: true`) proves unreliable
  (e.g. concurrent crashes leave it set on a domain that is actually
  in use).
- User research shows the silent-deletion behaviour surprises users
  in a problematic way.

---

## DEC-0010: Express install fixes Windows edition to Pro

**Status:** Accepted — 2026-05-07
**Owner:** install wizard / Phase 4
**Related:** `docs/INSTALL_WIZARD_PLAN.md` §3 Screen 3 and §5

### Context

The install wizard could expose a Windows-edition picker (Home / Pro
/ Enterprise) on the configuration screen, or it could fix a default.
Windows in-place edition switching supports **upgrades** (Home → Pro
→ Enterprise via `changepk.exe` / `DISM /Online /Set-Edition:...`)
but **does not** support downgrades — Pro → Home requires a clean
reinstall.

This asymmetry makes the default choice load-bearing: pick too high
and the user is stuck if they wanted Home for cost reasons; pick too
low and the user has to act later to upgrade.

### Decision

1. **Express mode fixes Pro.** No edition picker. Pro is the safest
   default given the upgrade-only constraint: any user wanting
   Enterprise can upgrade later without reinstall; almost no users
   want to downgrade to Home.
2. **Manual mode** (entered when "From ISO" detects a non-Pro Windows
   edition) shows only the editions present on the supplied ISO and
   installs as detected.
3. **Post-install edition switch** is exposed in Machine Settings as
   *"Change Windows edition"*. The action invokes `changepk.exe` /
   `DISM` in the guest, supports upgrades only, and surfaces a clear
   warning if the user requests a downgrade ("Downgrading requires
   reinstalling Windows. Continue?").
4. The wizard does **not** ask for a Windows licence key. Activation
   is left to Machine Settings post-install. Express install
   produces an unactivated Pro guest the user can activate with their
   own licence at their convenience.

### Alternatives considered

- **Picker in express mode.** Rejected: every user pays the
  decision-making cost for a choice that fewer than ~10% are
  expected to want to deviate from. Manual mode and Machine
  Settings cover the deviation cases.
- **Default to Home.** Rejected: Home → Pro upgrade requires a new
  product key + `changepk.exe`, but Pro → Home requires reinstall.
  Defaulting to Home creates more dead-end paths.
- **Default to Enterprise.** Rejected: Enterprise activation requires
  volume licensing; not appropriate for individual users.

### When to reconsider

- Microsoft changes the in-place edition-switch mechanics (e.g.
  enables Pro → Home in-place).
- User research shows >10% of users actually want Home (cost-driven
  segment).
- Enterprise becomes the more common default for our target
  audience.

---

## DEC-0009: GPU passthrough scope, tiers, and timing

**Status:** Accepted — 2026-05-07
**Owner:** Phase 4.5 / post-MVP P0
**Related:** `docs/GPU_PASSTHROUGH.md` (full deliberation);
`FOLLOWUPS.md` "GPU passthrough — Phase 4.5"; `ROADMAP.md` Phase 4.5;
`docs/THREAT_MODEL.md` §C4 (extended on implementation)

### Context

Photoshop, Premiere, AutoCAD, Blender, and Fusion 360 are unusable
on a software-rendered VM (filters take seconds, video timelines
crash). Without GPU passthrough, "real Windows apps on Linux"
ships short of its promise for power-user workloads.

GPU passthrough is mature on Linux (vfio-pci, IOMMU, libvirt
hostdev) but materially extends scope and is fundamentally
multi-GPU-only on the RAIL-as-native-windows model we ship.

### Decision

1. **Timing**: GPU passthrough lands as **Phase 4.5 / post-MVP P0**,
   not in Phase 4 base. MVP demo ships with software rendering;
   GPU is the immediate first follow-up.
2. **Tier 1 commitment** (full support, CI smoke-tests when
   hardware available): NVIDIA RTX 20/30/40-series with driver
   465+, AMD RDNA2 (RX 6000) and RDNA3 (RX 7000), multi-GPU only.
3. **Tier 2 documented, not maintained**: AMD Polaris/Vega/RDNA1
   with `vendor-reset` upstream module; NVIDIA pre-2021 with
   hide-the-VM tricks. Docs link to upstream; user installs and
   maintains workarounds themselves.
4. **Tier 3 explicitly out**: Intel Arc (wait for usage data),
   single-GPU systems (architecturally incompatible — see DEC-0009
   §"Single-GPU constraint" via `docs/GPU_PASSTHROUGH.md`).
5. **Looking Glass integration** is a separate subsequent
   follow-up (post-Phase 4.5), tracked independently. LG unlocks
   single-GPU usability via compositor-restart hot-switch and
   adds a Desktop-mode alternative for users wanting lower
   latency than RDP encode/decode.
6. **Software-rendering fallback** is documented as the universal
   path that always works for productivity apps (Word, Outlook,
   Visual Studio); not viable for GPU-intensive apps.
7. **TA7 (malicious GPU firmware)** added to threat model when
   implementation lands.

### Alternatives considered

- **Phase 4 in-scope (GPU is part of MVP)**: would add ~3-4 weeks
  before MVP demo ships; combined with Tier 2 follow-up risks 6+
  week slipage for solo developer; rejected in favor of
  v0.1 + v0.2 release cadence.
- **Tier 2 actively maintained (AMD vendor-reset shipped by us)**:
  too much per-release maintenance burden for a solo developer;
  rejected in favor of "documented, link to upstream."
- **Intel Arc Tier 1**: insufficient usage data; treat as Tier 3
  until first user reports.
- **No GPU passthrough at all (software-rendered only)**: kills
  the project's positioning for power-user workloads; rejected.

### Consequences

- (+) MVP ships faster (no GPU dependency on Phase 4 timeline).
- (+) v0.1 demo (architecture works) and v0.2 demo (GPU
  acceleration) give two press moments; second is informed by
  first.
- (+) Solo-developer scope-creep risk minimized.
- (+) Power-user workloads explicitly addressed in v0.2.
- (−) MVP demo is "Notepad as native window" — technically
  interesting but less impressive than "Photoshop on Linux".
- (−) Single-GPU users get "unsupported for GPU mode" until
  Looking Glass integration lands; software-rendering fallback
  is documented but limited.
- (−) Tier 2 docs without active maintenance puts AMD older /
  NVIDIA older users on community ground for workaround
  reliability.

### Reconsider when

- Most user reports come from Tier 2 or Tier 3 hardware (e.g.,
  many users on RX 580 or Intel Arc) — may justify lifting them
  to Tier 1.
- A single-GPU user demonstrates Looking Glass + hot-switch UX
  cleanly enough that we can offer it as Tier 1 instead of
  Tier 2 (requires LG integration to land first).
- AMD's reset-bug `vendor-reset` module gets upstreamed into the
  Linux kernel — at which point Tier 2 AMD older becomes
  effectively Tier 1.
- A user reports they were locked out by an MVP without GPU
  passthrough and cancelled adoption — reconsider Phase 4
  in-scope decision.

---

## DEC-0008: Distribution via deb/rpm/AUR/NixOS/PyPI; no Flatpak/AppImage/Snap

**Status:** Accepted — 2026-05-07
**Owner:** release tooling, packaging
**Related:** `docs/PACKAGING.md`; `docs/DECISIONS.md` DEC-0003 (no
Docker)

### Context

Users install CrossDesk via their distro's mechanism. WinApps ships
`bash <(curl ...)`, NixOS flake, and AUR. That's adequate for their
audience but leaves out users who want `apt install` or `dnf
install` from their distro's package manager — exactly the
trust-by-default audience CrossDesk targets.

Format choice also affects security posture (sandboxed Flatpak vs
distro package), update story, and per-distro maintenance burden.

### Decision

CrossDesk ships in five formats:

1. **`deb`** for Debian-family (Debian, Ubuntu, Mint, Pop_OS).
2. **`rpm`** for RPM-family (Fedora, RHEL, openSUSE).
3. **AUR PKGBUILD** for Arch.
4. **NixOS flake** for NixOS users.
5. **PyPI** wheel for the host module (developers, headless).

Skipped formats and reasons:

- **Flatpak**: sandbox model conflicts with our requirements
  (libvirt session, D-Bus, direct compositor, multi-GB VM disk).
  Punching the holes erases the sandbox.
- **AppImage**: no value over deb/rpm; harder updates.
- **Snap**: same sandbox issue as Flatpak.
- **Docker / OCI**: contradicts DEC-0003 (no Docker).

### Alternatives considered

- **PyPI-only.** Easiest to release, but expects users to manage a
  Python environment, doesn't integrate with distro update story.
  Rejected as primary; kept as supplementary.
- **bash curl-pipe-installer (WinApps style).** Trust model is
  bad; users running unknown install scripts as their user is
  exactly the threat we want to remove. Rejected.
- **Flatpak with permissive `--filesystem=host`.** Erases the
  sandbox without simplifying anything. Rejected.

### Consequences

- (+) Native distro integration — `apt`/`dnf`/`pacman`/`nix run`.
- (+) Native update story per distro.
- (+) Trust-by-default audience served on their preferred format.
- (−) Five build paths to maintain. CI complexity.
- (−) Per-distro repos to host (Copr, PPA, OBS, AUR).
- (−) GPG/Sigstore signing per format adds setup work.

### Reconsider when

- Flatpak gains a way to expose libvirt session to a sandboxed
  app without erasing the sandbox. Then revisit Flatpak.
- A new universal Linux packaging format gains traction with our
  audience. Today's market is deb/rpm/AUR/Nix; that may shift.

---

## DEC-0007: Semver everywhere with N-1 minor compatibility window

**Status:** Accepted — 2026-05-07
**Owner:** proto schema, host package, guest agent
**Related:** `docs/VERSIONING.md`; `proto/crossdesk/v1/*.proto`;
`FOLLOWUPS.md` `crossdesk upgrade` item

### Context

WinApps does not version anything. Re-running their `setup.sh`
overwrites the install; there's no upgrade story. CrossDesk's
`crossdesk upgrade` command (in FOLLOWUPS) only works if we can
answer "is this host compatible with that agent" deterministically.

Without a versioning policy, every upgrade is a wipe-and-reinstall
which destroys the user's Windows configuration (apps installed,
settings, files). Unacceptable for a project that expects users to
spend days configuring their VM.

### Decision

Three things are versioned with semver: the proto schema (per
`proto/crossdesk/vN/`), the host package, and the guest agent. Each
has its own version. They coordinate via a `Hello` handshake on
first connect, exchanging `protocol_version`, `host_version`,
`agent_version`, and a `capabilities` string.

The host follows an **N-1 minor compatibility rule**: it accepts
agents at its minor version or one minor below, within the same
major. Major mismatches refuse with a clear message recommending
full reinstall.

Field numbers in proto schemas are reserved before use (we already
do this — commit `b43bb16`); reserved numbers cannot be reused. New
features ship as either MINOR additions (backwards-compatible) or
capability flags (opt-in within a version).

The CLI is stable in v1.x: argument order, flag names, exit codes
held constant; breaking changes go in v2 with a deprecation period.

### Alternatives considered

- **No versioning policy** (WinApps approach). Every upgrade is a
  wipe; users lose config. Rejected.
- **N-2 minor compatibility** (more permissive). Adds maintenance
  burden of supporting older agent versions for longer. Rejected
  for now; reconsider if release cadence warrants.
- **Strict same-version-only.** Forces agents to upgrade
  lockstep with hosts; bad UX for users who upgrade host but
  haven't restarted VM. Rejected.

### Consequences

- (+) `crossdesk upgrade` becomes safe — users can upgrade hosts
  without losing in-VM work.
- (+) Mismatches produce clear, actionable error messages.
- (+) Capability flags allow experimental features without proto
  bumps.
- (−) Adds a Hello handshake to every connection (microseconds, but
  measurable).
- (−) Maintaining N-1 compatibility requires testing two versions
  of the agent against current host on every release.

### Reconsider when

- A class of bugs slips through because tests don't cover the N-1
  matrix sufficiently. Solution: add a CI matrix testing host vs
  N-1 agent.
- We hit a case requiring MAJOR proto bump that's controversial
  (e.g., transport replacement). The decision-record gets a new
  ADR superseding this one only on the specific aspect that
  changes.

---

## DEC-0006: Structured logging and trace propagation from day one

**Status:** Accepted — 2026-05-07
**Owner:** every component that logs
**Related:** `docs/OBSERVABILITY.md`; `docs/DECISIONS.md` DEC-0002
(zero telemetry); `docs/REQUIREMENTS.md` N5

### Context

Every audit and bug report starts with logs. If logs are
unstructured text, support time scales linearly with log volume.
If logs are JSON with a propagated trace ID, support time is
constant: filter to the trace, read the events.

Retrofitting structured logging into a project is a refactor of
every print statement and a re-think of every error path. Doing
it from day one costs a few hours of setup and a discipline of
"don't add `print()`."

### Decision

From day one of CrossDesk implementation:

1. **Python** uses `structlog` configured to emit JSON Lines with
   mandatory fields (`timestamp`, `level`, `component`, `trace_id`,
   `span_id`, `event`).
2. **Rust** uses the `tracing` crate with `tracing-subscriber` JSON
   formatter and `tracing-opentelemetry` for trace export.
3. **Trace IDs** propagate via gRPC metadata using W3C Trace
   Context. Every CLI command starts a root trace. Every gRPC call
   (host↔guest) carries the trace.
4. **Allow-list redaction** for any field with `password`, `secret`,
   `token`, etc. in its name. Tests fail if a non-allowed field is
   logged.
5. **No `print()`** in merged code. Linter catches it (Ruff
   `T201`).
6. **Logs land on local disk only.** Optional OTLP exporter is
   opt-in (per DEC-0002).

### Alternatives considered

- **Unstructured `logging.info(...)`.** Free initially, expensive
  forever. Rejected.
- **Wait until we have integration testing pain, then refactor.**
  Always slips later than expected. Rejected.
- **Sentry / external crash reporting.** Conflicts with
  DEC-0002. Rejected.

### Consequences

- (+) Bug reports become tractable: ask user for
  `crossdesk logs --trace-id ABC...`.
- (+) Trace propagation means a single ID covers a user action
  end-to-end, including across the host↔guest boundary.
- (+) Redaction allow-list catches accidental secret logging at
  test time.
- (−) Every log statement requires choosing a structured event
  name and field set. Slightly more code than `print()`.
- (−) `tracing` and `structlog` are dependencies that must be
  configured early; getting it wrong (e.g., wrong JSON shape
  initially) is a small but real refactor cost.

### Reconsider when

- A new logging library appears with materially better ergonomics
  *and* the same structured-output discipline. Migration cost
  weighed against benefit.
- A user-visible regression is traced to logging overhead (very
  unlikely; structlog/tracing are fast).

---

## DEC-0005: Mock-driven testing as architectural foundation

**Status:** Accepted — 2026-05-07
**Owner:** all components touching Linux-or-Windows-only APIs
**Related:** `docs/CROSS_PLATFORM_DEV.md`; `AGENTS.md` "no polling" rule

### Context

CrossDesk's runtime depends on AF_VSOCK, libvirt, FreeRDP RAIL,
D-Bus, and Windows-only `windows-rs`. None of these run on macOS.
Periods of development without Linux+KVM hardware (e.g., a month on
Mac) become unproductive without a mock layer.

Even with hardware, integration-only testing makes CI slow, flaky,
and dependent on hardware-class runners.

### Decision

Every component touching a Linux-or-Windows-only API is reached
through a trait (Rust) or Protocol (Python). We ship two
implementations per trait: the real one and a mock one with
matching invariants and failure-injection hooks.

Specifically:

1. Transport (`AF_VSOCK`), libvirt client, FreeRDP invocation,
   guest agent (from host's POV), filesystem hot-plug, D-Bus
   signals, and Windows registry all sit behind a trait/Protocol.
2. Mocks enforce the same validation rules as real implementations
   (e.g., AuthContext rejection, `mount_token` length).
3. Mocks expose hooks for failure injection (drop-mid-stream,
   timeout, malformed-response).
4. CI runs unit tests on macOS and Ubuntu; in-process integration
   tests on Ubuntu; real-libvirt smoke tests gated behind a label
   on a self-hosted Linux+KVM runner (when one exists).
5. Production code never imports a mock module.

### Alternatives considered

- **Integration-only testing on a Linux runner.** Slow CI, hardware-
  bound, untestable on macOS. Rejected.
- **No mocks; "test on Linux when you have hardware."** Wastes
  development time during periods without hardware. Rejected.
- **Mocks but only at the gRPC layer.** Doesn't help components
  below gRPC (libvirt, FreeRDP); leaves gaps. Rejected for
  "every Linux-only API" instead.

### Consequences

- (+) Any developer can build, type-check, and run unit tests on
  macOS or Windows.
- (+) CI is fast; integration tests are deterministic on mocks.
- (+) Failure injection enables testing of error paths real
  implementations rarely surface.
- (−) Two implementations per component to maintain. Drift risk
  managed by reviewer discipline + module docstring noting what's
  mocked.
- (−) Real libvirt / real Windows behavior still requires hardware
  smoke tests. Mocks don't catch everything.

### Reconsider when

- A class of bugs repeatedly slips past mocks and is caught only by
  hardware smoke tests. May indicate the mock is too lenient and
  needs to enforce additional invariants (cheaper) or that the
  abstraction is at the wrong layer (more expensive: refactor).
- Hardware testing becomes cheap enough (e.g., GitHub Actions ships
  KVM-capable runners by default) that the cost-benefit shifts.

---

## DEC-0004: Performance budgets are normative

**Status:** Accepted — 2026-05-07
**Owner:** all phases
**Related:** `docs/REQUIREMENTS.md` N1; `ROADMAP.md` SPOFs

### Context

CrossDesk's UX depends on tight latencies — especially heartbeat
round-trip (gates the recovery FSM) and cold app launch (gates "feels
like a native app"). Without published budgets, "fast enough" drifts
release by release until users feel the regression and we can't say
when it happened.

### Decision

The budgets in `docs/REQUIREMENTS.md` §N1 are normative — a regression
beyond budget by more than 20% on any metric is a release blocker,
not a "nice to fix later." CI must include a microbenchmark suite
that exercises the heartbeat round-trip and the cold-launch path.

The budgets are realistic, not aspirational: they are grounded in
measured baselines from comparable setups (Windows-in-libvirt RAIL
deployments) and in physical constraints (Windows idle footprint,
FreeRDP RAIL session setup latency, virtio-balloon behavior). They
also differentiate by workload — a Notepad cold launch and a
Photoshop cold launch are scored on different scales. See N1.1a /
N1.1b / N1.1c.

Initial budget table was set aggressively (e.g., heartbeat <100 ms
p50, host RAM <100 MB) and was reset on 2026-05-07 after grounding
against measurements. The reset was a refinement of the same
decision, not a new one.

### Alternatives considered

- **No published budgets, "fix it when users complain"** — guarantees
  drift, makes regression bisects costly.
- **SLO with monthly review meetings** — overkill for a pre-MVP
  project; revisit if we reach ops scale.

### Consequences

- (+) Regressions caught at PR time, not after release.
- (+) Reviewers have a concrete number to push back with.
- (−) Adds a benchmark layer to maintain.
- (−) Some optimizations gated on having the harness running.

### Reconsider when

- Multiple users ask for a feature whose implementation can't fit the
  current budget; we may need to negotiate a budget revision rather
  than skip the feature.

---

## DEC-0003: No Docker, no privileged daemon, no `qemu:///system`

**Status:** Accepted — 2026-05-07
**Owner:** install pipeline, transport, security
**Related:** `docs/THREAT_MODEL.md` §C4; `docs/GOALS.md` NG6;
`docs/COMPARISON_WINAPPS.md`; `FOLLOWUPS.md` "Skipped on purpose"

### Context

WinApps's primary onboarding path is `docker compose up` against a
`dockur/windows` privileged container. The path is fast for casual
users but adds a privileged daemon, exposes RDP on a TCP port,
requires `NET_ADMIN` and `/dev/kvm` capabilities, and ties the project
to a third-party container image as the actual hypervisor.

CrossDesk's positioning (security-first, single-user, type-checked
async) is incompatible with that posture.

### Decision

CrossDesk runs against `qemu:///session` libvirt, as the user, with
no daemon root. Docker / Podman / `dockur/windows` are out of scope
permanently — not "later when we have time." `qemu:///system` is
also rejected because it requires root and a session-bus daemon,
removing the direct `$WAYLAND_DISPLAY` access we rely on.

This is also captured as a top-level constraint in `AGENTS.md`
"Coding rules".

### Alternatives considered

- **Optional Docker backend** — would require maintaining two threat
  models, two installation paths, two transport layers. Permanent
  fork in our codebase.
- **`qemu:///system` for shared multi-user mode** — multi-user is a
  non-goal (`docs/GOALS.md` NG4); this is unwarranted complexity.

### Consequences

- (+) No daemon root in our threat model.
- (+) Direct compositor access without bind-mounting sockets into a
  container.
- (+) AF_VSOCK works without translation through container
  networking.
- (+) JIT VirtioFS can hot-plug devices via libvirt without
  intermediating layers.
- (−) Onboarding takes longer than `docker compose up`. Mitigated by
  `crossdesk install` one-command bootstrap with auto-ISO download.
- (−) Users who already use Docker for everything can't reuse their
  setup.

### Reconsider when

- A future supported deployment (e.g., remote-mount NixOS with
  rootless privileged containers) makes the privilege story comparable
  to `qemu:///session`. Even then, only as a *secondary* path; the
  primary path stays libvirt-direct.

---

## DEC-0002: Zero telemetry, zero phone-home

**Status:** Accepted — 2026-05-07
**Owner:** host process; install pipeline; CLI
**Related:** `docs/REQUIREMENTS.md` N2.6; `docs/THREAT_MODEL.md`;
`docs/GOALS.md`

### Context

CrossDesk's positioning is security-first. Many comparable projects
ship optional telemetry, "anonymous usage analytics," or "crash
reporting that helps us improve." Each one is a network connection we
make on the user's behalf, an attack surface to defend, and a privacy
obligation.

For CrossDesk's audience — users who picked us specifically because
of the security model — even opt-in telemetry erodes trust.

### Decision

CrossDesk performs no automated outbound network connections beyond
those the user explicitly initiates:

1. ISO download from Microsoft (user opted in by running
   `crossdesk install` without `--iso-path`).
2. Windows Update inside the VM (the user's Windows VM, the user's
   choice).
3. Optional `crossdesk upgrade` when the user runs it.

There is no usage analytics endpoint, no crash report uploader, no
"check for updates on startup," no version ping, no DNS prefetch.

Logs stay local. `crossdesk logs` aggregates from the local
filesystem. If a user wants to share logs for support, they paste
them — they are not transmitted automatically.

### Alternatives considered

- **Opt-in telemetry, default off** — even the *option* would
  introduce serializers, redaction logic, and an endpoint to defend.
  Cost outweighs benefit.
- **Crash reporting via Sentry/similar** — same objection. Local crash
  dumps are sufficient.
- **Update check on launch** — undermines our claim. Users can run
  `crossdesk upgrade` when they want.

### Consequences

- (+) Trust claim is straightforward to verify: `tcpdump` on a fresh
  install should be silent except for explicit user actions.
- (+) No telemetry endpoint to maintain or defend.
- (+) GDPR / data-handling story is "we don't have any."
- (−) Less data on what users do, what fails, what releases regress.
- (−) Bug reports require users to opt in by sharing logs manually.

### Reconsider when

- Never silently. If we ever consider telemetry, it requires:
  1. A new ADR superseding this one.
  2. Default-off, explicit opt-in.
  3. Public schema of every byte transmitted.
  4. User-runnable verification that disabling it actually disables
     it (`tcpdump`-friendly).

---

## DEC-0001: Windows password lifecycle — single account, gpedit-locked, health-check fallback

**Status:** Accepted — 2026-05-06
**Amended by:** DEC-0013 (fallback location and surfacing)
**Owner:** install pipeline / credential management
**Related:** `FOLLOWUPS.md` items "VM credential management" and
"Auth health-check before every RAIL launch"

### Context

CrossDesk creates a Windows VM with an auto-generated password stored
in `~/.config/crossdesk/vm.toml`. If the user changes the password
manually inside Windows (Settings → Account → Sign-in options) the
host's stored value goes stale and RDP/RAIL connections fail.

WinApps doesn't address this — they document it as a limitation and
require users to update the config file by hand.

### Decision

Adopt a layered defense:

1. **Single Windows account** named `crossdesk` (clearly system-ish,
   not "user" or "Administrator").
2. **Random password generated at install**, persisted in
   `~/.config/crossdesk/vm.toml` (mode 0600).
3. **Disable "Change Password" via gpedit** in
   `<FirstLogonCommands>`: User Configuration → Administrative
   Templates → System → Ctrl+Alt+Del Options → Remove Change Password.
4. **Disable password expiration** entirely — Windows never prompts
   for a forced rotation.
5. **Auth health-check before every RAIL launch.** Host RPCs the guest
   with current credentials; on FAIL, surface a clear message
   pointing at `crossdesk vm credentials repair`.
6. **`crossdesk vm credentials repair` recovery flow** — prompts for
   the current Windows password, verifies it, atomically updates the
   host file.

### Alternatives considered

- **Option A — dual accounts (`crossdesk` service + human user).**
  WSL2-style separation. Rejected because RAIL apps would run as the
  service account, breaking Office/Adobe per-user licensing,
  OneDrive, and document-folder mapping. The single-user
  use case (one Linux user, one Windows VM) doesn't justify the
  complexity.

- **Option D — subscribe to Windows Security Event Log (4723/4724).**
  Real-time detection of password changes via guest agent. Rejected:
  gain over health-check is small (users change passwords rarely),
  requires `SeSecurityPrivilege` in the agent, and even with
  detection we still need user-driven recovery (we never know the
  new password they typed).

- **Option E — passwordless / Windows Hello-based RDP.**
  Configure the account with no password, rely on AF_VSOCK + mTLS +
  per-frame `AuthContext` as the only auth boundary. Rejected for
  MVP: opens security categories we don't want to debug (Windows
  policy interactions, RDP NLA semantics with empty passwords),
  removes a defense-in-depth layer that catches misconfigurations.

### Consequences

- (+) User can't accidentally drift the credential silently — gpedit
  prevents the easy path; health-check catches the hard path.
- (+) Single account = "natural" UX (apps see the user's profile,
  documents, licenses).
- (−) Power users who bypass gpedit (e.g., `net user crossdesk *`
  from elevated cmd) still cause drift. Health-check + repair flow
  handles it but with friction.
- (−) gpedit-imposed restriction may surprise users who expect full
  control over their VM. Document explicitly: "this is your VM, but
  CrossDesk owns its credentials. Don't change them via Windows UI;
  use `crossdesk vm credentials rotate`."

### Reconsider when

- A user reports being locked out by elevated `net user` after
  bypassing gpedit, and the repair flow proves too cumbersome
  → consider Option D (event-log watcher) for proactive detection.
- We add multi-user shared-VM support
  → must revisit: dual-account becomes the right model.
- We move to passwordless authentication elsewhere in the stack
  (e.g., Hello PIN as primary)
  → revisit Option E.
