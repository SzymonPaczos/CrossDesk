# Backlog

Jedyne źródło otwartej pracy. Pełne plany faz —
[`docs/EXECUTION_PLAN.md`](../docs/EXECUTION_PLAN.md) (this-week granular)
+ [`ROADMAP.md`](../ROADMAP.md) (phases). Bieżące breakages —
[`status.md`](status.md). Archiwum zamkniętych prac —
[`history/completed-work.md`](history/completed-work.md).

> Sfoldowany z FOLLOWUPS.md (1260 linii) 2026-05-23 — archiwum:
> [`history/2026-05-23-followups-archive.md`](history/2026-05-23-followups-archive.md).
> Inline `FOLLOWUPS:NNN` adnotacje w źródłach rozwiązują się przeciwko
> archiwum (decyzja [DEC-META-004](rules/decisions.md)).

**Konwencja:** jedna pozycja = jedna linia opisu + (opcjonalnie) jedna
linia kontekstu. Cross-refs do `docs/` / kodu obowiązkowe.
**Priorytety:** P0 = krytyczne / blokuje rozwój, P1 = ważne, P2 =
nice-to-have. **Status:** `[HW]` = hardware-gated; `[~PARTIAL]` =
częściowo shipped (reszta w [`status.md`](status.md)).

---

## P0

### Display / Phase 4 baseline
- **X11 RAIL pipeline.** Implement
  [`host/src/crossdesk_host/display/rail_manager.py`](../host/src/crossdesk_host/display/rail_manager.py)
  RAIL launch z `GDK_BACKEND=x11`; translate `RailWindowEvent` →
  compositor ops (CREATED → spawn + WM_CLASS; DESTROYED → close; FOCUS/
  TITLE/ICON/MOVED/RESIZED → WM hints). Idempotent + out-of-order
  tolerant. `[HW]`

### GPU passthrough (Phase 4.5 / post-MVP)
ADR: [`docs/DECISIONS.md`](../docs/DECISIONS.md) DEC-0009. Strategia:
[`docs/GPU_PASSTHROUGH.md`](../docs/GPU_PASSTHROUGH.md).
- **`crossdesk gpu setup` helper.** Per-distro kernel cmdline (GRUB /
  systemd-boot / NixOS), initramfs binding (mkinitcpio / dracut /
  initramfs-tools), GPU + audio function PCI ID detection, `--commit`
  vs `--dry-run` default. Plus `crossdesk gpu verify` post-reboot.
- **Tier 1 vendor smoke tests.** Manual QA matrix per release: ≥1 NVIDIA
  Tier 1 + ≥1 AMD Tier 1 host. CI bez dedicated runner. `[HW]`

### Looking Glass (post-Phase 4.5)
Strategia: `docs/GPU_PASSTHROUGH.md` §"GPU passthrough interakcja z RAIL".
- **Bundle LG client w distro packages.** ~5 MB binary do deb/rpm/AUR/
  NixOS/PyPI. GPL-2.0+ kompatybilne. Update
  [`docs/PACKAGING.md`](../docs/PACKAGING.md).
- **LG host installer w Windows install pipeline.** Optional component
  (`crossdesk install --gpu --with-lg`) → secondary OEM disk + Windows-
  side autostart. `[HW]`
- **IVSHMEM device w `infra/launch-vm.py`.** 8 MB shared memory region
  do libvirt domain XML gdy LG enabled.
- **Scream audio bundling.** LG nie ma audio; Scream = standard companion.
  Bundle Scream client + server z LG package set.
- **`crossdesk launch --mode=desktop` CLI.** Per-app config knob
  `mode = "rail" | "desktop"` w `~/.config/crossdesk/peripherals.toml`.
  `desktop` mode → spawn LG client zamiast FreeRDP RAIL.

