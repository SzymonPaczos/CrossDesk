# Distribution & updates — visual overview

One-page entry point for "how do users get CrossDesk and how do
they update it." Diagrams + short captions; the prose deep-dive
lives in [`PACKAGING.md`](PACKAGING.md), the version-compatibility
rules in [`VERSIONING.md`](VERSIONING.md).

## TL;DR

Five distro-native package formats plus a cross-distro Flathub
channel — one user command each:

```
apt install crossdesk         # Debian / Ubuntu / Mint / Pop_OS
dnf install crossdesk         # Fedora / RHEL / openSUSE
yay -S crossdesk              # Arch / Manjaro / EndeavourOS
nix run github:SzymonPaczos/CrossDesk#crossdesk    # NixOS
pip install crossdesk-host    # headless / dev / any distro
flatpak install flathub dev.crossdesk.CrossDesk    # any distro (post-MVP)
```

Two independent update layers:
1. **Linux host** — distro package manager (`apt upgrade`, etc.)
   or `flatpak update`.
2. **In-VM agent.exe** — separate `crossdesk upgrade` RPC, hot-swap
   without restarting the VM.

Flatpak is shipped for **distribution reach**, not as a security
boundary — see §5 for the honest trade-off. Snap is deferred
(classic-confinement review path is slow); AppImage stays out of
scope (no store, no auto-update).

## 1. Distribution matrix — who picks what

```
                         ┌─────────────────────────────────────┐
                         │        Tagged release v0.1.0        │
                         └──────────────────┬──────────────────┘
                                            │
                   ┌────────────────────────┼────────────────────────┐
                   │                        │                        │
            ┌──────▼──────┐         ┌───────▼───────┐         ┌──────▼──────┐
            │   Debian    │         │   Red Hat     │         │    Arch     │
            │  Ubuntu     │         │  Fedora       │         │  Manjaro    │
            │   Mint      │         │  openSUSE     │         │  EndeavourOS│
            └──────┬──────┘         └───────┬───────┘         └──────┬──────┘
                   │                        │                        │
                ┌──▼──┐                  ┌──▼──┐                  ┌──▼──┐
                │ deb │                  │ rpm │                  │ AUR │
                └──┬──┘                  └──┬──┘                  └──┬──┘
                   │                        │                        │
                  apt                      dnf /                    yay /
                update                    zypper                   paru
                upgrade                   update                   -Sua
                   │                        │                        │
            ┌──────▼─────┐         ┌────────▼────────┐         ┌─────▼─────┐
            │ NixOS      │         │ Headless / dev  │         │  Source   │
            │ flake.nix  │         │ pip / venv      │         │  build    │
            └──────┬─────┘         └────────┬────────┘         └─────┬─────┘
                   │                        │                        │
              nix flake                  pip install             cargo build +
              update                     --upgrade               python -m build

   ─────────────────────  cross-distro store channel  ──────────────────────

                              ┌──────────────────┐
                              │     Flathub      │  ◄── any distro with
                              │    (Flatpak)     │      Flatpak runtime
                              └────────┬─────────┘      (Fedora Silverblue,
                                       │                 SteamOS, elementary,
                                  flatpak update         Pop_OS, …)
                                       │
                          (+ portal prompts on first launch;
                           NOT a security boundary — see §5)
```

One package per distro family for the native channel. Each uses
its native package manager to update the **host layer**. PyPI is
for developers and headless setups (no GUI, no systemd
auto-install). Source build is the permanent fallback.

The Flathub channel is **additional, not primary** — a discovery /
ease-of-install play for users who live in their distro's
software center (GNOME Software, KDE Discover, Pop!_Shop) and
expect to find apps there. Details:
[`PACKAGING.md`](PACKAGING.md) "Format-by-format analysis" + §5
below for the trade-off.

## 2. Release pipeline — tag → channels

```
   developer
      │
      │ git tag v0.1.0 && git push --tags
      ▼
┌──────────────────────────────────────────────────────────────────┐
│   GitHub Actions  (.github/workflows/release.yml — 🚧 Week 22)   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. cross-rs build  →  guest/agent.exe  (x86_64-pc-windows-gnu)  │
│  2. cosign sign     →  agent.exe.sig    (Sigstore keyless)       │
│  3. python -m build →  crossdesk_host-*.whl                      │
│  4. dpkg-deb        →  crossdesk_*.deb                           │
│  5. rpmbuild        →  crossdesk-*.rpm                           │
│  6. nix build       →  result/         (verify flake builds)     │
│  7. PKGBUILD srcinfo→  AUR push                                  │
│                                                                  │
└──────────┬───────────────┬────────────────┬──────────────────────┘
           │               │                │
           ▼               ▼                ▼
   ┌───────────────┐ ┌─────────────┐ ┌──────────────┐
   │  GH Releases  │ │   AUR.git   │ │  PyPI.org    │
   │  (deb/rpm/    │ │  (PKGBUILD) │ │  (wheel)     │
   │   nixhash)    │ └─────────────┘ └──────────────┘
   └───────┬───────┘
           │
   apt repo  (deb.crossdesk.??)  ◄── Tier 2, pending domain decision
   Copr / OBS  (rpm)             ◄── Tier 2
```

