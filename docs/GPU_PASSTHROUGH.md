# GPU Passthrough — analysis and accepted plan

Status: **Decision accepted — 2026-05-07** (Phase 4.5 / post-MVP P0).
See `docs/DECISIONS.md` DEC-0009.
Owner: Phase 4.5 work after MVP demo ships.
Related: `docs/THREAT_MODEL.md` §C4 (extended on implementation),
`ROADMAP.md` Phase 4.5 entry, `FOLLOWUPS.md` "GPU passthrough —
Phase 4.5".

## Accepted plan summary

1. **GPU passthrough lands as Phase 4.5 / post-MVP P0**, not in
   Phase 4 base. MVP demo ships with software rendering inside the
   VM (Notepad-class apps); GPU work is the immediate first
   follow-up that unlocks Photoshop/Premiere/AutoCAD/Blender.
2. **Tier 1 commitment:** NVIDIA RTX 20/30/40-series (driver 465+)
   and AMD RDNA2/RDNA3 (RX 6000/7000), multi-GPU systems only.
3. **Tier 2 documented, not maintained:** AMD Polaris/Vega/RDNA1
   (with `vendor-reset` upstream module), NVIDIA pre-2021 with
   hide-the-VM tricks. Docs link to upstream solutions; we don't
   ship the workarounds.
4. **Tier 3 explicitly out:** Intel Arc (wait for usage data),
   single-GPU systems (architecturally incompatible with our RAIL
   model — see §"The single-GPU showstopper" below).
5. **Looking Glass integration is a separate subsequent
   follow-up**, not part of the GPU passthrough Phase 4.5 work
   itself. LG is what unblocks single-GPU users (with
   compositor-restart hot-switch caveat) and gives Desktop-mode
   alternative for power users. See `FOLLOWUPS.md` "Looking Glass
   integration — post-Phase 4.5".
6. **Software-rendered fallback documentation** — the path that
   always works, on every hardware, for productivity apps. Not
   suitable for Photoshop/Premiere but suitable for Word/Outlook/
   Visual Studio. Documented as the universal fallback. See
   `FOLLOWUPS.md` "Software rendering fallback documentation".
7. **TA7 (malicious GPU firmware)** added to
   `docs/THREAT_MODEL.md` when GPU passthrough implementation
   lands. Placeholder documented now.

The remainder of this document is the deliberation that led to
this decision; preserved for reference and for future
reconsideration trigger conditions (see DEC-0009).

This document captures the full deliberation about GPU passthrough so
no context is lost while the user decides scope and priority.

---

## TL;DR

GPU passthrough is technically mature, would unlock the
"professional-tier" apps (Photoshop, Premiere, AutoCAD, Blender,
Fusion 360) that are currently unusable on a software-rendered VM,
but it changes scope significantly:

- **Hardware requirement:** multi-GPU systems only. Single-GPU systems
  fundamentally cannot run our "RAIL apps as native windows" model
  with passthrough simultaneously.
- **Vendor caveats:** NVIDIA modern (driver 465+) is fine; AMD
  Polaris/Vega has a reset-bug needing `vendor-reset` kernel module;
  Intel Arc is experimental.
- **Effort estimate:** ~3-4 weeks for Tier 1 (NVIDIA RTX modern + AMD
  RDNA2/RDNA3 multi-GPU), plus ~1 week each for Tier 2 vendor
  caveats.
- **Recommendation:** Post-MVP P0. MVP demo with software rendering
  works for productivity apps (Word, Outlook, etc.); GPU passthrough
  is the first major follow-on.

The user provisionally said "must-have" before reading this doc; the
final decision is parked here for next-day review.

---

## What GPU passthrough actually is, technically

A GPU is a PCIe device. Linux's `vfio-pci` framework lets us unbind a
PCIe device from its normal driver (`nvidia`, `amdgpu`, `i915`) and
bind it to a generic passthrough driver. QEMU/libvirt then exposes
that PCIe device — with its memory-mapped IO regions, MSI/MSI-X
interrupts, and DMA capability — directly to the guest VM. From
inside Windows, the GPU appears as a real PCI card. The Windows
NVIDIA/AMD/Intel driver loads against it and uses it like bare metal.

Performance: 95-99% of bare-metal in the VM. The IOMMU translates
guest-physical addresses to host-physical, so DMA from the GPU goes
through hardware-accelerated translation with negligible overhead.

