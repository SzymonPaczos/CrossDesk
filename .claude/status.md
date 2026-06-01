# Status — known issues

Bieżące breakages / partial implementations. Jedna pozycja = jedna linia
opisu (max ~2 linie kontekstu). Naprawa lub świadome zostawienie:
flag w [`backlog.md`](backlog.md).

Pełne plany prac — `docs/EXECUTION_PLAN.md`. Archiwum zamkniętych
prac — `history/completed-work.md`.

---

## 🎉 MILESTONE — Windows app jako natywne okno Linuksa (2026-06-01, Linux+KVM)

**Osiągnięte na żywo:** `crossdesk install --iso-path Win10_22H2_Polish.iso
--locale pl-PL` instaluje Windows 10 Pro end-to-end, a FreeRDP RAIL renderuje
**Notepada jako natywne okno X na pulpicie Linuksa** (`"Bez tytułu —
Notatnik"` 1426×782, Map State IsViewable). Rdzeń obietnicy CrossDeska działa.

Działająca komenda renderująca (bezpośredni RAIL; = to co `build_rail_argv`
teraz produkuje):
```
DISPLAY=:0 XAUTHORITY=<xwayland-auth> xfreerdp3 /v:127.0.0.1:3389 \
  /u:crossdesk /p:<vm.toml> /cert:ignore /sec:tls \
  /app:program:'C:\Windows\System32\notepad.exe,name:Notepad' /wm-class:notepad
```

**Fixy zweryfikowane na żywo (zmergowane):** autounattend `/IMAGE/NAME`
(nie INDEX), `--locale` (autounattend musi pasować do języka ISO),
generic Pro ProductKey, per-device boot order, NIC **e1000e** (Win10 nie ma
virtio-net w pudełku — jak dysk SATA), RDP enable + TermService autostart +
firewall, injekcja hasła vm.toml→autounattend, hostfwd 3389 (qemu:commandline,
bo `<portForward>` wymaga passt), `build_rail_argv`: `/sec:tls` + usunięcie
prefiksu `||` (alias vs ścieżka → RAIL_EXEC_E_FILE_NOT_FOUND).

**Pozostało (warstwa zarządzania CrossDeska, NIE blokuje renderowania):**
- **`crossdesk launch` przez daemon** — działa host-side na mockach, ale na
  realnym gueście wymaga agenta online (gate verify-credentials). To znaczy:
  guest AF_VSOCK connector (DEC-0017, kod gotowy, niezweryfikowany — `/dev/
  vhost-vsock` root-only bez reguły udev) ALBO transport TCP-przez-SLIRP
  (10.0.2.2) + provisioning mTLS PKI do guesta + agent.exe uruchomiony na
  realnym Windows (nigdy nietestowany). Dziś renderowanie idzie czystym
  FreeRDP RAIL (bez agenta), co jest poprawne — agent dodaje zarządzanie
  (zdarzenia okien, lifecycle) na wierzchu.
- **NLA wyłączone** (`/sec:tls`) — dla konta lokalnego workgroup FreeRDP 3.x
  nie robi fallbacku Kerberos→NTLM. Docelowo: NLA + NTLM z nazwą komputera
  jako domeną (ustawić znany ComputerName), albo zostać przy TLS.
- **virtio perf** — dysk SATA + NIC e1000e (zgodność instalacji). Po
  instalacji można przełączyć na virtio-blk/virtio-net z virtio-win ISO.

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
