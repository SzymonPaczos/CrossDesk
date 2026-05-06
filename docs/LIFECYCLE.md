# Lifecycle: power, suspend/resume, autostart

How CrossDesk handles the host's power events (suspend, resume,
shutdown), how the host process starts at user login, and how
autopause / virtio-balloon / heartbeat interact across these
events.

This is daily-use critical: laptops sleep, lids close, batteries
die. Without proper handling, the heartbeat FSM
(`docs/REQUIREMENTS.md` F5.1) will see a frozen guest as a "stuck"
guest and trigger HARD_DESTROY, killing a perfectly fine VM. User
wakes their laptop to find a destroyed VM.

WinApps has a `TimeSync.ps1` that polls `\\tsclient\home\.local\
share\winapps\sleep_marker` every 5 minutes and runs `w32tm
/resync` if the marker exists. That's reactive and only addresses
clock drift. We need to coordinate the entire FSM, not just clocks.

## The four event classes

1. **Host suspend** (laptop lid closes, user does Suspend, system
   suspend timeout fires). Linux freezes; QEMU process is paused
   along with everything else.
2. **Host resume** (lid opens, user wakes). Linux unfreezes; QEMU
   resumes; Windows wall-clock is now stale.
3. **Host shutdown / reboot.** Linux is going down; we want a
   graceful VM shutdown, not a forced kill.
4. **Host login (graphical session start).** User just logged in;
   we want optional VM start, not mandatory.

## D-Bus signals we listen for

`org.freedesktop.login1.Session` exposes:

- **`PrepareForSleep(true)`** — emitted ~5 seconds before suspend.
- **`PrepareForSleep(false)`** — emitted on resume.
- **`PrepareForShutdown(true)`** — emitted before shutdown.
- **`PrepareForShutdown(false)`** — emitted on cancellation (rare).

We listen via `dbus-next` (Python) on the host process's main
asyncio loop. Each signal triggers a coordinated handler.

## Suspend handler sequence

When `PrepareForSleep(true)` arrives:

1. **Pause the heartbeat FSM** to prevent false-positive
   HARD_DESTROY. The FSM enters a special `SUSPENDED` state from
   any prior state. While in `SUSPENDED`, missed heartbeats are
   ignored.
2. **Quiesce in-flight RPCs**: cancel non-critical streams (e.g.,
   long-running discovery scans), let critical ones (e.g., a
   `LaunchApp` mid-flight) complete or cancel cleanly.
3. **Issue `virsh suspend <domain>`** to pause the VM at the
   hypervisor level. The VM's CPU state is captured to RAM (not
   to disk); RAM is still allocated.
4. **Release the D-Bus inhibitor lock** (we held one to delay
   suspend until step 1-3 complete; ~100 ms typical).
5. Linux suspends. QEMU process is frozen with everything else.

Total time budget for suspend handler: 1-2 seconds. We don't want
to delay the user's laptop sleep noticeably.

## Resume handler sequence

When `PrepareForSleep(false)` arrives:

1. **Resume the VM**: `virsh resume <domain>`. CPU state restored
   from RAM, VM continues executing.
2. **Sync time**: invoke `virsh domtime <domain> --sync` (uses
   QEMU guest agent if running) or queue a `TimeSync` RPC to our
   own agent if we use it for time. Documented as the preferred
   path in `docs/COMPARISON_WINAPPS.md` (better than WinApps's
   marker-file polling).
3. **Restart heartbeat with grace period**: FSM exits `SUSPENDED`
   into `PROBING` for ~10 s, accepting that the first few
   heartbeats may be late as the guest stack is reawakening.
4. **Verify auth context**: the previous AuthContext (with stream
   nonce + sequence) may have rolled. The agent and host
   re-handshake the AuthContext on resume to ensure both sides
   have a fresh nonce.

If the heartbeat doesn't recover within the grace period, FSM
proceeds to `PROBING` → `SOFT_RECOVERY` → `HARD_DESTROY` per the
normal recovery ladder. Suspend/resume isn't a get-out-of-jail-free
card; if the guest really did die during the suspend (e.g., disk
ran out of space, BSOD), recovery still happens.

## Shutdown handler sequence

When `PrepareForShutdown(true)` arrives:

1. **Issue `virsh shutdown <domain>`** for graceful guest shutdown.
   This is `ACPI shutdown`-equivalent — the guest OS receives the
   signal and runs its shutdown sequence.
2. **Wait up to N seconds** (default 30) for the guest to finish.
3. **Fall back to `virsh destroy`** if it doesn't shut down in
   time.
4. **Persist install state** if any — flush
   `~/.local/state/crossdesk/install.state.json` to disk.
5. **Release D-Bus inhibitor**.

Don't delay the user's shutdown by more than 30 seconds. If the VM
is stubborn, force-destroy and accept the risk that Windows might
have unsaved changes (it had its chance).

## Autopause × balloon × heartbeat

Three orthogonal mechanisms that can interact badly:

**Autopause**: after N seconds of no active RAIL session, the host
suspends the VM (`virsh suspend`). RAM stays allocated; CPU goes
to zero. Wake on next `crossdesk launch`. Already in FOLLOWUPS.

**virtio-balloon**: the guest can release RAM back to the host
when it's not using all the allocated memory. The host can request
more from the guest. Dynamic right-sizing.

**Heartbeat**: 500-ms cadence ping-pong; misses ratchet the FSM.

