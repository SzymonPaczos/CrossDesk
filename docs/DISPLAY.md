# Display & forwarding strategy

How CrossDesk renders Windows app windows on the Linux desktop:
RAIL pipeline, Wayland-native plan, multi-monitor handling,
HiDPI auto-detection, and the place where GPU passthrough plugs in.

GPU passthrough is a sufficiently large topic that it lives in its
own deliberation document at `docs/GPU_PASSTHROUGH.md`. This file
covers everything else about the display path.

## Pipeline overview

```
Windows app (in VM)
    ↓ renders to GPU/framebuffer (real GPU if passthrough; software if not)
Windows RDP server
    ↓ encodes per-window pixel deltas using H.264, AVC444, RFX, or NSC codec
[gRPC channel forwards RAIL window-lifecycle events: CREATED, FOCUS, MOVED, ICON_CHANGED, DESTROYED]
FreeRDP RAIL on the Linux host (one process per app instance)
    ↓ decodes per-window stream, manages window-class hint, forwards window to compositor
Linux compositor (Wayland or X11)
    ↓ Windows app appears as a native Linux window
```

Two channels carry traffic:

1. **Pixel data** — RDP TCP/UDP transport inside the VM, which
   FreeRDP terminates host-side. Despite our use of AF_VSOCK for the
   *control plane*, the *display plane* still goes through FreeRDP's
   own RDP stack. The bytes traverse the in-host loopback of the
   AF_VSOCK transport that QEMU exposes as the VM's RDP server,
   which is internally routed without leaving the host.
2. **Control / window lifecycle** — gRPC over AF_VSOCK with our
   AuthContext discipline, used for everything *except* pixel data.
   Window CREATED/MOVED/DESTROYED events that we use to coordinate
   the Linux WM are sent over this control channel, not over RDP.

This split matters: if a malicious Windows app somehow manipulates
RDP RAIL events to confuse our window manager, our gRPC channel
remains the source of truth for window lifecycle.

## Pre-MVP path: X11 RAIL via FreeRDP

For Phase 4 (and pre-MVP demos), we use FreeRDP RAIL with
`GDK_BACKEND=x11`. On Wayland sessions, this means we run through
XWayland. Reasons:

- FreeRDP's RAIL implementation is X11-centric historically.
- Window-decoration handling (titlebar, resize handles) is mature
  on X11.
- WinApps does the same thing (`third_party/winapps/`); we match
  their baseline.

Trade-offs accepted:
- XWayland adds a translation layer (~5-10 ms input latency, modest
  but measurable).
- HiDPI on Wayland with XWayland is awkward — XWayland scales
  bitmaps which looks blurry on fractional-scale outputs.
- Some Wayland-only window-management features (e.g., GNOME Shell
  Activities tagging) work less smoothly with XWayland clients.

This is acceptable for first-launch and matches WinApps quality.
Improvement is the post-MVP Wayland-native path below.

## Post-MVP path: Wayland-native RAIL

Native Wayland clients use a small set of protocols for window
management:

- **`xdg-shell`** — top-level windows, popups, surface roles.
- **`xdg-decoration-unstable-v1`** — server-side vs client-side
  decoration negotiation.
