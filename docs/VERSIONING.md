# Versioning & compatibility

How CrossDesk versions itself, the gRPC protocol, and the host↔guest
agent contract — and what compatibility we promise across versions.

This is what makes `crossdesk upgrade` safe to run instead of a
"wipe and reinstall" sledgehammer.

## Three things being versioned

1. **The gRPC protocol** (`proto/crossdesk/v1/*.proto`) — wire
   format between host and guest.
2. **The host package** (`crossdesk-host`) — the Python daemon and
   CLI.
3. **The guest agent** (`agent.exe`) — the Rust NT service running
   inside the Windows VM.

Each has its own version, but they coordinate via a handshake (see
below).

## Semver, with discipline

All three follow semver (`MAJOR.MINOR.PATCH`):

- **MAJOR**: breaking change to the public contract.
- **MINOR**: backwards-compatible feature addition.
- **PATCH**: backwards-compatible bug fix.

What's "public" differs per component:

### Proto schema (most strict)

- **MAJOR**: removing a field, renaming a field, changing a field's
  wire type, removing an RPC. Done only with a bump to
  `proto/crossdesk/v2/` namespace.
- **MINOR**: adding a new optional field with a reserved-and-now-
  used number. Adding a new RPC. Adding a new enum value (with
  default fallback semantics).
- **PATCH**: documentation-only changes; comment fixes.

Field numbers are reserved before use. We have already done this
once (`b43bb16: chore(proto): reserve future field numbers`) — that
discipline continues. Reserved numbers cannot be reused for other
fields.

### Host package

- **MAJOR**: breaking CLI interface change (e.g., `crossdesk launch`
  changes argument order); breaking config file schema change;
  proto MAJOR bump it depends on.
- **MINOR**: new CLI subcommand; new config field with safe default;
  proto MINOR bump consumed.
- **PATCH**: bug fix without behavior change.

### Guest agent

- **MAJOR**: agent ABI change requiring full reinstall (e.g., new
  service registration parameters, new on-disk file layout).
- **MINOR**: hot-swappable feature addition.
- **PATCH**: bug fix, hot-swappable.

## The handshake

When the host first connects to the guest agent (after VM start, or
after agent restart), both sides exchange version info as the very
first frame:

```proto
message Hello {
  string protocol_version = 1;     // semver of the proto schema, e.g., "1.4.0"
  string host_version = 2;         // semver of the host package, e.g., "0.5.2"
  string agent_version = 3;        // semver of the guest agent
  string capabilities = 4;         // comma-separated feature flags
}
```

Sent in both directions. Each side decides whether to proceed,
proceed-with-warning, or refuse based on the rules below.

## Compatibility matrix

The host follows an N-1 minor rule: it accepts agents at its own
minor version or one minor version below. Same major version
required.

| Host minor | Agent minor | Result |
|------------|-------------|--------|
| 1.5 | 1.5 | accept |
| 1.5 | 1.4 | accept (host knows agent is older; degrades gracefully) |
| 1.5 | 1.3 | refuse — too old; recommend `crossdesk upgrade` |
| 1.5 | 1.6 | refuse — agent newer than host; user upgrades host first |
| 1.5 | 2.0 | refuse — major mismatch; full reinstall required |
| 0.x | * | development; refuse on any mismatch (prerelease) |

The same matrix applies to the proto version inside the Hello
message: host accepts proto N-1 minor.

In a refusal case, the host emits a structured error pointing the
user at the right command:

```
Error: incompatible CrossDesk versions.
  Host:  v1.5.2 (proto v1.5.0)
  Agent: v1.3.0 (proto v1.3.0)
The agent is too old to talk to this host. Run:
  crossdesk upgrade
to update the in-VM agent without reinstalling Windows.
```

## `crossdesk upgrade` (already in FOLLOWUPS)

The upgrade command:

1. Updates the host package via the user's installer mechanism
   (apt/dnf/pacman/pip/etc.).
2. Connects to the guest, exchanges Hello messages.
3. If agent version < host version (within MAJOR):
   - Streams the new `agent.exe` to the guest via
     `ControlService.UpgradeAgent` RPC.
   - Agent stages the new binary to a temp path, restarts the NT
     service, exchanges a new Hello.
   - Host verifies the new agent version is what was sent.
4. If MAJOR mismatch: prints "full reinstall required" with `crossdesk
   uninstall && crossdesk install` instructions.

Risk: hot-swap of the agent while the heartbeat is in flight. Plan:
the upgrade flow puts the FSM into a special `UPGRADING` state that
suppresses HARD_DESTROY for a configurable window (default 60 s).
Heartbeat resumes automatically after the new agent is up.

## Capabilities flags

A capabilities string in the Hello message lets us add features
without bumping versions:

```
capabilities="rail,vsock,jit-virtiofs,credential-rotate"
```

Each feature flag is documented; the host queries
`agent_capabilities.has("jit-virtiofs")` before enabling that
feature for that session.

This lets us roll out experimental features as opt-in flags without
proto bumps:

```
capabilities="rail,vsock,credential-rotate,exp:gpu-passthrough"
```

The `exp:` prefix marks a flag as experimental — its semantics may
change before promotion to a stable flag.

## CLI versioning

`crossdesk` subcommands (top-level): `install`, `launch`, `vm`,
`logs`, `metrics`, `doctor`, `uninstall`, `upgrade`, etc.

CLI is stable in v1.x: argument order, flag names, exit codes
documented and held constant. Breaking changes are v2 with a
deprecation period.

Subcommand-specific behavior may evolve within v1.x via additive
flags. New flags must have safe defaults.

## Configuration file schema

`~/.config/crossdesk/*.toml` schema has the same versioning story:

- Adding optional fields is MINOR.
- Removing or renaming fields is MAJOR.
- The host migrates older configs on read where reasonable
  (e.g., reading a v1.0 vm.toml from a v1.5 host); records the
  migration in logs; offers `crossdesk config migrate` to commit
  the migration to disk.

## When we will need MAJOR bumps

Reasonable major-version events:

- Replacing `AF_VSOCK` transport with something else (unlikely but
  possible if a better mechanism appears).
- Replacing the AuthContext frame structure (e.g., adopting a
  different replay-defense scheme).
- Restructuring the agent's NT service layout in a way that needs
  a clean install.

We will not bump majors casually. The N-1 minor compatibility window
has to be wide enough that a user upgrading once a quarter doesn't
hit majors.

## Implementation phasing

### P0 (foundation, comes early)
- `Hello` message added to proto with `protocol_version`,
  `host_version`, `agent_version`, `capabilities` fields.
- Handshake logic on connect, on both sides.
- Compatibility matrix enforcement with structured error messages.
- Versioning policy documented (this file).

### P1
- `crossdesk upgrade` agent hot-swap path (already in Operations
  FOLLOWUPS — extend with handshake-aware sequencing).
- Capabilities flag system, with documented flag inventory.
- `crossdesk config migrate` for config-schema bumps.

### P2
- Deprecation tracking: when a MINOR adds a field that obsoletes
  an older one, surface a warning at startup until removed in a
  MAJOR.
- `crossdesk version` command that shows host + agent versions
  side-by-side and warns of mismatch.

## What WinApps does for comparison

WinApps does not version anything. Re-running `setup.sh` overwrites
the existing install. There's no upgrade path; users either
manually compare files or wipe and re-install. This is the bar we
are above.

dockur/windows has its own versioning for the container image
(`ghcr.io/dockur/windows:11`) but that is the container, not the
WinApps tooling itself. Mismatches between WinApps and dockur
versions are silent until something breaks at runtime.
