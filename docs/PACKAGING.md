# Distribution & packaging

> Looking for the visual overview (diagrams of the format matrix,
> release pipeline, and dual-layer update flow)? Start at
> [`DISTRIBUTION.md`](DISTRIBUTION.md). This file is the prose
> deep-dive — per-format analysis, decision rationale, signing,
> sequencing.

How users get CrossDesk on their Linux box. Per-format analysis,
chosen primary path, and the bundling story for `agent.exe` (a
Windows binary that must ship inside a Linux package).

WinApps does `bash <(curl https://raw.githubusercontent.com/...
/setup.sh)` plus a NixOS flake plus AUR. They don't ship deb/rpm.
That works for their audience but is not adequate for users who
want `apt install crossdesk` from their distro's package manager.

## What needs to be shipped

A complete CrossDesk install consists of:

1. **Python host package** — `crossdesk-host` Python module,
   entry-point script (`crossdesk` CLI).
2. **Compiled `agent.exe`** — Rust-cross-compiled Windows binary,
   bundled inside the host package and copied to a secondary OEM
   disk during `crossdesk install`.
3. **Qt6/QML wizard** — `crossdesk-gui` Rust+CXX-Qt binary.
4. **PKI templates** — scripts in `infra/` to generate the user's
   mTLS certificates.
5. **Default configs** — TOML templates for
   `~/.config/crossdesk/`.
6. **systemd user service unit** — for VM autostart and lifecycle
   integration.
7. **`.desktop` file** — for `crossdesk-gui` in the user's app
   menu.
8. **Translations** — gettext/Qt translation files (see
   `docs/I18N.md`).

The bundle is **runtime-Linux, build-anywhere**. Build output is
distro-installable.

## Format-by-format analysis

### `pip install crossdesk-host` (PyPI)

**Pros:** universal Linux + macOS + Windows for development, simple
release process, semver native, `pip install --user` for unprivileged
installs.

**Cons:** packaging a Windows `.exe` and a Qt GUI into a pip-
installable wheel is awkward. Wheels expect Python-native code; we
need post-install steps for systemd unit installation, FreeRDP
runtime check, etc. Not how distro-managed users install desktop
software.

**Verdict:** ship as a pip package for the **host component only**,
useful for developers and headless setups. Not the primary user-facing
distribution.

### `deb` (Debian / Ubuntu)

**Pros:** native package manager integration. Users do
`sudo apt install crossdesk` from a PPA or third-party repo.
Dependencies declared (libvirt, qemu-kvm, freerdp3-x11, qt6-base).
Auto-update via apt. systemd unit installed via `dh_systemd_user`.

**Cons:** more work to build. Requires `dh-virtualenv` or `fpm` to
package Python with its dependencies. Two distro families
(Debian-derivatives) per build.

**Verdict:** **primary path for Debian/Ubuntu/Mint/Pop_OS users.**
Substantial user base. Worth the build complexity.

### `rpm` (Fedora / RHEL / openSUSE)

**Pros:** native package manager (`dnf`, `zypper`). dnf-copr or
public OBS repo for hosting. Same logic as deb but for RPM-family.

**Cons:** same as deb but for RPM. Two slightly-different families
(Fedora vs openSUSE) require care.

**Verdict:** **primary path for Fedora/RHEL/openSUSE users.**
Same effort tier as deb.

### AUR (Arch User Repository)

**Pros:** community-driven, easy to publish (`PKGBUILD` in a git
repo, push to AUR). Arch users are technical and welcome PKGBUILDs.
Low maintenance from us — community typically maintains.

**Cons:** Arch-only.

**Verdict:** **easy add-on, ship from day one.** Initial PKGBUILD
maintained by us; expect the community to take over.

### NixOS flake

**Pros:** declarative; NixOS users are exactly the security-
conscious audience CrossDesk targets. WinApps already has a flake
in `third_party/winapps/flake.nix` we can study.

**Cons:** niche but high-value audience.

**Verdict:** **ship from early; small effort, fits target audience.**

### Flatpak

**Pros:** sandbox + Flathub auto-update + cross-distro single
binary. Modern packaging ergonomics.

