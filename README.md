# CrossDesk

Run Windows applications as native Wayland or X11 windows on a Linux
desktop. The Linux host controls a Windows virtual machine over gRPC
on `AF_VSOCK` with mTLS and per-frame authentication. A Rust NT
service inside the VM forwards window events to the host, which spawns
FreeRDP RAIL processes to render each app as its own native window.

```sh
crossdesk install            # auto-download Win11 ISO, install, register agent
crossdesk launch notepad     # Notepad appears as a native Linux window
```

**Status:** pre-release. Phase 1 (VM bootstrap + NT service) is
complete; Phase 2 (transport + mTLS) is in progress. See
[ROADMAP.md](ROADMAP.md).

## Why CrossDesk and not WinApps?

WinApps and CrossDesk both render Windows apps as Linux windows via
FreeRDP RAIL. Differences that matter:

| | WinApps | CrossDesk |
|---|---|---|
| Privileged daemon | Docker for the easy path (privileged container, `NET_ADMIN`, `/dev/kvm`) | None — `qemu:///session` runs as the user |
| Transport | RDP over TCP `127.0.0.1:3389`, TLS-only auth | gRPC over `AF_VSOCK`, mTLS + per-frame `AuthContext` |
| Filesystem exposure | Permanent `\\tsclient\home` whole-`$HOME` mount | JIT VirtioFS hot-plugged per file, detached on `ReleaseAck` |
| Implementation | 1993-line bash, no tests | Python `mypy --strict` + Rust `cargo test`, asyncio end-to-end |
| Maturity | 5+ years, ~10k stars, 91-app catalog | Pre-release |

We trade WinApps' maturity for an architecture we can defend.

Full comparison: [docs/COMPARISON_WINAPPS.md](docs/COMPARISON_WINAPPS.md).
Where we sit in the broader landscape: [docs/COMPETITION.md](docs/COMPETITION.md).

## Design summary

- **Hypervisor:** `qemu:///session` user libvirt. No Docker, no daemon
  privilege escalation; the host process keeps direct access to the
  user's Wayland/X11 sockets.
- **Transport:** gRPC over `AF_VSOCK` with mTLS. Each frame carries an
  `AuthContext` (peer-cert fingerprint + stream nonce + monotonic
  sequence) and is rejected on any mismatch — defense in depth against
  CID collision and replay independent of the TLS layer.
- **Display:** FreeRDP in RAIL mode. Per-window events
  (CREATED / FOCUS / DESTROYED) flow from the guest agent to a
  host-side window manager.
- **Storage:** Just-in-time VirtioFS. Host directories are not mapped
  permanently; libvirt hot-plugs the parent directory of an opened
  file and detaches it after the guest sends `ReleaseAck`.
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
| [guest/](guest/) | Rust | Windows NT service, RAIL bridge, vsock client |
| [gui/](gui/) | Rust + CXX-Qt | Qt6/QML installation wizard |
| [proto/](proto/) | proto3 | gRPC service definitions |
| [infra/](infra/) | Shell + Python | VM bootstrap and PKI generation |

## Building

Linux host with KVM, libvirt, Python 3.9+, a Rust toolchain, and Qt6.

```sh
# Python host daemon
cd host && pip install -e . && mypy --strict src/ && pytest

# Rust guest agent (cross-compiled to Windows)
cd guest && cargo build --release --target x86_64-pc-windows-gnu

# Qt installer GUI
cd gui && cargo run -p crossdesk-gui
```

## Documentation

| Doc | What |
|-----|------|
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
| [FOLLOWUPS.md](FOLLOWUPS.md) | Action items, prioritized by area |
| [AGENTS.md](AGENTS.md) | Project map for AI agents and new contributors |

## Contributing

Read [AGENTS.md](AGENTS.md) — it's the navigation map *and* contains
the coding rules. Conventional Commits. Type-checked async Python on
the host (`mypy --strict`). Idiomatic Rust on the guest (`cargo
clippy`).

## License

GPL-3.0-or-later. The `third_party/winapps/` subtree is AGPLv3 and is
included for reference only — code is not copied verbatim into
CrossDesk.
