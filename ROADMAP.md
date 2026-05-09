✅ Phase 1 — Bootstrap VM + NT Service
Foundation: qemu:///session + autounattend.xml + floppy inject
Proof: headless Windows install → agent.exe registered as NT service, starts before user login, survives reboot
SPOF: FirstLogonCommands → sc create — if SCM silently rejects the binary (missing signed driver / ACL), everything above is impossible to diagnose without RDP
Phase 2 — Transport vsock + mTLS + AuthContext
Foundation: tonic gRPC over AF_VSOCK with mTLS handshake
Proof: bidirectional Host↔Guest stream, peer_cert_fingerprint + stream_nonce + sequence verified per-frame; deliberate CID collision rejected
SPOF: AuthContext enforcement before payload processing — a single code path bypassing validation = the whole threat model collapses
Phase 3 — Control Session FSM + Adaptive Heartbeat
Foundation: ControlService.OpenSession + HeartbeatService.Channel + FSM recovery
Proof: AppLaunchRequest → AppLaunched → AppLifecycleEvent(EXITED); synthetic guest stall transitions HEALTHY → DEGRADED → PROBING → SOFT_RECOVERY → HARD_DESTROY with exponential backoff
SPOF: tuning EWMA RTT + miss_threshold — false-positive HARD_DESTROY = virsh destroy during user work (data loss); false-negative = hung session without recovery
Phase 4 — RAIL Display Integration
Foundation: RailWindowEvent → FreeRDP RAIL spawn → native Wayland/X11 window
Proof: CREATED event from Guest produces a window in the Linux compositor with correct geometry/title/icon; DESTROYED cleans up without leak
SPOF: event ordering and idempotency (CREATED before FOCUS_GAINED, no lost DESTROYED) — HWND↔Linux window state divergence = ghost windows or orphaned process
Phase 5 — JIT VirtioFS + ReleaseAck Protocol
Foundation: minimal-path share → libvirt hot-plug → Guest mount → ReleaseAck → detach
Proof: file click in Linux → share visible only to that process → app close → LockReport (0 handles) → ReleaseAck → virsh detach-device; path traversal blocked
SPOF: ReleaseAck handshake — detach before flush = corrupt write; no ReleaseAck = permanent share leak (violates the "NO permanent mount" invariant)
Phase 4.5 — GPU passthrough (post-MVP P0; decision: docs/DECISIONS.md DEC-0009)
Foundation: vfio-pci binding + libvirt hostdev + multi-GPU host (Tier 1: NVIDIA RTX 20/30/40 driver 465+, AMD RDNA2/3) → Photoshop/Premiere/AutoCAD/Blender hardware-accelerated in VM
Proof: Photoshop 4K filter runs <1s instead of >5s software rendering; end-to-end latency (RAIL CREATED → first frame) ≤ N1.1c budget
SPOF: AMD reset bug (external vendor-reset module — Tier 2 documented), legacy NVIDIA Code 43 (Tier 2 documented), single-GPU NOT SUPPORTED without Looking Glass; update docs/THREAT_MODEL.md with TA7 (malicious GPU firmware)
After Phase 4.5 — Looking Glass integration (post-Phase 4.5, P0): LG integration for Desktop-mode + reclaiming single-GPU users with hot-switch caveat. Software-rendering fallback documentation in parallel.
