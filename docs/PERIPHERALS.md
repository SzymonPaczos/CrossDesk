# Peripherals & host integration

How CrossDesk forwards (or chooses not to forward) host peripherals to
Windows apps: audio, clipboard, drag-and-drop, microphone, camera,
smart cards, FIDO2, printers, and USB devices generally.

WinApps puts all of this into the user's `RDP_FLAGS` config string
where they hand-edit FreeRDP syntax. CrossDesk uses typed config
fields validated against a schema, mapped to the right FreeRDP flags
in our host code. The user never sees raw FreeRDP flags.

Default stance: **opt-in for everything that crosses the trust
boundary.** Audio and clipboard get reasonable defaults (audio off,
clipboard text-only); printers, USB, smart cards default off and
require explicit opt-in.

## Configuration model

In `~/.config/crossdesk/peripherals.toml`:

```toml
[audio]
enable = false                  # default off; opt-in
direction = "playback-only"     # "playback-only" | "playback-record" | "off"

[clipboard]
mode = "text-only"              # "off" | "text-only" | "rich"
direction = "bidirectional"     # "host-to-guest" | "guest-to-host" | "bidirectional"

[drag_and_drop]
enable = false                  # default off
direction = "host-to-guest"     # only direction we plan to support

[microphone]
enable = false                  # default off

[camera]
enable = false                  # default off

[smartcard]
enable = false                  # default off; PCSC-Lite passthrough

[printer]
enable = false                  # default off
mode = "auto"                   # "auto" | "named:<printer>"

[usb]
mode = "deny-all"               # "deny-all" | "allow-list"
allow_list = []                 # list of PCI vendor:product IDs
```

This file is loaded by the host process; each enabled item maps to
specific FreeRDP flags + libvirt domain XML adjustments at VM start.

## Audio

### Goal
Forward Windows audio output (and optionally microphone input) to
the host's PipeWire/PulseAudio so the user hears Windows app audio
through their normal Linux audio stack and can independently mute,
adjust volume, or route per-app.

### How it works
FreeRDP's RAIL audio extension (`/sound:sys:pulse` for PulseAudio,
`/sound:sys:pipewire` for native PipeWire if available, or
`/sound:sys:sdl`) connects the Windows audio session to a host-side
sink. The sink shows up in `pavucontrol` (or `wpctl` for PipeWire-
native) as a separate stream named per-app where possible.

### Per-app streaming
A specific design goal: each Windows app's audio shows up as a
separate stream in PipeWire so the user can mute Word's notification
sounds without muting Spotify. This requires:

1. Tagging the FreeRDP RAIL audio stream with the app's name
   (`PA_PROP_APPLICATION_NAME` / equivalent PipeWire metadata).
2. Per-window FreeRDP RAIL connections (which is already our model:
   each launched app gets its own FreeRDP process), so each
   produces its own PipeWire stream.

### Latency
Real-time audio over RDP has historically been jittery. FreeRDP's
audio is best-effort. Voice calls over Teams may stutter under load;
music playback usually fine. We document this honestly.

### Microphone
Bidirectional audio adds the user's microphone as a Windows audio
input device. FreeRDP `/microphone:sys:pulse`. Off by default
because it crosses the trust boundary in the dangerous direction
(host data into guest).

### Comparison
WinApps default: `/sound /microphone +home-drive`. They include
mic by default. Our default is **playback-only** — safer, opt-in
to mic per-VM via config.

## Clipboard

### Goal
Bidirectional clipboard between Linux and Windows so that Ctrl+C in
a Linux terminal can be Ctrl+V'd into Word inside a CrossDesk
window.

### Modes
- **off:** clipboard isolated. Recommended for high-trust workflows
  where the user doesn't want Windows apps to see what's on their
  Linux clipboard.
- **text-only:** plain text both directions. Default. Safe.
- **rich:** HTML, RTF, image data, file references. Convenient but
  exposes more data shape to the guest. Opt-in.

### How it works
FreeRDP `+clipboard` enables the basic channel. Rich content
requires `cliprdr` extended formats (FORMAT_FILELIST, FORMAT_HTML,
etc.). FreeRDP 3.x supports these but with quality varying by
content type.

### Edge cases
- **File references in clipboard.** Copying a file in Windows
  Explorer puts a `FORMAT_FILELIST` on the clipboard. If we forward
  this to Linux, Linux apps see it as a list of UNC paths
  (`\\tsclient\...`) which they can't resolve. Our approach: in
  `rich` mode, intercept FORMAT_FILELIST and translate to local
  paths (similar to our path-translation for command-line file
  arguments). In `text-only` mode, drop the entry.
- **Clipboard polling.** Windows polls the clipboard ~5×/s by some
  apps. We don't want this to wake our heartbeat path. FreeRDP
  manages the channel internally; our control plane stays
  unaffected.

### Comparison
WinApps doesn't expose clipboard mode as a config knob — it's
hard-coded `+clipboard` in their default flags. We offer fine-
grained control because exposing rich clipboard data is a meaningful
trust decision, not a default.

## Drag-and-drop

### Goal
Drag a file from Linux file manager into a Windows app window
(host-to-guest direction).

### How it works
FreeRDP RAIL supports drag-and-drop via the `cliprdr` channel with
`FORMAT_FILELIST` on drop. The drag is initiated by the host
compositor (Linux WM); the drop is received by the Windows app via
RAIL. Path translation applies: `/home/user/foo.docx` becomes
`\\tsclient\home\foo.docx` (or the JIT VirtioFS mount path,
depending on our final approach).

