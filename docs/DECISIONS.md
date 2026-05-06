# Design decisions

Architectural decisions with rationale, alternatives considered, and a
note on when to reconsider. Add new entries at the top. Mark superseded
decisions with **Superseded by:** linking to the newer entry; do not
delete history.

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
**Related:** `ARCHITECTURE.md` §1; `docs/THREAT_MODEL.md` §C4;
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

This is also captured as a top-level constraint in `AGENT.md`.

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