Interaction matrix:

- **Autopause active + heartbeat**: when autopause kicks in, we
  also pause the heartbeat (similar to suspend handler — same
  state machine, `SUSPENDED` state). Otherwise the FSM would see
  the paused VM as stuck.
- **Balloon during suspend**: balloon's RAM-deflation is paused
  while the VM is paused. No interaction needed; QEMU handles it.
- **Balloon during heartbeat**: balloon-induced memory pressure
  can slow the guest momentarily. Document that brief heartbeat
  RTT spikes after balloon adjustments are expected and should
  not trigger PROBING.

Coordination: a single supervisor object in
`host/src/crossdesk_host/lifecycle/` owns the FSM state across
suspend, autopause, and balloon events. No direct interaction
between subsystems — everything goes through the supervisor.

## systemd user service

CrossDesk runs as a systemd user unit, not a system service. The
unit lives at `/usr/lib/systemd/user/crossdesk-host.service`
(or distro-equivalent), enabled per-user via `systemctl --user
enable crossdesk-host`.

Key directives:

```ini
[Unit]
Description=CrossDesk host daemon
After=graphical-session.target
PartOf=graphical-session.target
Wants=dbus.socket

[Service]
Type=notify
ExecStart=/usr/bin/crossdesk-host serve
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
```

- `After=graphical-session.target` — host needs the user's session
  active for D-Bus and Wayland/X11 socket access.
- `PartOf=graphical-session.target` — host stops cleanly when the
  user logs out.
- `Type=notify` — host signals systemd when ready (after libvirt
  connection established and gRPC server bound).

## VM autostart on host login

**Default: off.** Not every user wants their VM running every time
they log in. Booting Windows at login adds 30-60 seconds of disk +
RAM activity even if they never use the VM that session.

Opt-in via `crossdesk install --autostart` or `crossdesk vm
autostart enable`. When enabled:

- The host daemon starts the VM via `virsh start <domain>` shortly
  after connecting to libvirt.
- Heartbeat begins; FSM enters `STARTING` then `HEALTHY`.
- User can `crossdesk launch <app>` immediately without a
  perceptible delay.

When disabled (default):

- The host daemon starts but the VM stays off.
- First `crossdesk launch` triggers VM start (cold path; takes
  ~30-60 s).

`crossdesk vm autostart disable` reverses it.

## Hibernation

Hibernation (`systemctl hibernate`) writes RAM to disk and powers
off. On resume, RAM is restored from disk.

**Our handling**: same as suspend, with one caveat. The QEMU
process's RAM is snapshotted to disk along with everything else.
On resume, time may be far in the past — `domtime --sync` is more
critical than for short suspend.

If the host is hibernated for hours or days, we may want to detect
"resumed after long absence" and force a more aggressive heartbeat
re-sync (perhaps cycling through a brief `PROBING` state regardless
of whether heartbeat looks OK initially) to catch any clock-skew-
induced AuthContext sequence issues.

## Failure modes

### "Lid closed but PrepareForSleep didn't fire"

Some Linux configurations (typically server distros, or with
incomplete D-Bus setup) skip the PrepareForSleep signal. Our handler
sees no event; the laptop suspends without us pausing the FSM.
On resume, missed heartbeats trigger PROBING → SOFT_RECOVERY.

Mitigation: a heuristic "rapid heartbeat-miss followed by recovery"
detector. If heartbeat goes from healthy → 10 misses → healthy in
under N seconds (where N is short, like 30), assume we just woke
from suspend, downgrade the SOFT_RECOVERY trigger to "log a warning,
don't actually shut down."

### "User suspends, then unplugs the laptop and stores it for a week"

Normal behavior: VM resumes when laptop wakes. Time sync handles
the clock. Should work.

If the host battery died mid-suspend and the system actually powered
off, the VM disk is in whatever state it was when last written.
QEMU's RAM-state file is gone. On host boot, `crossdesk install`
state file shows the VM as last seen healthy; first start is a
normal boot, not a resume. Document this is normal.

### "User runs `systemctl --user stop crossdesk-host` while VM is running"

Stop sequence: signal SIGTERM, host responds by quiescing
in-flight work (cancel streams, flush state), gracefully shut down
via `virsh shutdown` if VM is up, exit. systemd's
`TimeoutStopSec=60` covers most cases.

If the user runs `kill -9` directly: the VM keeps running orphaned.
On next start, host detects orphaned VM via libvirt list, attaches
to it, resumes heartbeat FSM. No data loss.

## Sequencing of work

### P0 (foundation)
- D-Bus listener for `PrepareForSleep` / `PrepareForShutdown` in
  `host/src/crossdesk_host/lifecycle/`.
- FSM `SUSPENDED` state with proper transitions.
- Suspend handler: pause heartbeat, virsh suspend, release
  inhibitor.
- Resume handler: virsh resume, time sync, heartbeat restart with
  grace period.
- systemd user service unit shipped in distro packages.

### P1
- Shutdown handler: graceful virsh shutdown with timeout.
- Autopause × balloon × heartbeat coordination via single
  supervisor.
- VM autostart on login (opt-in).
- Heuristic "wake from suspend missed event" detector.

### P2
- Hibernation-specific handling (more aggressive time resync).
- Documented power profile interactions (e.g., laptop battery-saver
  policy that suspends aggressively).