### Direction
We support **host-to-guest only** initially. Guest-to-host
drag-and-drop (drag a file from a Windows file manager onto a
Linux app) is technically possible but adds complexity to our JIT
VirtioFS model (the file would need to materialize on the host
filesystem) and is rarely useful in our productivity-app target.

### Comparison
WinApps doesn't expose DnD as a feature — users don't know it
exists. We document and surface it.

## Microphone & camera

### Goal
Allow Windows apps (Teams, Zoom, OBS) to access the host's mic
and webcam.

### How it works
- **Microphone:** FreeRDP `/microphone:sys:pulse`. Already covered
  in Audio section.
- **Camera:** FreeRDP RAIL doesn't have a native camera-redirection
  protocol that's reliable in 3.x. Two options:
  1. **USB passthrough** of the webcam at the QEMU level (libvirt
     `<hostdev>` for USB devices). Works but takes the camera away
     from Linux — host can't use it while VM is using it.
  2. **Virtual webcam software** (e.g., `obs-v4l2sink`) where Linux
     webcam is presented via a virtual device that the VM accesses.
     More complex setup but lets host and guest share.

We default to USB passthrough as the simpler path; document option 2
for users who need shared access.

### Comparison
WinApps doesn't address camera. Mic via `/microphone` default. Our
camera handling is a feature beyond their scope.

## Smart cards & FIDO2

### Goal
Forward smart card readers (corporate auth, banking) and FIDO2
hardware keys (Yubikey, etc.) to the Windows VM.

### How it works
- **Smart cards:** FreeRDP `/smartcard` with PCSC-Lite passthrough
  on the host (`pcscd` running, `libccid`, etc.). The Windows guest
  sees a virtual smart card reader; the host's pcscd handles the
  actual hardware.
- **FIDO2:** the harder case. FIDO2 keys present as USB HID
  devices. FreeRDP doesn't have a clean FIDO2 channel; the realistic
  approach is USB passthrough of the specific device when needed.

### Scope
Smart card support is corporate-workflow critical for some users
(Bank Pekao SA Office 365, government PKI auth, large enterprise).
We support it but document it as advanced — it requires PCSC-Lite
configuration and the right host packages.

FIDO2 is more niche and harder. Document but don't promise
first-class support; users on FIDO2 in Windows VMs can do USB
passthrough themselves.

### Comparison
Neither WinApps nor Cassowary mentions smart cards. Adding it makes
us viable for corporate users who can't otherwise use Linux + RDP
RAIL.

## Printer

### Goal
Forward host CUPS printers to the Windows guest so that a "Print"
in Word produces output on the user's actual printer.

### How it works
FreeRDP `/printer` with `/printer:CUPS` flag enables printer
redirection. Windows sees a "Microsoft Easy Print" generic driver
that converts to PostScript/PDF and forwards to the host. CUPS on
the host receives it and prints.

### Quality caveat
Printer redirection over RDP has been historically slow and
sometimes flaky. Generic Easy Print works for basic documents;
exotic features (duplex, stapling, color profiles) may not survive
the round-trip. Document.

### Modes
- `mode = "auto"`: forward all CUPS printers
- `mode = "named:<printer>"`: forward only a specific printer

### Comparison
WinApps doesn't expose printer config; users add `/printer` to
`RDP_FLAGS` if they need it. We default off, opt-in via typed
config.

## USB devices generally

### Goal
Pass arbitrary USB devices to the VM (serial converters, fitness
trackers, hardware programmers, etc.).

### How it works
libvirt `<hostdev>` USB block in the domain XML. We don't pass
through wholesale (that would be a security disaster); user
specifies a vendor:product allow-list:

```toml
[usb]
mode = "allow-list"
allow_list = [
  "0403:6001",  # FTDI USB-serial
  "0461:4d22",  # Logitech mouse
]
```

The host process watches USB events (via libudev) and on hotplug of
an allow-listed device, attaches it to the running VM via libvirt
`virsh attach-device`. On unplug, detach.

### Default
`mode = "deny-all"`. Users who need USB explicitly opt-in. Most
users never enable this.

### Comparison
WinApps doesn't address USB beyond the `/usb` flag. We provide
allow-list policy plus libvirt-mediated hotplug, which is more
robust.

## Sequencing of work

### MVP (Phase 4 + immediate post-MVP)
- Audio default playback-only, off by default — typed config knob
- Clipboard text-only default — typed config knob

### Post-MVP P1
- Audio per-app PipeWire tagging
- Clipboard rich-content mode with FORMAT_FILELIST translation
- Drag-and-drop host-to-guest
- Microphone (extension of audio)
- Printer redirection

### Post-MVP P2
- Smart card / PCSC-Lite passthrough
- USB allow-list with libudev hotplug attach/detach
- Camera USB passthrough
- FIDO2 (best-effort, undocumented in core; advanced setup guide)

## Threat model implications

Each peripheral that crosses the trust boundary widens the surface
the guest can attack. Documented in `docs/THREAT_MODEL.md`:

- Audio in (mic): guest can record arbitrary host audio. Off by
  default.
- Clipboard rich: guest can read host data (text/HTML/files). Off
  by default for rich; text-only is the default.
- Drag-and-drop in: guest sees dropped file path; with our JIT
  VirtioFS, guest only sees the file (not directory siblings).
- Smart card: guest can issue auth challenges to the smart card; the
  user's PIN entry is on the smart card itself, not host-mediated,
  so host PIN exposure is limited.
- USB allow-list: per-device allow-list scoped narrowly.

Default-off plus typed config means the user must consciously
enable each peripheral, with the trust implication documented.
