# CrossDesk

Run Windows applications as native Wayland or X11 windows on a Linux
desktop. The Linux host controls a Windows virtual machine over gRPC
with mTLS and per-frame authentication. A Rust NT service inside the VM
forwards window events to the host, which spawns FreeRDP RAIL processes
to render each app as its own native window.

```sh
crossdesk doctor                       # check the host is ready
crossdesk install --iso-path Win.iso   # unattended Windows install + agent, ~15 min
crossdesk launch notepad               # Notepad appears as a native Linux window
```

**Status:** pre-alpha, and the honest version is below — nothing here is
claimed until it has run on real hardware.

*Verified live on Linux+KVM:* a fresh `crossdesk install` brings up
Windows unattended and the in-VM NT-service agent connects by itself in
about 12 minutes with zero manual steps; the agent survives an RDP
disconnect and a hard reset; `crossdesk launch` renders Notepad and Paint
as separate native Linux windows over mTLS; killing the VM outright
(`virsh destroy`) is noticed in about a second and the agent is back in
roughly 25 seconds — booting the installed disk, not reinstalling over it;
heartbeat round-trips run at a ~2.5 ms median and a launch reaches a mapped
window in ~2.7 s; `crossdesk doctor` passes on a good host and fails loudly
on a broken one.

*Not verified yet:* the persistent virtio-fs share, suspend/resume across a
host sleep, and installing from a distro package. Those are the remaining
v0.1.0 acceptance criteria — tracked, with their real state, in
[PLAN.md](PLAN.md).

Bring your own Windows ISO (`--iso-path`); auto-download is not
implemented. See [ROADMAP.md](ROADMAP.md) for phase definitions,
[docs/MVP_SCOPE.md](docs/MVP_SCOPE.md) for what ships in v0.1.0, and
[docs/GUI_PLAN.md](docs/GUI_PLAN.md) for v1.0 scope. Post-1.0 ideas live
in [docs/POST_1_0_IDEAS.md](docs/POST_1_0_IDEAS.md).

## Why

The obvious incumbent here is WinApps, and it works. But its happy path
runs a privileged Docker container with `NET_ADMIN` and `/dev/kvm`, and
permanently exposes `$HOME` to the guest via `\\tsclient\home` — always
on, with no way to say no. I wanted the same FreeRDP RAIL trick without
handing a Windows VM that much of my system.

So CrossDesk runs the VM under user-session libvirt (`qemu:///session`) —
no privileged container, no daemon running as root — and **file sharing is
opt-in and off by default**. Turn it on and you choose the scope; the
v0.1.0 default when enabled is `documents`
([DEC-0019](docs/DECISIONS.md)). Opening a file with a Windows app also
shares just that file's folder, for that session only. The whole `$HOME`
— roughly what WinApps gives you — is available too, behind a warning
that spells out what it exposes. A single `custom` folder is config, and
a per-file just-in-time mount that
vanishes when the file closes is the eventual tight-isolation mode —
post-1.0, not today.

Side-by-side comparison: [docs/COMPARISON_WINAPPS.md](docs/COMPARISON_WINAPPS.md).
Where this sits in the broader landscape: [docs/COMPETITION.md](docs/COMPETITION.md).

## Quick start

A Linux host with KVM, and your own Windows ISO — CrossDesk does not
download one for you.

**1. Host packages.** You need KVM, QEMU, libvirt (the *user* session —
no root daemon), OVMF/edk2 UEFI firmware, and FreeRDP 3.x. Package names
differ across distros, so rather than guess: install CrossDesk (below),
then let it tell you.

**2. Check the host.**

```sh
crossdesk doctor
```

Ten checks — CPU virtualization, `/dev/kvm`, vsock, QEMU, FreeRDP, OVMF,
libvirt, free disk space, config, VM credentials. It exits non-zero and
names whatever is wrong. Fix anything it flags before going on; it is the
same pre-flight `install` runs for you.

**3. Install Windows into the VM.** Unattended — you do not click through
Windows setup.

```sh
crossdesk install --iso-path ~/Downloads/Win10_22H2_English.iso --locale en-US
```

`--locale` **must match your ISO's language** (a Polish ISO needs
`pl-PL`), or Windows setup stops on a language prompt and waits for a
human who is not there. Budget ~15–25 minutes; the run ends with the
in-VM agent connected to the host on its own.

**4. Launch something.**

```sh
crossdesk launch notepad
crossdesk launch 'C:\Program Files\Some App\app.exe'   # anything installed in the guest
```

To remove all of it again — domain, disk, credentials, config:

```sh
crossdesk uninstall     # asks first; --force skips the prompt, --dry-run previews
```

## Design summary

- **Hypervisor:** `qemu:///session` user libvirt. No Docker, no daemon
  privilege escalation; the host process keeps direct access to the
  user's Wayland/X11 sockets.
- **Transport:** gRPC with mTLS over a host-local channel — never a
  network listener. Each frame carries an `AuthContext` (peer-cert
  fingerprint + stream nonce + monotonic sequence) and is rejected on any
  mismatch: defense in depth against replay, independent of the TLS layer.
  `AF_VSOCK` is the decided transport ([DEC-0017](docs/DECISIONS.md)) and
  the code is there — but every live milestone so far has run the
  loopback-TCP bring-up path instead (`transport.bind_kind`), so that is
  what "works today" honestly means.
