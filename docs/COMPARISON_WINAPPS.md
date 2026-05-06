# CrossDesk vs WinApps — Comparative Analysis

Purpose: WinApps (`third_party/winapps/`) and CrossDesk solve the same problem
— Windows applications as native Linux windows via FreeRDP RAIL — but with
very different stacks. This document enumerates every WinApps feature we
might want to preserve in CrossDesk, every WinApps weakness we should not
inherit, and every CrossDesk advantage we should defend.

All `third_party/winapps/...:NN` references are file:line citations into the
vendored subtree at HEAD as of the import.

---

## 1. Executive summary

| | **WinApps** | **CrossDesk** |
|---|---|---|
| **Status** | ~5 years mature, ~10k★, real users | Pre-MVP, Phase 2 in progress |
| **Stack** | Bash (`setup.sh` 1993 lines), PowerShell, Yad GUI | Python (asyncio, mypy --strict) + Rust (tokio, windows-rs) + Qt6/QML |
| **Backends** | Docker, Podman, libvirt, manual | libvirt `qemu:///session` only (by design) |
| **Transport** | RDP-over-TCP (port 3389, host-localhost) | gRPC over `AF_VSOCK` + mTLS + per-frame `AuthContext` |
| **Display** | FreeRDP RAIL (mature, hardened) | FreeRDP RAIL (planned, Phase 3) |
| **VM bootstrap** | dockur/windows container OR manual virt-manager | Zero-touch `autounattend.xml` + secondary OEM disk |
| **File sharing** | Static `\\tsclient\home` (whole `$HOME` exposed) | Just-in-time VirtioFS hot-plug per-app |
| **App discovery** | PowerShell registry walk + UWP + Chocolatey + Scoop | **Not implemented** |
| **App catalog** | 91 hand-curated apps with SVG icons | **Empty** |
| **License** | AGPLv3 main / GPLv3 launcher | GPL-3.0-or-later |

**One-line take:** WinApps is a working product with thin architecture;
CrossDesk is solid architecture without a working product yet. We need to
absorb their feature set without absorbing their fragility.

---

## 2. What WinApps does well — features we must preserve in CrossDesk

### 2.1 Windows-side registry tweaks (the secret sauce)

WinApps' `oem/RDPApps.reg` and `oem/install.bat` encode 5+ years of tribal
knowledge about what makes RDP RAIL actually work. **CrossDesk needs all of
these regardless of backend choice.** Citations from
`third_party/winapps/oem/RDPApps.reg`:

| Registry key | Value | Why |
|---|---|---|
| `HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server` → `fDenyTSConnections` | `0` | Master RDP enable. Default blocks all RDP. |
| `HKLM\SYSTEM\...\WinStations\RDP-Tcp` → `UserAuthentication` | `1` | Require NLA before connection. |
| `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Terminal Server\TSAppAllowList` → `fDisabledAllowList` | `1` | **CRITICAL FOR RAIL**: lets *any* app run as a RemoteApp, not just whitelisted ones. |
| `HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services` → `fAllowUnlistedRemotePrograms` | `1` | Redundant safeguard with the above. |
| `HKLM\SYSTEM\CurrentControlSet\Control\Keyboard Layout` → `IgnoreRemoteKeyboardLayout` | `1` | Force guest-side keyboard layout — prevents host/guest layout collisions. |
| `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced` → `EnableSnapBar` | `0` | Disable W11 snap toolbar (UX polish). |

**Action for CrossDesk:** port these into a `*.reg` file dropped onto the
secondary OEM disk and applied in `autounattend.xml`'s `<FirstLogonCommands>`.
The four marked CRITICAL are non-negotiable for RAIL.

### 2.2 The full FreeRDP RAIL command template

Reconstructed from `third_party/winapps/bin/winapps:855-865`:

```sh
xfreerdp \
  $RDP_FLAGS_NON_WINDOWS \
  /d:"$RDP_DOMAIN" \
  /u:"$RDP_USER" \
  /p:"$RDP_PASS" \
  /scale:100|140|180 \
  +auto-reconnect \
  /drive:media,"$REMOVABLE_MEDIA" \
  /wm-class:"$FULL_NAME" \
  /app:program:"$WIN_EXECUTABLE",hidef:on,icon:"$ICON",name:"$FULL_NAME",cmd:"\\tsclient\\home\\<file>" \
  /v:"$RDP_IP"
```

