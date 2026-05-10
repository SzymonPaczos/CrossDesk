# Threat model

STRIDE per component. Threat actors enumerated. Mitigations and
residual risk noted per finding.

This document is normative for security-relevant changes: any change
to the security boundary or to a component's data flow should be
accompanied by a corresponding update here and an ADR in
`docs/DECISIONS.md`.

## Threat actors

| ID | Actor | Capability |
|----|-------|------------|
| TA1 | Non-CrossDesk Linux process on the same machine, same user | Reads `$HOME` unless restricted. Can attempt to connect to local sockets, read files. |
| TA2 | Malicious or buggy Windows app inside the VM | Full ring-3 access in the Windows VM. Can call our gRPC endpoints, attempt arbitrary syscalls, attempt VM escape. |
| TA3 | Local network adversary | ARP spoofing, DNS poisoning, MITM if any traffic leaves the host's local network stack. |
| TA4 | Physical adversary with disk access | Cold boot, DMA, evil maid against the unencrypted disk image, against `~/.config/crossdesk/`. |
| TA5 | Supply-chain attacker | Compromised PyPI / Cargo dependency; compromised Microsoft ISO download URL. |
| TA6 | Installer-time MITM | Network adversary during ISO download or first-boot fetches. |

## Trust boundaries

```
+-------------------------------------------------------------+
|  Linux user session (TA1 lives here)                        |
|                                                             |
|  +-----------------------------------+                      |
|  |  CrossDesk host process            |                     |
|  |  (Python, asyncio, no privilege   |                      |
|  |   escalation)                      |                     |
|  +-----------+-------------------+----+                     |
|              |                   |                          |
|       D-Bus  |        AF_VSOCK   |  libvirt session         |
|       sockets|     (mTLS+AuthCtx)|  (qemu:///session)       |
|              |                   |                          |
|  +-----------v---+    +----------v-------------+            |
|  | Wayland/X11   |    | QEMU process (user)    |            |
|  | compositor    |    +-----------+------------+            |
|  +---------------+                |                         |
|                                   | virtio + AF_VSOCK       |
+-----------------------------------|-------------------------+
                                    |
                  +=================v=========================+
                  ‖  Windows guest (TA2 lives here)           ‖
                  ‖                                           ‖
                  ‖  +-----------------------------+          ‖
                  ‖  |  Guest agent (Rust NT svc)  |          ‖
                  ‖  +-----------------------------+          ‖
                  ‖  +-----------------------------+          ‖
                  ‖  | Windows apps (RAIL clients) |          ‖
                  ‖  +-----------------------------+          ‖
                  +===========================================+
```

The double-line border around the Windows guest is the strict trust
boundary. Every byte that crosses it (in either direction) must
either:

1. Travel over the AF_VSOCK + mTLS + per-frame `AuthContext` channel
   and pass validation, or
2. Travel through libvirt's hot-plug mechanism (e.g., JIT VirtioFS
   mount-then-detach).

There are no other approved channels.

## STRIDE per component

### C1. Host process (Python daemon)

| | Threat | Vector | Mitigation | Residual |
|-|--------|--------|------------|----------|
| **S** | TA1 impersonates the host to other components | Local socket / D-Bus name squatting | Unique D-Bus name; consumers verify peer credentials via `GetConnectionUnixUser` | Low |
| **T** | TA1 modifies host config or state files | `~/.config/crossdesk/` is user-writable | Mode 0600 on secret files; atomic rename on writes | Low |
| **R** | Host can deny actions taken | Logs unsigned, replayable | Structured JSON logs with monotonic sequence numbers; trace IDs across actions | Low at single-user scale |
| **I** | Host leaks credentials to logs | `print(password)` in error paths | TTY-gated `credentials show`; structured-log redaction allow-list (no `Password` field ever serialized) | Low if redaction is enforced by lint |
| **D** | TA1 exhausts host resources | gRPC connection floods on AF_VSOCK | AF_VSOCK has no listener exposed to TA1 — only the QEMU peer can connect | Low |
| **E** | TA1 obtains host's privileges | Inherits the user's privileges only | Host runs as user; nothing to elevate to | None — no daemon root |

### C2. Guest agent (Rust NT service)