### Post-MVP / winapps parity
- **App discovery service.** Źródło: `third_party/winapps/install/
  ExtractPrograms.ps1` (336 lines PowerShell). Reimplement jako Rust
  binary w `guest/` (mamy windows-rs), gRPC RPC nad VSOCK. Sources:
  `HKLM\...\App Paths` + `HKLM\...\Uninstall` + `HKCU\...\Uninstall` +
  `WOW6432Node` 32-bit + UWP via `Get-AppxPackage` + Chocolatey + Scoop.
  Beat winapps gap (oni robią tylko App Paths).

---

## P1

### Display & forwarding
- **Wayland-native RAIL.** FreeRDP 3.x Wayland support audit; missing
  `xdg-shell` / `xdg-decoration-unstable-v1` / `xdg-foreign-unstable-v2`
  / `wlr-foreign-toplevel-management` handlers (upstream FreeRDP PR
  preferred). Migrate `rail_manager.py` do Wayland-native default na
  Wayland sessions; fall back na X11 dla unknown compositors. `[HW]`
- **Multi-monitor RAIL — wiring deferred parts.** `enumerate_monitors()`
  shipped; podłączyć do `rail_manager._handle_create` + WM-hint
  forwarding via `_NET_WM_DESKTOP` / xdg_output_manager + per-monitor
  scale re-eval on drag-between. `[~PARTIAL]` `[HW]`
- **HiDPI per-monitor scale + monitor-change re-eval.** `hidpi.py`
  shipped system-level; per-monitor wymaga RANDR/wl_output per-output
  enumeration; re-evaluation on monitor change events. `[~PARTIAL]`

### Peripherals & host integration
Strategia: [`docs/PERIPHERALS.md`](../docs/PERIPHERALS.md). Typed config
([`host/src/crossdesk_host/config/peripherals.py`](../host/src/crossdesk_host/config/peripherals.py))
shipped — implementacje brakują.
- **Audio z PipeWire per-app tagging.** FreeRDP `/sound:sys:pipewire`
  (pulse fallback). Tag każdy RAIL stream `PA_PROP_APPLICATION_NAME`
  → separate streams w `pavucontrol` / `wpctl`.
- **Clipboard rich-content + file-list translation.** FreeRDP
  `+clipboard` + extended formats. Rich mode: intercept FORMAT_FILELIST
  guest→host, translate UNC → local paths. Text-only mode: drop FILELIST.
  Off default = isolation.
- **Drag-and-drop host-to-guest.** Host compositor initiates; FreeRDP
  RAIL receives drop + FORMAT_FILELIST; Windows app opens via translated
  path. Direction limited host→guest; reverse OOS.
- **Microphone.** FreeRDP `/microphone:sys:pulse` lub pipewire. Default
  off; opt-in per VM przez typed config.
- **Printer redirection via CUPS.** FreeRDP `/printer:CUPS`. Modes:
  `auto` (all) lub `named:<printer-name>`. Document Easy Print quality
  caveats (duplex, color).

### Versioning & compatibility
Strategia: [`docs/VERSIONING.md`](../docs/VERSIONING.md). ADR DEC-0007.
- **`crossdesk upgrade` agent hot-swap z handshake-aware sequencing.**
  FSM enters `UPGRADING` state during agent swap (suppresses
  HARD_DESTROY ≤60s); exits po pierwszym Hello z nowego agenta. Patrz
  P2 Operations `crossdesk upgrade` (ten sam ficzer, dwa side).
- **N-1 agent CI matrix.** GitHub Actions job: build previous minor
  agent, run handshake tests vs current host. Catches accidentally-
  breaking proto changes. Compat-matrix wf już istnieje; brakuje
  trigger na faktyczny pre-built agent.
- **CLI semver commitment v1.x — snapshot test.** Snapshot `--help`
  output, fail on unexpected change. Strategia w `VERSIONING.md`;
  brakuje test'u. `[~PARTIAL]`
- **`crossdesk config migrate` CLI subcommand.** Shipped 2026-05-23:
  argparse plumbing + migration logic in `cli/config_cmd.py`; 6 tests.
  Remaining: migration registry for v2+ schema (host daemon config +
  app catalog). `[~PARTIAL]`