**Cons:** the sandbox is a serious problem. CrossDesk needs:
- libvirt access (talk to host's libvirt daemon)
- D-Bus session bus access
- Direct compositor access ($WAYLAND_DISPLAY, $DISPLAY)
- Filesystem access for `~/.config/crossdesk/`,
  `~/.local/state/crossdesk/`, the VM disk image (often
  GB-sized), the user's home directory for file forwarding
- Spawn child processes (FreeRDP)

Each of these requires Flatpak permissions that effectively erase
the sandbox. By the time we have all the holes punched, we get
"Flatpak in name only" with worse UX than a normal package.

**Verdict:** **skip.** The sandbox model is wrong for our use case.

### AppImage

**Pros:** single-file portable binary.

**Cons:** updates are awkward (AppImageUpdate is a separate
project). Self-contained means we ship our own copies of system
libraries (Qt, FreeRDP), bloating the file. systemd integration
is harder.

**Verdict:** **skip.** Doesn't add value over deb/rpm for our
audience.

### Snap

**Pros:** cross-distro, sandboxed.

**Cons:** same sandbox issues as Flatpak. Plus Canonical-centric.

**Verdict:** **skip** for the same reasons as Flatpak.

### Container (Docker / Podman / OCI)

**Verdict:** **skip.** Already documented in `docs/DECISIONS.md`
DEC-0003 — we don't run inside Docker. We could ship the host
process as a container that talks to host libvirt, but that
contradicts our "no privileged daemon" stance and adds nothing.

## Chosen distribution matrix

**Tier 1 (we ship and maintain):**
- `deb` for Debian/Ubuntu (PPA on launchpad.net or third-party
  repo with apt source).
- `rpm` for Fedora (Copr repo) and openSUSE (OBS repo).
- AUR PKGBUILD for Arch.
- NixOS flake.
- PyPI for the host module (developers, headless).

**Tier 2 (community welcome):**
- Gentoo ebuild.
- Slackware build script (SBo).
- Distro-specific Snap if a community member wants it (we won't
  block it but we don't ship it).

**Skipped:**
- Flatpak (sandbox incompatible).
- AppImage (no value-add).
- Docker / OCI container (DEC-0003).

## Bundling `agent.exe` inside the Linux package

The Rust-cross-compiled `x86_64-pc-windows-gnu` binary ships as a
binary asset inside whatever Linux package format. It lives at:

```
/usr/share/crossdesk/agent.exe
/usr/share/crossdesk/agent.exe.sig    # Sigstore signature
/usr/share/crossdesk/oem/RDPApps.reg
/usr/share/crossdesk/oem/install.bat
/usr/share/crossdesk/oem/lean_profile.ps1   # if --lean
```

`crossdesk install` reads from `/usr/share/crossdesk/` and copies to
the secondary OEM disk attached to the Windows VM during install.

Code signing (also in FOLLOWUPS): we plan Sigstore for `agent.exe`
initially. EV cert if/when funding/scale warrants. This is a
security-formalization item; documented here because the package
must ship the signature artifact alongside the binary.

## CI build matrix

GitHub Actions builds release artifacts on tag:

```yaml
release:
  strategy:
    matrix:
      target:
        - { os: ubuntu-latest, format: deb }
        - { os: ubuntu-latest, format: rpm }
        - { os: ubuntu-latest, format: aur-pkgbuild }
        - { os: ubuntu-latest, format: nix-flake-output }
        - { os: ubuntu-latest, format: pypi-wheel }
  steps:
    - cross build agent.exe (always Linux runner with cross-rs)
    - sign agent.exe with Sigstore
    - build crossdesk-gui (Rust + CXX-Qt) for the target distro
    - package per-format
    - upload release artifact to GitHub Releases
```

Repos:
- deb: hosted on a third-party repo or PPA we maintain (e.g.,
  `https://repo.crossdesk.dev/deb/`).
- rpm: Fedora Copr (free, automated) and openSUSE OBS.
- AUR: `https://aur.archlinux.org/packages/crossdesk` (community
  edits welcome).
- NixOS: `flake.nix` in the main repo — `nix run
  github:SzymonPaczos/CrossDesk#crossdesk` works directly.
- PyPI: `pip install crossdesk-host`.

Initial release: PyPI + AUR + NixOS flake (lowest effort, most
technical audience). deb + rpm follow within a release or two.

## Update story per format

| Format | Update mechanism |
|--------|------------------|
| deb / rpm | distro auto-update (`apt update && apt upgrade`) |
| AUR | `yay -Sua` (community standard) |
| NixOS | `flake update` + rebuild |
| PyPI | `pip install --upgrade crossdesk-host` |

`crossdesk upgrade` (the in-app command) is **about the in-VM agent**,
not about the host package. The host package is updated via the
user's distro mechanism. The in-VM agent is hot-swapped via gRPC
(`ControlService.UpgradeAgent` RPC) per `docs/VERSIONING.md`.

## License notes

CrossDesk is GPL-3.0-or-later. All package formats ship the LICENSE
file. The `third_party/winapps/` subtree is AGPLv3 reference and is
**not** included in distributed packages — it's strictly a
development-time vendor (kept out of `MANIFEST.in` / `Cargo.toml`
package data).

## Distribution-time signing

Ship signed packages where the format supports it:

- deb: dpkg-sig via a CrossDesk release key. Public key on the
  download page.
- rpm: GPG-signed.
- AUR: PKGBUILD references upstream tarball signed by the same key.
- NixOS: source hash in flake.lock; reproducible build.
- PyPI: PEP 458 / PEP 480 signed releases when ready.

The release key is stored offline; used only for tagging releases.
Documented in `docs/SECURITY.md` (to be created with security
formalization work — overlap with future security work).

## Sequencing of work

### P0 (initial release, lowest effort)
- AUR PKGBUILD published.
- PyPI wheel for host module.
- NixOS flake.
- README + install docs cover all three.

### P1
- deb package + apt repo (on a host we control).
- rpm package + Copr/OBS repos.
- CI release matrix wired to build all four formats on tag.
- Sigstore signing for `agent.exe`.

### P2
- Update mechanism docs per distro.
- GPG signing of distribution packages.
- Community documentation for adding distro support (Gentoo,
  Slackware, etc.).