One linux runner builds everything (cross-rs handles the Windows
PE32+ cross-compile for `agent.exe`). Sigstore signs the agent
keyless — no offline secret to babysit at this stage. Apt repo +
Copr/OBS belong to "Tier 2" because they need a hosted domain;
that's an open user-decision (see AGENTS.md "Pending user-decision
reminders"). Until then, deb/rpm artifacts attach to GitHub
Releases and users `dpkg -i` / `dnf install` them manually.

Details: [`PACKAGING.md`](PACKAGING.md) "CI build matrix" and
"Distribution-time signing".

## 3. Two-layer update flow — the important diagram

CrossDesk has **two independent update layers**. Conflating them
is the most common source of confusion, so this diagram is the
core of the doc.

```
   ┌─────────────────────────────────────────────────────────────┐
   │                  Linux host (your machine)                  │
   │                                                             │
   │   ┌───────────────────────────────────────────────────┐     │
   │   │  crossdesk  (Python host + GUI + agent.exe blob)  │     │
   │   │                                                   │     │
   │   │  ◄──── apt upgrade  /  dnf update  /  yay -Sua    │     │
   │   │       (outer layer: distro package manager)       │     │
   │   └───────────────────────────────┬───────────────────┘     │
   │                                   │ gRPC over AF_VSOCK      │
   │                                   │ + mTLS + Hello          │
   │   ┌───────────────────────────────▼───────────────────┐     │
   │   │  Windows VM (libvirt qemu:///session)             │     │
   │   │                                                   │     │
   │   │  ┌─────────────────────────────────────────────┐  │     │
   │   │  │  agent.exe  (NT service, Rust)              │  │     │
   │   │  │                                             │  │     │
   │   │  │  ◄──── crossdesk upgrade ───────────────┐   │  │     │
   │   │  │       (inner layer: hot-swap RPC)       │   │  │     │
   │   │  │       FSM: HEALTHY → UPGRADING → HEALTHY│   │  │     │
   │   │  │       (HARD_DESTROY suppressed ≤60 s)   │   │  │     │
   │   │  └─────────────────────────────────────────┘   │  │     │
   │   └───────────────────────────────────────────────────┘     │
   └─────────────────────────────────────────────────────────────┘

   Outer layer                          Inner layer
   ─────────────                        ───────────────────────
   apt / dnf / yay / nix / pip          crossdesk upgrade RPC
   restart systemd user unit            hot-swap, no VM restart
   verifies: dpkg-sig / GPG /           verifies: cosign sig on
     flake.lock hash                      agent.exe (Sigstore)
   user-paced (you decide when)         Hello handshake on
                                          reconnect → check N-1
                                          minor compatibility
```

The Linux host updates like any other program — through the
distro package manager. The **in-VM agent is updated separately**,
via a control-plane RPC, in FSM state `UPGRADING` (which suppresses
the watchdog's `HARD_DESTROY` for up to 60 s while the binary
swaps). On reconnect, the Hello handshake exchanges
`protocol_version`, `host_version`, `agent_version`, and
`capabilities`; host accepts an agent at its own minor or one
below (same major) — the **N-1 minor rule**.

Why two layers? Distros only know how to ship Linux files. The
Windows guest binary lives inside a VM disk that the host package
deploys *during install*; updates to that binary need a path that
doesn't require reinstalling the whole package or rebuilding the
VM image. `crossdesk upgrade` is that path.

Details: [`PACKAGING.md`](PACKAGING.md) "Update story per format",
[`VERSIONING.md`](VERSIONING.md) Hello handshake.

## 4. What's already shipped vs what's left

```
     Format       Build artifact          Hosting/channel        Status
     ─────────────────────────────────────────────────────────────────
     PyPI         crossdesk_host*.whl     pypi.org               ✅ ready
     AUR          PKGBUILD                aur.archlinux.org      ✅ ready
     NixOS        flake.nix               github (flake input)   ✅ ready
     deb          *.deb                   GH Releases (Tier 1)   🚧 Week 22
                                          deb.crossdesk.??       🚧 Tier 2
                                                                   (domain
                                                                    pending)
     rpm          *.rpm                   GH Releases (Tier 1)   🚧 Week 22
                                          Copr / OBS             🚧 Tier 2
     CI release   release.yml workflow    GitHub Actions         🚧 Week 22
     Code sign    cosign on agent.exe     Sigstore keyless       🚧 Week 22
     EV cert      —                       —                      ⏸ deferred
                                                                    (user-
                                                                    decision)
     Flatpak      *.flatpak               Flathub                🚧 Phase 6+
                  + manifest                                       (post-MVP
                  dev.crossdesk.            (cross-distro reach)    add-on)
                  CrossDesk.json
     Snap         —                       Snap Store             ⏸ deferred
                                                                    (classic
                                                                    confinement
                                                                    review)
```