This is not a CrossDesk invention. It is the same mechanism used by:

- Cloud GPU instances (AWS p4, GCP A100): they run guest VMs on
  KVM/QEMU with passed-through GPUs.
- NVIDIA DGX appliance virtualization.
- The /r/VFIO community's gaming VMs (~2014 onwards).
- VMware vSphere DirectPath I/O (same idea, different host).

The technology is mature. The hard part is **integration into our
specific UX model**.

## Hardware requirements (gating)

| Component | Requirement | Reality |
|-----------|-------------|---------|
| **CPU** | IOMMU support: Intel VT-d or AMD-Vi (also marketed as AMD IOMMU) | Every consumer CPU since ~2015 has it. Has to be enabled in BIOS — it ships disabled on some platforms. |
| **Motherboard** | Firmware exposes proper IOMMU groups | Most mid-range and up. Cheap motherboards put many devices in one group, breaking single-device passthrough without ACS-override kernel patches (out-of-tree, security-implications). |
| **GPU** | Sits in its own IOMMU group, or shares only with its audio function | Discrete GPUs typically yes. iGPU often shares with chipset → harder to pass. |

Plus kernel cmdline parameters:

```
intel_iommu=on iommu=pt vfio-pci.ids=10de:2204,10de:1aef
```
(example: NVIDIA RTX 3080 with its HDMI audio function)

Plus early binding in initramfs so `vfio-pci` claims the GPU before
`nvidia`/`amdgpu` does. The way this is done is distro-specific:

- Arch: `/etc/mkinitcpio.conf` MODULES, then `mkinitcpio -P`
- Fedora: `/etc/dracut.conf.d/`, then `dracut -f`
- Debian/Ubuntu: `/etc/initramfs-tools/modules`, then `update-initramfs -u`
- NixOS: `boot.initrd.kernelModules` + `boot.kernelParams` in
  `configuration.nix`

We will need a per-distro setup helper or detailed documentation per
distro.

## The single-GPU showstopper

This is the most important constraint and the reason GPU passthrough
fundamentally cannot be a default for CrossDesk.

If the user has only one GPU, passing it through means the Linux host
loses access to it during VM operation. The host has no display
adapter. Wayland or X11 cannot run. The console is invisible (unless
the user has a VGA framebuffer device which is rare on modern
hardware). The compositor crashes. Login screen vanishes.

There are three known workarounds, all of which **break our UX
model**:

### 1. Hot-switching (single-GPU passthrough)
- Stop X11/Wayland with `systemctl stop display-manager`
- Unbind GPU from `nvidia`/`amdgpu`, bind to `vfio-pci`
- Start the VM
- Use the VM directly via attached monitor/keyboard
- After VM stops: reverse the procedure, restart compositor

Disruptive. Screen blanks. User is logged out. Completely incompatible
with "RAIL apps appear next to Firefox in your existing session."

### 2. Software rendering fallback
- Configure host to use `llvmpipe` or `vesa` driver while VM runs
- VM gets the real GPU; host limps along on CPU rendering

Result: host compositor jitters at 5-15 FPS. RAIL window forwarding
relies on host compositor performance. Practically unusable.

### 3. Looking Glass (IVSHMEM-based shared memory)
- VM renders to its passed-through GPU
- A QEMU IVSHMEM device shares a memory region between VM and host
- Windows-side Looking Glass driver copies framebuffer to shared
  memory
- Linux-side Looking Glass client renders the VM's display in a
  window on the Linux host

This works and is a popular gaming-VM pattern. But it gives the user
**a single window containing the entire Windows desktop**, not
individual RAIL windows. It defeats the entire CrossDesk premise.

### Conclusion

For single-GPU systems, CrossDesk's model and GPU passthrough are
**mutually exclusive at the hardware level**. We will document this
explicitly and `crossdesk doctor` will refuse to set up GPU
passthrough on single-GPU hosts.

Users on single-GPU systems get software rendering inside the VM.
This is fine for Word, Excel, Outlook, Notepad, Visual Studio, and
most productivity tools. It is not fine for Photoshop, Premiere,
AutoCAD, or Blender.

## Multi-GPU scenarios (the realistic target)

Three configurations work cleanly:

