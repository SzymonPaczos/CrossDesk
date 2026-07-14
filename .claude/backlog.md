# Backlog — post-MVP / kiedyś (parking)

> **To NIE jest board „co dalej".** Droga do v0.1.0 → [`PLAN.md`](../PLAN.md)
> (jedyny board MVP). Ten plik = długi ogon pozycji **poza** v0.1.0 + kontekst
> techniczny. Jak szukasz co robić teraz — nie tu. Stan / partiale —
> [`status.md`](status.md). Archiwum — [`history/completed-work.md`](history/completed-work.md).

Pozycje realnie należące do v0.1.0 (P0 hard_destroy, FS Stage B, doctor/uninstall
live, pomiary N1, M5, packaging test) żyją w `PLAN.md`; tu zostają jako kontekst.

> Sfoldowany z FOLLOWUPS.md (1260 linii) 2026-05-23 — archiwum:
> [`history/2026-05-23-followups-archive.md`](history/2026-05-23-followups-archive.md).
> Inline `FOLLOWUPS:NNN` adnotacje w źródłach rozwiązują się przeciwko
> archiwum (decyzja [DEC-META-004](rules/decisions.md)).

**Konwencja:** jedna pozycja = jedna linia opisu + (opcjonalnie) jedna
linia kontekstu. **Priorytety** tu są *względne w obrębie post-MVP*.
**Marker `[HW]`** (box jest żywy od 2026-07) = **genuine hardware, którego ten
box NIE ma**: GPU passthrough, Looking Glass, multi-monitor (2+ ekrany),
self-hosted CI runner. Rzeczy „tylko odpalić na tym boxie" (real libvirt,
VirtioFS, perf, suspend/resume) **nie są już `[HW]`** — są w `PLAN.md` NEXT.
`[~PARTIAL]` = częściowo shipped (reszta w [`status.md`](status.md)).

---

## Inbox — zapisane automatycznie, do sklasyfikowania

<!-- Nietrywialne zadanie odkryte poza bieżącym scope trafia tu OD RAZU,
gdy priorytet jest niejasny (reguła „zapisz najpierw" w rules/general.md,
adopcja 2026-07-12). Praca v0.1.0 → PLAN.md, nie tu. Najpierw deduplikuj.
Zapis ≠ zgoda na implementację. Pusto = nic nieoczekującego. -->

_(pusto)_

---

## P0

### ✅ BRAK DETEKTORA ŚMIERCI VM — ZROBIONE `414c879` (2026-07-14, live-verified)
Zamknięte tego samego dnia, w którym odkryte. **Zmierzone na żywo:** `virsh destroy` →
wykryte w **1 s** → auto-recovery → domena w 6 s → **agent w 25 s** (budżet 90 s),
bootując dysk bez nośników. Wymagało **trzech** brakujących elementów, nie jednego:
realne `LibvirtDomainEventSource` (nie istniało), recovery w `DomainEventReactor`
(tylko logował), oraz `LibvirtController.start()` (nie było czym wystartować martwej
domeny — `hard_destroy()` robi `destroy()+create()`, a `destroy()` na martwej rzuca).
Czyste wyłączenie gościa świadomie **nie** jest wskrzeszane. Oryginalny opis:

<details><summary>diagnoza z live-verify</summary>

**Zabity VM nie jest w ogóle zauważany przez daemona.** Odkryte przy przejeździe
Fazy B na żywej domenie: `virsh destroy windows-guest` → 60 s obserwacji → **zero**
linii w logu daemona, zero eskalacji FSM, domena leży wyłączona. Root cause
zweryfikowany (nie zgadnięty):

- **FSM heartbeatu tyka z `request_iterator`** strumienia gRPC
  (`ipc/heartbeat.py`). Śmierć VM zamyka strumień → **FSM przestaje tykać i nigdy
  nie dojdzie do HARD_DESTROY**. FSM eskaluje tylko gdy gość *żyje, ale jest
  niezdrowy* — nie gdy zniknie.
- **`daemon.py` nie wpina żadnego źródła zdarzeń domeny** (grep po
  `DomainEventReactor|LibvirtDomainEventSource|domain_events|event_source`: 0 trafień).
- **`LibvirtDomainEventSource` NIE ISTNIEJE** — `lifecycle/domain_events.py` ma tylko
  `DomainEventReactor` + `MockDomainEventSource`. Realnego źródła nigdy nie napisano.

**Co trzeba zrobić:** realne `LibvirtDomainEventSource` (libvirt event loop →
`VIR_DOMAIN_EVENT_STOPPED`) wpięte przez `DomainEventReactor` do daemona, z akcją
recovery.