### Distribution & packaging
Strategia: [`docs/PACKAGING.md`](../docs/PACKAGING.md). ADR DEC-0008.
- **`deb` package + apt repo.** `dh-virtualenv` lub `fpm`. Repo
  `https://repo.crossdesk.dev/deb/` (domain pending — patrz reminders
  w `AGENTS.md`). GPG-signed.
- **`rpm` package + Copr/OBS repos.** Fedora Copr (free, automated);
  openSUSE OBS. RPM signing via OBS lub self-hosted key.
- **Sigstore signing dla `agent.exe`.** Wired do release CI. Public
  verification key on download page. Documented w install docs.

### Lifecycle: power, suspend/resume, autostart
- **VM autostart on login (opt-in).** `crossdesk install --autostart`
  + `crossdesk vm autostart enable|disable`. Default off.
- **Shutdown handler — install-state persistence + D-Bus inhibitor
  release.** CLI `crossdesk vm shutdown` shipped; brakuje
  `lifecycle/coordinator.py` daemon-shutdown path. `[~PARTIAL]`
- **Hibernation-aware AuthValidator / nonce / sequence resync.**
  `LifecycleCoordinator` stamps shipped; faktyczny `AuthValidator`
  wiring czeka na hardware (touch security model = ADR required per
  AGENTS.md). `[~PARTIAL]` `[HW]`
- **Autopause × balloon — Phase 7 driver implementation.**
  `BalloonHook` Protocol seam shipped; real virtio-balloon driver
  brakuje. Plus single `lifecycle/` supervisor owning state machine
  across all three mechanisms (autopause + LifecycleCoordinator dziś
  duplikują order — merge when third caller arrives). `[~PARTIAL]`

### Performance budgets
Strategia: [`docs/PERFORMANCE.md`](../docs/PERFORMANCE.md). ADR DEC-0004.
Budgets w [`docs/REQUIREMENTS.md`](../docs/REQUIREMENTS.md) §N1.
- **Integration benchmarks.** `host/tests/benchmarks/`:
  `bench_install_pipeline.py`, `bench_cold_launch_lightweight.py` (N1.1a),
  `bench_recovery_destroy_start.py` (N1.6a). Slower; gated by PR label
  `perf-full`. Run on main-branch nightly. `[HW]` dla cold-launch.
- **`tools/bench_report.py`.** Agreguje wyniki across runs → markdown
  table for release notes.
- **PR comment automation.** GitHub Action posting perf table. Już
  częściowo wired w `bench_report.py` (ale jako step, nie automation).

### GPU passthrough Tier 2 docs
- **AMD reset-bug Tier 2 docs.** Detection (`lsmod | grep vendor_reset`);
  doctor warning surface; link do upstream instalacji; sami nie shippujemy
  modułu.
- **NVIDIA pre-2021 Tier 2 hide-the-VM docs.** Explain Code 43 history;
  document `<hidden>` flag opt-in; warn drivers 465+ obsolete; for users
  stuck on old explain workaround.
- **TA7 row w `docs/THREAT_MODEL.md`.** Malicious GPU firmware threat +
  mitigations (signed firmware verification, no ACS override, IOMMU
  enforcement). Adds when implementation lands per DEC-0009. **`[user-approval]`**

### Looking Glass P1
- **Single-GPU hot-switch path.** Detection (doctor) + orchestration:
  compositor stop → GPU rebind to vfio-pci → VM start z LG host → LG
  client spawn on iGPU/vesa fallback → reverse on exit. `[HW]`
- **C8 IVSHMEM channel w `docs/THREAT_MODEL.md`.** New component row:
  IVSHMEM jako non-VSOCK trust surface; brak per-frame AuthContext;
  threat reduced (unidirectional pixel firehose). **`[user-approval]`**

