# Follow-ups

Items deliberately out of scope for the audit waves (commits `8eb9ace` →
`3098ea7`). Listed here so they don't get lost; each one points at the file or
phase it's blocked on.

## Build & verification

- **Windows cross-compile not verified.** macOS `cargo check --workspace`
  passes, but `x86_64-pc-windows-gnu` target is not installed locally. Add a
  CI job that runs `rustup target add x86_64-pc-windows-gnu` and
  `cargo check --target x86_64-pc-windows-gnu` against `guest/` so the
  Windows-only modules (`agent-svc/service.rs`, `agent-svc/host_uuid.rs`,
  `rail-bridge/windows.rs`) are exercised.
- **End-to-end mTLS smoke test against the new 32-byte `mount_token`.**
  Unit tests cover length-rejection (`tests/test_filesystem_service.py`).
  `tests/test_smoke_e2e.py` was green during the audit but should be
  re-read to confirm any frame it emits over the wire carries a 32-byte
  token. If it currently constructs a `MountResult`/`LockReport`/
  `ReleaseAck` without one, those frames will now be dropped silently.

## Phase work still owed

- **AF_HYPERV vsock connector** — `guest/crates/ipc-vsock/src/connector.rs`
  still dials TCP loopback. Replace `TcpStream::connect` with a real
  `WSAConnect` against `AF_HYPERV` once we leave dev. The public
  `Service<Uri>` surface is already shaped for the swap.
- **Real virtiofs mount/flush** —
  `guest/crates/fs-mount/src/mount.rs::mock_handle_mount_request` and
  `guest/crates/fs-mount/src/flush.rs::mock_generate_lock_report` /
  `mock_generate_release_ack` are placeholder stubs with the `mock_`
  prefix exactly so call sites flag them at review. Phase 5 replaces
  them with WinFSP/virtiofs-backed implementations.
- **RAIL window icon extraction** —
  `guest/crates/rail-bridge/src/events.rs` leaves `icon_png` empty.
  Phase 4: `ExtractIconExW` + PNG-encode for `KIND_CREATED` and
  `KIND_ICON_CHANGED`.

## Tech debt

- The `// type: ignore[override]` ergonomics on bidirectional gRPC
  servicers were avoided by switching to `AsyncIterator`. If a future
  grpc-stubs bump narrows the parent signature again, the override may
  resurface; keep an eye on `crossdesk_host.proto.*_pb2_grpc.pyi` after
  every regeneration.
