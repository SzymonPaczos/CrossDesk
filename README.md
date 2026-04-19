# CrossDesk

> **Run Windows applications as native Linux desktop windows** — bridging two worlds on a single workstation.

CrossDesk is a high-performance integration layer that seamlessly connects Linux workstations and Windows environments. It uses hardware virtualization to execute Windows applications on your Linux desktop, rendering them as native windows with zero network overhead.

## ✨ Why CrossDesk?

Windows and Linux don’t have to be enemies. Instead of choosing one or running them in isolation, CrossDesk lets you leverage both ecosystems on the same machine:

- **Native Integration**: Windows apps appear as native Linux windows in your desktop environment (Wayland/X11)
- **Zero Network Overhead**: Communication between host and guest happens via CPU sockets (`vsock`), not TCP/IP
- **Hardware Optimized**: Built on QEMU/libvirt with event-driven architecture—no polling, no wasted cycles
- **Security-First**: Just-in-time resource mounting means the host directory is only accessible when needed by a specific process
- **Zero-Touch Provisioning**: Windows VMs self-install via `autounattend.xml` with automated agent deployment

## 🏗️ Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│  Linux Host                                                 │
│  ┌──────────────────────┐          ┌────────────────────┐  │
│  │ Python Orchestrator  │          │  FreeRDP RAIL      │  │
│  │ (systemd daemon)     │◄────────►│  (display server)  │  │
│  └──────────────────────┘          └────────────────────┘  │
│           ▲                                  ▲               │
│           │ gRPC over vsock                 │               │
│           │ (async streams)                 │               │
│  ┌────────┴──────────────────────────────────┴─────────┐   │
│  │  QEMU/KVM (libvirt session)                         │   │
│  │                                                     │   │
│  │  ┌──────────────────────────────────────────────┐  │   │
│  │  │  Windows Guest VM                            │  │   │
│  │  │  ┌────────────────────────────────────────┐  │  │   │
│  │  │  │ Rust NT Service Agent                  │  │  │   │
│  │  │  │ (gRPC endpoint, process manager)       │  │  │   │
│  │  │  └────────────────────────────────────────┘  │  │   │
│  │  │                                              │  │   │
│  │  │  Windows applications run here              │  │   │
│  │  └──────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Getting Started

### Requirements

- Linux host with QEMU/KVM and libvirt support
- Python 3.9+
- Rust toolchain (for building the guest agent)
- Windows ISO for guest installation

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/crossdeskgroup/CrossDesk.git
   cd CrossDesk
   ```

2. **Review the architecture documentation**
   ```bash
   cat ARCHITECTURE.md
   ```

3. **Follow the roadmap for implementation progress**
   ```bash
   cat ROADMAP.md
   ```

## 📋 Project Phases

**Phase 1: Bootstrap VM + NT Service**
- Headless Windows installation via `autounattend.xml`
- Automatic NT service registration for the Rust agent

**Phase 2: Transport & Security**
- gRPC over `vsock` with mutual TLS and per-frame authentication

**Phase 3: Session Management & Heartbeat**
- Adaptive heartbeat protocol with automatic recovery
- State machine for graceful failure handling

**Phase 4: Display Integration**
- RAIL (Remote App Integrated Locally) mode rendering
- Native Wayland/X11 window compositing

**Phase 5: Just-In-Time Storage**
- Dynamic filesystem mounting based on process needs
- Automatic cleanup and resource release

## 🏛️ Core Principles

1. **No Docker** — Direct `qemu:///session` libvirt for Wayland/X11 socket access
2. **Event-Driven Only** — Async gRPC streams, never polling loops
3. **Zero-Touch Setup** — Automated VM provisioning and agent deployment
4. **Security by Default** — JIT resource mounting, mTLS authentication, per-frame validation

## 📚 Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — System design, technology stack, security model
- **[ROADMAP.md](ROADMAP.md)** — Implementation phases and critical dependencies (SPOFs)
- **[AGENT.md](AGENT.md)** — AI development directives and code standards

## 🛠️ Development

This project maintains strict code quality standards:

- **Rust**: Idiomatic code, no `unwrap()` without justification
- **Python**: Type hints (`mypy --strict`), async-only, `black` formatting
- **Git**: Conventional Commits with clear message structure

See [AGENT.md](AGENT.md) for the full development mandate.

## 📄 License

GPL v3 or later

## 🤝 Contributing

We welcome contributions! Before submitting a PR:

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system design
2. Review [AGENT.md](AGENT.md) for code standards
3. Ensure your changes align with the [ROADMAP.md](ROADMAP.md)

## 📞 Support & Feedback

For questions, feature requests, or bug reports, please open an issue on GitHub.

---

**Status**: Active Development (Phase 1 complete, Phase 2 in progress)