### Software rendering fallback
- **Document supported app classes per render path.** Word/Outlook/
  Excel/VS: software OK. Photoshop/Premiere/AutoCAD/Blender: software
  unusable. Concrete table w `docs/USER_GUIDE_HARDWARE_COMPAT.md` (new).
- **`crossdesk doctor` rekomenduje app categories per hardware tier.**
  "Hardware Tier 3 → productivity apps OK via software rendering";
  redirect Photoshop/Premiere → Wine/CrossOver/cloud GPU.

### Phase 1 follow-ups (przed Phase 4)
- **CrossDesk Lean Windows profile (opt-in).** PowerShell
  `infra/lean_profile.ps1` z `<FirstLogonCommands>`. Removes Edge/
  Cortana/OneDrive/Tips/Games/Skype/Teams personal/Xbox; **keeps**
  .NET/VC++/Windows Update/Defender/AV+video drivers. Opt-in via
  `crossdesk install --lean`. Land przed Phase 4 → RAIL latency tests
  na representative image. Acceptance: Office + Adobe + VS install +
  activate normally na lean.
- **`crossdesk install` real call sites for steps 2-7.** 7-step state
  machine shipped jako idempotent stubs; `generate_credentials` real,
  reszta "hardware-gated" exit 1. Real wiring: `iso_download` (Phase 5
  scrape), `libvirt_domain` (`infra/launch-vm.py`), `autounattend` (Lean
  profile integration), `win_install` (libvirt boot), `agent_register`
  (mTLS PKI gen + Windows-side cert install), `healthcheck` (Hello +
  heartbeat probe). `[HW]`

### Phase 3 follow-ups
- **Two-layer health check — synthetic AuthContext bypass + probe-driven
  SOFT_RECOVERY short-circuit.** Observability MVP shipped; bypass-and-
  short-circuit czeka na ADR (touch security model). `[~PARTIAL]`
  **`[user-approval]`**

### Post-MVP / winapps-parity (P1 tier)
- **Adopt 91-app catalog jako starting point.** Źródło:
  `third_party/winapps/apps/<name>/info` (91 entries). Copy non-trademark
  fields (`WIN_EXECUTABLE`, `MIME_TYPES`, `CATEGORIES`) do TOML. Skip
  SVG icons (Microsoft/Adobe trademark unclear); generate icons z `.exe`
  resources at discovery time. (Dziś 20-app catalog shipped 2026-05-11;
  rozszerz do 91.)
- **Sleep/wake time sync.** Prefer `qemu-guest-agent` + `virsh domtime`;
  fallback: WinApps marker-file approach via gRPC (host writes
  "host-resumed" signal on D-Bus suspend wakeup → guest agent
  `w32tm /resync`). `[HW]`
- **GUI launcher / taskbar applet.** Extend Qt6/QML installer wizard
  (`gui/`) → permanent applet: VM start/stop/pause/reboot + app picker.
  WinApps' Yad-based launcher to porównanie.
- **Desktop notifications via D-Bus.** ✅ `DBusNotifier` shipped
  2026-05-23 (`integrations/notifications.py`): real dbus-next aio call,
  sync/async context detection via `asyncio.get_running_loop()`. Wired
  to 3 call sites via `SubprocessNotifier` interface compatibility.

### Operations & lifecycle (post-MVP)
- **`crossdesk doctor` — pre-flight diagnostic.** Expanded 2026-05-23:
  added `check_cpu_virt_extensions`, `check_vsock_module`,
  `check_qemu_version`, `check_config_dir_writable`; `--gpu` flag wired
  to GPU_CHECKS. Remaining: wiring as pre-step for `crossdesk install`
  + free disk check. `[~PARTIAL]`
- **`crossdesk uninstall` — clean removal.** `virsh destroy` +
  `virsh undefine --remove-all-storage`, każdy `crossdesk-*.desktop`,
  cached ISO, install state. `--keep-config` preserves `vm.toml`;
  `--force` skips confirmation. Critical for trust.
