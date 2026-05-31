# Status — known issues

Bieżące breakages / partial implementations. Jedna pozycja = jedna linia
opisu (max ~2 linie kontekstu). Naprawa lub świadome zostawienie:
flag w [`backlog.md`](backlog.md).

Pełne plany prac — `docs/EXECUTION_PLAN.md`. Archiwum zamkniętych
prac — `history/completed-work.md`.

---

## Live install — pierwszy realny boot Windows (2026-06-01, Linux+KVM box)

`crossdesk install --iso-path Win10_22H2_Polish.iso` realnie bootuje VM
end-to-end: doctor → ISO → creds → tools.iso (pycdlib) → qemu-img 64G →
define+start domeny libvirt → **Windows Setup uruchamia się** (OVMF → CD →
WinPE → wybór edycji „Windows 10 Pro" via autounattend `/IMAGE/INDEX=6`).
Naprawione w trakcie: per-device boot order, generic Pro ProductKey,
`--locale` (autounattend en-US musi pasować do języka ISO).

**Co jeszcze NIE domknięte (autounattend tuning + sprzęt):**
- **Pełna auto-instalacja**: nawet z pasującym locale Setup pokazuje
  ekran wyboru edycji (autounattend nie tłumi w 100% UI windowsPE) —
  potrzebny audyt kompletności answer-file / nudge. Dysk nie urósł =
  Setup w fazie „Zbieranie informacji", przed kopiowaniem plików.
- **`/dev/vhost-vsock` Permission denied** — `qemu:///session` nie otwiera
  urządzenia (root-only). Vsock pomijany przy instalacji (Windows i tak
  się instaluje); link agenta wymaga reguły udev. Patrz backlog.
- **Guest AF_VSOCK connector** — niezaimplementowany (DEC-0017): retarget
  + parsing gotowe, socket FFI hardware-gated. Bez tego agent po
  instalacji nie połączy się z hostem (Faza 5).
- **`--locale` domyślnie en-US** — dla polskiego ISO użyj
  `crossdesk install --iso-path … --locale pl-PL`.

---

## Hardware-gated (czeka na Linux+KVM box)

- **`agent.exe` real Windows verification** — `LogonUserW`,
  `LibvirtFilesystemController`, RAIL window icon extraction
  (ExtractIconExW), wszystkie peryferia, GPU passthrough acceptance.
  Code shipped; runtime correctness niezweryfikowana bez sprzętu.
- **End-to-end install flow** — `crossdesk install` 7-step state
  machine: `generate_credentials` działa, reszta zwraca "hardware-gated"
  i exit 1. `--dry-run` przebiega zielony bez sprzętu.
- **VM acceptance testów (perf, Office, GPU smoke)** — workflow
  `linux-kvm-smoke` w `.github/workflows/ci.yml` jest no-op
  placeholderem dopóki self-hosted runner nie dojdzie.

## Świadome zaślepki (`🚧 mock` / Phase deferred)

- **RAIL launch ścieżka host-side** — `cli/launch_cmd.py` woła mgmt
  `Launch` RPC; handler (`ipc/management.py`) resolve app → gate creds →
  `spawn_rail_with_auth_check` → `RealFreeRDPInvocation.spawn_rail`
  (wszystko zaimplementowane, daemon wpina współdzielony freerdp +
  VerifyCoordinator + RailManager). Realny render okna jest HW-gated
  (wymaga guesta z serwerem RDP); ścieżka host-side przetestowana
  e2e na `MockFreeRDPInvocation`. file_path→JIT-mount + adopcja sesji
  po HWND w RailManager — Phase 4 follow-up.
- **`host/src/crossdesk_host/watchdog/sleep_sync.py`** — Phase 7 stub:
  logi only; systemd-sync wire-up po pełnym suspend/resume protocole.
- **`host/src/crossdesk_host/installer/iso_downloader.py::ScrapeBackend`**
  — Phase 5 placeholder: Protocol + `fetch()` z cache + sha256
  zacommitowane, `HttpScrapeBackend` jeszcze nie ma. Vulture / dead-code
  audit ignoruje aż do Phase 5.
- **Mock virtiofs handlers** w `guest/crates/fs-mount/` — `mock_handle_mount_request`,
  `mock_generate_lock_report`, `mock_generate_release_ack`. Phase 5
  zastąpi WinFSP/virtiofs.
- **`guest/crates/ipc-vsock/src/transport/real.rs::RealTransport`** —
  dial TCP loopback zamiast AF_HYPERV. `tower::Service<Uri>` shape
  stabilny, swap nie zmieni callerów.

## Partial — kod shipped, podłączenia / pokrycie brakujące

- **Multi-monitor RAIL** — `enumerate_monitors()` shipped, ale
  wiring do `rail_manager._handle_create` + `_NET_WM_DESKTOP` /
  xdg_output_manager hints + per-monitor scale re-eval na drag-between
  zostaje Phase 2.
- **HiDPI per-monitor scale** — `hidpi.py` detection ladder
  (wlr-randr → gsettings → kreadconfig5 → xrdb → env) shipped na
  poziomie systemu; per-monitor scale wymaga RANDR/wl_output
  per-output enumeration (multimonitor.py jest geometry-only).
- **Hibernation-aware resume** — `LifecycleCoordinator` stempluje
  `time.time()` + `time.monotonic()` i emituje
  `lifecycle_hibernation_detected`; faktyczny resync `AuthValidator`
  + nonce + sequence czeka na hardware (touch security model =
  ADR boundary per AGENTS.md).
- **Two-layer health check w PROBING** — observability MVP
  (`boot_probe` hook + log paths) shipped; synthetic AuthContext bypass
  + probe-driven SOFT_RECOVERY short-circuit deferred (ADR-required).
- **Config schema versioning** — `vm.toml` `schema_version` shipped;
  `crossdesk config migrate` CLI subcommand + migration registry
  brakuje (argparse plumbing w `cli/main.py` + scope-creep w
  pierwszym PR).
- **Verify-credentials real LogonUserW** — Stage 4 shipped
  (`guest/crates/agent-svc/src/credentials.rs::windows_impl::verify`);
  runtime correctness gated on real Windows guest;
  `docs/THREAT_MODEL.md` residual-risk flip + `docs/VERSIONING.md`
  `auth.verify-credentials.v1` capability promotion są user-owned.
- **Shutdown handler** — `crossdesk vm shutdown` CLI shipped;
  install-state persistence + D-Bus inhibitor release przeniesione do
  daemon-shutdown path (`lifecycle/coordinator.py`).
- **Desktop notifications** — `error_notifications.py` z 5 helperami +
  wired do HeartbeatServiceServicer / LifecycleCoordinator / RailManager;
  `DBusNotifier` shipped 2026-05-23 (dbus-next aio path); runtime
  verification gated on Linux session bus.

## Ostatnio zamknięte (krótka pamięć, pełne dane w `history/completed-work.md`)

Najnowsze: zob. `WORK_LOG.md` "Recent" + `.claude/history/completed-work.md`.