### iGPU + dGPU laptop (most common scenario)
Many modern laptops have an Intel UHD or AMD APU integrated GPU plus
a discrete NVIDIA or AMD card. The Linux host runs on the iGPU; the
dGPU is passed through to the VM. Standard MUX/Optimus laptops can
sometimes do this; non-MUX laptops have additional complications
because the dGPU's outputs go through the iGPU.

### iGPU + dGPU desktop
Some Intel/AMD CPUs have integrated graphics; some motherboards route
those outputs to physical ports. If the user has an iGPU-capable CPU
and the motherboard exposes its outputs, this works the same as the
laptop case.

### Two discrete GPUs
A user with two GPU cards (e.g., a cheaper RX 6400 driving Linux and
an RTX 4070 reserved for the VM) gets the cleanest passthrough story.
This is the /r/VFIO community's preferred setup.

Performance impact on the host: minimal. The Linux host runs on its
chosen GPU at full speed; the VM runs on the other at full speed.
Memory bandwidth contention exists but is usually not noticeable.

## Vendor-specific issues

### NVIDIA

**Historical (pre-2021): Code 43.** Until 2021, NVIDIA's Windows
driver actively detected hypervisor presence (via the `HV_VENDOR_ID`
field in CPUID and other signals) and refused to load with "Error 43"
when running in a VM. Workarounds involved spoofing the hypervisor
vendor ID (`hv_vendor_id=randomstring,kvm=off` in QEMU args), and
sometimes patching the GPU's vBIOS to remove certain identifiers.

**Modern (2021+):** NVIDIA officially supports consumer GPU
passthrough as of driver 465. No spoofing needed. Just bind to
`vfio-pci`, configure `<hostdev>` in libvirt domain XML, boot the VM,
install the NVIDIA driver inside Windows. It works.

**Cards we will guarantee Tier 1:** RTX 20-series (Turing), RTX
30-series (Ampere), RTX 40-series (Ada Lovelace), RTX 50-series
(Blackwell when released). All with driver 465+.

**Cards we will support as Tier 2:** GTX 9-series (Maxwell), GTX
10-series (Pascal). These work but may need Code 43 workarounds if
the user's specific driver/Windows combination triggers it. Document
the workaround; do not auto-apply it (user opt-in).

### AMD

**The reset bug.** AMD discrete GPUs from the Polaris (RX 4xx, RX
5xx), Vega (RX Vega 56/64, Radeon VII), and partially RDNA1 (RX 5xxx)
generations have a long-standing "reset bug": after a VM shuts down,
the GPU is left in an undefined state from which the host driver
cannot recover. The host needs a full system reboot to reuse the GPU.

