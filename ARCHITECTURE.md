# CrossDesk: System Architecture & Implementation Guide

## 0. Project Manifesto & Vision
**CrossDesk** is an uncompromising, high-performance integration layer bridging Linux workstations (Host) and Windows environments (Guest). It destroys the boundaries of virtual machines by rendering Windows applications as native Linux desktop windows.
It operates on First Principles of hardware virtualization: asynchronous event-driven architecture, zero-network overhead via CPU sockets (`vsock`), and Just-In-Time (JIT) storage allocation. 

## 1. Core Principles & Epistemic Constraints
- **No Docker.** Use native `qemu:///session` (libvirt user-space) to retain host-level Wayland/X11 socket access.
- **Event-Driven.** No polling/looping. Guest and Host communicate purely via asynchronous gRPC streams.
- **Zero-Touch Provisioning.** Windows VM is installed headless via `autounattend.xml` and secondary virtual floppy injection.

## 2. Technology Stack
- **Orchestrator (Host):** Python 3.9+ (systemd user daemon, asyncio, libvirt API, Wayland DBus parsing).
- **Guest Agent (Windows):** Rust (NT System Service, windows-rs).
- **IPC Transport:** gRPC over `vsock` (AF_VSOCK). Bypasses TCP/IP firewall rules.
- **Display Engine:** FreeRDP (RAIL mode) with `GDK_BACKEND=x11` fallback enforced for Wayland hosts (MVP phase).

## 3. Security & Resource Management
- **JIT VirtioFS Mounting:** Host `~/` directory is NOT permanently mapped. When `document.docx` is clicked, Python hot-plugs ONLY the parent directory to `X:\` via libvirt. Share is instantly destroyed when the process exits.
- **State Machine & Heartbeat:** Rust agent emits a gRPC heartbeat every 500ms. If the Python host misses 3 beats while libvirt reports VM status as "Running", the host triggers `virsh destroy` and `virsh start`.
- **Dynamic RAM:** `virtio-balloon` in QEMU scales RAM dynamically based on Guest load.

## 4. Bootstrapping Strategy
- Inject a secondary OEM virtual drive to QEMU containing `autounattend.xml` and `agent.exe`.
- Use `FirstLogonCommands` to automatically copy `agent.exe` to `C:\Windows\System32\` and execute `sc create CrossDeskAgent` to register the Rust binary as a high-privilege service.