Essential flags: `/app:program:`, `/wm-class:` (so the Linux WM groups
windows correctly), `/scale:` (one of 100/140/180 only), `+auto-reconnect`,
`/drive:media,`. WinApps does **not** use `/cert:tofu`, `/sound`,
`/microphone`, `/gfx:AVC444`, `/network:`, or any cache flags by default —
those are pushed to user-configurable `RDP_FLAGS_*`.

**Action for CrossDesk:** this is the literal command our Phase 3 RAIL
manager needs to construct. See `host/src/crossdesk_host/display/rail_manager.py`.

### 2.3 Path translation for file arguments

`third_party/winapps/bin/winapps:847-850`:

```sh
FILE_PATH=$(echo "$2" | sed \
  -e 's|^'"${HOME}"'|\\\\tsclient\\home|' \
  -e 's|^'"${REMOVABLE_MEDIA}"'|\\\\tsclient\\media|' \
  -e 's|/|\\|g')
```

When the user does `winapps word ~/foo.docx`, the path is rewritten to
`\\tsclient\home\foo.docx` and forwarded as `/app:cmd:`. Forward slashes
become backslashes.

**Action for CrossDesk:** equivalent helper in `host/`. Note that with our
just-in-time VirtioFS we can do better — we can mount only the file's parent
directory, exposing nothing else. WinApps' approach exposes the entire
`$HOME` to the guest at all times.

### 2.4 App discovery (PowerShell)

`third_party/winapps/install/ExtractPrograms.ps1` (336 lines) is the
crown-jewel piece worth porting. It enumerates installed apps from four
sources:

1. **Registry App Paths** (`HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths`, line 181) — narrower but more curated than `Uninstall` keys; avoids junk.
2. **UWP packages** via `Get-AppxPackage`, filtering out `IsFramework`, `IsResourcePackage`, and `SignatureKind=System` (lines 209–231).
3. **Chocolatey shims** in `C:\ProgramData\chocolatey\bin\*.exe`.
4. **Scoop shims** in `$HOME\scoop\shims\*.shim`.

Icon extraction: `System.Drawing.Icon::ExtractAssociatedIcon` → PNG →
base64-encoded → emitted as bash array literals (lines 6–45, 90–94).

The output is a sourceable bash file:
```
NAMES+=("Microsoft Word")
EXES+=("C:\Program Files\...\WINWORD.EXE")
ICONS+=("iVBORw0K...base64...")
```

**Notable gap WinApps misses:** they ignore the standard
`HKLM\...\Uninstall` ARP keys and `WOW6432Node` 32-bit registry view. We
should include both.

**Action for CrossDesk:** rewrite `ExtractPrograms.ps1` as a Rust binary
running inside our guest agent (we already have `windows-rs`), exposing
discovery as a gRPC RPC over VSOCK. Faster than spawning PowerShell for
every scan, and we can poll on app install/uninstall events.

### 2.5 The 91-app catalog

`third_party/winapps/apps/<name>/info` files are dead simple bash:

```sh
NAME="Word"
FULL_NAME="Microsoft Word"
WIN_EXECUTABLE="C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"
CATEGORIES="WinApps;Office"
MIME_TYPES="application/msword;application/vnd.openxmlformats-officedocument.wordprocessingml.document;..."
ICON="ms-word"
```

Plus `apps/<name>/icon.svg` — 91 hand-crafted SVGs (e.g., the Photoshop one
was exported from Adobe Illustrator; the Word one has Cyrillic layer names —
clearly community-contributed over years).

**License-compatibility note:** main winapps is AGPLv3, our project is
GPL-3.0. Reusing the `.svg` files and `info` files directly is OK with
attribution, but we should double-check trademark/icon-art licensing for
each (Microsoft, Adobe trademarks). Safer path: reuse the `info` schema and
the executable-path data, redraw icons or pull them from `.exe` resources at
discovery time.

### 2.6 MS Office URL scheme handler

`third_party/winapps/apps/ms-office-protocol-handler.desktop`:

```
MimeType=x-scheme-handler/ms-word;x-scheme-handler/ms-excel;
  x-scheme-handler/ms-powerpoint;x-scheme-handler/ms-outlook;
  x-scheme-handler/ms-access;x-scheme-handler/ms-visio;
  x-scheme-handler/ms-project;x-scheme-handler/ms-teams;
  x-scheme-handler/ms-whiteboard;x-scheme-handler/ms-officeapp;
Exec=winapps manual %u
```

Clicking `ms-word://...` in Firefox/Chromium → routed to Word in the VM.
This is a quietly killer UX feature that takes 10 lines to add.

### 2.7 Two-layer health check before RDP

`third_party/winapps/setup.sh:1040-1195`:

1. **Port probe** — `timeout 5 nc -z $RDP_IP 3389`
2. **RDP smoke test** — spawn a hidden FreeRDP session running
   `cmd.exe /c "type NUL > $TEST_PATH && tsdiscon"`, then poll for the
   marker file appearing on the host's `\\tsclient\home` share. If the file
   shows up, the RDP path *and* drive redirection both work end-to-end.

**Adapt for CrossDesk:** replace the marker file with a gRPC `HealthCheck`
RPC over our VSOCK channel. Same idea: don't assume RDP is healthy just
because the port is open — round-trip a real request.

### 2.8 Sleep/wake time sync

`third_party/winapps/oem/TimeSync.ps1`: scheduled task on user logon, polls
every 5 min for `\\tsclient\home\.local\share\winapps\sleep_marker`. If
present, runs `w32tm /resync` and deletes the marker. The host writes the
marker on suspend.

This avoids Windows time drift after host suspend/resume.

**For CrossDesk:** if we use `qemu-guest-agent`, libvirt handles this
automatically (`virsh domtime` calls). If not, we replicate via gRPC ping
from the host on resume.

### 2.9 Autopause

`third_party/winapps/setup.sh` `AUTOPAUSE`/`AUTOPAUSE_TIME` config: after
N seconds with no FreeRDP session active, pause the VM (`virsh suspend`).
RAM stays reserved, CPU drops to zero. The `-20s` constant subtraction in
their math (`bin/winapps`) accounts for RDP's RemoteApp forced-disconnect
delay — an easily-missed gotcha.

### 2.10 FreeRDP version fallback chain

`third_party/winapps/setup.sh:413-454` and similar: tries `xfreerdp` →
`xfreerdp3` → `sdl-freerdp3` → `sdl3-freerdp` → flatpak
`com.freerdp.FreeRDP`. Good defensive coding — distros ship FreeRDP under
many binary names.

### 2.11 WinApps-Launcher (taskbar widget)

External repo `winapps-org/WinApps-Launcher` (Bash + Yad), packaged at
`third_party/winapps/packages/winapps-launcher/default.nix`. Provides VM
start/stop/pause/reboot from a system tray icon, plus an app picker.

**For CrossDesk:** our Qt6/QML installer wizard could extend into a
permanent taskbar applet covering the same surface. Bigger scope, much
nicer UX than Yad dialogs.

### 2.12 Configuration format

`~/.config/winapps/winapps.conf` is bash-sourced, ~20 documented fields:
`RDP_USER`, `RDP_PASS`, `RDP_ASKPASS`, `RDP_DOMAIN`, `RDP_IP`, `VM_NAME`,
`WAFLAVOR`, `RDP_SCALE`, `REMOVABLE_MEDIA`, `RDP_FLAGS`,
`RDP_FLAGS_WINDOWS`, `RDP_FLAGS_NON_WINDOWS`, `DEBUG`, `AUTOPAUSE`,
`AUTOPAUSE_TIME`, `FREERDP_COMMAND`, `PORT_TIMEOUT`, `RDP_TIMEOUT`,
`APP_SCAN_TIMEOUT`, `BOOT_TIMEOUT`, `HIDEF`. See README.md:377-549.

**For CrossDesk:** same field set, but TOML and validated against a typed
schema (`pydantic` or similar). Bash-sourcing is dangerous (any value can
inject shell).

### 2.13 Notification surface

