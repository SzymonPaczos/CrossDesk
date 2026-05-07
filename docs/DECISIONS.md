# Design decisions

Architectural decisions with rationale, alternatives considered, and a
note on when to reconsider. Add new entries at the top. Mark superseded
decisions with **Superseded by:** linking to the newer entry; do not
delete history.

---

## DEC-0008: Distribution via deb/rpm/AUR/NixOS/PyPI; no Flatpak/AppImage/Snap

**Status:** Accepted — 2026-05-07
**Owner:** release tooling, packaging
**Related:** `docs/PACKAGING.md`; `docs/DECISIONS.md` DEC-0003 (no
Docker)

### Context

Users install CrossDesk via their distro's mechanism. WinApps ships
`bash <(curl ...)`, NixOS flake, and AUR. That's adequate for their
audience but leaves out users who want `apt install` or `dnf
install` from their distro's package manager — exactly the
trust-by-default audience CrossDesk targets.

Format choice also affects security posture (sandboxed Flatpak vs
distro package), update story, and per-distro maintenance burden.

### Decision

CrossDesk ships in five formats:

1. **`deb`** for Debian-family (Debian, Ubuntu, Mint, Pop_OS).
2. **`rpm`** for RPM-family (Fedora, RHEL, openSUSE).
3. **AUR PKGBUILD** for Arch.
4. **NixOS flake** for NixOS users.
5. **PyPI** wheel for the host module (developers, headless).

Skipped formats and reasons:

- **Flatpak**: sandbox model conflicts with our requirements
  (libvirt session, D-Bus, direct compositor, multi-GB VM disk).
  Punching the holes erases the sandbox.
- **AppImage**: no value over deb/rpm; harder updates.
- **Snap**: same sandbox issue as Flatpak.
- **Docker / OCI**: contradicts DEC-0003 (no Docker).

### Alternatives considered

- **PyPI-only.** Easiest to release, but expects users to manage a
  Python environment, doesn't integrate with distro update story.
  Rejected as primary; kept as supplementary.
- **bash curl-pipe-installer (WinApps style).** Trust model is
  bad; users running unknown install scripts as their user is
  exactly the threat we want to remove. Rejected.
- **Flatpak with permissive `--filesystem=host`.** Erases the
  sandbox without simplifying anything. Rejected.

### Consequences

- (+) Native distro integration — `apt`/`dnf`/`pacman`/`nix run`.
- (+) Native update story per distro.
- (+) Trust-by-default audience served on their preferred format.
- (−) Five build paths to maintain. CI complexity.
- (−) Per-distro repos to host (Copr, PPA, OBS, AUR).
- (−) GPG/Sigstore signing per format adds setup work.

### Reconsider when

- Flatpak gains a way to expose libvirt session to a sandboxed
  app without erasing the sandbox. Then revisit Flatpak.
- A new universal Linux packaging format gains traction with our
  audience. Today's market is deb/rpm/AUR/Nix; that may shift.

---

## DEC-0007: Semver everywhere with N-1 minor compatibility window

**Status:** Accepted — 2026-05-07
**Owner:** proto schema, host package, guest agent
**Related:** `docs/VERSIONING.md`; `proto/crossdesk/v1/*.proto`;
`FOLLOWUPS.md` `crossdesk upgrade` item

### Context

WinApps does not version anything. Re-running their `setup.sh`
overwrites the install; there's no upgrade story. CrossDesk's
`crossdesk upgrade` command (in FOLLOWUPS) only works if we can
answer "is this host compatible with that agent" deterministically.

Without a versioning policy, every upgrade is a wipe-and-reinstall
which destroys the user's Windows configuration (apps installed,
settings, files). Unacceptable for a project that expects users to
spend days configuring their VM.

### Decision

Three things are versioned with semver: the proto schema (per
`proto/crossdesk/vN/`), the host package, and the guest agent. Each
has its own version. They coordinate via a `Hello` handshake on
first connect, exchanging `protocol_version`, `host_version`,
`agent_version`, and a `capabilities` string.

The host follows an **N-1 minor compatibility rule**: it accepts
agents at its minor version or one minor below, within the same
major. Major mismatches refuse with a clear message recommending
full reinstall.