**Pułapka projektowa (ważna):** `hard_destroy()` robi `destroy()` **+** `create()`,
a `destroy()` na **martwej** domenie rzuca `RuntimeError` (`real.py`). Recovery po
zabiciu VM musi wołać **samo `create()`** — naiwne wpięcie `hard_destroy` do
detektora **wywali się**.

**Budżet:** zmierzony reconnect po `create()` = **105 s** przy budżecie #6 = 90 s.
Nawet z działającym wyzwalaczem kryterium nie przechodzi. Kandydat na przyczynę:
dysk SATA + NIC e1000e zamiast virtio (jest osobna pozycja „virtio perf").
Alternatywa: właściciel re-definiuje budżet.

**Kontekst:** naprawa P0 `hard_destroy` steady-state (data-loss) jest **ZAMKNIĘTA
i live-verified** — recovery bootuje dysk, nośniki wyjęte, zero reinstalacji. Była
**konieczna, ale niewystarczająca** dla #6.


### A7-live install-path findings (żywa reinstalacja + adversarial audyt 11-agent, 2026-07-01)
Czysta reinstalacja na żywym KVM boxie **potwierdziła A7-live core**: świeży
`crossdesk install` → Windows unattended → agent NT-service **auto-łączy się w
~12 min, zero ręcznych kroków** (Hello+READY+heartbeat). Naprawione+zmergowane:
drive-find (`0dc3424`) + FreeRDP TOFU pin-clear (`2ab10d1`). Adversarial Workflow
(6 potwierdzonych defektów) + live-diagnoza odsłoniły resztę:

- **[P0-latentny, BLOKUJE A3] `hard_destroy` → REINSTALACJA Windows = utrata danych.**
  Domena ma install-ISO na `<boot order='1'>` przez CAŁE życie VM; nie ma
  steady-state XML. `hard_destroy()` ([`libvirt_ctl/real.py`](../host/src/crossdesk_host/libvirt_ctl/real.py) 94-107)
  robi `destroy()`+`create()` z persistent config → post-install auto-recovery
  heartbeat-FSM ([`ipc/heartbeat.py`](../host/src/crossdesk_host/ipc/heartbeat.py) 272-274 →
  `watchdog/fsm.py` HARD_DESTROY) bootuje install-ISO → **autounattend reinstaluje
  Windows na istniejącym dysku, bez człowieka** (albo wedge na firmware). Dziś
  latentny (daemon używa mock-libvirt); **A3 NIE MOŻE wpiąć realnego
  `LibvirtController` do lifecycle dopóki to nie naprawione.** Fix: po pierwszym
  Hello redefiniuj domenę do steady-state (eject oba CD, disk `boot order=1`,
  `defineXML` z zachowaniem UUID by przeżyło destroy+create) + persist flag
  „installed" w `install.state.json`.
  **[MECHANIZM shipped 2026-07-05]** `build_steady_state_domain_xml` +
  `redefine_steady_state` (Protocol/real/mock) + testy gotowe; ZOSTAJE tylko
  wpięcie finalize po Hello + live-verify (box-gated). Front w
  [`PLAN.md`](../PLAN.md) TERAZ; stan w [`status.md`](status.md) Partial.
- **[P1] Brak post-install wait — `_step_run_autounattend` deklaruje sukces gdy
  domena tylko `is_running()`.** ([`cli/install_cmd.py`](../host/src/crossdesk_host/cli/install_cmd.py)
  398-411; `install_agent_service`/`post_install_tweaks` = no-op printy). Host
  nigdy nie obserwuje przejścia installing→installed → **żaden finalize (eject /
  redefine / logoff konsoli / healthcheck) nie może być zsekwencjonowany**, a
  padnięty in-guest FirstLogonCommand jest niewidoczny. Enabler dla powyższego +
  console-session fix. Fix: bounded poll na pierwszy Hello/heartbeat (timeout →
  czytelny błąd wskazujący VNC + FirstLogonCommands log) gate'ujący finalize.
- **✅ [P1 ZROBIONE `0bccb73`] Console-session blokowała PIERWSZY managed RAIL
  launch.** AutoLogon(LogonCount=1) zostawiała aktywną sesję konsoli `crossdesk`;
  Win10 single-session → RDP RemoteApp jako ten sam user padał `LOGON_FAILED_OTHER`.
  Fix: order-21 `shutdown /r` (OS-initiated, czysty) na końcu FirstLogonCommands →
  czysty logon screen, agent (session 0) reconnectuje. **LIVE-VERIFIED na drugiej
  pristine reinstalacji:** Hello#1 → auto-reboot → Hello#2 → `crossdesk launch
  notepad` renderuje Notepada (1426×782 natywne okno). Follow-up (P1): pierwszy
  launch tuż po reconnectcie ściga się z verify-creds → bounded post-install-wait
  (niżej) by wygładził.
- **[P1] Eject install media po instalacji.** Install-ISO zostaje podłączone →
  każdy reboot re-trafia „press any key to boot from CD"; **live: ACPI reboot
  świeżego gościa ZAWIESIŁ go na firmware**, recovery = eject ISO + destroy+start.
  Współdzieli fix ze steady-state XML (P0 wyżej). Host-side, gated na post-install-wait.
- **✅ [P1 ZROBIONE `29ccea5`+`bac8dfd`] Hardcoded ścieżki OVMF łamały non-Debian.**
  Fix: `resolve_ovmf()` w `domain_xml.py` (env override `CROSSDESK_OVMF_CODE/VARS`
  → Debian/Fedora/Arch candidate-list → `FileNotFoundError` z listą ścieżek);
  `create_libvirt_domain` woła to (I/O) i przekazuje do `DomainSpec`, `build_domain_xml`
  zostaje pure. + `check_ovmf_firmware` doctor pre-flight. 9 nowych testów.
  **Pozostaje (P2):** Win11 (secure=yes+smm) wymaga osobnego deskryptora.
- **[P2] mTLS guest identity nie rotuje przy reinstalacji.** `_resolve_mtls_pki`
  ([`cli/install_cmd.py`](../host/src/crossdesk_host/cli/install_cmd.py) 185-210)
  reużywa `infra/certs/pki` (default) → każda instalacja na klonie dzieli tę samą
  guest identity + CA (contra per-install-uniqueness obietnica `pki.py`). RDP TOFU
  rotuje, mTLS nie — niespójność. Hardening (same-user host compromise = out of
  scope per THREAT_MODEL). Fix: mint fresh leaf przy wykrytej reinstalacji, albo
  głośny warn + gate in-repo dev-dir za env/flag.
- **[P2] Single-VM hardcoded assumptions.** `_DISK_GB=64` (brak `--disk-size`),
  `vsock_cid=3` + `_DOMAIN_NAME="windows-guest"` (2 instalacje kolidują;
  `define_and_start` cicho niszczy istniejącą domenę), hostfwd `3389` + endpoint
  `10.0.2.2:50051` (SLIRP-only, brak port-conflict detekcji). Większość świadoma
  per DEC-0017 single-VM; warte: `--force`/confirm guard przed clobber + port-conflict
  doctor check.
- **[C-2, audyt 2026-07-07 P2-8] Marker-gated `RealLibvirtController`
  destructive-path integration test.** Trigger: owner greenlight P0 live-verify
  (needs-owner ▶). Wtedy: pytest marker `live_libvirt` (deselected by default)
  pokrywający `define_and_start` → `redefine_steady_state` → `hard_destroy` →
  `undefine` na jednorazowej throwaway domenie (NIGDY `windows-guest`), odpalany
  w cyklu live-verify → kryt. #6 staje się regression-guarded. Dziś
  `test_libvirt_real.py` pokrywa tylko czysty `_with_domain_uuid`.

</details>

### Filesystem bridge — kierunek A→B (DECYZJA właściciela 2026-06-12; beta-blocker #1)
- **Etap A: litera dysku `Z:` + redirect Dokumenty.** `[~PARTIAL 2026-06-12]`
  Host-side + generator skryptu **ZROBIONE** na `feat/fs-drive-letter`
  (5 commitów; bramki zielone): config (`shared_folder_drive_letter` D-Z +
  `redirect_documents`/`redirect_desktop` + `shared_folder_drive_path()`),
  workdir UNC→`Z:\` w `_peripheral_flags`, `installer/drive_map.py` generator
  skryptu logon + 9 testów. **Live-findings (na żywej VM) zmieniły mechanizm:**
  Run key NIE odpala się przy logonie RAIL (rdpinit shell) → ścieżka (i)
  MARTWA; **trwałe mapowanie `/persistent:yes` JEST auto-odtwarzane przez MPR**
  → to jest mechanizm drive'a. `workdir:Z:\` jest racy → robust lever to
  redirect shell-foldera (leniwy). **POZOSTAJE:** GUI-verify Save dialogu
  (brak xdotool/scrot w sesji — doinstaluj lub user patrzy) + wybór triggera
  one-time (A: deklaratywny `HKCU\Network` przez autounattend / B: agent-svc
  `CreateProcessAsUser`) + wiring provisioning. Pełny stan:
  [`history/2026-06-12-fs-stage-ab-plan.md`](history/2026-06-12-fs-stage-ab-plan.md)
  §2.7 „AKTUALIZACJA MECHANIZMU" + `status.md` A1. **Bez boundary files.**
- **Etap B: VirtioFS jednego folderu jako trwały dysk `Z:`** (po becie).
  Plan: [`history/2026-06-12-fs-stage-ab-plan.md`](history/2026-06-12-fs-stage-ab-plan.md)
  §2.8. Gated: smoke-test sterownika virtio-win VirtioFS
  `[HW]` + weryfikacja vhost-user/memfd na `qemu:///session` + **ADR
  właściciela + THREAT_MODEL row** **`[user-approval]`**. Provider-swap pod
  tym samym `Z:` (redirect z Etapu A bez zmian); rdpdr zostaje fallbackiem.

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

### CI / supply chain — fala z audytu 2026-07-12 (✅ ZROBIONA `05653c7`, 2026-07-14)
Sign-off właściciela 2026-07-14 („wykonaj falę + merge"); `.github/**` przestało
być boundary dla pętli (`loop-spec.md` toggles). **zizmor: 86 findings (42 High)
→ 16 (0 High / 0 Medium / 0 Low, 3 informational).**
- **✅ [P1] `security.yml` manual-only vs dokumentacja — ZROBIONE.** Przywrócone
  triggery `push` + `pull_request` + `schedule` (pn 06:17 UTC) → `AGENTS.md:64-69`
  („runs on every push, every PR, and weekly on Mondays") stało się **prawdziwe
  bez edycji boundary** (opcja (a) z needs-owner §8). Repo publiczne = Actions
  darmowe, więc powód billing-freeze'u 2026-05-20 odpadł.
- **✅ [P1, Red Team HIGH] SHA-pinning third-party — ZROBIONE.** Wszystkie 4
  third-party przypięte do 40-hex SHA: `dtolnay/rust-toolchain` ×5 →
  `4be7066…c30` (branch `stable`), `bufbuild/buf-setup-action` → `a47c93e…a99`
  (v1.50.0), `gitleaks/gitleaks-action` → `ff98106…0c7` (v2.3.9),
  `softprops/action-gh-release` był już przypięty. `image: semgrep/semgrep` →
  digest `sha256:59fbed…66e`. Naprawiony też **dryf komentarz↔YAML**:
  `release.yml` twierdził, że jest przypięty, gdy nie był. Konwencja
  („third-party = hash, first-party = tag") jest teraz **maszynowo sprawdzalna**
  w `.github/zizmor.yml` — bez niej `--no-config` pokazuje **33 High**.
  ⏸ **Zostaje decyzja właściciela:** czy zratchetować także first-party
  (`actions/*`, `github/*`) do hash-pinu, czego chce `ci-cd.md` §2 — to te 33
  findings. Zaparkowane w `needs-owner.md`.
  Nie zrobione (świadomie, poza zakresem fali): `actions/attest-build-provenance`
  + `cargo build --locked` w release — trigger: przed pierwszym tagowanym release.
- **✅ [P1, Red Team LOW 2026-07-12] pre-push secret-gate bypass — ZROBIONE
  `1b9c6f1` (2026-07-14).** `.githooks/pre-push` iterował `for f in $CHANGED_FILES`
  (niecytowane) → nazwa ze spacją rozpadała się na tokeny, `[ -f "$f" ]` je odrzucał,
  plik z realnym sekretem **nigdy nie był skanowany** (gdy gitleaks nieobecny = jedyna
  bramka). Potwierdzone empirycznie: `git diff --name-only` wypisuje ścieżkę ze spacją
  BEZ cudzysłowów. **Fix:** diff czytany NUL-delimited do tablicy + helper
  `changed_match`; ten sam split dotykał pętli console.log/print/qmllint oraz
  akumulatorów `SECRET_HITS`/`QML_HITS` → też tablice. 3 testy regresyjne
  (`host/tests/test_pre_push_hook.py`), **sentinel-verified**: spaced-filename test
  pada na starym hooku (skaner przechodzi obok pliku), przechodzi na nowym.
- **✅ [P1] Brak dependency bota — ZROBIONE.** `.github/dependabot.yml`: 4
  ekosystemy (github-actions, cargo ×2 guest+gui, pip host), tygodniowo (pn),
  cooldown 5 dni, minor/patch grupowane, majory osobno; security-updates omijają
  cooldown z definicji. **Uwaga:** `dtolnay/rust-toolchain` NIE będzie bumpowany
  automatycznie — repo publikuje branche (`stable`), nie tagi semver, a dependabot
  potrzebuje wersji w komentarzu przy `uses:`. Pin bumpować ręcznie (udokumentowane
  w nagłówku `dependabot.yml`; warto sprawdzać przy cotygodniowym audycie).
- **✅ [P2, ta sama fala] Top-level `permissions:` + `persist-credentials` —
  ZROBIONE.** `contents: read` na górze `ci.yml`, `compat-matrix.yml`,
  `security.yml`, `release.yml`; `persist-credentials: false` na **wszystkich 13**
  checkoutach (artipacked → 0). Przy okazji odwrócono dwa złamane least-privilege:
  `security.yml` dawał `security-events: write` **wszystkim** 5 jobom (teraz tylko
  dwa uploadujące SARIF), a `release.yml` dawał `contents: write` jobowi
  trzymającemu sekret podpisujący (teraz tylko `publish-release`).

### Display & forwarding
- **RAIL window icons — native high-res Windows icons on Linux windows.**
  (user request 2026-06-02; supersedes the P2 "Auto-extract icons" item.)
  Today FreeRDP sets only a 32×32 `_NET_WM_ICON` from the RDP RAIL ICON
  orders — blurry in docks/hi-DPI. The proto already carries the payload
  (`RailWindowEvent.icon_png`, populated for CREATED/ICON_CHANGED), so **no
  proto change**. Design:
  1. **Agent (rail-bridge)** — on CREATED, resolve the window's process
     image (`GetWindowThreadProcessId` → `OpenProcess` →
     `QueryFullProcessImageNameW`), extract the largest icon
     (`PrivateExtractIconsW(path, 0, 256, 256, …)`), convert HICON→RGBA
     (`GetIconInfo` → `GetDIBits` 32bpp top-down BGRA; alpha-from-mask
     fallback), PNG-encode (`png` crate), set `icon_png`. The exact seam is
     `events.rs::build_rail_event` (`icon_png: vec![]` TODO). Adds windows-rs
     `Win32_UI_Shell` + `Win32_Graphics_Gdi` features.
  2. **Host consume** — two paths (do both):
     a. *Titlebar / window icon*: set a rich multi-size `_NET_WM_ICON`
        (16/32/48/64/128/256) on the RAIL X window, found by **WM_CLASS
        instance == app_id** (we already pass `/wm-class:<app_id>`; per-app
        is the right granularity for icons). Needs PNG decode + X11 prop
        set — Pillow + python-xlib (new host deps) OR a small ctypes/xcb
        helper. Source = the agent's `icon_png` (RailManager already stores
        it in `_windows[hwnd]["icon_png"]`).
     b. *Dock / launcher / alt-tab*: write per-app
        `~/.local/share/applications/crossdesk-<app>.desktop` with
        `StartupWMClass=<app_id>` + `Icon=crossdesk-<app_id>`, and install
        the extracted icon into `~/.local/share/icons/hicolor/<size>/apps/`.
        Idiomatic, **no runtime X11/deps** — the desktop matches WM_CLASS to
        the .desktop and uses its icon. Highest-visibility, lowest-risk.
  Correlation note: control-plane `icon_png` is keyed by HWND; the X window
  is keyed by WM_CLASS=app_id. They don't share a key per-window, but
  per-app is sufficient for icons (cache the latest non-empty icon per
  process_id→app, or extract once at discovery). `[HW]`
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
- **[C-1, audyt 2026-07-07 P2-4] PKGBUILD `sha256sums=('SKIP')` → pin.**
  Trigger: PIERWSZY tagowany release tarball (kryt. #12 packaging test). Wtedy:
  `updpkgsums` przeciw opublikowanemu tarballowi + regen `.SRCINFO`; dodać pin
  do release checklist. Dopóki tarball nie istnieje — nie ma czego hashować.

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
- **Live-install follow-ups (2026-06-01).** Pierwszy realny boot ujawnił
  (`status.md` "Live install"): (a) **autounattend windowsPE UI nie tłumi
  ekranu wyboru edycji** mimo `/IMAGE/INDEX=6` — audyt kompletności
  answer-file; (b) **`/dev/vhost-vsock` udev rule** dla `qemu:///session`
  (dziś vsock pomijany przy instalacji → agent się nie połączy) —
  reguła `KERNEL=="vhost-vsock", MODE="0660", GROUP="kvm"` lub doc; (c)
  **autounattend locale auto-detect z ISO** (mamy `--locale`, ręczne) —
  czytać język z `install.wim`/ISO; (d) **virtio-win driver ISO** by
  przełączyć dysk boot z SATA na virtio-blk (perf, DEC-0016 reconsider).
- **GUI ISO auto-download (Fido backend).** Wizard (`gui/`) ma krok
  `Step1Iso`, ale `iso_downloader` to Phase-5 stub bez `HttpScrapeBackend`
  — UI jest, pobierania nie ma. Implementuj Fido-style download MS ISO.
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

### Resilience & observability (public-beta)
✅ **ZMERGOWANE do `main`** (`0f31d52` i dalsze) — zapis „NIE merged" był
nieprawdą, poprawiony 2026-07-14. Pełny stan:
[`status.md`](status.md) "Resilience & observability". Z audytu/diagnozy
2026-06-12: gdy komponent zewnętrzny pada (FreeRDP itd.), host tego nie
wykrywał/logował/notyfikował.
- **✅ FreeRDP supervision** — `display/rail_supervisor.py` reap+log+notify;
  per-app capture log; `FreeRDPInvocation.wait()`. Naprawia zombie xfreerdp.
- **✅ Notifier ożywiony w prod** — daemon wpina `SubprocessNotifier` do
  RailManager+Heartbeat (były dead-code).
- **✅ Graceful shutdown + crash catchall** — SIGTERM/SIGINT, `daemon_crashed` log.
- **✅ Log do rotującego pliku** — `crossdesk logs` działa bez journald.
- **Real `LibvirtDomainEventSource`** — Phase-3, **`[HW]`** (lands z real
  libvirt controller; reactor+mock seam już shipped+testowany).
- **`crossdesk logs --component guest`** — wymaga **nowego RPC host→guest
  (proto = boundary)**; `[user-approval]`. Dziś stub P2.
- **Live-verify realnego crashu FreeRDP** na żywej VM (notyfikacja+log+brak
  zombie) — kod+unit-tested, live zostaje.

### Operations & lifecycle (post-MVP)
- **`crossdesk doctor` — pre-flight diagnostic.** Expanded 2026-05-23:
  added `check_cpu_virt_extensions`, `check_vsock_module`,
  `check_qemu_version`, `check_config_dir_writable`; `--gpu` flag wired
  to GPU_CHECKS. Remaining: wiring as pre-step for `crossdesk install`
  + free disk check. `[~PARTIAL]`
- **`crossdesk uninstall` — clean removal.** `[~PARTIAL 2026-07-05 `8261a35`]**
  Domena (`undefine`: destroy-if-running + `undefineFlags(NVRAM)`),
  `crossdesk-*.desktop`, cached ISO, install state (+ VM disk), config
  (`--keep-config` zachowuje `vm.toml`) — **kod kompletny + testy**. Świadomie
  BEZ `--remove-all-storage`: nasz dysk znika z state-dir, a flaga próbowałaby
  skasować file-backed CD-ROM źródła (w tym ISO Windowsa usera). **Zostaje:**
  (a) live-verify pełnego usunięcia na realnym libvirt (Phase 2); (b) ✅ shipped
  `427b15e` — interaktywny confirm (EOF-safe: piped stdin = „nie"), `--force`
  pomija; `--dry-run` bez zmian.
- **`crossdesk logs --component guest` — guest gRPC log pull.** Host
  log sources shipped (journalctl + JSONL + libvirt + FreeRDP); guest
  jest P2 stub ("not yet implemented"). Wire gRPC stream tail. `[~PARTIAL]`
- **First-launch experience po `crossdesk install` succeeds.** Desktop
  notification ("CrossDesk ready — run `crossdesk launch notepad`")
  via `org.freedesktop.Notifications`, brief next-steps file w
  `~/.config/crossdesk/getting-started.md`, optionally auto-launch
  Notepad jako smoke test (`--launch-test`). Don't open browsers.
- **Produkcyjny agent jako NT-service (nie console) — STABILNOŚĆ, beta-blocker.**
  Live finding 2026-06-09: console-mode agent jest związany z cyklem życia
  sesji RDP → **zamknięcie okna RAIL / takeover sesji ubija ControlSession**,
  kolejny `launch` failuje na verify-credentials ("no live guest session").
  NT-service (kod jest, autounattend instaluje) przeżywa disconnect sesji +
  reboot + nie trzyma sesji RDP (brak session-takeover, brak cmd-artefaktu).
  Wymaga produkcyjnej reinstalacji guesta z autounattend (`[HW]`).
- **Daemon reapuje zakończone xfreerdp (zombie `<defunct>`) — ops.** Live finding
  2026-06-09: daemon spawnuje xfreerdp jako subprocess ale nie `wait()`-uje po
  jego śmierci → zombie w tablicy procesów (PPID=daemon). Niegroźne, ale do
  naprawy: `asyncio` child watcher / reap na `transport`/`freerdp` poziomie
  gdy RAIL session kończy się lub jest ubijany.

### Cross-platform foundation

### Internationalization
- **CLI translations wave 2.** `apps_cmd.py` column headers wrapped
  2026-05-23; `cli/install_cmd.py`, `installer/` package — still
  English-literal. `[~PARTIAL]`

---

## P2

### Porządkowe z audytu 2026-07-12
- **[P2] `SECURITY.md`** — repo publiczne bez kanału disclosure (skill §12).
  Krótki plik: kanał zgłoszeń, wspierane wersje (pre-release: tylko `main`),
  kto triage'uje. Publikacja = decyzja właściciela (public-facing).
- **✅ [P2] `status.md` kłamał o branchach — POPRAWIONE 2026-07-14.** Trzy
  gałęzie (`feat/resilience-logging`, `feat/fs-drive-letter`,
  `feat/usability-shared-fs`) opisane jako „NIE merged" **są w `main`** —
  zweryfikowane `git merge-base --is-ancestor`, nie na oko: `e15cf2b` (workdir),
  `0f31d52` (rail_supervisor), `1986295`+`9afb465`+`688b2a7` (Etap A),
  `configure_logging(log_file=)` w `observability/log.py`. Wszystkie zapisy
  poprawione w `status.md` i tutaj.
  **⏸ Zostaje (decyzja właściciela):** skasowanie 17 zmergowanych gałęzi na
  `origin` — akcja na współdzielonym remote, nie robię jej sam. Patrz
  `needs-owner.md`.
- **✅ [P2] Wiszące referencje do `handoff.md` — NAPRAWIONE 2026-07-14.** Plik był
  nietrackowanym scratchem sesji i wypadł z drzewa (`709363b`), zostawiając
  martwe cytaty §2.7/§2.8. Treść **odzyskana z historii** (`7f656fc`) do
  [`history/2026-06-12-fs-stage-ab-plan.md`](history/2026-06-12-fs-stage-ab-plan.md);
  wszystkie referencje w `status.md` i `backlog.md` przepięte.
- **[P2] Host bez lockfile'a Pythona** — CI i box resolvują zależności świeżo
  (`pip install -e`); `ci-cd.md` §3 chce zamrożonego locka. Decyzja
  kierunkowa: uv (`uv.lock` + `--locked` w CI) vs pip-tools.
- **[P2] `libvirt_call` na współdzielonym default executorze**
  (`libvirt_ctl/aio.py:29` — Security Review 2026-07-12, NOTE) — dedykowany
  `ThreadPoolExecutor` + test saturacji puli (N>pool_size zawieszonych
  wywołań nie głodzi innych `run_in_executor`).
- **[~PARTIAL 2026-07-14] `zizmor` — zainstalowany na boxie, brakuje joba w CI.**
  Izolowany venv (`~/.local/share/zizmor-venv`, symlink `~/.local/bin/zizmor`,
  wersja 1.27.0) + konfiguracja `.github/zizmor.yml` (polityka pinowania).
  Jest realną bramką lokalną (użyty do zamknięcia fali `05653c7`). **Zostaje:**
  job w `security.yml` = item A6 w `loop-spec.md`. Poniższy oryginalny opis:
- **[P2] `zizmor` nieobecny lokalnie i w CI** — zainstalować na boxie (audyt
  statyczny; dziś odpalony jednorazowo przez `uvx`) i rozważyć job w
  `security.yml`.
- **[NOTE] pre-commit bumpuje timestampy `architecture.md`/`ignorefiles.md`
  przy każdym commicie** — toolkit 2026-07-11 (NEW-PROJECT §8.2) uznaje
  timestamp-bump za kłamiący sygnał świeżości (git log wystarcza). Świadoma
  decyzja z maja (opcja b) — utrzymać albo wyłączyć: właściciel.
- **[NOTE] SHA w starych wpisach audit-log nie rozwiązują się** po rewrite
  historii 2026-07-07 (np. `13df5d1` z wpisu 07-06) — historyczne, bez akcji.

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
- **Auto-extract icons from `.exe` resources.** → **promoted to P1
  "RAIL window icons"** (Display & forwarding) per user request
  2026-06-02; see that entry for the full agent+host design. This P2 line
  remains only as the *discovery-time* variant (extract icons for the app
  catalog / launcher), distinct from the live per-window RAIL icon path.

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
- **[C-3, planning-addendum audytu 2026-07-07] `lifecycle/coordinator.py`
  suspend/resume blokuje event-loop.** `suspend()`/`resume()` (dawniej
  `:139,162`) blokują na ścieżce D-Bus PrepareForSleep + delegacji z mgmt.
  Świadomie WYŁĄCZONE z branch 3 (deadline-bound libvirt) bo coordinator
  mutuje stan FSM (`fsm_group`) — offload do wątku wymaga projektu
  thread-safety, nie mechanicznego owinięcia w `libvirt_call`. Trigger: przed
  live-verify suspend/resume (#5) na `backend=real`.
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
- **~~mTLS failure-mode testy~~ — ZWERYFIKOWANE JAKO ZROBIONE (2026-07-05).**
  Item z audytu 2026-05-31 jest **nieaktualny**: dedykowane testy failure-mode
  istnieją i pokrywają krytyczną ścieżkę mTLS/auth. `test_mtls_handshake.py`
  napędza **realny** handshake gRPC po loopbacku i asertuje odrzucenie na
  warstwie TLS dla: brak cert klienta, cert podpisany złym/niezaufanym CA, cert
  wygasły (nigdy nie dochodzą do dispatchu). `test_auth_validator.py` (unit)
  pokrywa cert-pinning (fingerprint mismatch), brak cert, malformed PEM,
  sequence-regression/skip-forward, concurrent streams. `test_auth_rejection_paths.py`
  pokrywa per-plane (Control/Heartbeat/Filesystem) odrzucenia. `test_security_edges.py`
  dokłada nonce/sequence edge-cases. („hostname-validation" nie jest zadaniem
  AuthValidatora — to warstwa TLS, pokryta wrong-CA/expired w handshake teście.)
- **AGENTS.md „Repository layout" drift.** Sekcja listuje 5 podkatalogów
  `host/src/crossdesk_host/`, faktycznie 23 (m.in. `cli/`, `doctor/`,
  `abstractions/`, `lifecycle/`, `filesystem_ctl/`…). AGENTS.md =
  boundary file → edycja wymaga zgody właściciela. (audyt 2026-05-31)
- **FreeRDP `/app:` quoted-`cmd:` tokenizer warning (Phase-5 latent).**
  Na FreeRDP 3.24 klauzula z `cmd:"<plik>"` *przed* kolejnymi sub-keyami
  (`hidef:`/`name:`/`workdir:`) emituje `[get_next_comma]: Invalid quoted
  argument` (po jednym na trailing sub-key; non-fatal, parse dochodzi do TCP
  connect). **Dziś uśpione** — `cmd_arg` jest zawsze `""` (`request.file_path`
  → JIT-mount to Phase-5, niewpięte; oba call-site'y `AppLaunchSpec` mają
  pustą `argv`), więc shipowana klauzula A1 (program+icon+hidef+name+workdir,
  bez `cmd:`) parsuje się czysto (0 błędów, zweryfikowane na żywym
  `xfreerdp3` 3.24.2, też ścieżki ze spacjami). Gdy Phase-5 wepnie
  file-open: dać `cmd:` na końcu klauzuli, zrezygnować z cudzysłowu, albo
  użyć `/args-from`; dodać test `workdir`+`cmd` razem. (review A1 2026-06-04)

---

## Czeka na decyzję właściciela

Wymaga zgody na touch boundary plików per `AGENTS.md` "File boundaries"
(proto, THREAT_MODEL, DECISIONS, REQUIREMENTS, MVP_SCOPE, GOALS, ROADMAP).

- **Kierunek systemu plików — ROZSTRZYGNIĘTE 2026-06-12: A → potem B.**
  Praca przeniesiona do P0 „Filesystem bridge — kierunek A→B" (góra pliku);
  plan wykonawczy [`history/2026-06-12-fs-stage-ab-plan.md`](history/2026-06-12-fs-stage-ab-plan.md)
  §2.7 (Etap A) + §2.8 (Etap B). Tu zostaje
  tylko część `[user-approval]` Etapu B: **ADR + THREAT_MODEL row dla
  trwałego scoped VirtioFS mount** — owner autoryzuje gdy Etap B startuje
  (po smoke-teście sterownika virtio-win VirtioFS).
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

> **Główny blocker („brak Linux+KVM boxa") ZNIKNĄŁ 2026-07** — box jest żywy,
> Fazy 1–4 zweryfikowane na żywo. To co zostało „zablokowane" to teraz tylko
> pozycje na **genuine hardware, którego ten box nie ma** (klasa C w
> [`status.md`](status.md) „Gating"):

- **Self-hosted `linux-kvm-smoke` CI runner** — potrzebny Proxmox/dedykowany
  runner (nie ten laptop-dev-box).
- **GPU passthrough / Looking Glass** — passthrough-capable multi-GPU host.
- **Multi-monitor RAIL** — 2+ fizyczne ekrany.

Wszystko inne oznaczone `[HW]` wyżej, co wymaga tylko *tego* boxa (real libvirt,
VirtioFS, perf, suspend/resume), jest **odblokowane** — patrz `PLAN.md` NEXT.
