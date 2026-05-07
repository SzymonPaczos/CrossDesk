# Cross-platform development & testing strategy

How we build and test CrossDesk on a Mac (or any host without
KVM/libvirt/AF_VSOCK) for the periods when we have no Linux hardware,
and how the same scaffolding pays off long-term as the test
foundation.

This document is the answer to two related questions:

1. We are physically on macOS for ~1 month with no access to a Linux
   host with KVM. Can we still ship code we trust? (Yes, with
   mock-driven design from day one.)
2. After we get hardware, do we throw the mocks away? (No. The mocks
   are unit-test fixtures forever; they remove integration-test
   flakiness from CI.)

## The problem

CrossDesk's runtime depends on three Linux-only kernel/userspace
features:

- **AF_VSOCK** — the kernel socket family for host↔guest VM
  communication. Linux has it; macOS does not, Windows does not (in a
  cross-compatible way).
- **libvirt** — Linux-only. `qemu:///session` is what we drive. macOS
  has libvirt packages but no usable hypervisor backend behind them.
- **KVM** — Linux kernel hypervisor. Doesn't exist outside Linux.

Plus several tools that are Linux-or-Windows-only:
- FreeRDP RAIL (built for Linux/X11/Wayland)
- D-Bus session bus (Linux desktop standard)
- Wayland and X11 compositors

Without a strategy, "develop on macOS" means "write code blind." With
a strategy, ~80% of our code can be written, type-checked, and unit-
tested on macOS, with the remaining ~20% (the actual hypervisor
calls and real network paths) deferred to integration testing on
Linux hardware.

## Strategy: trait/protocol abstraction with real + mock implementations

For every Linux-only or Windows-only dependency, we define a trait
(Rust) or Protocol (Python) at the API boundary. The host code uses
the trait, never the concrete implementation directly. We ship two
implementations: the real one (Linux runtime) and the mock one
(everywhere we test).

### Components requiring abstraction