- **`crossdesk logs --component guest` — guest gRPC log pull.** Host
  log sources shipped (journalctl + JSONL + libvirt + FreeRDP); guest
  jest P2 stub ("not yet implemented"). Wire gRPC stream tail. `[~PARTIAL]`
- **First-launch experience po `crossdesk install` succeeds.** Desktop
  notification ("CrossDesk ready — run `crossdesk launch notepad`")
  via `org.freedesktop.Notifications`, brief next-steps file w
  `~/.config/crossdesk/getting-started.md`, optionally auto-launch
  Notepad jako smoke test (`--launch-test`). Don't open browsers.

### Cross-platform foundation

### Internationalization
- **CLI translations wave 2.** `apps_cmd.py` column headers wrapped
  2026-05-23; `cli/install_cmd.py`, `installer/` package — still
  English-literal. `[~PARTIAL]`

---

## P2

### Display
- **Per-frame display latency benchmark.** Add do microbench harness:
  "RAIL CREATED event → first frame drawn" na known-good test app.
  Wayland-native vs XWayland. `[HW]`
- **Looking Glass jako documented alternative.** Document w
  `docs/DISPLAY.md`; users run LG directly jeśli chcą; nie integrujemy.

### Peripherals
- **Smart card / PCSC-Lite passthrough.** FreeRDP `/smartcard` + `pcscd`
  host package. Required for corporate workflows (banking PKI, gov auth).
  Document host-side `libccid` setup.
- **USB allow-list z libudev hotplug.** Host-side libudev watcher
  attach/detach via libvirt `virsh attach-device` based on
  vendor:product allow-list w config. Default `deny-all`.
- **Camera USB passthrough.** Default: cała USB webcam via libvirt
  `<hostdev>`. Document `obs-v4l2sink` virtual-webcam alternative.
- **FIDO2 best-effort documentation.** No native FreeRDP channel; users
  rely na USB passthrough HID. Document procedure; nie obiecujemy
  first-class support.
- **Threat-model rows per peripheral.** One row w `docs/THREAT_MODEL.md`
  per enabled peripheral. **`[user-approval]`**

### Observability
- **Optional Prometheus exporter (community).** Small script polluje
  `GetMetrics` + exposes `/metrics` HTTP endpoint. Out of core; document
  contract for community contribution.
- **Microbench harness reads from histograms.** Performance regression
  checks w CI consume `heartbeat_rtt_seconds` + `launch_duration_seconds`
  histograms. Tied do perf-budgets work.

### Performance
- **Self-hosted KVM runner z `hardware-smoke` workflow.** Real-hardware
  numbers gated by PR label + hardware availability. Runner doesn't
  exist; wire workflow file ready. `[HW]`
- **Trend analysis.** Weekly metric summary over time. Useful gdy mamy
  months of history.

### Versioning
- **Deprecation tracking.** MINOR adding field obsoleting older →
  one-time warning at startup do MAJOR removal. Tooling: registry w
  `proto/DEPRECATED.md` z deprecation dates.

### Distribution
- **Update mechanism docs per distro.** README install section explaining
  `apt update`, `dnf upgrade`, `yay -Sua`. Distinct from `crossdesk
  upgrade` (in-VM agent).
- **Distribution-time GPG signing dla deb/rpm.** Release key offline.
- **Community documentation for adding new distros.** Gentoo ebuild
  template, SBo build script template. Nie shippujemy — ułatwiamy
  community.

### Lifecycle
- **Power profile docs.** User-facing docs covering laptop battery-saver
  / lid-close-suspend policy interactions; recommended `crossdesk`
  configuration per scenario.

### Internationalization
- **Weblate (or similar) integration.** Hosted translation service tak
  translators nie wymagają git. Contingent on community contribution
  volume.
- **Plural-form audit.** gettext `ngettext` dla pluralized strings.
  Few expected; revisit po first Polish translation pass.
- **Locale-aware number/date formatting.** File sizes, timestamps
  user-visible output. `locale.format_string` Python; Qt handles GUI
  natively.