Field numbers in proto schemas are reserved before use (we already
do this — commit `b43bb16`); reserved numbers cannot be reused. New
features ship as either MINOR additions (backwards-compatible) or
capability flags (opt-in within a version).

The CLI is stable in v1.x: argument order, flag names, exit codes
held constant; breaking changes go in v2 with a deprecation period.

### Alternatives considered

- **No versioning policy** (WinApps approach). Every upgrade is a
  wipe; users lose config. Rejected.
- **N-2 minor compatibility** (more permissive). Adds maintenance
  burden of supporting older agent versions for longer. Rejected
  for now; reconsider if release cadence warrants.
- **Strict same-version-only.** Forces agents to upgrade
  lockstep with hosts; bad UX for users who upgrade host but
  haven't restarted VM. Rejected.

### Consequences

- (+) `crossdesk upgrade` becomes safe — users can upgrade hosts
  without losing in-VM work.
- (+) Mismatches produce clear, actionable error messages.
- (+) Capability flags allow experimental features without proto
  bumps.
- (−) Adds a Hello handshake to every connection (microseconds, but
  measurable).
- (−) Maintaining N-1 compatibility requires testing two versions
  of the agent against current host on every release.

### Reconsider when

- A class of bugs slips through because tests don't cover the N-1
  matrix sufficiently. Solution: add a CI matrix testing host vs
  N-1 agent.
- We hit a case requiring MAJOR proto bump that's controversial
  (e.g., transport replacement). The decision-record gets a new
  ADR superseding this one only on the specific aspect that
  changes.

---

## DEC-0006: Structured logging and trace propagation from day one

**Status:** Accepted — 2026-05-07
**Owner:** every component that logs
**Related:** `docs/OBSERVABILITY.md`; `docs/DECISIONS.md` DEC-0002
(zero telemetry); `docs/REQUIREMENTS.md` N5

### Context

Every audit and bug report starts with logs. If logs are
unstructured text, support time scales linearly with log volume.
If logs are JSON with a propagated trace ID, support time is
constant: filter to the trace, read the events.

Retrofitting structured logging into a project is a refactor of
every print statement and a re-think of every error path. Doing
it from day one costs a few hours of setup and a discipline of
"don't add `print()`."

### Decision

From day one of CrossDesk implementation:

1. **Python** uses `structlog` configured to emit JSON Lines with
   mandatory fields (`timestamp`, `level`, `component`, `trace_id`,
   `span_id`, `event`).
2. **Rust** uses the `tracing` crate with `tracing-subscriber` JSON
   formatter and `tracing-opentelemetry` for trace export.
3. **Trace IDs** propagate via gRPC metadata using W3C Trace
   Context. Every CLI command starts a root trace. Every gRPC call
   (host↔guest) carries the trace.
4. **Allow-list redaction** for any field with `password`, `secret`,
   `token`, etc. in its name. Tests fail if a non-allowed field is
   logged.
5. **No `print()`** in merged code. Linter catches it (Ruff
   `T201`).
6. **Logs land on local disk only.** Optional OTLP exporter is
   opt-in (per DEC-0002).

### Alternatives considered

- **Unstructured `logging.info(...)`.** Free initially, expensive
  forever. Rejected.
- **Wait until we have integration testing pain, then refactor.**
  Always slips later than expected. Rejected.
- **Sentry / external crash reporting.** Conflicts with
  DEC-0002. Rejected.

### Consequences

- (+) Bug reports become tractable: ask user for
  `crossdesk logs --trace-id ABC...`.
- (+) Trace propagation means a single ID covers a user action
  end-to-end, including across the host↔guest boundary.
- (+) Redaction allow-list catches accidental secret logging at
  test time.
- (−) Every log statement requires choosing a structured event
  name and field set. Slightly more code than `print()`.
- (−) `tracing` and `structlog` are dependencies that must be
  configured early; getting it wrong (e.g., wrong JSON shape
  initially) is a small but real refactor cost.

### Reconsider when

- A new logging library appears with materially better ergonomics
  *and* the same structured-output discipline. Migration cost
  weighed against benefit.
- A user-visible regression is traced to logging overhead (very
  unlikely; structlog/tracing are fast).

---

## DEC-0005: Mock-driven testing as architectural foundation

