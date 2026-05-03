# CrossDesk: Architecture

CrossDesk runs Windows applications as native windows on a Linux desktop. A
Linux host boots a Windows VM, an in-VM agent forwards application events, and
the host renders each Windows window through FreeRDP RAIL. This document
describes the design and the constraints that shape it.

## 1. Constraints

- **No Docker.** The host runs as a regular user under `qemu:///session` so it
  keeps direct access to the user's Wayland/X11 sockets.
- **Event-driven.** Host and guest communicate through asynchronous gRPC
  streams; no polling loops on either side.
- **Zero-touch provisioning.** The Windows VM installs unattended via
  `autounattend.xml` plus a secondary virtual floppy carrying the agent.

## 2. Components

- **Host orchestrator** — Python 3.9+ (`asyncio`, libvirt API, Wayland DBus).
  Runs as a systemd user daemon.
- **Guest agent** — Rust NT service (`windows-rs`).
- **Transport** — gRPC over `AF_VSOCK`. Avoids TCP/IP and the host firewall
  entirely.
- **Display** — FreeRDP in RAIL mode. On Wayland hosts the MVP forces
  `GDK_BACKEND=x11` until native Wayland support lands.

## 3. Security and resource model

- **Just-in-time VirtioFS.** The host home directory is never mapped
  wholesale. When the user opens a file, the host hot-plugs only the parent
  directory to a guest drive and detaches it as soon as the process releases
  the handle.
- **Per-frame `AuthContext`.** Every gRPC frame carries a peer-cert
  fingerprint, stream nonce, and monotonic sequence number. The server rejects
  the stream on any mismatch — defense in depth against CID collisions and
  replay attacks, independent of the TLS layer.
- **Heartbeat and recovery FSM.** The guest emits a heartbeat every 500 ms.
  If the host misses three consecutive beats while libvirt still reports the
  VM as `Running`, the host transitions through PROBING → SOFT_RECOVERY
  (`virsh shutdown`) → HARD_DESTROY (`virsh destroy` + `virsh start`).
- **Dynamic memory.** `virtio-balloon` resizes guest RAM in response to load.

## 4. Bootstrapping

The installer attaches a secondary OEM virtual disk containing
`autounattend.xml` and `agent.exe`. `FirstLogonCommands` copies the agent into
`C:\Windows\System32\` and registers it as a service via
`sc create CrossDeskAgent`. From the next boot onward the agent starts before
user login and survives reboots.