| Component | Real | Mock |
|-----------|------|------|
| Transport (`AF_VSOCK` socket) | `tokio::net::VsockStream` (Rust) / `socket.socket(AF_VSOCK)` (Python) | TCP loopback with fake handshake to simulate VSOCK semantics |
| Libvirt client (host side) | `libvirt-python` real bindings | `MockLibvirtClient` returning canned domain XML and accepting all lifecycle commands as no-ops |
| FreeRDP invocation | `subprocess.exec(['xfreerdp', ...])` | `MockFreeRDPInvocation` that records argv to a file and returns immediately |
| Guest agent (from host's POV) | tonic gRPC server in the Windows VM | `MockGuestAgent` — in-process tonic stub |
| Filesystem service (libvirt hot-plug) | real libvirt `attach-device` / `detach-device` | `MockFilesystem` that tracks mount/unmount via in-memory state |
| D-Bus session signals | real `dbus-next` listening on `org.freedesktop.login1` | `MockDBus` that emits scripted suspend/resume events |
| Windows registry (guest side) | real `windows-rs` `RegOpenKeyExW` | `MockRegistry` with a builder API for canned keys |

### Naming and placement

- Rust: trait in the same module as its real implementation.
  `MockTransport` lives in `guest/crates/ipc-vsock/src/mock.rs`,
  gated behind `#[cfg(any(test, feature = "mock"))]`.
- Python: Protocol class in
  `host/src/crossdesk_host/abstractions/<component>.py`, with the
  real implementation in
  `host/src/crossdesk_host/<component>/__init__.py` and the mock in
  `host/src/crossdesk_host/<component>/mock.py`. Mocks are not
  imported in production paths.

### Mock fidelity rules

A mock that drifts from reality is worse than no mock. Rules:

1. **Mocks must enforce the same invariants as the real
   implementation.** `MockVsockTransport` must reject frames missing
   `AuthContext` exactly the way the real one does. If the real one
   rejects a 31-byte `mount_token` (real one accepts only 32 bytes),
   the mock must reject it too.
2. **Mocks must fail in the same shape.** If `libvirt.connectOpen()`
   raises `libvirt.libvirtError` on a missing daemon, the mock raises
   the same exception type when configured to simulate that
   condition.
3. **Mocks expose hooks for failure injection.** Tests want to
   simulate "vsock connection drops mid-stream" or "libvirt domain
   start fails." The mock's API should make these one-line.
4. **Mocks have minimal state.** Don't reimplement libvirt's full XML
   processor in the mock. Track just enough state to satisfy our
   client code's assumptions.

## In-process integration test

Once the abstractions exist, we can run host and guest code in a
single Python+Rust test harness:

- Python host instantiates `MockVsockTransport` and connects it to a
  Rust guest process via stdin/stdout (or a shared TCP loopback
  socket bound by the test harness).
- The Rust guest is launched via `cargo run --features=mock` with
  `MockTransport` listening on the same socket.
- Both sides go through the real protocol (gRPC + AuthContext + mTLS
  with test certs) over the mock transport.
- Tests exercise full flows: `Installer.run() → MockLibvirt confirms
  domain start → MockGuestAgent registers → host issues
  Launch(notepad) → MockFreeRDP records the argv → host observes
  RailWindowEvent(CREATED)`.

This catches:
- Wire-format mismatches between host and guest (~80% of cross-side
  bugs)
- Concurrency issues in our async code
- AuthContext validation bugs
- State machine transition errors

This does not catch:
- Real libvirt edge cases (storage allocation failures, race
  conditions in domain lifecycle)
- Real Windows behavior (driver loading order, RDP server startup
  timing)
- Real FreeRDP protocol quirks (codec negotiation, RAIL window
  ordering edge cases)

The latter requires a Linux+KVM smoke test on real hardware.

## CI matrix

GitHub Actions matrix from day one:

```yaml
jobs:
  python-host:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
    steps:
      - cargo install / pip install
      - mypy --strict src/
      - pytest

  rust-guest-cross-compile:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
    steps:
      - rustup target add x86_64-pc-windows-gnu
      - cargo check --workspace --target x86_64-pc-windows-gnu
      - cargo test --workspace --features mock  # tests run on host arch

  in-process-integration:
    runs-on: ubuntu-latest
    steps:
      - python harness drives Python host + spawned Rust guest
      - end-to-end mock smoke test

  linux-kvm-smoke (optional, conditionally):
    runs-on: self-hosted-with-kvm
    if: github.event_name == 'pull_request' && labeled
    steps:
      - actual libvirt + qemu boot of a small Windows test VM
      - real RPC round-trips
      - happens only when explicitly requested via PR label
```

The `linux-kvm-smoke` runner doesn't exist yet (no hardware). We
plumb the workflow file regardless so it's ready when hardware
arrives.

## Cross-compile setup on macOS

For Rust components targeting Windows, we use `cross-rs`
(Docker-based, runs on Apple Silicon and Intel Macs):

```sh
brew install --cask docker
cargo install cross --git https://github.com/cross-rs/cross
cd guest
cross build --release --target x86_64-pc-windows-gnu
```

Alternative: native MinGW via Homebrew (`brew install
mingw-w64`). Faster than cross-rs but doesn't reproduce the Linux CI
toolchain exactly. Use `cross` as the source of truth; native MinGW
for fast iteration.

For Python, no cross-compile needed — pure asyncio code runs on
macOS. The only Python-Linux dependency is `libvirt-python` which
should be `extras` in `pyproject.toml`, optional in dev environments
on macOS.

## Verified working command sequence (2026-05-08)

Confirmed on macOS Apple Silicon. Native MinGW is the **fast,
verified path** for local iteration:

```sh
# Prerequisites (one-time per host):
#   - Xcode Command Line Tools.
#   - Rust toolchain via rustup.
brew install mingw-w64
rustup target add x86_64-pc-windows-gnu

# Build:
cd guest
cargo build --target x86_64-pc-windows-gnu
file target/x86_64-pc-windows-gnu/release/agent.exe
# → "PE32+ executable (console) x86-64, for MS Windows"
```

The `[target.x86_64-pc-windows-gnu]` linker block in
`.cargo/config.toml` already wires MinGW; no per-build env tweaks
needed. The produced `agent.exe` lives under
`guest/target/x86_64-pc-windows-gnu/{debug,release}/agent.exe`. Its
`[[bin]]` name is `agent` (the NT service it registers as is
`CrossDeskAgent` — see [REQUIREMENTS.md F1.9](REQUIREMENTS.md)).

### cross-rs status

Cross-rs is documented above as "the source of truth for CI" but
**does not yet build this repo end-to-end**. Two issues surfaced
during verification:

1. The default cross-rs image
   `ghcr.io/cross-rs/x86_64-pc-windows-gnu:main` ships without
   `protoc`. The `proto` build script now uses
   [protoc-bin-vendored][pbv] to bundle a `protoc` binary, side-
   stepping the system-protoc requirement on every host (cross-rs,
   CI runners, fresh dev machines).
2. Cross-rs only mounts the cargo workspace directory (`guest/`)
   into the build container, so `proto/build.rs`'s relative paths
   `../../../proto/crossdesk/v1/*.proto` land **outside** the
   container mount and fail. The proto IDL lives at the repo root
   because the Python host also consumes it; resolving this needs
   either a `Cross.toml` volume mount, an upgrade to a workspace
   root at `CrossDesk/`, or a path-vendoring step. Tracked under
   "Cross-compile pipeline working from macOS" in `FOLLOWUPS.md`
   (now P1 since native MinGW is verified working).

[pbv]: https://crates.io/crates/protoc-bin-vendored

On Apple Silicon, cross-rs is also intrinsically slow because the
default image is x86_64-only and runs under emulation (~15× CPU
overhead per rustc invocation). For day-to-day Mac iteration, native
MinGW is preferred regardless. CI runners are Linux x86_64 and run
the cross-rs image natively; the protoc + path-mount issues will
need to be solved before CI can `cross build` (currently CI uses
`cargo check --target x86_64-pc-windows-gnu` with native MinGW
installed via Homebrew/apt — see `.github/workflows/ci.yml`).

### Bugs surfaced by the first cross-compile

The first run also surfaced three pre-existing bugs in
Windows-only code that `cargo check --workspace` on macOS hadn't
caught (no Windows target installed locally before this task). Fixed
in the same commit:

- `windows = "0.58"` moved `SetWinEventHook`, `UnhookWinEvent`, and
  `HWINEVENTHOOK` from `Win32::UI::WindowsAndMessaging` to
  `Win32::UI::Accessibility`; `rail-bridge`'s feature list and
  imports updated.
- `GetSystemFirmwareTable` now takes a `FIRMWARE_TABLE_PROVIDER`
  newtype instead of `u32`; `agent-svc/src/host_uuid.rs` updated.
- `define_windows_service!` macro generates `ffi_service_main` as a
  private function; the dispatcher call is now wrapped in a public
  `start_service_dispatcher()` in `agent-svc/src/service.rs`.

## Pyproject and Cargo features for mock toggling

Python:
```toml
[project.optional-dependencies]
mock = []  # mocks are pure-Python, no extra deps
linux = ["libvirt-python>=10", "dbus-next>=0.2"]

[tool.pytest.ini_options]
addopts = "--strict-markers"
markers = [
    "linux_only: requires real libvirt + KVM",
    "integration: in-process host+guest mock harness",
]
```

Rust:
```toml
[features]
default = []
mock = []  # gates MockTransport, MockLibvirtClient
windows-real = []  # gates real windows-rs paths
```

Tests on macOS run with `--features mock`; CI on Linux runs with
default features for cross-compile checks plus `--features mock` for
unit tests.

## Documentation per component

Every abstraction gets a one-paragraph "what's mocked" note in its
module docstring. Example:

```python
# host/src/crossdesk_host/abstractions/transport.py
"""
Transport abstraction.

Real implementation: AF_VSOCK socket, mTLS handshake, per-frame
AuthContext validation.

Mock implementation (transport/mock.py): TCP loopback with the same
mTLS + AuthContext stack but skipping the AF_VSOCK address family.
Mock enforces all the same validation rules; failure injection hooks
exposed via `MockTransport(simulate_drop_after_n_frames=...)`.
"""
```

When the real implementation changes, a code reviewer checks whether
the mock should change too. If divergence is intentional (e.g., real
adds a feature mock doesn't yet support), document it.

## Migration plan from current codebase

The current codebase is Phase 1 and partial Phase 2. It does not yet
have the abstractions. Work needed:

1. **Identify direct calls** to libvirt, AF_VSOCK socket APIs,
   FreeRDP subprocess, D-Bus, Windows registry. Use `grep` and
   `cargo-deny` for forbidden direct deps.
2. **Introduce trait/Protocol** in the agreed module per component.
3. **Move existing concrete code** into a "real" implementation
   module behind the trait/Protocol.
4. **Write the mock** alongside the real one.
5. **Migrate call sites** to use the trait/Protocol type.
6. **Add a test** using the mock to demonstrate the migration.

This is incremental: do one component per PR. Don't try to convert
everything at once.

Order of priority (driven by the Mac vacuum work):

1. Transport abstraction first — required for any meaningful mock
   testing.
2. Libvirt client second — required for `crossdesk install` work.
3. FreeRDP invocation third — required for Phase 4 RAIL development.
4. Filesystem (libvirt hot-plug) — Phase 5, less urgent.
5. D-Bus signals — needed for lifecycle suspend/resume work.
6. Windows registry abstraction — needed for app discovery work.

## Disk hygiene

Cargo `target/` directories grow fast — a workspace with several crates,
multiple targets, and Rust LTO can cross 5 GB of cache. Our defaults
keep growth under control:

- **Lean dev profile** (`debug = "line-tables-only"` in
  `guest/Cargo.toml` `[profile.dev]`) cuts debug-info ~50% versus the
  default `debug = true`. Stack traces still work, full source-level
  debugging is not provided — fine for our workflow.
- **Single workspace `target/` per workspace.** `guest/Cargo.toml` and
  `gui/Cargo.toml` each have their own — no per-crate target dirs.
- **Sparse crates.io registry** (`.cargo/config.toml`) cuts
  `~/.cargo/registry` size and speeds up dependency resolution.
- **Cross-compile target is contained.** `cargo build --target
  x86_64-pc-windows-gnu` adds about ~500 MB to `guest/target/x86_64-
  pc-windows-gnu/` but does not bloat the host-arch tree.

Realistic disk usage after a full local build:

| Tree | Typical size |
|------|-------------|
| `guest/target/debug/` (host arch) | 200-400 MB |
| `guest/target/release/` (host arch) | 100-200 MB |
| `guest/target/x86_64-pc-windows-gnu/release/` | 200-500 MB |
| `gui/target/debug/` | 400-800 MB (Qt is heavy) |
| `host/.venv/` | 150-250 MB |
| **Total typical** | **~1-2 GB** |

To reclaim space, run `./scripts/clean-build.sh`. It clears every Cargo
`target/` and Python cache (`.mypy_cache`, `.pytest_cache`,
`.ruff_cache`, `__pycache__`) and prints sizes before and after. The
`host/.venv/` is left alone (recreating it costs minutes); delete it
manually if needed.

If `target/` repeatedly grows beyond 5 GB, the standard culprits are:

1. Long-lived branches with old build artifacts → `cargo clean` after
   merging.
2. `incremental = true` accumulating compile fragments → run `cargo
   clean -p <crate>` for individual crates.
3. Multiple Rust toolchains installed via `rustup` (each pulls down
   ~1 GB) → `rustup toolchain list` then `rustup toolchain remove
   <unused>`.

Use `sccache` (`cargo install sccache`) with
`RUSTC_WRAPPER=sccache` if you build the same code repeatedly across
different checkouts; the shared cache pays for itself within the
first rebuild.

## What this strategy does not solve

- We still cannot run real Windows on macOS to verify Win32 behaviors.
  Mock guest agent stubs out `windows-rs` calls; their real behavior
  needs Windows or real Linux+KVM.
- Performance microbenchmarks are not portable. Heartbeat RTT
  measurements taken on a TCP loopback differ from real AF_VSOCK.
  The benchmark harness is meaningful only on Linux.
- libvirt edge cases (storage failures, network reconfig races) only
  reproduce on real libvirt.

These are the cases where we will need real hardware and accept that
some bugs are caught only by integration testing.

## Cost vs. benefit

Cost: ~2-3 weeks of refactoring to introduce the abstractions across
the existing codebase, plus ongoing discipline (every new piece of
Linux-or-Windows-only code needs a mock).

Benefit:
- ~1 month of macOS development is productive instead of placebo.
- Long-term: unit tests don't depend on the Linux runner being
  configured. CI is faster (no libvirt setup per job). Local dev on
  any OS works.
- Failure injection enables testing of error paths that real
  implementations rarely surface (e.g., "what happens when libvirt
  starts the VM but never returns success?").

Net: highly worth it. This is the kind of investment that compounds —
the longer the project runs, the more we save.
