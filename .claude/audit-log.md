# Audit Log

Newest audit first. Format: each run dopisuje sekcję `## Audyt YYYY-MM-DD` na górę.

## Audyt 2026-07-06

**Git:** `13df5d1` on `main`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 125 files)
- pytest collected: 1014
- bandit medium/high: 0

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 16
- gui cargo-deny issues: 3
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf: n/a
- .proto files: 5

**QML (`gui/`)**

- qmllint: n/a

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 0
- test files (python): 249
- #[test] annotations (rust): 84

**Drift & meta**

- architecture.md Last Updated: 2026-07-06 (0d ago)
- META decisions (status: aktywna): 7
- ADR DEC-NNNN total: 17

**Security**

- gitleaks: n/a (use `CROSSDESK_FULL_AUDIT=1 git push` for history scan)

**Cadence**

- previous audit: 2026-06-12 (24d ago)

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

### Warstwa głęboka (agent, 2026-07-07)

Okno: `bf38110..13df5d1` (2026-06-12 → 2026-07-05, ~114 commitów pętli
autonomicznej). Cztery równoległe przeglądy (bezpieczeństwo / slop+dead-code /
testy / architektura+decyzje); wszystkie P1 zweryfikowane ręcznie w aktualnych
plikach przed raportem.

**Zgodność z decyzjami: CZYSTA.** No-polling zweryfikowane per-site (wszystkie
`while True:` event/stream-driven; jedyny sleep-poll to zatwierdzony
DEC-META-006 `_tail_file`). Proto nietknięte. Wszystkie edycje boundary files
(`7d8720b`, `34bc3d3`) pokryte zapisanymi podpisami właściciela w
`needs-owner.md`. Seam libvirt szczelny (`import libvirt` tylko w
`libvirt_ctl/real.py`); mock-importy w prod tylko na whiteliście. Brak Dockera,
brak leafów certów w git.

**Suita testowa:** 1013 passed / 1 uzasadniony skip / 0 fail (44,5 s).
Hermetyczność istotnie poprawiona w oknie: guard anti-real-libvirt (`13c765f`)
zweryfikowany jako szczelny (autouse, jedyny choke-point `_connect`), izolacja
FreeRDP-config i peripherals-config domknięta. Negatywne testy mTLS
(`test_mtls_handshake.py`) napędzają realny handshake TLS z poprawnym
dyskryminatorem (UNAVAILABLE ≠ UNIMPLEMENTED) — wzorcowe. Testy finalize
kodują kontrakt anti-data-loss (retry zostawia krok nieoznaczony).

**cargo-deny (16 guest + 3 gui):** wyłącznie `warning[duplicate]` (zdublowane
wersje transitive crates) + 1 `advisory-not-detected` (stale ignore, P2 niżej).
Nie-security.

**Skille/MCP (§8):** brak `~/DevProjects/claude-toolkit` na tym boxie (nic do
synchronizacji); brak `.mcp.json`. Bez zmian.

#### P0 — brak

#### P1 (5)

1. **[SEC] Hasło VM w plaintext w logu daemona.**
   `freerdp/real.py:133` loguje pełny argv FreeRDP (z `/p:<hasło>` z
   `rail_command.py:139`) na INFO → tee do rotującego pliku
   `~/.local/state/crossdesk/logs/` (0644). Redakcja
   (`observability/redaction.py`) jest value-blind (matchuje nazwy kluczy
   `password|secret|token`, nie wartości) → nie łapie. Lokalne konto czyta log →
   RDP na `localhost:3389` → pełna kontrola guesta (+ whole-$HOME share =
   `~/.ssh`). Obala 0600-ochronę `vm.toml`. (Linia logu sprzed okna —
   `986d523` 2026-05-07 — ale sweep `a211087` deklarował pokrycie security,
   które ta dziura falsyfikuje.) Fix: redakcja `/p:...` przed logiem +
   rozważyć 0600 na pliku logu.
2. **[SEC] `autounattend.prepared.xml` z realnym hasłem world-readable.**
   `cli/install_cmd.py:229-231` — `write_text()` bez 0600, plik trwa w
   state-dir. Kontrast: `vm.toml` 0600 z repair-path, tools ISO 0600 przez
   `mkstemp` — ta jedna kopia sekretu odstaje. Fix: `os.open(..., 0o600)`.
3. **[SEC] Blokujące wywołania libvirt na event-loopie bez deadline'u.**
   `ipc/control.py:220-221` (`on_session_ready()` w async handlerze) →
   `finalize_steady_state` → `real.py` `defineXML`/`_connect`; analogicznie
   `ipc/heartbeat.py:274` `hard_destroy()`. Uzbrojone dopiero przez A3 seam
   (`30579a6` + `9ac1da1`). Zwisający libvirtd przy pierwszym Hello = zamrożony
   cały daemon (3 plany + heartbeat + D-Bus listener), bez timeoutu. Łamie
   `.claude/rules/backend.md` („libvirt event-loop deadlines — pick one").
   Fix: `run_in_executor` + `asyncio.wait_for` wokół każdego wywołania real
   controllera osiągalnego z servicerów.
4. **[SLOP] Daemon nie loguje wybranego backendu libvirt przy starcie.**
   `daemon.py:131-138` — selekcja mock/real bez żadnej linii logu; jedyny ślad
   mocka to per-operacyjne `[LIBVIRT MOCK]` — czyli dopiero przy zdarzeniu
   lifecycle, dokładnie wtedy gdy rozróżnienie mock/real decyduje o losie VM.
   Fix: 1 linia `logger.info` przy selekcji (warning dla mocka).
5. **[TESTY] Gałąź mock→`on_session_ready=None` bez testu.**
   `daemon.py:186-189` — guard „finalize na mocku maskowałby data-loss" (P0
   z PLAN.md) egzekwowany wyłącznie inline w `serve()`; refactor mógłby go
   cicho odwrócić i żadna bramka tego nie złapie. Fix: wyciągnąć selekcję do
   testowalnego helpera + 2 testy (mock→None, real→finalize).

