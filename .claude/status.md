# Status — known issues

Bieżące breakages / partial implementations. Jedna pozycja = jedna linia
opisu (max ~2 linie kontekstu). Naprawa lub świadome zostawienie:
flag w [`backlog.md`](backlog.md).

Pełne plany prac — `docs/EXECUTION_PLAN.md`. Archiwum zamkniętych
prac — `history/completed-work.md`.

---

## Usability push (2026-06-02, branch `feat/usability-shared-fs`) — CLI/TUI/GUI + filesystem + any-app

Sesja po resecie hosta. Wszystko gate-green (mypy --strict 120, host suite,
cargo check/clippy). Live-proofy wymagające VM odłożone (host zresetowany —
czekam na OK właściciela zanim wzniecę ciężką VM).

**Shipped (zacommitowane na `feat/usability-shared-fs`):**
- **Most plików host↔guest** (`d548d2e`): scoped, opt-in folder współdzielony
  (`PeripheralsConfig.shared_folder_*`, default OFF, default path
  `~/CrossDesk-Shared` — NIE `~/CrossDesk`, bo to repo). `to_freerdp_flags`
  emituje `/drive:`; `build_rail_argv` dostał `extra_flags` i odpala CAŁY
  `to_freerdp_flags()` (audio/clipboard/printer/USB/share) — wcześniej
  peripherals config był liczony, ale NIGDY nieaplikowany przy launchu.
- **GUI icon fix** (`bbc425b`): manager renderował się BEZ ikon nawigacji
  ("Cannot open qrc:/icons/*.svg"). Root cause: ikony przez `QmlModule.qrc_files`
  nie rejestrują się pod `qrc:/icons/` w cxx-qt 0.7.3. Fix: `icons.qrc` +
  top-level `CxxQtBuilder::qrc()`. Zweryfikowane na żywo (0 błędów, okno wstaje).
- **Launch-by-path** (`c1268f3`): `crossdesk launch 'C:\...\app.exe'` odpala
  DOWOLNĄ zainstalowaną apkę (Office poza standardową ścieżką, gra, instalator)
  bez wpisu w katalogu — `_spec_from_exe_path` wykrywa ścieżkę .exe i wyprowadza
  app_id/WM_CLASS z basename. Zweryfikowane host-side na żywo (ścieżka
  rozpoznana → gate verify-creds; gola na agencie odłożona).

**CLI:** w pełni działa (audyt wszystkich subkomend na żywo — graceful errors,
poprawne exit codes). **TUI:** nie istnieje (projekt = CLI + Qt GUI; nie
tworzę). **GUI:** builduje + odpala (Qt6 6.10.2), ikony naprawione.

**Otwarte znaleziska / decyzje:**
- **Ikony okien (host consumer)** — CZEKA NA DECYZJĘ właściciela:
  `.desktop`/icon-theme (bezzależnościowe) vs `_NET_WM_ICON` (python-xlib+Pillow).
  Agent-side gotowy (256×256 płynie). Patrz `backlog.md` P1 "RAIL window icons".
- **BUG: StartupWMClass↔WM_CLASS mismatch** — `apps install` pisze
  `.desktop` z `StartupWMClass=crossdesk-<id>`, ale okno RAIL dostaje
  WM_CLASS `<id>` (z `/wm-class:<id>`). Dock nie skojarzy okna z launcherem.
  Do naprawy z konsumentem ikon (uzgodnić na `crossdesk-<id>` po obu stronach).
- **i18n .qm nie kompilują się** — `lrelease` (Qt linguist) nieobecny na hoście;
  `build.rs` go woła z `.ok()` (cicho), więc tłumaczenia nie wchodzą, GUI leci
  po angielsku (źródłowy język). Env-gap (brak qt6 l10n tools). P2.
- **App discovery proto-gated** — `registry-scan` (guest) realny, ale brak RPC
  guest→host (RegistryScannerService) by przenieść wyniki + `ListDiscoveredApps`
  to stub. Wymaga edycji proto (boundary, owner). Launch-by-path to interim.
- **Live-proofy odłożone:** most plików (zapis z notepada → host; instalator →
  guest) i launch-by-path na żywym agencie — wymagają wzniesienia VM.

---

## 🎉 MILESTONE — Pełna ścieżka produktowa: `crossdesk launch notepad` przez daemon + agent online (2026-06-02, Linux+KVM)

**Osiągnięte na żywo:** agent.exe na realnym Windows łączy się z daemonem
przez **TCP-SLIRP + mTLS**, kończy handshake (Hello accepted, control READY,
heartbeat), a `crossdesk launch notepad` → daemon → **verify-credentials
(realny LogonUserW na żywym agencie)** → FreeRDP RAIL → **Notepad jako
natywne okno X** (`0x1000078 "Bez tytułu — Notatnik" 1426×782 IsViewable`).
Warstwa zarządzania steruje renderem — nie ręczny FreeRDP. Daemon odbiera już
`RailWindowEvent` z agenta (rail-bridge WinEvent hook → control plane).