`notify-send` is wired throughout `setup.sh` for user-visible errors (VM
won't start, forced stop, restart timeout, RDP drop). Cheap polish, easy to
miss.

---

## 3. Where WinApps is weak — pitfalls we should not inherit

### 3.1 Bash as primary control language

`setup.sh` is 1993 lines of bash. There are no types, no tests (the project
has zero CI — only pre-commit `shellcheck`/`shfmt`). Error handling is by
exit-code convention; control flow is implicit; the function call graph is
almost impossible to follow.

**CrossDesk advantage:** Python with `mypy --strict` and `pytest` for the
host, Rust with `cargo test` for the guest. We get types, tests, and async
primitives for free.

### 3.2 RDP over TCP/IP

WinApps' `compose.yaml` exposes port 3389 on `127.0.0.1`. Localhost is
better than wildcard, but the surface is still IP, the firewall is still in
the path, and any local process can probe RDP. There is no per-frame
authentication beyond TLS handshake — replay defense relies entirely on TLS.

**CrossDesk advantage:** `AF_VSOCK` skips the network stack entirely.
mTLS + per-frame `AuthContext` (peer cert fingerprint + stream nonce + monotonic
sequence) defends against CID collisions and replay independent of the TLS
layer. Documented in `ARCHITECTURE.md`.

### 3.3 Static `\\tsclient\home` exposure

Whenever any app is open, the entire user `$HOME` is mounted into Windows.
If a malicious or buggy Windows app runs, it has full read/write to the
user's documents. WinApps treats this as acceptable; we should not.

**CrossDesk advantage:** just-in-time VirtioFS — the host hot-plugs only the
parent directory of the file the user opens, and detaches it on `ReleaseAck`
from the guest. This is in `ARCHITECTURE.md` §3 and is one of CrossDesk's
distinguishing security features.

### 3.4 Docker as a backend at all

WinApps supports `dockur/windows` — running Windows in a privileged
container with `/dev/kvm` and `NET_ADMIN`. This is a popular path for users
but a regression in isolation versus a real VM, and it ties them to a
third-party (Docker) for their core feature.

**CrossDesk's stance is correct:** `qemu:///session` only, no Docker, no
daemon privilege escalation. We should not add Docker support even on user
request.

### 3.5 No HiDPI / multi-monitor handling

WinApps' DPI story is `/scale:100|140|180` — three discrete values, no
detection, no per-monitor scaling, no auto-fit. Multi-monitor is "set
`/multimon` and good luck"; their own README warns of black-screen FreeRDP
bugs.

**Opportunity for CrossDesk:** detect the user's compositor scale via
Wayland `wl_output.scale` or X11 RANDR, pick the closest FreeRDP supported
scale, and re-launch on monitor change. Multi-monitor: forward each RAIL
window to its own output via WM hints.

### 3.6 Limited registry walk

`ExtractPrograms.ps1` only looks at `HKLM\...\App Paths` — missing
many legitimately-installed apps registered only under `Uninstall`. Also
ignores `WOW6432Node` (32-bit apps on 64-bit Windows).

**For CrossDesk:** include all four (HKLM/HKCU × Uninstall/App Paths) plus
WOW6432Node, plus UWP. Filter junk with explicit denylist, not heuristic.

### 3.7 Manual MIME and icon curation

The 91-app catalog requires hand-editing `info` files for new apps and
hand-drawing SVGs. Unscalable.

**For CrossDesk:** auto-derive MIME types from the Windows registry's
`HKCR\<ext>` and `HKCR\<progid>\shell\open\command`. Pull icons from `.exe`
resources at discovery time (don't ship hand-drawn art).

### 3.8 No NTP / locale / keyboard config flow

WinApps has registry-level `IgnoreRemoteKeyboardLayout` (good) but no
config knobs for timezone or locale. Users hit it manually on first boot.

**For CrossDesk:** read host `timedatectl` + locale env, push to guest via
`autounattend.xml` and via runtime gRPC. Pre-flight problem solved.

### 3.9 No printer/USB/clipboard/audio toggles

WinApps puts these in `RDP_FLAGS` for the user to hand-edit FreeRDP flags
they don't necessarily understand. Defaults are bare-bones (`/cert:tofu
/sound /microphone +home-drive` per their README).

**For CrossDesk:** typed config fields (`enable_audio: bool`,
`enable_clipboard: bool`, `enable_printer: bool`, `usb_devices: list[str]`),
mapped to the right FreeRDP flags by our host code.

### 3.10 No CI / no integration tests

`.pre-commit-config.yaml` is the entire QA layer. Their PRs don't run
end-to-end tests. CrossDesk should have a minimum CI matrix from day one
(pytest, mypy, cargo test, plus an integration test with a known-good VM).

---

## 4. Where CrossDesk has clear wins — defend these

| | Why we win |
|---|---|
| **Transport security** | VSOCK + mTLS + per-frame `AuthContext` vs RDP-over-TCP with TLS-only |
| **No Docker** | `qemu:///session` runs as the user; WinApps' Docker path needs `NET_ADMIN`, `/dev/kvm` privileged passthrough |
| **JIT VirtioFS** | Per-app, per-file mounts vs entire `$HOME` exposed permanently |
| **Type safety** | Python `mypy --strict` + Rust vs 1993-line untyped bash |
| **VM bootstrap** | Zero-touch `autounattend.xml` + secondary OEM disk vs user-runs-virt-manager-by-hand |
| **Heartbeat FSM** | Documented PROBING → SOFT_RECOVERY → HARD_DESTROY state machine vs WinApps' "exit and let the user retry" |
| **Dynamic memory** | `virtio-balloon` integrated vs static RAM_SIZE |

These are all design-level, not features-to-build — they're already in
ARCHITECTURE.md. Our job is to keep them as constraints when adding
parity-with-winapps features.

---

## 5. License compatibility

- WinApps main code: **AGPLv3** (`third_party/winapps/LICENSE.md`)
- WinApps-Launcher: **GPLv3** (`packages/winapps-launcher/default.nix:70`)
- CrossDesk: **GPL-3.0-or-later** (root `LICENSE` if present, README §License)

GPLv3 is a subset of AGPLv3 — copying code from AGPLv3 *into* GPL-3.0
upgrades the obligations: any network-served deployment of CrossDesk would
need to expose source. **Recommendation:** copy *logic and ideas*
(registry tweaks, command structures, schemas), not verbatim code.
Re-implement in our own languages with attribution in commit messages and a
NOTICES file. The 91 SVG icons are a separate question — they may have
trademark issues independent of license (Microsoft Word logo, Adobe
Photoshop logo, etc.).

---

## 6. Master action items

Priority key: **P0** = required for MVP parity, **P1** = high-value
post-MVP, **P2** = nice-to-have.

### P0 — must-do for parity

1. **Replicate critical Windows registry tweaks** in our autounattend
   pipeline. The four CRITICAL keys from §2.1 (`fDenyTSConnections`,
   `UserAuthentication`, `fDisabledAllowList`, `fAllowUnlistedRemotePrograms`)
   are non-negotiable for RAIL. Add to `infra/` as a `.reg` file and wire
   into `<FirstLogonCommands>` in `infra/autounattend.xml`.

2. **Build the FreeRDP RAIL command** in
   `host/src/crossdesk_host/display/rail_manager.py` matching §2.2's
   template — `/app:program:`, `/wm-class:`, `/scale:`, `+auto-reconnect`,
   `/drive:media,`. Phase 4 work (RAIL Display Integration).

3. **Implement path translation** (`$HOME` → `\\tsclient\home`, `/` → `\`)
   as a host-side helper for `cmd:` argument forwarding. But: bind it to
   our JIT VirtioFS mount path, not a permanent share.

4. **MS Office URL scheme handler** — port `apps/ms-office-protocol-handler.desktop`
   into our `.desktop` generation flow.

5. **Implement app discovery** — port `ExtractPrograms.ps1` logic to a
   Rust `winapp-discovery` binary in `guest/`, exposed as a gRPC RPC.
   Fix the gaps: include `Uninstall` keys (HKLM + HKCU), include
   `WOW6432Node`, include UWP, exclude system noise.

6. **`.desktop` file generator** — Python module under `host/` matching the
   schema in §2.5, output to `~/.local/share/applications/crossdesk-*.desktop`.

### P1 — high-value follow-ups

7. **Adopt the 91-app catalog as a starting point** — copy the
   non-trademark fields (executable paths, MIME types, freedesktop
   categories) into our own catalog format (TOML preferred). Replace icons
   either by extracting from `.exe` at discovery time or by community
   re-contribution.

8. **Two-layer health check** before declaring the VM ready: gRPC port +
   round-trip RPC. Today our code probably only checks libvirt state.

9. **FreeRDP version fallback chain** — match WinApps' detection logic
   (`xfreerdp`, `xfreerdp3`, `sdl-freerdp3`, `sdl3-freerdp`, flatpak).

10. **Autopause** — config field + `virsh suspend` integration; subtract
    20s from user's threshold to account for RAIL cleanup overhead (the
    WinApps `-20s` constant from `bin/winapps`).

11. **Sleep/wake time sync** — if `qemu-guest-agent` covers it, prefer
    that. Otherwise mirror WinApps' marker-file approach via gRPC.

12. **GUI launcher / taskbar applet** — extend the existing Qt6/QML
    wizard into a permanent applet. Out-of-scope for MVP but a clear UX
    win.

13. **Notify-send equivalent** — wire host-side errors to desktop
    notifications via `org.freedesktop.Notifications` (we already have
    DBus access).

### P2 — nice-to-have (do better than WinApps here)

14. **HiDPI improvements** — auto-detect compositor scale, choose closest
    FreeRDP scale, re-launch on monitor change. WinApps does none of this.

15. **Multi-monitor RAIL** — forward each RAIL window to its appropriate
    output. WinApps explicitly warns this is broken on their stack.

16. **Typed config knobs for redirections** — `enable_audio`,
    `enable_clipboard`, `enable_printer`, `usb_devices: list[str]` in our
    TOML config, mapped to FreeRDP flags by host code.

17. **Locale + timezone propagation** — read host `timedatectl` + locale
    env on first boot, inject into autounattend.xml's `<UnattendXml>` and
    via `qemu-guest-agent` runtime updates.

18. **Auto-derive MIME types** from `HKCR\<ext>` registry instead of
    hand-curated lists.

19. **Auto-extract icons** from `.exe` resources during discovery, not
    hand-drawn SVGs.

---

## 7. What we explicitly skip

- **Docker / Podman backends** — collides with our "no Docker" constraint.
- **dockur/windows container image** — same reason.
- **Bash-driven control flow** — not portable to async Python.
- **`compose.yaml`** — not applicable.
- **`renovate.json`, `flake.nix`** — packaging concerns; we'll do our own.
- **Verbatim AGPLv3 code** — license-incompatible direction; copy ideas, re-implement.
- **Static `\\tsclient\home` mount** — security regression vs our JIT VirtioFS.

---

## 8. Catch-all checklist (everything WinApps documents)

The most exhaustive list of WinApps user-visible features is in their
README.md. The major buckets are: 91 community-tested apps, multi-backend
support (3 already covered), 20+ config knobs (covered in §2.12), MIME +
URL scheme integration (§2.6), GUI launcher (§2.11), Office URL handlers
(§2.6), pre-built `.desktop` files, sound/microphone/home-drive defaults,
multi-monitor (broken), `/kbd:unicode`, certificate management workflow,
KVM 2-5% overhead claim, distro-specific install paths (Debian, Fedora,
Arch, openSUSE, Gentoo, NixOS, Flatpak), Windows 10 Pro/Enterprise/Server +
Windows 11 support, FreeRDP v3 requirement, AppArmor/SELinux notes,
VirtIO drivers, CPU pinning, Hyper-V enlightenments, QEMU guest agent
integration, `virtiofs` shared folder fallback, kernel anti-cheat
limitation, and the "User Agent Switcher browser extension" workaround for
Office webapps.

Everything in that list either maps to one of our P0/P1/P2 items above, is
a constraint we already respect (e.g., libvirt KVM), or is irrelevant
(Docker-specific). The `present-in-CrossDesk` column in the per-feature
checklist reduces to: nothing on the user-visible side is implemented in
CrossDesk yet — Phase 1 is VM bootstrap only. The action-items list is
therefore the entire surface to build.
