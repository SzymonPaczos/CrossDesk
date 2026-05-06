# Competitive landscape

Where CrossDesk sits relative to existing options for "Windows
applications on a Linux desktop." For each: approach, when it wins,
when it loses, where CrossDesk differs.

## WinApps (winapps-org/winapps)

Vendored at `third_party/winapps/`. Full per-feature comparison in
`docs/COMPARISON_WINAPPS.md`.

- **Approach:** Windows in a Docker container (`dockur/windows`) or a
  manually-provisioned libvirt VM. FreeRDP RAIL over RDP-over-TCP.
  Bash orchestration (1993-line `setup.sh`).
- **Wins on:** maturity (~10k★, 5+ years), 91-app community catalog,
  Docker one-liner onboarding for casual users, broad community
  testing.
- **Loses on:** privileged daemon path (Docker), TLS-only RDP auth
  (no per-frame replay defense), static `\\tsclient\home`
  whole-`$HOME` exposure, bash-driven orchestration with no tests.
- **Where we differ:** AF_VSOCK + mTLS + per-frame `AuthContext`,
  JIT VirtioFS, qemu:///session user libvirt, type-checked async
  Python + Rust.

## Cassowary (casualsnek/cassowary, abandoned)

- **Approach:** very similar to WinApps' libvirt path: KVM Windows VM
  + FreeRDP RAIL.
- **Status:** unmaintained for 3+ years.
- **Wins on:** historical reference for "what works in this design."
- **Where we differ:** active development, formalized security model,
  one-command bootstrap, JIT filesystem.

## Wine / CrossOver / Bottles

- **Approach:** translates Win32 syscalls to Linux without a Windows
  VM.
- **Wins on:** no Windows license needed, lighter resource use, fast
  per-app launch, works offline, no VM boot time.
- **Loses on:** doesn't run Microsoft 365 (Office activation rejects),
  Adobe Creative Cloud (DRM enforcement), Visual Studio (deep .NET
  dependency), many anti-cheat-protected games, anything that probes
  for genuine Windows.
- **Where we differ:** different paradigm. Not a competitor for users
  whose blocking apps work in Wine. Direct competitor for users who
  need real Windows.

## WSL2 / WSLg

- **Approach:** Linux on a Windows host — opposite direction.
- **Where we differ:** different user. CrossDesk targets a Linux user
  who needs occasional Windows apps; WSL2 targets a Windows user who
  needs Linux tools.

## Manual virt-manager + RDP

- **Approach:** advanced user manually creates a Windows VM in
  virt-manager, installs Windows from ISO, runs an RDP/RAIL client
  against it by hand.
- **Wins on:** maximum flexibility, mature GPU passthrough story,
  works for gaming, no third-party orchestrator.
- **Loses on:** every step manual. Onboarding measured in hours, not
  minutes. No `.desktop` integration. No app discovery. No automatic
  recovery.
- **Where we differ:** CrossDesk is essentially "this, automated, with
  per-frame authentication, JIT filesystem, and no shell to log into."

## Direct QEMU + RemoteApp

- **Approach:** users who skip libvirt and run QEMU directly with
  custom command lines.
- **Wins on:** complete control, smallest dependency surface.
- **Loses on:** even more manual than virt-manager. No snapshot
  management, no hot-plug ergonomics, no XML normalization.
- **Where we differ:** we use libvirt because reimplementing its
  lifecycle management isn't worth it.

## Looking Glass / Sunshine / Moonlight

- **Approach:** GPU-accelerated streaming from a Windows VM (Looking
  Glass: same-host shared memory; Sunshine + Moonlight: network
  streaming).
- **Wins on:** native GPU, full desktop, gaming-grade latency.
- **Loses on:** not RAIL (full desktop, not per-app windows). Built
  for fullscreen gaming, not workflow integration.
- **Where we differ:** CrossDesk renders per-app windows into the
  Linux compositor. Looking Glass / Sunshine show the whole Windows
  desktop in one window or one fullscreen.

## Hyper-V RemoteApp (Windows-on-Windows)

- **Approach:** Microsoft's RemoteApp for serving Windows apps from a
  Windows VM to a Windows client.
- **Where we differ:** the client is Linux, not Windows. We adapt RAIL
  to a Linux compositor, which RemoteApp itself doesn't address.

## Where CrossDesk wins

For users who:

- Need to run real Windows apps (Office activation, Adobe DRM, .NET
  enterprise software) from a Linux desktop, where Wine doesn't cut
  it.
- Care about per-frame authentication and limited host exposure.
- Want a single-command install rather than multi-hour virt-manager
  setup.
- Don't want a Docker daemon in their security model.

## Where WinApps still wins (today)

For users who:

- Want it to work today (CrossDesk is pre-MVP).
- Need an app on the 91-app catalog list and don't want to add their
  own.
- Are comfortable with `\\tsclient\home` and the Docker dependency.
- Don't intend to use the per-frame-auth claim.

This is honest accounting, not concession. Our advantage shows when
the user starts asking the questions WinApps cannot answer well: "Can
I trust this?", "Does it run as root?", "What does the Windows VM see
of my home directory?", "What happens if the VM gets stuck?".