#### P2 (14)

1. **[SEC]** PKI write-then-chmod race — `installer/pki.py:76-84`: klucz
   istnieje z umask-perms między `write_bytes` a `chmod(0o600)`. Fix:
   `os.open` z 0600 od razu.
2. **[SEC]** Guest-controlled `icon_png` zapisywane bez walidacji do icon
   theme (`display/window_icon.py` `offer`/`_apply`) — powierzchnia ataku na
   host-side dekodery obrazów (gdk-pixbuf itd.). Defense-in-depth: sygnatura
   PNG + cap rozmiaru.
3. **[SEC]** `linux-kvm-smoke` (ci.yml) — label-gate bez guardu same-repo →
   pwn-request na self-hosted runner. Dziś teoretyczne (runner nie istnieje);
   przed postawieniem dodać `head.repo.full_name == github.repository`.
4. **[SEC]** PKGBUILD `sha256sums=('SKIP')` — tarball bez integralności
   buduje `agent.exe` trafiający do każdego guesta. Pin przy release.
5. **[SLOP]** Stale wpis w `ignorefiles.md`: `DBusNotifier._send_sync` nie
   jest już no-opem (realny `dbus_next` call) — wpis do usunięcia/aktualizacji.
6. **[SLOP]** `installer/drive_map.py` — 0 production callers (tylko testy),
   nieza rejestrowany w `ignorefiles.md` → przyszłe audyty będą re-flagować.
   Zarejestrować albo wpiąć.
7. **[SLOP]** Drift PLAN.md (#10) + backlog.md: twierdzą, że uninstall
   `--force`/confirm „zostaje" — a jest shipped (`427b15e`,
   `cli/uninstall_cmd.py:30-56`).