- **RTL language readiness.** When first RTL translation arrives
  (Arabic / Hebrew), audit GUI layouts. Qt handles most automatically.
  OOS until needed.

### GPU passthrough
- **Per-distro automated setup beyond docs.** Auto-apply kernel cmdline
  + initramfs config via `crossdesk gpu setup --commit` dla 4 primary
  distros. Each distro module w `infra/gpu_setup/<distro>/`.
- **GPU performance benchmarks.** `host/benches/bench_gpu_filter_latency.py`
  — Photoshop-class filter completion time na known image. Real-hardware
  only; `hardware-smoke` workflow. `[HW]`

### Looking Glass
- **`docs/USER_GUIDE_DESKTOP_MODE.md`.** When RAIL vs Desktop,
  trade-offs, LG audio troubleshooting via Scream.

### Software rendering
- **Investigate llvmpipe optimizations.** Light investigation, no
  commitment. Newer llvmpipe versions / specific Mesa tuning może
  flipnąć "doesn't work" apps.

### Phase 1
- **Locale + timezone propagation.** Read host `timedatectl` + locale
  env at `infra/launch-vm.py` install + inject do `autounattend.xml`
  `<TimeZone>` + `<UserLocale>`. Skip TimeSync.ps1 marker-file mechanism
  jeśli `qemu-guest-agent` enabled (`virsh domtime` covers post-suspend).
- **Detect Windows 11 IoT Enterprise LTSC + short-circuit redundant
  debloat steps.** Read `install.wim` edition string; jeśli LTSC, skip
  matching `Remove-AppxPackage` (no-ops). LTSC requires enterprise
  licensing → few hobbyist users hit this.

### Phase 4 (RAIL Display Integration — beat winapps)
- **HiDPI auto-detect — beat winapps here.** Their model: `RDP_SCALE`
  config knob 3 discrete values. Ours: read Wayland `wl_output.scale`
  / X11 RANDR at launch, pick closest FreeRDP-supported scale
  (100/140/180 in 3.x), re-launch on monitor change. "No config knob,
  just works." (Basic auto-detect shipped; advanced features tu.)
- **Multi-monitor RAIL — beat winapps here.** Their README warns
  `/multimon` causes black screens. Forward each RAIL window to
  appropriate output via WM hints. Same module as HiDPI.

### Post-MVP / winapps-parity (P2 tier)
- **Typed config for redirections.** WinApps' `RDP_FLAGS` is free-form
  string. Replace z typed TOML: `enable_audio`, `enable_clipboard`,
  `enable_printer`, `usb_devices: list[str]`. Map → FreeRDP flags w
  host code. User nie widzi raw FreeRDP syntax. (Typed config dla
  peripherals już istnieje; rozszerz na pozostałe redirections.)
- **Auto-derive MIME types from registry.** Read `HKCR\<ext>` +
  `HKCR\<progid>\shell\open\command` during discovery → MIME associations
  automatic. WinApps hand-curates (unscalable).
- **Auto-extract icons from `.exe` resources.** `ExtractIconExW` (already
  na Phase 4 followups list for RAIL window icons) → PNGs at discovery.
  No hand-drawn art; icon zawsze matches version user faktycznie ma.

### Operations & lifecycle (post-MVP P2 tier)
- **`crossdesk vm snapshot create|list|restore|delete`.** Wraps
  `virsh snapshot-create-as` / `snapshot-list` / `snapshot-revert` /
  `snapshot-delete`. UX: "checkpoint before risky software." Requires
  VM stopped/paused for safe snapshots. Document storage growth.
- **`crossdesk upgrade` — update CrossDesk + in-VM agent.** Host
  packages via installer mechanism, then hot-swap `agent.exe` via gRPC
  `ControlService.UpgradeAgent`: stream binary, agent stages, restart NT
  service. Forward-compat check vs protocol-version field. Patrz P1
  Versioning `crossdesk upgrade` agent hot-swap (related).