- **Display:** FreeRDP in RAIL mode. Per-window events
  (CREATED / FOCUS / DESTROYED) flow from the guest agent to a
  host-side window manager.
- **Storage:** opt-in, off by default. When enabled, one configured share
  is exposed to the guest — v0.1.0 defaults to `documents`
  ([DEC-0019](docs/DECISIONS.md)); whole `$HOME` is a warned opt-in and a
  single `custom` folder is config. A launch that carries a file argument
  additionally shares that file's folder for the session. Just-in-time
  VirtioFS (hot-plug the opened file's directory, detach on `ReleaseAck`)
  is the eventual tight-isolation mode and is **not** what ships in v0.1.0.
- **Recovery:** Adaptive heartbeat FSM with explicit
  HEALTHY → DEGRADED → PROBING → SOFT_RECOVERY → HARD_DESTROY states.

See [docs/GOALS.md](docs/GOALS.md) for the vision and
[docs/TECH_STACK.md](docs/TECH_STACK.md) for the stack rationale, plus
[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) for what we defend
against (and what we don't).

## Components

| Path | Language | Role |
|------|----------|------|
| [host/](host/) | Python 3.9+ | Orchestrator daemon, libvirt control, gRPC server |
| [guest/](guest/) | Rust | Windows NT service, RAIL bridge, gRPC client |
| [gui/](gui/) | Rust + CXX-Qt | Qt6/QML installation wizard |
| [proto/](proto/) | proto3 | gRPC service definitions |
| [infra/](infra/) | Shell + Python | VM bootstrap and PKI generation |

## Building

Linux host with KVM, libvirt, Python 3.9+, a Rust toolchain, and Qt6.

```sh
# Python host daemon
cd host && pip install -e .[dev] && mypy --strict src/ && pytest

# Rust guest agent (cross-compiled to Windows)
cd guest && cargo build --release --target x86_64-pc-windows-gnu

# Qt installer GUI
cd gui && cargo run -p crossdesk-gui
```

## Installing

Once a packaged release lands:

```sh
# Arch / AUR
yay -S crossdesk

# NixOS / nix-flake
nix run github:SzymonPaczos/CrossDesk

# pip (developer install)
pip install crossdesk-host
```

The package files live under [packaging/aur/PKGBUILD](packaging/aur/PKGBUILD)
and [flake.nix](flake.nix); deb / rpm hosting is post-MVP per
[docs/PACKAGING.md](docs/PACKAGING.md).

## Documentation

| Doc | What |
|-----|------|
| [PLAN.md](PLAN.md) | **What is left to v0.1.0**, and the honest state of each acceptance criterion |
| [ROADMAP.md](ROADMAP.md) | 5 phases with SPOFs called out |
| [docs/GOALS.md](docs/GOALS.md) | Vision, success criteria, non-goals |
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | Functional + non-functional, numbered |
| [docs/TECH_STACK.md](docs/TECH_STACK.md) | Why this stack |
| [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) | STRIDE per component |
| [docs/COMPETITION.md](docs/COMPETITION.md) | Where we sit in the design space |
| [docs/COMPARISON_WINAPPS.md](docs/COMPARISON_WINAPPS.md) | Deep comparison with the vendored WinApps |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Architecture decisions (ADRs) |
| [docs/GPU_PASSTHROUGH.md](docs/GPU_PASSTHROUGH.md) | GPU passthrough deliberation, decision pending |
| [docs/CROSS_PLATFORM_DEV.md](docs/CROSS_PLATFORM_DEV.md) | Mock-driven testing strategy |
| [docs/DISPLAY.md](docs/DISPLAY.md) | RAIL pipeline, Wayland-native, multi-monitor, HiDPI |
| [docs/PERIPHERALS.md](docs/PERIPHERALS.md) | Audio, clipboard, DnD, mic/cam, smartcard, printer |
| [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) | Structured logs, trace propagation, metrics |
| [docs/PERFORMANCE.md](docs/PERFORMANCE.md) | Benchmark harness and SLO enforcement |
| [docs/VERSIONING.md](docs/VERSIONING.md) | Semver, N-1 compat, Hello handshake |
| [docs/PACKAGING.md](docs/PACKAGING.md) | Distribution: deb/rpm/AUR/NixOS/PyPI |
| [docs/LIFECYCLE.md](docs/LIFECYCLE.md) | Suspend/resume coordination, systemd, autostart |
| [docs/I18N.md](docs/I18N.md) | Internationalization (English + Polish initial) |
| [docs/MVP_SCOPE.md](docs/MVP_SCOPE.md) | What ships in v0.1.0 (Phases 1–5 full) |
| [docs/EXECUTION_PLAN.md](docs/EXECUTION_PLAN.md) | Original week-by-week sequence — **frozen**; the live board is [PLAN.md](PLAN.md) |
| [.claude/backlog.md](.claude/backlog.md) | Action items, prioritized by area (P0/P1/P2) |
| [AGENTS.md](AGENTS.md) | Project map + agent workflow + file boundaries |

## Contributing

Read [AGENTS.md](AGENTS.md) — it's the navigation map *and* contains
the coding rules. Conventional Commits. Type-checked async Python on
the host (`mypy --strict`). Idiomatic Rust on the guest (`cargo
clippy`).

## License

GPL-3.0-or-later. The `third_party/winapps/` subtree is AGPLv3 and is
included for reference only — code is not copied verbatim into
CrossDesk.