8. **[TESTY]** Brak marker-gated testu integracyjnego dla destrukcyjnych
   ścieżek `RealLibvirtController` (box-gated; live-verify dziś wyłącznie
   manualny — dodać przy P0 live-cycle, żeby #6 zostało regression-guarded).
9. **[ARCH]** `architecture.md` „Transport: gRPC over AF_VSOCK" — brak
   wzmianki o shipped seamie `bind_kind=auto|tcp|vsock` (wszystkie żywe
   milestone'y szły po tcp).
10. **[ARCH]** AGENTS.md „22 subpackages" vs realne 20 (boundary → owner).
11. **[ARCH]** REQUIREMENTS.md nie dokumentuje `bind_kind` /
    `libvirt.backend` / `shared_folder_*` (wzorzec new-config wymaga wpisu;
    boundary → draft do needs-owner).
12. **[ARCH]** `uninstall.py:111-115` ręcznie deriwuje state/config-dir
    zamiast `installer/state.py::default_state_file()` — dwie niezależne
    derywacje tej samej ścieżki.
13. **[ARCH]** 2 commity `i18n:` poza Conventional Commits (`chore(i18n):`).
14. **[DEPS]** Stale ignore `RUSTSEC-2026-0202` w `gui/.cargo/audit.toml`
    (`advisory-not-detected`) — do usunięcia.

**Obserwacje bez akcji:** `_keepalive()` striplikowany w 3 plikach lifecycle
(dokładnie na progu reguły „wait for the fourth"); `logs_cmd.py:610` 1 Hz
queue-wakeup w `--follow` (pre-window, powierzchnia DEC-META-006); duplikaty
cargo-deny (transitive, kosmetyka).

**Werdykt:** 114 commitów pętli bez ani jednego P0 i bez złamania decyzji;
hermetyczność testów netto lepsza niż przed oknem. Wspólny wątek P1:
hasło VM chronione w 1 z 3 miejsc spoczynku, a świeżo uzbrojona ścieżka
real-libvirt nie ma jeszcze dyscypliny deadline'ów, której wymagają własne
reguły projektu. Decyzja właściciela: co naprawiamy.

---

## Audyt 2026-07-05

**Git:** `5d87d2d` on `main`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 126 files)
- pytest collected: 971
- bandit medium/high: 0

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 16
- gui cargo-deny issues: 4
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf: n/a
- .proto files: 5

**QML (`gui/`)**

- qmllint: n/a

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 0
- test files (python): 244
- #[test] annotations (rust): 84

**Drift & meta**

- architecture.md Last Updated: 2026-07-02 (3d ago)
- META decisions (status: aktywna): 7
- ADR DEC-NNNN total: 17

**Security**

- gitleaks: n/a (use `CROSSDESK_FULL_AUDIT=1 git push` for history scan)

**Cadence**

- previous audit: 2026-05-31 (35d ago)

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

### Warstwa głęboka (osąd agenta)

Metoda: 3 równoległe agenty (bezpieczeństwo+decyzje / slop+backend /
testy+architektura+dead-code); kluczowe *nowe* znaleziska zweryfikowane
ręcznie greppem+odczytem (event-loop subprocess, puste pakiety, brak
timeoutu, drift). Statyczna warstwa wzorowa (ruff/mypy/bandit/clippy/
cargo-audit = 0; cargo-deny spadł 24→16 guest, 15→4 gui; 0 TODO w src).

**Ogólna ocena:** zdrowy, zdyscyplinowany projekt. Rdzeń produktu
zweryfikowany na żywo (A7-live: świeży `crossdesk install` → agent
auto-online → Notepad/Paint jako natywne okna Linuksa, zero ręcznych
kroków). Bezpieczeństwo: 0 P0/P1 — per-frame AuthContext na wszystkich
3 planes, mTLS `require_client_auth`, tokeny kryptograficzne
(uuid4/secrets), abstrakcje respektowane, brak sekretów w git, decyzje
(No-Docker / No-polling / whole-$HOME) niezłamane. Slop niski, Manager
GUI ma uczciwe empty-state.

**P0 (standing — nie nowe, ale otwarte i blokujące):**
- **`hard_destroy` → REINSTALACJA Windows / utrata danych — BLOKUJE A3.**
  Install-ISO jest `boot order=1` przez całe życie VM; heartbeat-FSM
  auto-recovery robi `destroy()`+`create()` → bootuje install-ISO →
  autounattend reinstaluje Windows na dysku, bez człowieka. Latentny dziś
  (daemon=mock-libvirt). Realny `LibvirtController` NIE MOŻE wejść do
  lifecycle zanim nie wyląduje steady-state-XML finalize (eject ISO,
  disk boot=1, flaga „installed"). `backlog.md` P0 + `needs-owner.md`.

**P1 (nowe w tym audycie):**
- **Blokujący `subprocess.run` na pętli asyncio daemona.** `control.py:220`
  woła `rail_manager.handle_rail_event()` synchronicznie w pętli async
  `_consume_session`; ścieżka CREATED→`WindowIconStore.offer`→
  `_refresh_caches` (`display/window_icon.py:139`) odpala 2× `subprocess.run
  (timeout=15)` → do ~30s zamrożenia CAŁEJ pętli (heartbeat FSM, filesystem
  plane, wszystkie streamy) przy każdym oknie z ikoną. Komentarz
  `rail_manager.py:126` „never blocks event handling" jest fałszywy dla
  sync subprocess. Ryzyko: distortion timingu heartbeat-FSM → false-positive
  recovery. Fix: `asyncio.to_thread`/`run_in_executor`. (Pokrewne, mniejsze:
  `SubprocessNotifier.notify` `subprocess.run(timeout=2.0)` z heartbeat/rail
  na pętli.)
- **Brak negatywnych testów mTLS-handshake (named critical path).** Każdy
  test z `require_client_auth=True` pokrywa tylko happy-path; brak testu
  odrzucenia cert untrusted/wrong-CA/expired ani hostname-mismatch na
  warstwie TLS. Fingerprint-pinning (app-layer) pokryty. Znany w
  `backlog.md` Tech-debt; podniesiony do P1 bo audit.md §4 nazywa to
  MUST-cover.

**P2 (nowe):**
- `update_mime_database` (`integrations/mime.py:120`) `subprocess.run` **bez
  `timeout=`** → potencjalny wieczny hang (łamie backend.md „infinite hangs
  are bugs"; kontrast: `window_icon.py:139` ma timeout=15).
- Dwa martwe puste pakiety: `virtiofs/__init__.py` + `wayland/__init__.py`
  (0 bajtów, 0 importerów) — do usunięcia; nie w ignorefiles.
- Phase-9 scaffoldy z 0 prod-callerami, nie w ignorefiles: `recovery/`
  (`bundle`/`snapshot`; `ExportDiagnosticBundle` zwraca `zip_payload=b""`
  zamiast wołać `export_bundle`), `catalog/ratings.py` + `catalog/user_apps.py`
  (`ListApps` używa inline hardcoded listy). Wire albo dodać do manifestu.
- GUI install-wizard ma fejkowy silnik postępu (`wizard/progress.rs`
  `INSTALL_STEPS` hardcoded + `ProgressView.qml` Timer, nie woła `host/`).
  Udokumentowany jako mock w `gui/README.md`, ALE `ignorefiles.md`
  „Security / placeholder UI" mówi „(none currently)" → manifest drift.
  Eskaluje do P1 jeśli GUI kiedyś prezentowane jako funkcjonalne.
- `.claude/architecture.md` drift: „Just-in-time VirtioFS… no permanent
  home-dir mount" (`:25`) i „No permanent host-dir exposure to the guest"
  (`:62`) sprzeczne z shipowanym default whole-$HOME R/W (DEC-0018/
  DEC-META-007). architecture.md jest agent-editable → fix; `:62` mirroruje
  `GOALS.md` (boundary — tylko flaga).

**P2 (potwierdzone znane / nity):**
- fs-mount mocki (`fs-mount/src/flush.rs` `mock_generate_release_ack`→1024,
  `mock_generate_lock_report`→0 handles) wołane BEZ `#[cfg(feature=mock)]`
  z realnego filesystem-plane agenta (`agent-svc/src/filesystem.rs`) →
  placeholder trafia do prod-builda. Phase-5, ale schować za feature.
  (backlog Tech-debt — stan bez zmian.)
- AuthContext `traceparent` (proto) bez wzmianki w THREAT_MODEL — advisory,
  non-security-bearing (`auth.py` traktuje malformed jako non-fatal); 1 linia
  do THREAT_MODEL.
- Znane/tracked (nie do naprawy tu): AGENTS.md „Repository layout" 5 vs 22
  podkatalogi (boundary), autopause↔LifecycleCoordinator duplikat kolejności
  suspend („merge when third caller arrives").

**Testy:** krytyczne ścieżki (AuthValidator rejection ×3 planes, FSM
transitions z backoff, `test_smoke_inprocess` real-agent boundary) mocne
i asertywne; jedyna realna luka = negatywny mTLS-handshake (P1 wyżej).
Skips wszystkie uzasadnione (env/HW-gated), 0 xfail, 0 `assert True`.

**Decyzja właściciela:** czeka na akceptację listy → pozycje do
`backlog.md`.

---

## Audyt 2026-06-12

**Git:** `8f266bb` on `feat/usability-shared-fs`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff: n/a (not on PATH)
- mypy: n/a
- pytest: n/a
- bandit: n/a

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 24
- gui cargo-deny issues: 15
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf: n/a
- .proto files: 5

**QML (`gui/`)**

- qmllint: n/a

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 0
- test files (python): 234
- #[test] annotations (rust): 84

**Drift & meta**

- architecture.md Last Updated: 2026-06-09 (3d ago)
- META decisions (status: aktywna): 6
- ADR DEC-NNNN total: 16

**Security**

- gitleaks: n/a (use `CROSSDESK_FULL_AUDIT=1 git push` for history scan)

**Cadence**

- previous audit: 2026-05-23 (20d ago)

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

### Korekta warstwy statycznej (venv niedostępny dla audit.sh)

Skrypt nie widzi `host/.venv` — wartości policzone ręcznie z aktywowanym venv:

- ruff: **8 błędów, wszystkie w `host/tests/`** (3× I001 import-sort, 1× F401 unused
  import `test_heartbeat_boot_probe.py:20`, 3× E402 `test_lifecycle_coordinator.py:148-151`);
  5 auto-fixable
- mypy --strict: **0 błędów (121 plików)**
- pytest: **870 passed, 2 skipped, 36.9s**
- cargo-deny "issues" 24/15 = wyłącznie warningi `duplicate` (transitive windows-*
  crates) + 8× `license-not-encountered` (licencje w allowliście nieużywane przez
  graf zależności) — zero błędów, kosmetyka konfiguracji deny.toml

### Warstwa głęboka (4 równoległe przeglądy: bezpieczeństwo / slop / testy / architektura+decyzje)

**1. Bezpieczeństwo — czysto.** Per-frame `verify_auth_context` na każdej ramce
wszystkich 3 płaszczyzn (control.py:253, filesystem.py:46, heartbeat.py:205);
mTLS leaves poza git tree (`git ls-files infra/certs` → tylko generate_mtls.sh);
wszystkie bloki `unsafe` w guest/ mają `// Safety:`; spawn FreeRDP przez
list-argv (brak shell injection); walidatory shared-folder (pusta/względna
ścieżka, separatory w nazwie share, mkdir-fail → drop drive+workdir) działają
i są przetestowane.

**2. Slop — werdykt: to NIE jest AI slop.** Zero hardcoded danych udających
realne; zero "Coming soon"/TBD w src; wszystkie zaślepki (sleep_sync,
ScrapeBackend, fs-mount mocks, control.py:149 pid=9999) jawnie opisane i
zarejestrowane w ignorefiles.md/status.md; status.md uczciwie raportuje
PORAŻKI (A1 workdir UNC→System32); komentarze to "why", nie "what"; milestone'y
"LIVE-verified" mają pokrycie w realnych commitach. Jedyny znany wyjątek:
`mock_generate_release_ack` wołany bez cfg-gate z `agent-svc/filesystem.rs:98`
— już w backlogu (Tech debt).

**3. Testy — mocne na ścieżkach krytycznych.** AuthValidator rejection paths
(3 tryby × 3 płaszczyzny), FSM watchdog (wszystkie przejścia + backoff cap),
VerifyCoordinator (korelacja, timeout, trace), nowe gardy peripherals
(empty-path, relative-path, mkdir-fail — pokryte po adversarial review),
WindowIconStore (expect/offer/TTL). Znane luki bez zmian: mTLS cert-pinning
failure-modes (backlog), CLI semver snapshot (backlog). **Brak progu coverage
w pyproject** mimo deklarowanych 78% — kandydat na ratchet.

**4. Architektura/decyzje — zgodne.** No-Docker (DEC-0003) ✅; no-polling —
jedyny `while True: sleep` to zatwierdzony wyjątek `_tail_file` (DEC-META-006),
reszta to event-driven `await` ✅; brak `import libvirt` poza real.py ✅; brak
edycji proto na branchu ✅; layering config→display→ipc respektowany w nowym
kodzie ✅; brak dead code poza pozycjami z ignorefiles.md. Fałszywy alarm
odrzucony w weryfikacji: stdlib `logging.getLogger` w window_icon.py to
celowy wzorzec projektu (udokumentowany w heartbeat.py:67,
verify_coordinator.py:39, rail_manager.py:44 — caplog + configure_logging
timing), nie drift.

### Lista P0/P1/P2

**P0:** brak.

**P1:** brak nowych. (Istniejące w backlogu bez zmian stanu: fs-mount mock
cfg-gate, mTLS failure-mode testy, NT-service agent, zombie xfreerdp reaper.)

**P2 (nowe):**
1. **ruff 8 błędów w testach** — I001/F401/E402, 5 auto-fixable
   (`ruff check --fix tests/`); pre-commit gate najwyraźniej nie obejmuje
   `tests/` albo wersja ruff dryfuje vs CI.
2. **Brak coverage ratchet** — pyproject.toml nie ma `fail_under`; baseline
   ~78% znany → zamrozić podłogę (np. 75) zgodnie z regułą ratchet.
3. **audit.sh nie aktywuje `host/.venv`** — sekcja Python raportuje n/a;
   dodać `source host/.venv/bin/activate` fallback do skryptu.
4. **deny.toml: 8× license-not-encountered** — przyciąć allowlistę licencji
   do faktycznie występujących (kosmetyka).

**Cadence:** poprzedni audyt 2026-05-23 (20 dni) — powyżej 7-dniowego rytmu.

**Ratchet (zamknięte tego samego dnia, decyzja właściciela, branch
`chore/audit-p2-fixes`):** wszystkie 4 P2 naprawione — (1) `fd1365e` ruff
0 błędów + `c04769b`/`e0f73c9` bramki pre-push i CI rozszerzone na `tests/`;
(2) `e0f73c9` coverage floor `fail_under=75` (baseline 77.74%) uzbrojony
przez `--cov` w CI; (3) `31c8198` audit.sh widzi host/.venv (ruff/mypy/
pytest/bandit przestają raportować n/a); (4) `b754b42` deny.toml allowlisty
przycięte do faktycznie występujących licencji (`cargo deny check licenses`
→ "licenses ok" w guest+gui).

---

## Audyt 2026-05-31

**Git:** `73c6141` on `main`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 118 files)
- pytest collected: 804
- bandit: n/a

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 1
- gui cargo check warnings: 2
- gui clippy errors (-D warnings): 1
- cargo-deny: n/a
- cargo-audit: n/a

**Proto (`proto/`)**

- buf: n/a
- .proto files: 5

**QML (`gui/`)**

- qmllint: n/a

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 0
0
- test files (python): 214
- #[test] annotations (rust): 79

**Drift & meta**

- architecture.md Last Updated: 2026-05-24 (20604d ago)
- META decisions (status: aktywna): 5
- ADR DEC-NNNN total: 15

**Security**

- gitleaks: n/a (use `CROSSDESK_FULL_AUDIT=1 git push` for history scan)

**Cadence**

- previous audit: 2026-05-23 (20604d ago)

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

### Warstwa głęboka (agent — workflow, 17 agentów, fan-out + adwersarialna weryfikacja)

Pierwszy audyt na świeżym Linux+KVM boxie (po pełnym bootstrapie dev-env + runtime).

**Sprostowania warstwy statycznej (artefakty świeżego boxa, nie defekty kodu):**
- `guest clippy errors: 1` — błędne. `cargo clippy --workspace -- -D warnings` exit 0; guest **czysty**. Liczba w automacie to przeciek z gui / cold-build.
- `gui cargo check warnings: 2` + `gui clippy errors: 1` — to **porażka builda `cxx-qt 0.7.3`**, bo brak Qt6-dev + szybkiego linkera (mold/lld/gold) na tym boxie. Luka dev-env (do bootstrapu: `qt6-base-dev qt6-declarative-dev mold`), nie kod.
- `architecture.md … 20604d ago` + `previous audit … 20604d ago` — **bug `audit.sh`**: `date -j -f` (BSD/macOS) nie parsuje na Linuksie → epoch 0. Realnie poprzedni audyt 2026-05-23 (8 dni temu).
- bandit / cargo-deny / cargo-audit / buf / qmllint / gitleaks = `n/a` (niezainstalowane lokalnie) → pokrycie audytu zawężone (CI je pokrywa).
- Stray `0` po linii TODO/FIXME (l.38-39) — drobny double-print w `count_lines` na pustym wejściu.

**Fan-out:** 8 surowych znalezisk → **4 confirmed, 4 dropped** + 1 od krytyka kompletności.

**Confirmed:**
- **[P1] Polling** `host/src/crossdesk_host/cli/logs_cmd.py:492` (`_tail_file`) — `while True: … await asyncio.sleep(0.25)`. Łamie regułę „No polling" (AGENTS.md „Coding rules"). Docstring uzasadnia (unika zależności inotify/kqueue), ale **brak zatwierdzonego wyjątku** w `decisions.md` / `docs/DECISIONS.md`. → decyzja właściciela: zatwierdzić wyjątek i udokumentować, ALBO przepisać na inotify (`asyncio.add_reader` na fd inotify).
- **[P2] Hardcoded `1024`** `guest/crates/fs-mount/src/flush.rs:31` — `total_bytes_written: 1024` w `mock_generate_release_ack()`, wołane bezwarunkowo z `agent-svc/src/filesystem.rs:98` (bez cfg-gate). Znany Phase-5 stub (`status.md` „Mock virtiofs handlers"); nowy kąt = **feature-gate** by nie trafiał do prod-builda.
- **[P2] Empty `icon_png`** `guest/crates/rail-bridge/src/events.rs:71` — `icon_png: vec![]` (Phase 4 placeholder), osiągalne z `windows.rs:117`. Ikony okien zawsze puste do Phase 4.
- **[P2] Drift `AGENTS.md:102-108`** — „Repository layout" listuje 5 podkatalogów `crossdesk_host/`, faktycznie 23 (m.in. `cli/`, `doctor/`, `abstractions/`, `lifecycle/`, `filesystem_ctl/`…). **AGENTS.md = boundary file** → zmiana wymaga zgody właściciela.
- **[P2] Brak `// Safety:`** (krytyk) `guest/crates/registry-scan/src/windows_impl.rs:266` — `display_name.unwrap()` bez komentarza, mimo że ten sam plik używa `// Safety:` poprawnie (l.246/260). Infallible (None → early-return l.245), ale łamie regułę backendu „unwrap/expect wymaga komentarza".

**Dropped (poprawnie — false positives wychwycone przez weryfikację):**
- Phase-5 mocki wołane bezwarunkowo — udokumentowane (`status.md`, `EXECUTION_PLAN.md` Week 18).
- `[mock]` marker w MountResult detail — intencjonalny.
- test-credsy `crossdesk`/`test123` — za `#[cfg(test)]` / `--features mock`, nieobecne w prod-buildzie.
- `TraceContext::is_valid()` „dead" w Rust — realnie używane po stronie hosta (`observability/trace_ctx.py:167`), świadoma symetria API host↔guest.

**Luki / rekomendacje procesowe (krytyk kompletności):**
- Brak automatycznego grep-gate na `import libvirt` poza `*real.py` — dziś tylko dyscyplina reviewera. Kandydat na ratchet (analogicznie do mock-import-gate, FOLLOWUPS:269).
- Brak testów failure-mode mTLS (cert-pinning / hostname-validation); `AuthValidator` pokrywa rejection paths, ale nie scenariusze mTLS-specific.
- `DEFAULT_HOST_ENDPOINT 127.0.0.1:50051` (`agent-svc/src/planes.rs`) — dev-default czytany z env w runtime; brak checklisty pre-prod.

### Lista P0/P1/P2 (do decyzji właściciela)

- **P0:** brak.
- **P1:** Polling `logs_cmd.py:492` — wymaga rozstrzygnięcia (zatwierdzić wyjątek vs przepisać na inotify).
- **P2:**
  1. feature-gate Phase-5 mocków `fs-mount` (`flush.rs:31` hardcoded 1024).
  2. `rail-bridge/events.rs:71` empty `icon_png` (Phase 4 — już na liście followups RAIL).
  3. `AGENTS.md:102-108` layout drift (boundary — zgoda właściciela na edycję).
  4. `// Safety:` na `windows_impl.rs:266`.
  5. `audit.sh` `date -j` → port na GNU `date -d` (tooling).
  6. grep-gate `import libvirt` poza `*real.py` (ratchet).
  7. testy failure-mode mTLS.

**Werdykt:** kod produktowy zdrowy — 0 P0, 1 P1 (polling, wymaga tylko decyzji), reszta to świadomie odroczone stuby i porządki. Adwersarialna weryfikacja odrzuciła 4/8 surowych znalezisk jako false-positives.

---

## Audyt 2026-05-23

**Git:** `f2ff03c` on `chore/adopt-claude-toolkit`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 117 files)
- pytest collected: 783
- bandit medium/high: 0

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 26
- gui cargo-deny issues: 15
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf lint findings: 0
- buf format diff lines: 0
- .proto files: 5

**QML (`gui/`)**

- qmllint warnings: 0

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 1
- test files (python): 207
- #[test] annotations (rust): 79

**Drift & meta**

- architecture.md Last Updated: 2026-05-20 (3d ago)
- META decisions (status: aktywna): 5
- ADR DEC-NNNN total: 15

**Security**

- gitleaks worktree findings: 0

**Cadence**

- previous audit: 2026-05-23 (0d ago)

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

---

## Audyt 2026-05-23

**Git:** `ba357af` on `chore/adopt-claude-toolkit`

### Warstwa statyczna (automat)

**Python (`host/`)**

- ruff findings: 0
- mypy --strict errors: 0 (across 117 files)
- pytest collected: 783
- bandit medium/high: 0

**Rust (`guest/`, `gui/`)**

- guest cargo check warnings: 0
- guest clippy errors (-D warnings): 0
- gui cargo check warnings: 0
- gui clippy errors (-D warnings): 0
- guest cargo-deny issues: 26
- gui cargo-deny issues: 15
- guest cargo-audit vulns: 0
- gui cargo-audit vulns: 0

**Proto (`proto/`)**

- buf lint findings: 0
- buf format diff lines: 0
- .proto files: 5

**QML (`gui/`)**

- qmllint warnings: 0

**Code hygiene**

- files with TODO/FIXME/HACK/XXX (src only): 1
- test files (python): 207
- test files (rust): 1

**Drift & meta**

- architecture.md Last Updated: 2026-05-20 (3d ago)
- META decisions (status: aktywna): 0
0
- ADR DEC-NNNN total: 15

**Security**

- gitleaks worktree findings: 0

**Cadence**

- previous audit: none yet

**Do przeglądu agentem (warstwa głęboka):** bezpieczeństwo, slop, jakość testów, architektura, dead-code weryfikacja, zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`, MCP/skills. Procedura: `.claude/rules/audit.md`.

### Warstwa głęboka (agent review)

Pierwszy bieg po adopcji konwencji `claude-toolkit`. Zakres jak w
`.claude/rules/audit.md`. **TL;DR: codebase jest dobrze utrzymany —
0 P0, 0 P1 z nowych findings. Tylko 5 pozycji P2 (kosmetyka).**

#### Bezpieczeństwo
- **mTLS leaves w git history:** zweryfikowane greppem `git log --all
  --diff-filter=A -- 'infra/certs/'` — **NIGDY** nie były tracked. Tylko
  `generate_mtls.sh` ma historię. Komentarz w `.gitignore` jest stale i
  wprowadza w błąd (P2 niżej).
- **`gitleaks` worktree:** 0 findings.
- **`bandit -ll`:** 0 medium/high.
- **gRPC servicers:** `AuthValidator` (117 LOC w `ipc/auth.py`)
  enforces per-frame check via async `verify_auth_context`. Touch
  boundary per AGENTS.md — nie modyfikowane.

#### Slop / hardcoded data udające realne
- `ipc/control.py:141` zwraca `process_id=9999` jako placeholder
  z dokumentowanym komentarzem ("keeps the proto contract honest").
  Reachable tylko przez Phase 4 stub `cli/launch_cmd.py`, który też
  jest stubem. Świadome + dokumentowane.
- Hardcoded UI strings: 0 znalezionych (brak `Anna Kowalska`,
  `Lorem ipsum`, `John Doe` itp. w `host/src` i `gui/`).
- `palette.placeholderText` w QML to nazwa koloru Qt theme, nie UI
  string.

#### Backend
- **0 `while True: sleep()` polling.** Wszystkie `while True` (9
  hits w `host/src`) są await-driven: `asyncio.sleep`,
  `asyncio.Event.wait`, file `read()` chunked do EOF.
- **0 swallowed errors bez justyfikacji.** Wszystkie 10 hits
  `except Exception:` mają albo:
  - re-raise po cleanup (atomic write pattern w `atomic_write.py`,
    `user_apps.py`, `keyring/file_backend.py`, `credentials.py:112`)
  - explicit best-effort comment + log/notification call
    (`launch_cmd.py` z `nosec B110`, `rail_manager.py:127` z
    `logger.exception` + `notify_rdp_drop`)
  - dokumentowany "swallow silently — failed notification mustn't
    take down daemon" (`notifications.py:60`)
- **gRPC + HTTP timeouts:** AuthValidator enforces `_token_ok` +
  per-stream nonce. Server-side timeouts: gRPC server `add_secure_port`
  use default timeout-on-shutdown. Client-side: nie znaleziono
  bezpośrednich `aiohttp.ClientSession` w `host/src/` (ISO downloader
  jest mock-stub Phase 5).

#### Testy
- **783 pytest tests collected** (.5s wall — fast suite).
- **79 Rust `#[test]` annotations** across 11 plików w `guest` + `gui`
  (audit.sh policzył tylko 1 — bug regexu, P2 niżej).
- Strong coverage na krytycznych ścieżkach: `AuthValidator`,
  `LifecycleCoordinator` (7 nowych testów hibernation 2026-05-19),
  `HeartbeatServiceServicer.Channel` (boot_probe + missed-prepare
  heuristic + suspend/resume propagation), `RailManager` (26 tests
  na out-of-order events).
- Mock contract tests (`MockFilesystemController` 13, `MockLibvirt`
  per-method failure injection) — boundary fidelity.

#### Architektura
- **Abstrakcje respektowane:** `libvirt` importowany tylko w
  `libvirt_ctl/real.py` (10 funkcji + 1 type-only przy module-top).
  Brak `import libvirt` poza tym plikiem.
- **`*.mock` imports zgodne z policy:** 2 hits — `daemon.py:43`
  (Phase 3 dev-default, dokumentowany) + `filesystem_ctl/__init__.py:14`
  (subpackage re-export, whitelisted). CI grep gate aktywne.
- **DEC-0003 (no Docker):** ✓ brak Dockerfile / compose.yaml.
- **DEC-0005 (mock-driven):** ✓ Protocol abstrakcje + mock impls
  potwierdzone.
- **DEC-0006 (structured logging + trace):** ✓ `structlog` +
  `trace_ctx` + `traceparent` w `common.proto`.
- **`.claude/architecture.md` Last Updated: 2026-05-20** — 3d ago.
  Adoption commits z dziś nie bumpnęły bo `core.hooksPath` w tym
  clone'ie wskazuje na `.git/hooks/` (default), nie na
  `.githooks/`. Aktywacja per-clone (zob. CLAUDE.md "One-time setup").
  P2 niżej.

#### Dead code (weryfikacja heurystyk)
Wszystkie potencjalnie martwe pozycje wykryte greppem są DOKUMENTOWANE
w `.claude/ignorefiles.md` lub komentarzem w pliku:
- `iso_downloader.py::ScrapeBackend` — Phase 5 placeholder
  (ignorefiles.md).
- `watchdog/sleep_sync.py` — Phase 7 stub (ignorefiles.md).
- `cli/launch_cmd.py` — Phase 4 RAIL stub (ignorefiles.md).
- `guest/crates/registry-scan/src/windows_impl.rs:30` — Phase 8 TODO
  (App Discovery, backlog P0).
- `notifications.py::DBusNotifier._send_sync` — Phase 7 stub, ale
  **brak w ignorefiles.md** (P2 niżej, dodać po następnym commicie).

#### Zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`
- **15 ADR DEC-NNNN** w `docs/DECISIONS.md`. Wyrywkowa kontrola:
  DEC-0003 ✓, DEC-0005 ✓, DEC-0006 ✓.
- **5 META decyzji DEC-META-001..005** w `.claude/rules/decisions.md`
  (audit.sh nie policzył przez bug regexu, P2).
- 0 wykrytych regresji łamiących aktywną decyzję.

#### Skille / MCP
- `~/DevProjects/claude-toolkit/skills/` ma 1 skill (`weekly-audit`).
  Skopiowany do `.claude/skills/weekly-audit/SKILL.md` w tym commicie.
- **MCP:** brak `.mcp.json` w repo. Nic do sprawdzenia.

#### P0 / P1 / P2 z tego biegu

**P0:** żadnych. Codebase jest czysty pod kątem bezpieczeństwa,
swallowed errors, hardcoded data, decision violations.

**P1:** żadnych. Wszystkie partial / hardware-gated pozycje są już
udokumentowane w `.claude/status.md` lub `.claude/backlog.md`.

**P2 (kosmetyka — wszystkie meta o samej infrze audytu, nie o
codebase):**

1. **`audit.sh` regex bug — META decisions count.** Linia 144
   audit.sh: `grep -cE '^- \*\*DEC-META-[0-9]+'` nie matchuje
   bo nagłówki w `.claude/rules/decisions.md` są w formacie
   `^## DEC-META-NNN`. Fix: zmień regex na `^## DEC-META-[0-9]+`.
   Też wyciekło stray `0` w output (`||` fallthrough). Cel: liczyć
   poprawnie + bez "0\n0" stray output.
2. **`audit.sh` Rust test count bug.** Linia 113:
   `find guest gui -path '*/tests/*'` znajduje tylko integration
   test files. Unit testy w `mod tests` blocks (79 hits via
   `grep -rE '^\s*#\[(test|tokio::test)' --include='*.rs'`) nie są
   zliczone. Fix: zamień find na grep.
3. **`.gitignore` stary komentarz o mTLS keys.** Linie 67-69
   sugerują że `infra/certs/{ca,host,guest}.{key,crt}` są w git
   history — zweryfikowane: **nigdy nie były**. Tylko
   `generate_mtls.sh` był tracked. Komentarz wprowadza w błąd
   (sugeruje rotację + `git filter-repo` które są niepotrzebne).
   Fix: usuń lub przepisz komentarz na "files MUST never be
   tracked; rotate locally via generate_mtls.sh".
4. **`.claude/ignorefiles.md` brakuje wpisu** dla
   `notifications.py::DBusNotifier._send_sync` (Phase 7 stub
   landed wcześniej). Mały drift — dodać entry żeby vulture /
   dead-code audit nie raportował.
5. **Post-commit hook nie aktywny w tym clone'ie.**
   `core.hooksPath = .git/hooks` (default), nie `.githooks/`.
   Skutek: `.claude/architecture.md` + `.claude/ignorefiles.md`
   `Last Updated:` stamps drift względem realnego stanu repo.
   Aktywacja per-clone (`git config core.hooksPath .githooks`) jest
   udokumentowana w CLAUDE.md, ale brak automatycznej weryfikacji.
   Opcje: (a) dodać do `audit.sh` check że hooks są aktywne +
   ostrzeżenie; (b) po prostu uruchomić aktywację teraz; (c) zostawić
   bez zmian (user-clone responsibility per CLAUDE.md).

Audytu nie kończy żaden P0/P1 — wszystkie pozycje są albo
porządkowe (P2) albo już są w `backlog.md` / `status.md`.

---