**Workaround:** the `vendor-reset` out-of-tree kernel module
(<https://github.com/gnif/vendor-reset>) which knows how to perform
the proper reset sequence per architecture. Mature project, works,
but:

- Out-of-tree means the user installs it manually.
- Has to be reinstalled (or DKMS-rebuilt) every kernel upgrade.
- Sometimes breaks on new kernels for a few weeks until upstream
  catches up.

**RDNA2 (RX 6000 series)**: largely fixed in firmware. Reset works
without `vendor-reset` for most cards. We treat RDNA2 as Tier 1.

**RDNA3 (RX 7000 series)**: also fine, Tier 1.

**RDNA4 (RX 8000 series, future):** expect Tier 1 if/when released.

**Cards we will guarantee Tier 1:** RX 6000 series, RX 7000 series.
Newer welcome.

**Cards we will support as Tier 2:** Polaris (RX 4xx, 5xx), Vega
(Vega 56/64, Radeon VII), RDNA1 (RX 5xxx). User installs
`vendor-reset` themselves; we document the procedure and detect
whether the module is loaded.

### Intel

**Arc series (A380, A580, A750, A770, B-series).** Brand new
discrete GPUs from 2022+. Passthrough works in principle. Less
battle-tested than NVIDIA or AMD. Some users report driver
instability. Treat as **Tier 2 experimental**.

**Intel iGPU (UHD Graphics, Iris Xe).** Usually shares an IOMMU group
with chipset/PCH devices, making clean passthrough hard. Almost
always used as the host-side adapter, not the VM-side. **Out of
scope** as a passthrough target.

### Workstation and datacenter cards

**NVIDIA Quadro / RTX A-series, Tesla, GRID:** these support SR-IOV
with NVIDIA vGPU licensing (paid). Out of scope for MVP — enterprise
customers can run our setup with traditional passthrough.

**AMD Instinct, Radeon Pro:** similar story; out of scope.

## Crucial: how GPU passthrough interacts with our RAIL model

This is the insight that's not immediately obvious and that frames
the entire decision.

In CrossDesk, the user's experience is:

```
Windows app (Photoshop in the VM)
    ↓ renders hardware-accelerated
GPU in the VM (passed through)
    ↓ output to Windows-side framebuffer
Windows RDP server (captures the framebuffer)
    ↓ encodes via H.264 / AVC444 / RFX codec
[CrossDesk gRPC channel forwards events]
FreeRDP RAIL on the Linux host
    ↓ decodes, places per-app surface in the compositor
Linux compositor (Wayland / X11)
    ↓ Photoshop appears as a native Linux window
```

**Crucial observation:** The Linux host **does not directly use** the
GPU we pass through. The pixels travel through Microsoft's RDP
encoder/decoder pipeline. Even with full GPU passthrough, the user's
visual output is RDP-encoded H.264 (or AVC444), not "raw GPU
framebuffer."

This is fundamentally different from:

- **Looking Glass:** uses shared memory (IVSHMEM) to skip
  encode/decode entirely. Latency is sub-frame. But it gives a single
  full-desktop window, not RAIL.
- **Sunshine + Moonlight:** uses NVENC/AMF hardware encoding, network
  streaming. Lower latency than RDP but optimized for full-screen
  gaming, not RAIL window forwarding.
- **WinApps:** has the same RDP RAIL pipeline as us, but **no GPU
  passthrough** because Docker containers cannot easily passthrough
  PCIe devices. So WinApps users on heavy 3D apps are stuck on
  software rendering inside the VM.

So our trade-off when passing through a GPU is:

- **Without passthrough:** Photoshop's filters run on the VM's
  software rasterizer (CPU-only). A 4K image filter that takes 200ms
  on a real GPU takes 8 seconds on llvmpipe. Photoshop becomes
  unusable.
- **With passthrough:** Photoshop's filters run on the real GPU at
  full speed. The result is captured, encoded as H.264 with ~10-30ms
  encode latency, sent over the in-memory AF_VSOCK channel (~1ms),
  decoded by FreeRDP (~5ms), drawn to the compositor (~5ms). End-to-
  end latency for a frame: ~25-50ms versus a few seconds. Worse than
  bare metal but qualitatively different from software rendering.

This is why GPU passthrough is **must-have for Photoshop / Premiere /
AutoCAD** even though it does not give us bare-metal performance —
the alternative isn't bare metal, it's *unusable*.

## Realistic per-app expectations

| Application class | Without GPU passthrough | With GPU passthrough | Verdict |
|-------------------|-------------------------|----------------------|---------|
| Notepad, Word, Excel, Outlook, Teams (chat) | Fine | Fine | passthrough doesn't help |
| Photoshop, Illustrator, Lightroom, InDesign | Unusable (5-10 s per filter) | Usable, encode adds 10-30 ms | passthrough required |
| Premiere, DaVinci Resolve, After Effects | Crashes on timeline scrub or hardware-decode probe | Usable with live-preview hiccups | passthrough required |
| AutoCAD 2D / 3D, Fusion 360 | Marginal 2D, broken 3D | Smooth | passthrough required for 3D |
| Blender, 3DS Max, Cinema 4D | Crashes / disabled GPU features | Usable | passthrough required |
| Visual Studio, JetBrains IDEs | Fine | Fine, marginally faster | passthrough doesn't help |
| Office 365 with Teams meeting | Fine for chat, video calls choke | Better for video calls | passthrough optional |
| Games | Not our target use case | Works but Looking Glass / Sunshine are better fit | not our problem |

## Tier system proposal

We commit to three tiers of hardware support. Users can check their
own tier with `crossdesk doctor`.

### Tier 1 — guaranteed support
Multi-GPU host with one of:
- NVIDIA RTX 20/30/40/50-series (Turing through Blackwell), driver 465+
- AMD RX 6000-series (RDNA2)
- AMD RX 7000-series (RDNA3)
- AMD RX 8000-series (RDNA4) when available

CrossDesk includes setup, libvirt XML generation, and CI smoke-test
coverage as soon as we have hardware to run smoke tests on.

### Tier 2 — supported with caveats
Multi-GPU host with one of:
- NVIDIA GTX 9/10-series (Maxwell, Pascal): may require Code 43
  workarounds depending on driver/Windows combination
- AMD Polaris (RX 4xx/5xx), Vega, RDNA1 (RX 5xxx): requires
  `vendor-reset` kernel module installed by the user
- Intel Arc A-series and B-series: experimental, less battle-tested

`crossdesk doctor` detects these and prints a tier-specific warning
plus a link to the workaround documentation.

### Tier 3 — explicitly unsupported
- Single-GPU systems (any vendor)
- Intel iGPU as the passthrough target (group sharing prevents clean
  passthrough)
- NVIDIA Quadro/RTX A-series with vGPU licensing (out of scope for
  MVP; can fall back to traditional passthrough as Tier 1)

`crossdesk doctor` refuses to enable GPU passthrough on Tier 3 and
prints an explanation.

## Scope consequences for CrossDesk

Adding GPU passthrough is not a config flag. It is approximately
3-4 weeks of work for Tier 1, plus follow-up for Tier 2 caveats.

### Detection logic (`crossdesk doctor` extensions)

- Enumerate GPUs (`lspci -nnk | grep -i vga`)
- Identify vendor and chip (PCI vendor:device IDs)
- Determine IOMMU enabled (`/sys/class/iommu/`, `dmesg | grep IOMMU`)
- Check IOMMU group composition (`/sys/kernel/iommu_groups/`)
- Detect single vs multi-GPU
- Detect host's currently-using GPU (compare against
  `$WAYLAND_DISPLAY` / `$DISPLAY` driver bindings)