Three formats are code-complete (`packaging/aur/PKGBUILD`,
`flake.nix`, `host/pyproject.toml`). deb/rpm and the CI release
matrix land in Week 22 of
[`docs/EXECUTION_PLAN.md`](EXECUTION_PLAN.md). EV certificate for
`agent.exe` is intentionally deferred — Sigstore keyless covers
v0.1.0; EV moves once funding/scale justify it. Flatpak is a
post-MVP Phase 6+ add-on for distribution reach (see §5); Snap is
deferred until the Canonical classic-confinement path is worth
the wait.

## 5. The Flatpak trade-off; why Snap and AppImage stay out

Flatpak ships, but it's worth being honest about what's
sandboxed and what isn't. The diagram below is the reality;
treat it as **disclaimer, not deal-breaker**.

```
   ┌──────────────────── Flatpak sandbox ────────────────────┐
   │                                                         │
   │   crossdesk (host)                                      │
   │                                                         │
   │   ┌─ holes we punch ────────────────────────────────┐   │
   │   │  • libvirt session daemon (org.libvirt.…)       │   │
   │   │    → --talk-name=org.libvirt.* (full D-Bus)     │   │
   │   │  • $WAYLAND_DISPLAY direct (RAIL compositor)    │   │
   │   │    → --socket=wayland (no portal)               │   │
   │   │  • multi-GB qcow2 VM disks                      │   │
   │   │    → land in ~/.var/app/dev.crossdesk.…/data/   │   │
   │   │      (Flatpak-managed, not ~/.local/share)      │   │
   │   │  • spawn child process FreeRDP /usr/bin/xfreerdp│   │
   │   │    → --talk-name=org.freedesktop.Flatpak        │   │
   │   │      (host-spawn — exits the sandbox)           │   │
   │   │  • systemd user unit (status, restart)          │   │
   │   │    → portal: org.freedesktop.background          │
   │   │      (one-time consent, not auto-installed)     │   │
   │   └─────────────────────────────────────────────────┘   │
   │                                                         │
   │   Sum: D-Bus + Wayland + host-spawn permissions are     │
   │        all present. The sandbox isolates very little.   │
   │                                                         │
   │   But: Flathub is THE store for Fedora Silverblue,      │
   │        SteamOS, elementaryOS, GNOME OS users — without  │
   │        being on Flathub we don't reach them at all.     │
   │        Industry precedent: Bottles, GNOME Boxes, Heroic │
   │        Launcher all ship on Flathub with comparable     │
   │        permission lists. It works. Users use it.        │
   └─────────────────────────────────────────────────────────┘

   Snap:     same sandbox profile as Flatpak, BUT also requires
             "classic" confinement (libvirt access + child-spawn
             needs it). Classic confinement = manual Canonical
             review, often weeks/months. Ubuntu users have apt
             anyway. Effort/reach ratio worst of the three;
             deferred, not permanently rejected.

   AppImage: not a store, just a file. No auto-update
             (AppImageUpdate is a separate project users won't
             install). Self-contained = ~250 MB binary
             (Qt6+FreeRDP+libvirt-client all bundled). Worse UX
             than `apt install`. Skipped permanently.

   Docker:   contradicts DEC-0003 (qemu:///session, not
             qemu:///system; no privileged daemon). Skipped
             permanently.
```

The honest position: Flatpak is **a distribution channel, not a
security boundary**. Users who install from Flathub get the
convenience of a software center, auto-update via `flatpak
update`, and one-line install on any distro — same value
proposition as deb/rpm, plus reach into immutable distros where
deb/rpm don't apply (Silverblue, Kinoite, SteamOS, GNOME OS).
What they don't get is meaningful sandboxing, because CrossDesk
is structurally incompatible with sandboxing. README and Flathub
listing will say so plainly; we're not selling a security claim
we can't deliver.

Snap stays deferred until Canonical's classic-confinement review
path becomes worth the wait, or Snap Store reach grows beyond
Ubuntu desktop. Easy to add later; not blocking MVP.

Details: [`PACKAGING.md`](PACKAGING.md) "Flatpak", "Snap",
"AppImage" sections; [`DECISIONS.md`](DECISIONS.md) DEC-0008
(amended 2026-05-09).

## 6. Quick reference — install + update commands

```
Distro family       Install                          Update
──────────────────  ──────────────────────────────  ──────────────────────
Debian / Ubuntu     sudo apt install crossdesk      sudo apt upgrade
Fedora / openSUSE   sudo dnf install crossdesk      sudo dnf upgrade
                    sudo zypper install …             sudo zypper update
Arch / Manjaro      yay -S crossdesk                yay -Sua
NixOS               (add flake input)               nix flake update +
                                                      nixos-rebuild switch
Headless / dev      pip install crossdesk-host      pip install --upgrade …
Any distro          flatpak install flathub         flatpak update
(Flathub)             dev.crossdesk.CrossDesk         dev.crossdesk.CrossDesk

In-VM agent (any channel):  crossdesk upgrade
```

The host layer is whatever your distro provides. The agent layer
is one command, same on every distro, run from within the
already-installed host.

Details: [`PACKAGING.md`](PACKAGING.md) "Update story per format".
