# CrossDesk

Run Windows applications as native windows on a Linux desktop. The Linux host
boots a Windows VM under `qemu:///session`, runs an in-VM agent, and renders
each Windows app as a separate Wayland/X11 window via FreeRDP RAIL.

Status: pre-release. Phase 1 (VM bootstrap + NT service) is complete; Phase 2
(transport + mTLS) is in progress. See [ROADMAP.md](ROADMAP.md).

## Design summary

- **Hypervisor:** `qemu:///session` (libvirt user-space). No Docker, no daemon
  privilege escalation; the host process retains direct access to the user's
  Wayland/X11 sockets.
- **Transport:** gRPC over `AF_VSOCK` with mTLS. Each frame carries an
  `AuthContext` (peer cert fingerprint + stream nonce + monotonic sequence) and
  is validated server-side; this defends against CID collision and replay
  independently of the TLS layer.
- **Display:** FreeRDP in RAIL mode. Per-window events (CREATED / FOCUS /
  DESTROYED) are forwarded from the guest agent to a host-side window manager.
- **Storage:** Just-in-time VirtioFS. Host directories are not mapped
  permanently; libvirt hot-plugs a share when an app needs it and detaches it
  after the guest sends `ReleaseAck`.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design and threat model.

## Components

| Path        | Language     | Role                                              |
| ----------- | ------------ | ------------------------------------------------- |
| `host/`     | Python 3.9+  | Orchestrator daemon, libvirt control, gRPC server |
| `guest/`    | Rust         | Windows NT service, RAIL bridge, vsock client     |
| `gui/`      | Rust + CXX-Qt | Qt6/QML installation wizard                       |
| `proto/`    | proto3       | gRPC service definitions                          |
| `infra/`    | Shell + Python | VM bootstrap and PKI generation                  |

## Building

Requires a Linux host with KVM, libvirt, Python 3.9+, a Rust toolchain, and
Qt6.

```sh
# Python host daemon
cd host && pip install -e . && mypy --strict src/ && pytest

# Rust guest agent (cross-compiled to Windows)
cd guest && cargo build --release --target x86_64-pc-windows-gnu

# Qt installer GUI
cd gui && cargo run -p crossdesk-gui
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design and security model
- [ROADMAP.md](ROADMAP.md) — phased implementation plan with SPOF analysis
- [AGENT.md](AGENT.md) — coding rules for contributors and AI assistants

## License

GPL-3.0-or-later.