- Map vendor + chip → tier
- Output: `gpu_passthrough_status: { tier: 1|2|3, host_gpu: ..., available_for_passthrough: ..., warnings: [...] }`

Estimated 200-400 lines of Python in `host/src/crossdesk_host/diagnostics.py`.

### Setup helper

We will provide `crossdesk gpu setup` that:

1. Confirms tier from `doctor`
2. Identifies the GPU to pass and its companion devices (audio
   function, USB-C controller for newer GPUs)
3. Generates the kernel cmdline params for the user's bootloader
   (GRUB, systemd-boot, NixOS, or distro-specific)
4. Generates the initramfs-binding configuration per distro
5. Optionally writes the changes (with `--commit`) or prints them for
   manual application (`--dry-run`, default)
6. After reboot, runs `crossdesk gpu verify` to confirm the GPU is
   bound to `vfio-pci`

Estimated 300-500 lines of Python plus per-distro shell helpers. The
per-distro logic is the bulk of the effort because each distro's
boot/initramfs system is different.

### libvirt domain XML generation

Add `<hostdev>` blocks to the generated domain XML:

```xml
<hostdev mode='subsystem' type='pci' managed='yes'>
  <source>
    <address domain='0x0000' bus='0x01' slot='0x00' function='0x0'/>
  </source>
</hostdev>
<hostdev mode='subsystem' type='pci' managed='yes'>
  <source>
    <address domain='0x0000' bus='0x01' slot='0x00' function='0x1'/>
  </source>
</hostdev>
```

(The two functions are GPU + audio.) Plus optional `<rom file='...'/>`
for cards that need a custom vBIOS (rare with modern cards). Plus
`<features><kvm><hidden state='on'/></kvm></features>` for older
NVIDIA cards still hitting Code 43.

Estimated 100-200 lines added to `infra/launch-vm.py`.

### Vendor-specific paths

NVIDIA modern: trivial.
NVIDIA old: `<features><kvm><hidden state='on'/></kvm></features>`
plus `hv_vendor_id` and `kvm=off` in QEMU args.
AMD reset bug detection: probe `lsmod | grep vendor_reset`; warn if
the user's card needs it and the module isn't loaded; provide install
instructions.
Intel Arc: experimental flag, `--gpu-experimental-intel-arc` to
enable.

### Testing matrix

The fundamental challenge: we cannot CI-test GPU passthrough without
real hardware. CI can run unit tests for our detection logic, libvirt
XML generation, and tier mapping. End-to-end smoke testing requires
manual QA with at least one Tier 1 NVIDIA and one Tier 1 AMD test
rig per release.

Plan: solicit community testing for Tier 2 hardware (the
/r/VFIO community is active and helpful). Document expected behavior
per tier; users report deviations.

### Documentation burden