| | Threat | Vector | Mitigation | Residual |
|-|--------|--------|------------|----------|
| **S** | TA2 impersonates the agent to fool the host | Process injection inside the VM | mTLS pins the agent's cert at install time; `AuthContext.peer_cert_fingerprint` checked per frame | Low |
| **T** | TA2 modifies agent binary / config | NT service config / file replace | NT service runs as SYSTEM; `agent.exe` signed (Sigstore/EV); registry ACL restricts service config to admin | Medium — accepted; "VM compromise = lose that VM, never the host" |
| **R** | Agent can deny RPC requests it served | Unsigned per-side logs | Sequence numbers per stream; logged with trace IDs | Low |
| **I** | Agent leaks host data to other Windows processes | IPC surface inside the VM | Agent's IPC surface is the gRPC channel only; no named pipes, no shared memory, no temp files outside `%LOCALAPPDATA%\CrossDesk\` | Low |
| **D** | TA2 exhausts agent worker threads | RPC flood | tokio runtime with bounded concurrency; rate-limit `Launch` and `Discover` RPCs | Medium — possible to slow but not crash |
| **E** | TA2 elevates from ring-3 to NT SYSTEM via agent bug | RPC handler bug | Standard NT service hardening: validate every input, no env-block trust; Rust memory safety covers a class of these | Medium — bug-class risk; primary owner |

### C3. Transport (gRPC over AF_VSOCK + mTLS + AuthContext)

| | Threat | Vector | Mitigation | Residual |
|-|--------|--------|------------|----------|
| **S** | CID collision: another VM on the same host claims our CID | AF_VSOCK CID reuse | Per-frame `peer_cert_fingerprint` rejects unauthenticated CIDs | Low |
| **T** | Frame replay | Captured-then-replayed frames | `AuthContext.stream_nonce` + monotonic `sequence`; server rejects out-of-order or repeated | Low |
| **R** | One side denies sending a frame | Single-side logs | Sequence numbers + structured logs on both sides | Low |
| **I** | Eavesdrop on AF_VSOCK | Other QEMU process | TLS layer encrypts payloads; AuthContext is integrity-protected, not secret | Low |
| **D** | Flood the transport with malformed frames | Long-frame / parser DoS | Per-stream bounded buffers; first frame validated before allocation | Low |
| **E** | Code-execution bug in protobuf parser | Crafted payload | grpcio + tonic are reasonably hardened; we keep them updated | Low — bug-class risk |

### C4. VM lifecycle (libvirt qemu:///session)

| | Threat | Vector | Mitigation | Residual |
|-|--------|--------|------------|----------|
| **S** | TA1 issues `virsh` against our domain | Same-user libvirt access | libvirt session is per-user; TA1 already has these privileges | Low |
| **T** | TA1 modifies the VM disk image | Same-user file write | Nothing prevents this at the OS level | Medium — see "Out of scope" |
| **R** | Domain modifications by libvirt unsigned | Local-only logs | libvirt logs are local | Low at single-user scale |
| **I** | Disk image readable by TA1 | Same-user file read | Same as above | Medium — recommend FDE |
| **D** | TA1 destroys the VM | Same-user `virsh destroy` | No defense at OS level | Medium |
| **E** | VM escape (TA2 → host) | KVM/QEMU bug | KVM is the trust boundary; we keep QEMU updated; minimal device passthrough | Low — bug-class risk in QEMU/KVM |

### C5. Filesystem (JIT VirtioFS)

| | Threat | Vector | Mitigation | Residual |
|-|--------|--------|------------|----------|
| **S** | TA2 spoofs `MountResult` to extend a mount lifetime | Forged token | `mount_token` is 32-byte random; verified by host on every subsequent op | Low |
| **T** | TA2 writes outside the mounted directory via path traversal | `..` segments | Filesystem service rejects `..`, normalizes paths, refuses absolute paths in mount-relative ops | Low |
| **R** | Disputed file modifications | Single-side audit trail | LockReport + ReleaseAck logged with mount_token | Low |
| **I** | TA2 reads files outside the JIT mount | Cross-mount escape | Mount surface is exactly one directory at a time | Low |
| **D** | TA2 holds mounts open indefinitely | No `ReleaseAck` | LockReport expected within timeout; force-detach on heartbeat HARD_DESTROY | Low |
| **E** | n/a (no privileged FS operations exposed) | — | — | None |

### C6. Display (FreeRDP RAIL → Wayland/X11)

