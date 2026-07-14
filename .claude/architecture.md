# Architecture

**Last Updated:** 2026-07-14 23:12:30

> Slim snapshot for agents. The full layout, with one-line
> per-file/module descriptions, lives in
> [AGENTS.md](../AGENTS.md#repository-layout) — it's the canonical
> map and stays in sync with the directory tree because human
> contributors read it from `README.md`. This file is short on
> purpose: the pre-commit hook bumps `Last Updated:` so the timestamp
> lands inside the commit (not as drift) and an agent can see at a
> glance whether the snapshot is fresh or stale; the body is manual.

## Stack & core

- **Frontend (installer):** Qt6 / QML via CXX-Qt (Rust bindings).
- **Host (Linux):** Python 3.9+ asyncio; libvirt `qemu:///session`
  control plane; gRPC server.
- **Guest (Windows NT):** Rust NT service; `windows-rs`; tonic gRPC
  client; RAIL window-event bridge.
- **Transport:** gRPC with mTLS, plus per-frame `AuthContext` (peer
  fingerprint + nonce + monotonic seq). `AF_VSOCK` is the decided transport
  (DEC-0017 — that ADR settles AF_VSOCK vs AF_HYPERV and says nothing about
  TCP). The shipped bring-up path is loopback TCP via SLIRP, selected by the
  `transport.bind_kind = auto | tcp | vsock` seam (F4.4); every live milestone
  so far has run `tcp`. `docs/THREAT_MODEL.md` still describes AF_VSOCK as the
  live channel — parked for the owner (needs-owner §3c).
- **Display:** FreeRDP RAIL — one host process per registered app,
  rendering as a native Wayland or X11 window.
- **Storage:** opt-in file share (default off). Stage A = FreeRDP
  `/drive:` (rdpdr) redirect; Stage B = persistent virtio-fs share,
  default the whole `$HOME` (DEC-0018). Stage C JIT-per-file
  hot-plug/detach is post-1.0.

## Top-level layout

```
host/         — Python orchestrator daemon
guest/        — Rust NT service workspace
gui/          — Qt6/QML installer (CXX-Qt)
proto/        — gRPC IDL (single source of truth)
infra/        — PKI, autounattend, libvirt domain creation
docs/         — design docs, ADRs, threat model
third_party/  — vendored references (do not edit)
.claude/      — agent rules + this file + ignorefiles.md
.githooks/    — pre-commit / pre-push / post-commit
```

Full per-directory map: [AGENTS.md](../AGENTS.md#repository-layout).

## Data flow (one line)

guest agent (Windows) → AF_VSOCK gRPC + mTLS → host daemon (Linux)
→ libvirt control plane + FreeRDP RAIL spawning → native Wayland/X11
windows.

## RPC surface

All gRPC services are defined under `proto/crossdesk/v1/`:
`control`, `heartbeat`, `filesystem`, `common`. Edits to these are
restricted — see [AGENTS.md](../AGENTS.md) "File boundaries".

## Non-goals

Restated from `docs/GOALS.md` (read it for the full list):

- No Docker (per `docs/DECISIONS.md` DEC-0003).
- No polling — async streams both directions.
- File sharing is opt-in (default off); when on, the v0.1.0 default
  scope is the whole `$HOME` (DEC-0018). Stage C JIT-per-file is the
  eventual tight-isolation mode.