`docs/GPU_PASSTHROUGH_SETUP.md` (separate from this analysis doc)
covering:

- Hardware requirements explained for non-experts
- BIOS/UEFI settings to enable IOMMU per major board vendor
- Per-distro setup procedures (Arch, Ubuntu, Fedora, NixOS)
- Per-vendor caveats (NVIDIA Code 43 history, AMD reset bug,
  vendor-reset module)
- Troubleshooting guide
- How to revert if things go wrong (binding back, kernel cmdline
  removal)

Estimated several pages, will go through multiple revisions as users
report edge cases.

### Threat model implications

Adding GPU passthrough requires updating `docs/THREAT_MODEL.md`:

- The VM gains direct DMA access to the GPU. Without IOMMU, this
  would mean the VM could DMA-read or DMA-write arbitrary host
  memory. With proper IOMMU, the VM is constrained to the physical
  pages it owns plus the GPU's memory.
- ACS override (used to break apart cheap motherboards' lumped IOMMU
  groups) **disables this protection partially**. We will refuse to
  use ACS-override paths and document why.
- The GPU itself has firmware. A malicious GPU firmware (in theory)
  could persist across VM reboots. Modern GPUs have signed firmware
  but the threat is non-zero. We document this and recommend not
  passing through GPUs from untrusted sources (e.g., second-hand
  cards from unknown sellers, in extreme threat models).

A new threat actor row may be appropriate: TA7 = malicious GPU
firmware. Mitigations: signed firmware vendor verification, no ACS
override, IOMMU enforcement.

## Recommendation

GPU passthrough is **must-have for the project's positioning** ("run
real Windows apps including Photoshop and Premiere") but is **not
required for MVP demo** ("`crossdesk launch notepad` works"). The
clean path is:

1. **MVP demo** ships with software rendering only. Documents that
   GPU-heavy apps are coming.
2. **Phase 4.5 / first major post-MVP work** is GPU passthrough Tier
   1 (NVIDIA modern + AMD RDNA2/3, multi-GPU only).
3. **Tier 2 follows** in subsequent releases as we get hardware to
   verify against and as the community contributes test reports.
4. **Tier 3 (single-GPU) stays explicitly unsupported.** Users on
   single-GPU systems either stay on software rendering or step
   outside CrossDesk to run Looking Glass / Sunshine for those
   specific apps.

Effort estimate:
- Tier 1 NVIDIA + AMD RDNA2/3: 3-4 weeks
- Tier 2 NVIDIA old + AMD reset bug: +1-2 weeks
- Tier 2 Intel Arc: +1 week
- Documentation and per-distro setup helpers: +1-2 weeks ongoing

Total: roughly 6-9 weeks across phases for full vendor support; 3-4
weeks for "first version that handles the most common modern
hardware."

## Decisions taken (2026-05-07)

1. **Phase 4 in-scope vs Phase 4.5 / post-MVP P0?**
   → **Phase 4.5 / post-MVP P0.** MVP demo (Notepad-class) ships
   without GPU; GPU is the immediate first follow-up.
   Reasoning: solo-developer scope-creep risk; iterating in
   v0.1 + v0.2 releases gives two press moments and one is
   informed by the other; Mac vacuum month is productive on
   non-GPU work regardless.

2. **Single-GPU systems explicitly unsupported — accepted.**
   This is hardware physics; not a scope choice. `crossdesk
   doctor` refuses politely with a clear explanation. Looking
   Glass integration (separate subsequent follow-up) revisits
   the single-GPU case via compositor-restart hot-switch.

3. **Tier 2 effort — partial commitment.**
   - AMD Polaris/Vega/RDNA1: **Tier 2 documented**, not
     maintained. Link to `vendor-reset` upstream; document the
     procedure; user is on their own for module installation
     and DKMS rebuilds.
   - NVIDIA pre-2021 / hide-the-VM tricks: **Tier 2
     documented**, not auto-applied.
   - Intel Arc: **Tier 3 (out)** until first user files an
     issue with testing data demonstrating demand.

4. **TA7 (malicious GPU firmware) — yes, formalize when
   implementation lands.** Placeholder noted in `docs/THREAT_MODEL.md`
   §"Out of scope" stub now; full row added with mitigations
   when Phase 4.5 work begins.

These decisions are encoded as ADR DEC-0009 in
`docs/DECISIONS.md`. Reconsider triggers documented there.