**Status:** Accepted — 2026-05-07
**Owner:** all components touching Linux-or-Windows-only APIs
**Related:** `docs/CROSS_PLATFORM_DEV.md`; `AGENTS.md` "no polling" rule

### Context

CrossDesk's runtime depends on AF_VSOCK, libvirt, FreeRDP RAIL,
D-Bus, and Windows-only `windows-rs`. None of these run on macOS.
Periods of development without Linux+KVM hardware (e.g., a month on
Mac) become unproductive without a mock layer.

Even with hardware, integration-only testing makes CI slow, flaky,
and dependent on hardware-class runners.

### Decision

Every component touching a Linux-or-Windows-only API is reached
through a trait (Rust) or Protocol (Python). We ship two
implementations per trait: the real one and a mock one with
matching invariants and failure-injection hooks.

Specifically:

1. Transport (`AF_VSOCK`), libvirt client, FreeRDP invocation,
   guest agent (from host's POV), filesystem hot-plug, D-Bus
   signals, and Windows registry all sit behind a trait/Protocol.
2. Mocks enforce the same validation rules as real implementations
   (e.g., AuthContext rejection, `mount_token` length).
3. Mocks expose hooks for failure injection (drop-mid-stream,
   timeout, malformed-response).
4. CI runs unit tests on macOS and Ubuntu; in-process integration
   tests on Ubuntu; real-libvirt smoke tests gated behind a label
   on a self-hosted Linux+KVM runner (when one exists).
5. Production code never imports a mock module.

### Alternatives considered

- **Integration-only testing on a Linux runner.** Slow CI, hardware-
  bound, untestable on macOS. Rejected.
- **No mocks; "test on Linux when you have hardware."** Wastes
  development time during periods without hardware. Rejected.
- **Mocks but only at the gRPC layer.** Doesn't help components
  below gRPC (libvirt, FreeRDP); leaves gaps. Rejected for
  "every Linux-only API" instead.

### Consequences

- (+) Any developer can build, type-check, and run unit tests on
  macOS or Windows.
- (+) CI is fast; integration tests are deterministic on mocks.
- (+) Failure injection enables testing of error paths real
  implementations rarely surface.
- (−) Two implementations per component to maintain. Drift risk
  managed by reviewer discipline + module docstring noting what's
  mocked.
- (−) Real libvirt / real Windows behavior still requires hardware
  smoke tests. Mocks don't catch everything.

### Reconsider when

- A class of bugs repeatedly slips past mocks and is caught only by
  hardware smoke tests. May indicate the mock is too lenient and
  needs to enforce additional invariants (cheaper) or that the
  abstraction is at the wrong layer (more expensive: refactor).
- Hardware testing becomes cheap enough (e.g., GitHub Actions ships
  KVM-capable runners by default) that the cost-benefit shifts.

---

## DEC-0004: Performance budgets are normative

**Status:** Accepted — 2026-05-07
**Owner:** all phases
**Related:** `docs/REQUIREMENTS.md` N1; `ROADMAP.md` SPOFs

### Context

CrossDesk's UX depends on tight latencies — especially heartbeat
round-trip (gates the recovery FSM) and cold app launch (gates "feels
like a native app"). Without published budgets, "fast enough" drifts
release by release until users feel the regression and we can't say
when it happened.

### Decision

The budgets in `docs/REQUIREMENTS.md` §N1 are normative — a regression
beyond budget by more than 20% on any metric is a release blocker,
not a "nice to fix later." CI must include a microbenchmark suite
that exercises the heartbeat round-trip and the cold-launch path.

The budgets are realistic, not aspirational: they are grounded in
measured baselines from comparable setups (Windows-in-libvirt RAIL
deployments) and in physical constraints (Windows idle footprint,
FreeRDP RAIL session setup latency, virtio-balloon behavior). They
also differentiate by workload — a Notepad cold launch and a
Photoshop cold launch are scored on different scales. See N1.1a /
N1.1b / N1.1c.

Initial budget table was set aggressively (e.g., heartbeat <100 ms
p50, host RAM <100 MB) and was reset on 2026-05-07 after grounding
against measurements. The reset was a refinement of the same
decision, not a new one.

### Alternatives considered

- **No published budgets, "fix it when users complain"** — guarantees
  drift, makes regression bisects costly.
- **SLO with monthly review meetings** — overkill for a pre-MVP
  project; revisit if we reach ops scale.

### Consequences

- (+) Regressions caught at PR time, not after release.
- (+) Reviewers have a concrete number to push back with.
- (−) Adds a benchmark layer to maintain.
- (−) Some optimizations gated on having the harness running.

### Reconsider when

- Multiple users ask for a feature whose implementation can't fit the
  current budget; we may need to negotiate a budget revision rather
  than skip the feature.

---

## DEC-0003: No Docker, no privileged daemon, no `qemu:///system`

**Status:** Accepted — 2026-05-07
**Owner:** install pipeline, transport, security
**Related:** `docs/THREAT_MODEL.md` §C4; `docs/GOALS.md` NG6;
`docs/COMPARISON_WINAPPS.md`; `FOLLOWUPS.md` "Skipped on purpose"

### Context

WinApps's primary onboarding path is `docker compose up` against a
`dockur/windows` privileged container. The path is fast for casual
users but adds a privileged daemon, exposes RDP on a TCP port,
requires `NET_ADMIN` and `/dev/kvm` capabilities, and ties the project
to a third-party container image as the actual hypervisor.

CrossDesk's positioning (security-first, single-user, type-checked
async) is incompatible with that posture.

### Decision

CrossDesk runs against `qemu:///session` libvirt, as the user, with
no daemon root. Docker / Podman / `dockur/windows` are out of scope
permanently — not "later when we have time." `qemu:///system` is
also rejected because it requires root and a session-bus daemon,
removing the direct `$WAYLAND_DISPLAY` access we rely on.

This is also captured as a top-level constraint in `AGENTS.md`
"Coding rules".

### Alternatives considered

- **Optional Docker backend** — would require maintaining two threat
  models, two installation paths, two transport layers. Permanent
  fork in our codebase.
- **`qemu:///system` for shared multi-user mode** — multi-user is a
  non-goal (`docs/GOALS.md` NG4); this is unwarranted complexity.

### Consequences

- (+) No daemon root in our threat model.
- (+) Direct compositor access without bind-mounting sockets into a
  container.
- (+) AF_VSOCK works without translation through container
  networking.
- (+) JIT VirtioFS can hot-plug devices via libvirt without
  intermediating layers.
- (−) Onboarding takes longer than `docker compose up`. Mitigated by
  `crossdesk install` one-command bootstrap with auto-ISO download.
- (−) Users who already use Docker for everything can't reuse their
  setup.

### Reconsider when

- A future supported deployment (e.g., remote-mount NixOS with
  rootless privileged containers) makes the privilege story comparable
  to `qemu:///session`. Even then, only as a *secondary* path; the
  primary path stays libvirt-direct.

---

## DEC-0002: Zero telemetry, zero phone-home

**Status:** Accepted — 2026-05-07
**Owner:** host process; install pipeline; CLI
**Related:** `docs/REQUIREMENTS.md` N2.6; `docs/THREAT_MODEL.md`;
`docs/GOALS.md`

### Context

CrossDesk's positioning is security-first. Many comparable projects
ship optional telemetry, "anonymous usage analytics," or "crash
reporting that helps us improve." Each one is a network connection we
make on the user's behalf, an attack surface to defend, and a privacy
obligation.

For CrossDesk's audience — users who picked us specifically because
of the security model — even opt-in telemetry erodes trust.

### Decision

CrossDesk performs no automated outbound network connections beyond
those the user explicitly initiates:

1. ISO download from Microsoft (user opted in by running
   `crossdesk install` without `--iso-path`).
2. Windows Update inside the VM (the user's Windows VM, the user's
   choice).
3. Optional `crossdesk upgrade` when the user runs it.

There is no usage analytics endpoint, no crash report uploader, no
"check for updates on startup," no version ping, no DNS prefetch.

Logs stay local. `crossdesk logs` aggregates from the local
filesystem. If a user wants to share logs for support, they paste
them — they are not transmitted automatically.

### Alternatives considered

- **Opt-in telemetry, default off** — even the *option* would
  introduce serializers, redaction logic, and an endpoint to defend.
  Cost outweighs benefit.
- **Crash reporting via Sentry/similar** — same objection. Local crash
  dumps are sufficient.
- **Update check on launch** — undermines our claim. Users can run
  `crossdesk upgrade` when they want.

### Consequences

- (+) Trust claim is straightforward to verify: `tcpdump` on a fresh
  install should be silent except for explicit user actions.
- (+) No telemetry endpoint to maintain or defend.
- (+) GDPR / data-handling story is "we don't have any."
- (−) Less data on what users do, what fails, what releases regress.
- (−) Bug reports require users to opt in by sharing logs manually.

### Reconsider when

- Never silently. If we ever consider telemetry, it requires:
  1. A new ADR superseding this one.
  2. Default-off, explicit opt-in.
  3. Public schema of every byte transmitted.
  4. User-runnable verification that disabling it actually disables
     it (`tcpdump`-friendly).

---

## DEC-0001: Windows password lifecycle — single account, gpedit-locked, health-check fallback

**Status:** Accepted — 2026-05-06
**Owner:** install pipeline / credential management
**Related:** `FOLLOWUPS.md` items "VM credential management" and
"Auth health-check before every RAIL launch"

### Context

CrossDesk creates a Windows VM with an auto-generated password stored
in `~/.config/crossdesk/vm.toml`. If the user changes the password
manually inside Windows (Settings → Account → Sign-in options) the
host's stored value goes stale and RDP/RAIL connections fail.

WinApps doesn't address this — they document it as a limitation and
require users to update the config file by hand.

### Decision

Adopt a layered defense:

1. **Single Windows account** named `crossdesk` (clearly system-ish,
   not "user" or "Administrator").
2. **Random password generated at install**, persisted in
   `~/.config/crossdesk/vm.toml` (mode 0600).
3. **Disable "Change Password" via gpedit** in
   `<FirstLogonCommands>`: User Configuration → Administrative
   Templates → System → Ctrl+Alt+Del Options → Remove Change Password.
4. **Disable password expiration** entirely — Windows never prompts
   for a forced rotation.
5. **Auth health-check before every RAIL launch.** Host RPCs the guest
   with current credentials; on FAIL, surface a clear message
   pointing at `crossdesk vm credentials repair`.
6. **`crossdesk vm credentials repair` recovery flow** — prompts for
   the current Windows password, verifies it, atomically updates the
   host file.

### Alternatives considered

- **Option A — dual accounts (`crossdesk` service + human user).**
  WSL2-style separation. Rejected because RAIL apps would run as the
  service account, breaking Office/Adobe per-user licensing,
  OneDrive, and document-folder mapping. The single-user
  use case (one Linux user, one Windows VM) doesn't justify the
  complexity.

- **Option D — subscribe to Windows Security Event Log (4723/4724).**
  Real-time detection of password changes via guest agent. Rejected:
  gain over health-check is small (users change passwords rarely),
  requires `SeSecurityPrivilege` in the agent, and even with
  detection we still need user-driven recovery (we never know the
  new password they typed).

- **Option E — passwordless / Windows Hello-based RDP.**
  Configure the account with no password, rely on AF_VSOCK + mTLS +
  per-frame `AuthContext` as the only auth boundary. Rejected for
  MVP: opens security categories we don't want to debug (Windows
  policy interactions, RDP NLA semantics with empty passwords),
  removes a defense-in-depth layer that catches misconfigurations.

### Consequences

- (+) User can't accidentally drift the credential silently — gpedit
  prevents the easy path; health-check catches the hard path.
- (+) Single account = "natural" UX (apps see the user's profile,
  documents, licenses).
- (−) Power users who bypass gpedit (e.g., `net user crossdesk *`
  from elevated cmd) still cause drift. Health-check + repair flow
  handles it but with friction.
- (−) gpedit-imposed restriction may surprise users who expect full
  control over their VM. Document explicitly: "this is your VM, but
  CrossDesk owns its credentials. Don't change them via Windows UI;
  use `crossdesk vm credentials rotate`."

### Reconsider when

- A user reports being locked out by elevated `net user` after
  bypassing gpedit, and the repair flow proves too cumbersome
  → consider Option D (event-log watcher) for proactive detection.
- We add multi-user shared-VM support
  → must revisit: dual-account becomes the right model.
- We move to passwordless authentication elsewhere in the stack
  (e.g., Hello PIN as primary)
  → revisit Option E.