| | Threat | Vector | Mitigation | Residual |
|-|--------|--------|------------|----------|
| **S** | TA2 spoofs RAIL events to confuse the WM | Forged events | Events come over the same authenticated AF_VSOCK channel | Low |
| **T** | TA2 corrupts RAIL window content | Hostile pixel content | Visual content is intentionally untrusted (it's the Windows app's UI); not a security claim | n/a |
| **R** | n/a | — | — | — |
| **I** | RAIL window content readable by other Linux processes | Compositor isolation | Standard X11/Wayland isolation applies | X11 has well-known keyboard/screen-grab risks; Wayland is better. Documented. |
| **D** | TA2 spawns RAIL windows in a flood | Launch RPC abuse | Host rate-limits Launch RPC | Medium |
| **E** | n/a | — | — | — |

### C7. Configuration store (`~/.config/crossdesk/`, `~/.local/state/`)

| | Threat | Vector | Mitigation | Residual |
|-|--------|--------|------------|----------|
| **S** | TA1 spoofs config to redirect host to another VM | File rewrite | Config writable by user; TA1 has same privileges | Medium — accepted |
| **T** | TA1 modifies `vm.toml` to swap in known credentials | File rewrite | Mode 0600; loaded once at start; runtime mtime check | Medium |
| **T** | Credential drift: host `vm.toml` diverges from guest Windows password | Out-of-band password change inside the guest (gpedit, manual `net user`, malware in VM, restored snapshot) bypasses `crossdesk vm credentials rotate` two-phase commit | Pre-spawn `VerifyCredentials` RPC piggy-backed on the `OpenSession` bidi stream (host→guest); guest `LogonUserW` probe; typed `VerifyResult` with structured `repair_hint` per status; `display.session_starter.spawn_rail_with_auth_check` raises `AuthHealthCheckFailed` and aborts the FreeRDP spawn rather than letting xfreerdp fail downstream | Low — 🚧 mock guest impl today (`agent-svc/credentials.rs::mock_impl`); real `LogonUserW` pending Stage 4 / post-hardware. Until then the guarantee is "drift is detected and surfaced with an actionable hint" rather than "drift is detected against real Windows LSA" |
| **I** | TA1 reads `vm.toml` and obtains Windows password | Same-user read | Standard same-user access | Medium — recommend FDE |
| **D** | TA1 fills disk with state files | Disk fill | Same-user filesystem usage; no defense | Low — non-malicious case |
| **E** | n/a | — | — | None |

## Out of scope (explicitly not defended against)

- **Same-user adversarial Linux processes (TA1 with intent).** A
  malicious process running as the user can read `vm.toml`, modify
  the VM disk image, kill our daemon, replace `agent.exe` before
  install. Defense against this is OS-level: full-disk encryption,
  per-application sandboxing, MAC (AppArmor/SELinux). We document the
  recommendation; we don't implement it.
- **Compromised Microsoft download endpoint (TA6).** If MS's CDN
  serves a malicious ISO, our SHA256 list catches *known* hashes but a
  brand-new release would not be on the list yet. Document that users
  on first install of a brand-new Windows release should manually
  verify the ISO.
- **Compromised PyPI / Cargo dependency (TA5).** Standard supply-chain
  risk. We pin lockfiles; reproducible builds are a follow-up.
- **Side channels (TA4 with hardware access).** Cold boot, DMA, TPM
  attacks. Recommend FDE.
- **Endpoint with malware already installed on Linux (TA1 == kernel
  rootkit).** Game over. Out of scope.

## Residual risks ranked

| Rank | Risk | Owner |
|------|------|-------|
| 1 | TA2 elevates to NT SYSTEM via agent bug | Code review + Rust safety + fuzzing on the agent's RPC handlers |
| 2 | QEMU/KVM escape (TA2 → host) | Keep QEMU current; minimize device passthrough |
| 3 | TA1 reads `vm.toml` on disk | Recommend FDE; document in onboarding |
| 4 | Brand-new Windows ISO not yet hashed | Manual verification path during install |
| 5 | TA1 modifies VM disk image while VM is off | Recommend FDE; consider integrity-checking on VM start as a follow-up |

## What CrossDesk's security claim actually is

CrossDesk does not claim to defend the user against an adversary who
already runs code as the user on Linux (TA1 with intent), against
hardware-level adversaries (TA4), or against compromise of the
Windows VM itself by the user's own Windows software (TA2 within the
VM).

CrossDesk *does* claim to:

1. Never elevate beyond the user's privileges to do its job.
2. Never expose the user's `$HOME` to the Windows guest beyond the
   single file the user is actively opening.
3. Reject any frame from the guest that doesn't match the per-frame
   `AuthContext` we issued.
4. Recover deterministically from a guest that misbehaves up to and
   including a forced VM destruction without losing host-side state.

Anything else is bonus.
