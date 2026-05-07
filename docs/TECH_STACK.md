# Technology stack & rationale

For each major choice: what we picked, what we considered, why we
picked this. Recurring criterion: type-checked async by default.

## Host process — Python 3.9+ with asyncio

| Choice | Why |
|--------|-----|
| **Python over Go/Rust/Node** | libvirt has the most mature Python bindings; D-Bus integration is trivial; asyncio is in the stdlib; `mypy --strict` gives us types where we want them; iteration speed beats compiled languages for orchestration code. |
| **asyncio over thread pool** | The host is I/O-bound (libvirt RPC, gRPC streams, D-Bus signals). Threads add lock complexity for no throughput gain. |
| **mypy --strict** | Catches the bug classes that "Python is slow because no types" complaints actually point to. Necessary when the host orchestrates many concurrent state machines. |
| **grpcio + grpcio-tools** | gRPC's official Python implementation. Tonic on the Rust side speaks the same wire format. |

**Considered and rejected:**
- **Rust for the host** — would force native libvirt bindings (less
  mature) and a heavier build on the user's machine. The host has more
  I/O coordination than CPU-bound work.
- **Go for the host** — solid choice, but we lose mypy's expressive
  types and Python's async ecosystem. Single-language vs. dual-language
  pays back when a contributor wants to fix a host bug without
  learning Rust.

## Guest agent — Rust with tokio + tonic + windows-rs

| Choice | Why |
|--------|-----|
| **Rust over C++/C#** | Memory safety in NT-service code. windows-rs gives us idiomatic Win32 access. tokio is the natural async runtime for tonic. |
| **tonic over grpc-cpp/grpc-csharp** | Pure-Rust gRPC. Same proto codegen story as the host. |
| **windows-rs over winapi-rs** | Microsoft-maintained, generated from official metadata, kept current with Windows SDK. |
| **NT service over user-space agent** | Starts before user login, survives reboots, runs with appropriate privilege. Required for some discovery and credential ops. |

**Considered and rejected:**
- **C++ guest** — manual lifetime management around COM interfaces is
  exactly what Rust's borrow checker is for.
- **C# / .NET guest** — startup overhead is meaningful for a
  heartbeat-tight agent; CLR runtime adds dependency to ship.
- **Python guest** — Windows Python service experience is rough;
  cross-compile from Mac is impractical.

## GUI — Qt6 / QML via CXX-Qt

| Choice | Why |
|--------|-----|
| **Qt6 over GTK4/Electron/Tauri** | Mature accessibility, polished native look on KDE and reasonable on GNOME, no Chromium baggage, single-deployment-unit. |
| **QML over Qt Widgets** | Declarative UI ages better; designers can iterate without C++ rebuilds. |
| **CXX-Qt** | Lets the GUI live in the same Rust workspace as the guest agent's shared types. |

**Considered and rejected:**
- **Electron** — bundle size, RAM cost, and Chromium attack surface
  unjustified for a wizard with a status panel.
- **GTK4** — fine for GNOME, looks alien on KDE which is many of our
  users.
- **Tauri** — promising but Qt6's accessibility and embedded media
  story is more mature today.

## Transport — gRPC over AF_VSOCK with mTLS + per-frame AuthContext

| Choice | Why |
|--------|-----|
| **AF_VSOCK over TCP loopback** | Skips the network stack entirely. No firewall in the path, no `netstat` exposure, no port allocation. Linux ↔ guest QEMU only — exactly the topology we have. |
| **gRPC over raw protobuf / REST** | Bidirectional streaming is first-class. tonic + grpcio interop is well-trodden. Codegen story for both languages. |
| **mTLS over plain TLS** | Both ends authenticated cryptographically. Defends against guest-side impersonation if the AF_VSOCK CID space is ever shared. |
| **Per-frame AuthContext** | Defense in depth: even if mTLS is bypassed (or the CID collides), each frame carries fingerprint + nonce + sequence and is rejected on mismatch. Our security claim depends on this layer. |

**Considered and rejected:**
- **virtio-serial** — older transport, less ergonomic, no native gRPC
  integration.
- **TCP loopback** — adds the network stack and firewall to the trust
  path. WinApps does this and pays for it in their threat model.
- **TLS-only auth** — TLS handshake gates the connection but does not
  gate per-frame replay. AuthContext is what closes that gap.

## VM hypervisor — libvirt qemu:///session (no Docker)

| Choice | Why |
|--------|-----|
| **libvirt over direct QEMU CLI** | XML-based domain definition, snapshot management, hot-plug API, well-documented Python bindings. |
| **`qemu:///session` over `qemu:///system`** | Runs as the user. No daemon root. Direct access to the user's Wayland/X11 sockets. Smaller blast radius. |
| **No Docker / Podman / dockur/windows** | See `docs/DECISIONS.md` DEC-0007. Privileged daemon, additional layer, kills VSOCK transparency. |

**Considered and rejected:**
- **Direct QEMU CLI** — we'd reimplement libvirt's lifecycle
  management. Not worth it.
- **`qemu:///system`** — needs root, complicates display socket
  access, adds a daemon to the security model.
- **Docker** — see DEC-0007.

## VM bootstrap — autounattend.xml + secondary OEM disk

| Choice | Why |
|--------|-----|
| **autounattend.xml** | Microsoft's official unattended-install mechanism. No reverse engineering, no scraping. |
| **Secondary virtual floppy/CD with `agent.exe` + `*.reg`** | Standard Windows OEM customization channel. `<FirstLogonCommands>` reads from it before user login. |
| **No pre-baked images** | License + hosting cost. We help users get the official ISO; we don't redistribute Windows. |

## Filesystem sharing — JIT VirtioFS

| Choice | Why |
|--------|-----|
| **VirtioFS over 9p** | Modern, performance-oriented, supports DAX. Standard since QEMU 5.0. |
| **Just-in-time hot-plug over permanent share** | Per-file mounts are the security feature. Permanent share would expose `$HOME` for the lifetime of the VM — exactly what WinApps does and exactly what we don't want. |

## Display — FreeRDP RAIL (with Wayland-native plan)

| Choice | Why |
|--------|-----|
| **FreeRDP RAIL** | Industry-standard RAIL implementation. Multi-distro packaging. Long-term maintained. |
| **Eventually: native Wayland surface forwarding** | RAIL plus xdg-foreign / window-decoration protocol for Wayland-first systems. Documented as a follow-up; pre-MVP forces `GDK_BACKEND=x11`. |

**Considered and rejected:**
- **xrdp client wrappers** — less flexible RAIL handling.
- **VNC-style fullscreen forwarding** — defeats the "native window"
  goal.
- **Custom Wayland compositor extension** — distribution-specific; not
  portable.

## Build & packaging

| Component | Tool |
|-----------|------|
| Python host | `pyproject.toml` + `pip` (with `uv` optional for speed) |
| Rust workspaces (guest, gui) | `cargo` |
| Proto codegen | `buf` (lint, format, generate); fallback `protoc` |
| GUI Qt builds | `cargo` via CXX-Qt |
| Distribution | `deb` / `rpm` / `Flatpak` / `AUR` — decision pending in `docs/DECISIONS.md` DEC-0005 |

## What we explicitly avoid in our stack

- **Bash for orchestration logic** — see `AGENTS.md` "Coding rules"
  + `docs/DECISIONS.md` DEC-0003.
- **Polling loops** — every wait is async-event-driven.
- **TODO comments in merged code** — file an issue, link it.
- **Unscoped diffs** — a bug fix doesn't bundle a refactor.
- **Verbatim AGPLv3 code copies from `third_party/`** — re-implement
  logic in our languages.