**Transport (DEC-0017 dev TCP path):** guest dial `https://10.0.2.2:50051`
(SLIRP gateway → host loopback), host daemon binduje `127.0.0.1:50051`
przez nowy `TransportConfig.bind_kind=tcp`
(`CROSSDESK_CONFIG__TRANSPORT__BIND_KIND=tcp`). Bez vsock/udev/sudo.

**Jak odtworzyć (bring-up):**
1. Daemon (TCP, z X dla spawnu RAIL):
   ```
   cd host && source .venv/bin/activate
   DISPLAY=:0 XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.* \
   CROSSDESK_CONFIG__TRANSPORT__BIND_KIND=tcp CROSSDESK_FREERDP_BIN=xfreerdp3 \
   python -m crossdesk_host > /tmp/cd-daemon.log 2>&1 &
   ```
2. Agent online (non-destructive, bez reinstalacji): `~/crossdesk-provision/`
   ma `agent.exe` (windows-gnu, **console mode**) + `pki/{ca,guest.crt,guest.key}`
   + `run-agent.cmd`. Provisioning przez FreeRDP drive-redirect + RemoteApp cmd:
   ```
   xfreerdp3 /v:127.0.0.1:3389 /u:crossdesk /p:<vm.toml> /cert:ignore /sec:tls \
     /drive:prov,/home/szymon-paczos/crossdesk-provision \
     '/app:program:C:\Windows\System32\cmd.exe,cmd:/k \\tsclient\prov\run-agent.cmd'
   ```
   (run_in_background; cmd ustawia `CROSSDESK_HOST_ENDPOINT=https://10.0.2.2:50051`
   + `CROSSDESK_PKI_DIR` i uruchamia `agent.exe console`.)
3. `crossdesk launch notepad` → okno.

**Fixy/zmiany tej sesji (branch `feat/tcp-slirp-agent-online`, NIE pushnięte):**
- **SMBIOS 'RSMB' byte-order bug** (`host_uuid.rs`): `from_le_bytes` →
  `from_be_bytes` (0x52534D42). Bez tego `GetSystemFirmwareTable`=0 → agent
  crashował przed Hello. + graceful fallback (warn + pusty UUID, nie crash).
- **Host TCP-bind** `bind_kind` (auto|tcp|vsock) — `config` + `transport/real.py`
  + daemon. mTLS bez zmian (review: 0 realnych defektów).
- **Agent `console` run mode** (`main.rs`): `agent.exe console` / `CROSSDESK_CONSOLE=1`
  → planes::run bez SCM, z REALNYMI impl (LogonUserW). Default = SCM.
- **Production provisioning** (designed path): `tools_iso` wozi mTLS PKI;
  `autounattend.xml` kopiuje do `C:\CrossDesk\pki\` + ustawia endpoint
  `https://10.0.2.2:50051` przez **per-service Environment REG_MULTI_SZ**;
  `install_cmd` przekazuje PKI. (Reinstalacja → agent auto-online.)
- **catalog**: dodany `notepad` (find_app).

**Ikony okien (user request 2026-06-02) — agent-side DONE + zweryfikowane na żywo:**
rail-bridge ekstrahuje natywną ikonę .exe (256×256 przez `PrivateExtractIconsW`
→ HICON→RGBA→PNG) do `RailWindowEvent.icon_png`. **Zweryfikowane na żywo:**
realna ikona `notepad.exe` 256×256 (72 KB PNG, RGBA) trafia na hosta
(`CROSSDESK_ICON_DUMP_DIR`). Plik: `guest/crates/rail-bridge/src/icon.rs`.
**Pozostaje host consumer** (uczynić ikonę WIDOCZNĄ): ustawić bogaty multi-size
`_NET_WM_ICON` na oknie RAIL (match po WM_CLASS=app_id) + `.desktop`/
`StartupWMClass` dla docka. Pełny design: `backlog.md` P1 "RAIL window icons".
Dziś FreeRDP ustawia tylko 32×32 `_NET_WM_ICON` z RAIL ICON orders.

**Pozostało:**
- **Host icon consumer** (patrz wyżej) — wymaga decyzji o zależnościach
  (Pillow + python-xlib) albo bezzależnościowej ścieżki `.desktop`/icon-theme.
- **RailWindowEvent adoption / "ghost window" — NAPRAWIONE 2026-06-02.**
  Root cause: hook gubił `EVENT_OBJECT_CREATE` (okno niewidoczne w momencie
  CREATE) → host nigdy nie dostawał CREATED → tylko późniejsze MOVE dla
  nieznanego HWND ("ghost window"). Fix (`windows.rs`): emituj CREATED przy
  pierwszym widocznym zdarzeniu (set `SEEN_WINDOWS`). Zweryfikowane: 0 ghost
  warnów, RailManager loguje "Creating native Wayland window", a CREATED niesie
  icon_png. (HWND↔X-window adoption do faktycznego zarządzania oknem przez
  RailManager zamiast FreeRDP — dalej Phase 4.)
- **cmd window artifact**: provisioning RemoteApp cmd ("crossdesk-agent")
  renderuje się obok Notepada (kosmetyka bring-upu; produkcyjna ścieżka
  NT-service via autounattend nie ma cmd ani console-mode).
- **virtio perf / NLA→NTLM** — jak w milestone 2026-06-01.

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
