# Status — known issues

Bieżące breakages / partial implementations. Jedna pozycja = jedna linia
opisu (max ~2 linie kontekstu). Naprawa lub świadome zostawienie:
flag w [`backlog.md`](backlog.md).

Pełne plany prac — `docs/EXECUTION_PLAN.md`. Archiwum zamkniętych
prac — `history/completed-work.md`.

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

- **`host/src/crossdesk_host/cli/launch_cmd.py`** — Phase 4 RAIL spawn
  stub: wysyła desktop notification + log "RAIL session launch stub";
  realny spawn ląduje gdy hardware dostępny. (`.claude/ignorefiles.md`)
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