- **`crossdesk export-state` / `import-state` — backup/move the
  install.** Tarball `~/.config/crossdesk/` + `~/.local/state/crossdesk/`
  + libvirt domain XML dump. `--include-disk` for full portability
  (~30GB). Critical insurance — losing `vm.toml` = losing Windows access.

### Cross-platform foundation
- **`cargo deny` rule** preventing direct imports of `libvirt-python`,
  `socket.socket(AF_VSOCK)`, `tokio::net::VsockStream` outside
  abstraction layer.

### Tech debt
- **`// type: ignore[override]` ergonomics watch.** Bidirectional gRPC
  servicers ominęto przez `AsyncIterator`. Jeśli grpc-stubs bump narrows
  parent signature, override może resurface; eyes on
  `crossdesk_host.proto.*_pb2_grpc.pyi` after every regeneration.
- **Feature-gate Phase-5 fs-mount mocks.** `mock_generate_release_ack()`
  ([`guest/crates/fs-mount/src/flush.rs:31`](../guest/crates/fs-mount/src/flush.rs))
  zwraca hardcoded `total_bytes_written: 1024`; wołane bezwarunkowo z
  `agent-svc/src/filesystem.rs:98` (bez `#[cfg(feature)]`). Phase-5 stub
  (zob. `status.md`), ale brak cfg-gate = placeholder trafia do
  prod-builda. Schować za `mock` feature jak reszta. (audyt 2026-05-31)
- **mTLS failure-mode testy.** `AuthValidator` pokrywa rejection paths,
  ale brak dedykowanych testów cert-pinning / hostname-validation failure.
  `test_smoke_inprocess.py` to happy-path + trace. (audyt 2026-05-31,
  rekomendacja krytyka)
- **AGENTS.md „Repository layout" drift.** Sekcja listuje 5 podkatalogów
  `host/src/crossdesk_host/`, faktycznie 23 (m.in. `cli/`, `doctor/`,
  `abstractions/`, `lifecycle/`, `filesystem_ctl/`…). AGENTS.md =
  boundary file → edycja wymaga zgody właściciela. (audyt 2026-05-31)

---

## Czeka na decyzję właściciela

Wymaga zgody na touch boundary plików per `AGENTS.md` "File boundaries"
(proto, THREAT_MODEL, DECISIONS, REQUIREMENTS, MVP_SCOPE, GOALS, ROADMAP).

- **`docs/THREAT_MODEL.md` flips po Stage 4 LogonUserW shipped**
  (`auth.verify-credentials.v1` residual risk wymaga uzupełnienia)
  i **`docs/VERSIONING.md` capability promotion** (`auth.verify-
  credentials.v1` z planned → stable). Patrz `status.md` "Verify-
  credentials real LogonUserW".
- **TA7 row w `docs/THREAT_MODEL.md`** (GPU passthrough firmware threat
  — patrz P1 sekcja).
- **C8 IVSHMEM channel w `docs/THREAT_MODEL.md`** (LG IVSHMEM trust
  surface — patrz P1 sekcja).
- **Threat-model rows per peripheral** (P2 sekcja).
- **Phase 3 synthetic AuthContext bypass + SOFT_RECOVERY short-circuit
  ADR** — touch security model (P1 sekcja).
- **Domain name dla hosted package repos (deb / rpm)** — open question
  per AGENTS.md "Pending user-decision reminders". Ostatnio pytano
  2026-05-07; ~4-tygodniowa kadencja.
- **Code signing strategy dla `agent.exe`** (Sigstore vs EV cert) —
  deferred jako not-yet-justified. Ask before v0.1.0 release packaging
  begins.

## Zablokowane

- **Self-hosted Linux+KVM CI runner** — gated on user acquiring Linux
  machine. Status update gdy hardware acquisition changes (per
  AGENTS.md reminders).
- **Wszystkie `[HW]` pozycje powyżej** — czekają na ten sam blocker
  (Linux+KVM box). Migawka aktualnego stanu — `status.md` "Hardware-
  gated".