- **`xdg-foreign-unstable-v2`** — exporting/importing surface
  handles between clients (relevant for "this window is owned by
  another client" relationships).
- **`wlr-foreign-toplevel-management`** — listing toplevel windows
  (used by taskbar widgets; KDE/wlroots compositors).

For CrossDesk's Wayland-native path, the FreeRDP RAIL client needs
to:

1. Speak `xdg-shell` for each RAIL window it creates.
2. Receive `xdg-decoration` server-decoration responses and route them
   back to the Windows guest so the Windows window draws correctly
   without doubled decorations.
3. Optionally expose itself via `wlr-foreign-toplevel-management` so
   that wlroots-based panels (e.g., KDE Plasma's panel, Sway-bar)
   show CrossDesk windows correctly.

FreeRDP's Wayland support is partial as of 3.x. Our work:

- **Investigate FreeRDP 3.x Wayland support depth.** Determine which
  of the above protocols it implements natively and which we need to
  contribute.
- **Implement missing protocol handlers** in FreeRDP (upstream
  contribution preferred) or in a small CrossDesk-specific shim.
- **Migrate `host/.../display/rail_manager.py`** to launch FreeRDP
  with Wayland output by default on Wayland sessions, falling back
  to X11 if `WAYLAND_DISPLAY` is unset or if a known-broken Wayland
  compositor is detected.

Non-goal for this work: contributing a Wayland compositor extension.
Distribution-specific compositor patches don't survive long enough
to be worth maintaining.

## Multi-monitor handling

WinApps explicitly warns multi-monitor is broken (`/multimon` causes
black screens, per their README). CrossDesk does it differently
because we own both ends.

Strategy:

1. **Each RAIL window is a single Linux compositor surface.** No
   `/multimon` flag in our FreeRDP invocation. Window placement is
   per-window-per-monitor at the Linux WM level.
2. **Window placement uses WM hints** — `_NET_WM_DESKTOP`,
   `_NET_WM_STATE_FULLSCREEN`, plus `xdg_output` outputs on Wayland
   — to direct each RAIL window to its appropriate monitor.
3. **Per-monitor scale** is applied per-window via FreeRDP's
   `/scale-desktop:N`, choosing the closest of FreeRDP's supported
   scales (currently 100/140/180; FreeRDP 4.x may add finer
   granularity).
4. **Drag-between-monitors** works because the user is dragging a
   normal compositor window. The Linux WM handles the move; on
   release we re-issue `/scale-desktop:N` if the new monitor has a
   different scale.

This requires `host/.../display/rail_manager.py` to:

- Enumerate monitors via Wayland `xdg_output_manager` or X11 RANDR.
- Track per-monitor scale, resolution, position.
- Re-launch the FreeRDP RAIL session on per-monitor moves if scale
  changes (existing session can stay if scale is the same).

## HiDPI auto-detection

Three FreeRDP RAIL scale targets are supported in current FreeRDP
3.x: 100, 140, 180 percent. (FreeRDP 4.x is expected to support
arbitrary scale.) Our auto-detection logic:

1. Read the user's effective scale at launch time:
   - Wayland: `wl_output.scale` per output (integer for now;
     fractional via `wp_fractional_scale_v1` if compositor supports).
   - X11: `xrandr --query` output scaling factors.
   - GNOME: `gsettings get org.gnome.desktop.interface
     scaling-factor` plus `text-scaling-factor`.
   - KDE: `kreadconfig5 --file kdeglobals --group KScreen --key
     ScaleFactor`.
2. Map effective scale to nearest FreeRDP supported scale.
3. Launch with that `/scale-desktop:N`.
4. On monitor change events, re-evaluate per-window.

Edge cases:
- Mixed-scale multi-monitor (e.g., 4K @ 200% on monitor 1, 1080p @
  100% on monitor 2): each RAIL window scales to its current
  monitor.
- Compositor reports fractional scale (e.g., 125%): we round to the
  nearest FreeRDP scale (140% in this case) and accept the slight
  size mismatch. Document this trade-off in the user-facing docs.

This is materially better than WinApps' static config (`RDP_SCALE`
in `winapps.conf`). They picked 100/140/180 once at install, never
re-evaluated.

## RAIL window lifecycle events

Per-window events flow over our gRPC channel as `RailWindowEvent`
messages:

```proto
message RailWindowEvent {
  uint64 window_id = 1;        // guest-side HWND
  Kind kind = 2;
  string title = 3;            // for CREATED, TITLE_CHANGED
  bytes icon_png = 4;          // for CREATED, ICON_CHANGED
  Geometry geometry = 5;       // for CREATED, MOVED, RESIZED
  string app_id = 6;           // matches catalog or "ad-hoc:<exe-path>"
  enum Kind {
    CREATED = 0;
    DESTROYED = 1;
    FOCUS_GAINED = 2;
    FOCUS_LOST = 3;
    TITLE_CHANGED = 4;
    ICON_CHANGED = 5;
    MOVED = 6;
    RESIZED = 7;
    MINIMIZED = 8;
    RESTORED = 9;
  }
}
```

The host's RAIL manager translates these to compositor operations:

- **CREATED** → spawn FreeRDP RAIL process, set `WM_CLASS` to the
  app's catalog name (so the compositor groups windows correctly),
  register window with the desktop's window list.
- **FOCUS_GAINED/LOST** → coordinate with WM via X11 `_NET_ACTIVE_WINDOW`
  hints or Wayland `xdg-activation-v1`.
- **TITLE_CHANGED** → update `_NET_WM_NAME` / `xdg_toplevel.set_title`.
- **ICON_CHANGED** → update `_NET_WM_ICON` / appropriate Wayland
  protocol.
- **DESTROYED** → close FreeRDP session for that window, deregister
  from compositor. Idempotent (handle the case where DESTROYED
  arrives twice or arrives while we already closed the window).

Phase 4 work in `host/.../display/rail_manager.py`. Idempotence and
ordering tolerance (CREATED can arrive after FOCUS_GAINED if the
guest is fast and the network is delayed) are SPOFs — see
`ROADMAP.md` Phase 4 entry.

## Wayland session detection

We detect the user's session via:

```python
def detect_session() -> Literal["wayland", "x11", "unknown"]:
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"
```

For `wayland`: pre-MVP we still launch FreeRDP with
`GDK_BACKEND=x11` (XWayland fallback). Post-MVP we use native
Wayland.

For `x11`: native X11.

For `unknown`: refuse to start with a clear error directing the user
to a graphical session.

## Where GPU passthrough plugs in

When GPU passthrough is enabled (decision pending; see
`docs/GPU_PASSTHROUGH.md`), the Windows guest renders applications
to the passed-through GPU. The output is captured by the Windows
RDP server and encoded as H.264/AVC444 — exactly the same path as
without passthrough. The benefit is that the Windows side now has
real GPU acceleration; the limitation is that the host still
decodes H.264 to display.

For users with GPU passthrough who want lower latency than
H.264-encode-decode, an alternative path is to forward via Looking
Glass (IVSHMEM-based shared memory). This sacrifices RAIL (gives a
single full-desktop window instead of per-app windows) and is
out of scope as a default but could be an opt-in for power users.

If GPU passthrough is accepted (per `docs/GPU_PASSTHROUGH.md`
decision), the RAIL pipeline changes only in that the Windows
guest's compositor has GPU acceleration — no architectural change
to our display path.

## Performance budgets touching display

Reference `docs/REQUIREMENTS.md` N1:

- **N1.1a** lightweight cold launch ≤3 s p50: most of this budget is
  FreeRDP RAIL session setup (~1-1.5 s) plus Windows app launch
  (Notepad ~0.3 s, the rest is overhead).
- **N1.1b/c** budgets scale with the app and accept that a
  Photoshop launch is fundamentally slow even on bare metal.
- **Per-frame latency** target (not currently in N1, candidate for
  addition): ≤30 ms encode + decode + display for typical workloads
  on Wayland-native; ≤45 ms on XWayland.

Add a benchmark in our microbench harness (Phase 5 follow-up) that
measures RAIL window appearance time (CREATED event → compositor
draws first frame) on a known-good test app.

## Open questions to the user (recorded for review)

1. **Wayland-native RAIL is post-MVP P1?** Author's recommendation:
   yes. Pre-MVP X11 fallback works; we polish on Wayland after the
   core pipeline ships.
2. **Multi-monitor: tier 1 from day one or post-MVP?** Author's
   recommendation: working but not extensively tested at MVP; full
   polish (re-scale on monitor change, mixed-scale handling) post-
   MVP.
3. **Looking Glass as opt-in alternative for power users?** Author's
   recommendation: out of scope. Document its existence; don't
   integrate. Users wanting full-desktop GPU streaming can run
   Looking Glass directly without us.
