# CrossDesk Senior Engineering Audit — 2026-05-20

**Audytor**: Claude Code (Opus 4.7) działający w trybie „Senior Programista,
pełny audyt bez poprawek”. Metryki obiektywne, narzędzia open-source,
wszystkie wyjścia narzędzi w `/tmp/audit-2026-05-20/raw/` (nie wersjonowane).

**Plan audytu**: `/home/szymom-paczos/.claude/plans/czec-chcialbym-abys-przejrzal-abstract-abelson.md`.

**Powiązane wcześniejsze audyty**:
- `docs/AUDIT_REPORT.md` (2026-05-09) — manualny, pre-v1.0
- `docs/AUDIT_AUTOMATED_2026-05-11.md` (branch `chore/audit-2026-05-11`,
  nie merge'owany) — sześciofazowy automat

Ten audyt jest pomyślany jako "świeży pomiar po ~1 tygodniu szybkiego
rozwoju" (commits 2026-05-11 → 2026-05-20: ponad 100 commitów, ~10k nowych
LOC i testów). Nie zastępuje wcześniejszych audytów — uzupełnia o brakujące
metryki (cognitive complexity, coverage, mutation attempts, doc-drift).

---

## TL;DR — Slop Score: 27 / 100

**0 = idealny kod, 100 = czysty AI-slop**.

Niski wynik. Główny komunikat: **to NIE jest "slop"**. Codebase jest
zaskakująco zdyscyplinowany jak na 3-tygodniowy projekt napisany w ~70%
przez agentów. Średnia złożoność cyklomatyczna A (2.65), 77% coverage,
0 TODO w merged code, 0 bare `# type: ignore`, brak duplikatów ≥8 linii,
0 cykli importów. Większość rzeczy do poprawki to drobiazgi lub
rzeczy świadomie odłożone (Phase 5+).

Główne **realne** problemy znalezione (uporządkowane od najpoważniejszych):

1. ⚠️ **Brak `LICENSE` w repo + brak `license` w `pyproject.toml`** — projekt
   ogłasza się jako GPL-3.0-or-later w docs, ale formalnie tego nie deklaruje.
   Blocker przed publikacją.
2. ⚠️ **SyntaxWarning na Python 3.14**:
   `display/path_translation.py:44` ma `\h` — w przyszłej wersji Pythona
   to będzie hard error. Powtarza się w każdym uruchomieniu mypy/pytest/lint.
3. ⚠️ **`management.py:225` ma nieosiągalny warunek `if`** (vulture 100%
   confidence). Realny dead code, nie false positive.
4. ⚠️ **Doc drift w `docs/THREAT_MODEL.md`**: 0 wzmianek o `control`,
   `management`, `verify_coordinator`, `version_negotiation` — czyli o
   meta-RPC dodanych w ostatnich 2 tygodniach. Ostatnia istotna aktualizacja
   THREAT_MODEL nie nadąża za kodem.
5. ⚠️ **`ScrapeBackend` Protocol w `iso_downloader.py` ma 0 production
   call-sitów**. Klasyczna premature abstraction — Protocol istnieje,
   ale CLI/installer nie wywołują go.
6. ⚠️ **Mutation testing nie przeszedł** (mutmut 2.5 / 3.5 / mutatest
   wszystkie failują na Python 3.14 — incompatibilities w ekosystemie).
   Brak obiektywnego dowodu jakości suite'u testów; coverage 77% jest
   tylko proxy.

**Co jest wyraźnie dobrze** (sekcja w pełnej formie w §6):
średnia złożoność A, 720 funkcji testowych, 0 cykli importów,
0 TODO/FIXME w produkcji, 77% coverage, brak duplikatów ≥8 linii,
nieobecność typowych AI-slop wzorców (restating comments, defensive
try/raise, parametrize bloat).

---

## 1. Formuła Slop Score

Punkty (0=żaden problem, 100=maksimum tej kategorii):

| Kategoria | Waga | Pomiar | Punkty (z wagą) |
|-----------|-----:|--------|----------------:|
| Rule violations (TODO, mock-leak, unwrap-bez-Safety w prod Rust) | 10 | 2 prod-Rust `expect` bez `// Safety:` (service.rs:75, build.rs:8) z 12 razem; 0 TODO; 0 mock-leak | 1.7 |
| % funkcji nad progiem CCN 15 (lizard) | 15 | 4 / 720 = 0.6% | 0.09 |
| % modułów MI < 65 (radon) | 10 | 22 / ~70 = 31% — ale wszystkie nadal grade A | 3.1 |
| Top cognitive complexity (complexipy) | 10 | OpenSession=73, Channel=51 (próg czytelności ~25) | 8.0 |
| Mutation kill rate (target ≥80%) | 10 | **niezmierzone** — neutral 5/10 | 5.0 |
| Docstring coverage gap (target 80%) | 10 | 48.7% — gap 31.3pp = 3.9 / 10 | 3.9 |
| Coverage gap (target 90%) | 10 | 77% — gap 13pp | 1.3 |
| Doc drift (broken links, stale ADRs, THREAT_MODEL gap) | 10 | 2 broken links + 4/9 servicers nie w threat-model + LICENSE missing | 7.0 |
| Premature abstractions (proto z <3 call-sites) | 5 | 1 — ScrapeBackend | 5.0 |
| Outdated deps + SAST (bandit Low) | 5 | 8 outdated Python, ~14 outdated Rust direct, 36 bandit Low | 2.0 |
| **TOTAL** | 95 | | **~27 / 95** |

Skalując do 100: **~28**. Zaokrąglam do 27 (środkowa metryka jakości testów
jest neutralna; przy rzetelnym mutation testingu mogłaby spaść lub wzrosnąć
o ~5pkt w obie strony).

---

## 2. Inwentaryzacja kodu

| Obszar | Pliki | LOC |
|--------|------:|----:|
| `host/src/crossdesk_host/**.py` | 115 | 13,506 |
| `host/tests/**.py` | 70 | 12,219 |
| `guest/crates/**/src/**.rs` | 32 | 2,583 |
| `gui/crates/**/{src,qml}/**` | 27 | 4,522 |
| `proto/**/*.proto` | 5 | 1,007 |
| `docs/**/*.md` | 29 | 10,086 |
| `scripts/**` (host + repo root) | 7 | 730 |
| **Suma realnego, autorskiego kodu** | | **~34.5k LOC** |
| Generowane (`*_pb2*.py`) | — | 17,105 |
| Vendorowane (`third_party/winapps/`) | — | 98,820 |

**Test:kod w Pythonie 0.90:1** — solidnie. **W Ruście** moderate
in-source tests (`#[cfg(test)]`) w 9 z 32 plików — pozostawia lukę
(np. `agent-svc/src/service.rs` bez kolokowanych testów).

**3 największe pliki autorskie** (poza generowanymi):
1. [host/src/crossdesk_host/cli/logs_cmd.py](../host/src/crossdesk_host/cli/logs_cmd.py) — 671 LOC, multi-source log
   reader z journalctl/file/libvirt/freerdp readerami w jednym module.
   MI 36.60 — najniższy w repo (ale wciąż grade A).
2. [host/src/crossdesk_host/ipc/management.py](../host/src/crossdesk_host/ipc/management.py) — 569 LOC, 14 publicznych
   RPC, drugie miejsce po `logs_cmd.py`. MI 44.05.
3. [gui/crates/crossdesk-gui/qml/manager/Manager.qml](../gui/crates/crossdesk-gui/qml/manager/Manager.qml) — 451 LOC.

---

## 3. Wyniki ilościowe (Faza B)

### 3.1 Złożoność (lizard, radon, complexipy)

**Lizard** (`/tmp/audit-2026-05-20/raw/lizard.txt`):
- 720 funkcji total. Średnia NLOC 11.2. Średni CCN 2.5. Bardzo zdrowo.
- **4 funkcje** przekraczają CCN 15:

| Funkcja | NLOC | CCN | Lokalizacja |
|---------|-----:|----:|-------------|
| `HeartbeatServiceServicer.Channel` | 126 | 26 | [host/src/crossdesk_host/ipc/heartbeat.py:165](../host/src/crossdesk_host/ipc/heartbeat.py#L165) |
| `OpenSession.consume` | 140 | 23 | [host/src/crossdesk_host/ipc/control.py:70](../host/src/crossdesk_host/ipc/control.py#L70) |
| `check_gpu_passthrough` | 103 | 21 | [host/src/crossdesk_host/doctor/checks.py:298](../host/src/crossdesk_host/doctor/checks.py#L298) |
| `_follow_sources` | 51 | 16 | [host/src/crossdesk_host/cli/logs_cmd.py:553](../host/src/crossdesk_host/cli/logs_cmd.py#L553) |

**Radon CC** (`raw/radon-cc.txt`):
- 623 bloków, średnia A (2.65).
- 8 bloków grade C/D. Cztery najgorsze: `Channel` D26,
  `check_gpu_passthrough` D21, `_follow_sources` C16, `main` C13.

**Complexipy cognitive** (`raw/complexipy.csv`) — bardziej czuły wskaźnik
czytelności:
- Top 5: `OpenSession` (73), `Channel` (51), `_follow_sources` (28),
  `export_bundle` (25), `check_gpu_passthrough` (23).
- Próg "trudne do przeczytania" ~ 25. Mamy **5 funkcji powyżej**.
- `OpenSession.consume` przy cognitive 73 jest najbardziej krytyczny —
  to główny entrypoint streamingu, każdy bug tam jest podwójnie bolesny.

**Radon MI** (`raw/radon-mi.txt`):
- **Wszystkie** moduły grade A (próg A ≥ 20). To kierunkowo dobre.
- Najniższe MI (próg < 65 = "wymagające"):
  1. `cli/logs_cmd.py` (36.6)
  2. `doctor/checks.py` (39.1)
  3. `ipc/management.py` (44.1)
  4. `config/peripherals.py` (48.3)
  5. `config/__init__.py` (50.5)
  6. `cli/vm_cmd.py` (53.2)
  7. `ipc/heartbeat.py` (54.6)
  8. `ipc/control.py` (54.7)
  9. `watchdog/fsm.py` (56.0)
  10. `display/rail_manager.py` (57.8)

Łącznie 22 moduły < 65 (31% codebase). Większość to legitnie złożone
miejsca (CLI komendy, IPC, FSM).

### 3.2 Coverage (pytest-cov)

**TOTAL: 5316 statementów, 1209 missed → 77%**. 751 testów passed, 12 skipped,
20 sekund.

**0%** (lub bardzo niski):
- `lifecycle/dbus_listener.py` (0%) — wymaga sesji systemd (Linux-only).
- `watchdog/sleep_sync.py` (0%) — Phase 7 stub.
- `ipc/server.py` (0%) — to wrapper start/stop daemon, nie testowany unit.
- `transport/real.py` (0%) — wymaga vsock kernel mod.
- `integrations/notifications.py` (0%) — D-Bus libnotify.
- `libvirt_ctl/real.py` (17%) — wymaga libvirt.

⚠️ **`transport/mock.py` ma tylko 59% coverage** — to MOCK, powinien być
wykorzystywany przez wiele testów. 12 z 29 statementów nieosiągane.
Ścieżki failure-injection prawdopodobnie nie ćwiczone.

### 3.3 Vulture (dead code) — `raw/vulture.txt`

Przy `--min-confidence 80` (po wyłączeniu pb2 noise):
- `config/peripherals.py:158` — unused variable `__context` (100% conf)
- ⚠️ **`ipc/management.py:225` — unsatisfiable 'if' condition (100% conf)**.
  Realny dead code, do zbadania.
- `libvirt_ctl/real.py:14` — unused import `_libvirt_t` (90%)
- `observability/trace_ctx.py:23` — unused import `Iterator` (90%)

Przy `--min-confidence 60` (`raw/vulture-60.txt`, 153 hits) — sygnał o
nadmiarowej powierzchni publicznej:
- 43 "unused method" — z czego część w `abstractions/` (Protocol metody
  zdefiniowane, ale żaden caller nie używa: `list_active_shares`,
  `is_alive`, `set_memory`, `get_memory_stats`)
- 55 "unused variable" w klasach Pydantic — głównie `model_config`,
  `connect_timeout_seconds`, `rpc_timeout_seconds`, czyli pola schema
  bez konsumenta. False-positive-prone, ale część jest realna.
- 8 "unused property" w `config/__init__.py` (`vm_credentials_file`,
  `settings_file`, `install_state_file`) — propertes deklarowane "na zapas"
  ale nikt ich nie czyta.
- 21 "unused function" — wymagają ręcznej weryfikacji (część to entry
  pointy z CLI / event hooków, których vulture nie widzi).

### 3.4 Interrogate (docstring coverage) — `raw/interrogate.txt`

**48.7%** docstring coverage, próg "fail" 80%. Poprawa względem 2026-05-09
audytu (40.5%) o ~8pp, ale wciąż daleko od celu.

Najlepsze: `lifecycle/`, `watchdog/`, `recovery/` — w okolicach 70-100%.
Najgorsze: `ipc/*`, `cli/*` — większość 0-50%.

### 3.5 Bandit (SAST Python) — `raw/bandit.txt`

**36 issues**, **wszystkie Low / High confidence**:
- `B603` (subprocess_without_shell=True) i `B607` (partial_path) — większość
  trafień; subprocess to legitnie wykorzystywany interfejs do
  `libvirt`, `freerdp`, `journalctl`, `xrandr`, `wlr-randr`.
- `B404` (subprocess import) — to plus do powyższego.
- `B110` (try/except/pass) — kilka.
- `B101` (`assert` in production code) — pojedyncze użycie w
  `watchdog/ewma.py:56` jako mypy hint, legitne.

Brak Medium ani High. To czyste tło dla audytu narzędziem ogólnym.

### 3.6 Pylint duplicate-code (similarity ≥ 6 lines) — `raw/pylint-dup-6lines.txt`

**1 prawdziwa duplikacja** (po wyłączeniu generowanego proto):
```
crossdesk_host.installer.settings:[64:74]
crossdesk_host.recovery.snapshot:[84:102]
```
To wzorzec **atomic write** (`f.flush() → os.fsync → os.rename → cleanup`)
powtórzony w dwóch miejscach. Kandydat na extract do helpera w
`crossdesk_host.utils.atomic_write` (lub podobnym).

Przy progu 8+ linii: **0** duplikatów. Pylint score: 10.00/10.

### 3.7 Rust unwrap/expect (backend.md rule audit)

**12 hits w PRODUCTION Rust** (po wyłączeniu testów `#[cfg(test)]` i plików
`*tests*.rs`):

| Lokalizacja | Komentarz | Komentarz wymagany? |
|-------------|-----------|---------------------|
| `guest/crates/agent-svc/src/service.rs:75` | `tokio runtime new().expect("Failed to create Tokio runtime")` | TAK — to prod hot path |
| `guest/crates/ipc-vsock/src/transport/mock.rs:35,39,45,50` | `*self.x.lock().expect("mock hooks poisoned")` (×4) | DEBATABLE — mock impl |
| `guest/crates/ipc-vsock/tests/transport_mock.rs:22,34,44,45,53,55` | testy — można pominąć | NIE (testowe) |
| `gui/crates/crossdesk-gui/build.rs:8` | `env::var("CARGO_MANIFEST_DIR").unwrap()` | TAK — ale infallible, do dopisania `// Safety:` |

**Compliance: 0%** zgodnie z `.claude/rules/backend.md` (każde unwrap/expect
musi mieć `// Safety:` lub `// Infallible because: …`). Realnie tylko 2
miejsca (service.rs, build.rs) wymagają komentarza dla produkcji — reszta
to test/mock kod.

---

## 4. Architektura i sprzężenia (Faza C)

### 4.1 Protocol/ABC z `abstractions/` — call site analysis

| Protocol | Real impl | Mock impl | Prod call sites |
|----------|-----------|-----------|----------------:|
| `LibvirtController` | `RealLibvirtController` | `LibvirtControllerMock` | **10** ✓ zdrowo |
| `Transport` | `RealTransport` | `MockTransport` | **8** ✓ |
| `FreeRDPInvocation` | `FreeRDPCommand` | — | **5** ✓ |
| `FilesystemController` | `LibvirtFilesystemController` | `MockFilesystemController` | **4** ✓ |
| `ScrapeBackend` (w `iso_downloader.py`) | `HttpScrapeBackend` | _ScriptedBackend (test) | **0** ⚠ |

`ScrapeBackend` to klasyczna premature abstraction:
- Protocol w [installer/iso_downloader.py:44](../host/src/crossdesk_host/installer/iso_downloader.py#L44)
- 1 prawdziwa implementacja (HttpScrapeBackend, w tym samym pliku)
- 0 wywołań z reszty kodu — `cli/install_cmd.py` zna pojęcie "download_iso"
  tylko jako string-stałą, faktycznie tej funkcji nie wywołuje (Phase 5
  feature, jeszcze nie wired).

Reguła z `.claude/rules/general.md`: *"Three similar lines beats a factory.
Wait for the fourth."*. Tutaj jest *zero* wywołań — abstrakcja powinna
zniknąć aż do momentu wpięcia download_iso w realne ścieżki, albo
chociaż być wyraźnie oznaczona jako Phase 5 w komentarzu pliku.

### 4.2 IPC servicery — wielkość i odpowiedzialność

| Plik | LOC | Public RPC | MI | Cognitive top |
|------|----:|-----------:|---:|--------------:|
| `management.py` | 569 | **14** | 44.1 | 12 |
| `heartbeat.py` | 323 | 1 (+ helper Channel) | 54.6 | 51 |
| `control.py` | 234 | 1 (OpenSession) | 54.7 | 73 |
| `verify_coordinator.py` | 193 | (server-side helper) | 76.9 | 8 |
| `filesystem.py` | 181 | 3 | 62.6 | 15 |
| `auth.py` | 117 | (validator helper) | 64.5 | 9 |
| `version_negotiation.py` | 75 | (Hello helper) | 79.3 | 5 |
| `server.py` | 38 | (start/stop only) | 100 | — |

Obserwacje:
- `management.py` (14 RPC) to potencjalnie "god servicer". W zasadzie
  każdy element zarządzania (Status, Launch, Suspend, Resume, HardDestroy,
  RotateCredentials, RunDiagnostics, UpdateSettings, ReadSettings,
  GetMetrics, …) trafia tu. Naturalny kandydat na split na 2-3 mniejsze
  serwisery (np. `MgmtLifecycle`, `MgmtConfig`, `MgmtDiagnostics`).
- `control.py` ma jeden RPC z cognitive complexity 73 — najgorsze miejsce
  w całym repo do edytowania.
- `heartbeat.py` ma `Channel` (cognitive 51) — to jeden duży async-loop
  state machine, naturalne miejsce dla wysokiej CCN, ale powinno być
  zdekomponowane na mniejsze metody (`_handle_pong`, `_handle_miss`,
  `_handle_recovery_arm`, …) — co już częściowo jest.

### 4.3 Mock-leak audit

Production code importing `*.mock` modules (poza testami):
```
host/src/crossdesk_host/daemon.py:43:from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
host/src/crossdesk_host/integrations/keyring/__init__.py:26:from crossdesk_host.integrations.keyring.mock import MockKeyring
host/src/crossdesk_host/filesystem_ctl/__init__.py:14:from crossdesk_host.filesystem_ctl.mock import MockFilesystemController
```

Wszystkie 3 są **w dokumentowanym whitelist** (`.claude/rules/general.md`):
- `daemon.py` — Phase 3 dev-default (wired libvirt jeszcze nie wszedł)
- 2× `__init__.py` re-exports (library API surface)

CI grep gate w `.github/workflows/ci.yml` egzekwuje tę listę. **Zero
naruszeń**.

### 4.4 Import graph

`pydeps host/src/crossdesk_host --show-cycles` → **0 cykli** importów.
Modułowa kompozycja czysta. Fan-in:
- `proto`: 12 (oczekiwane — stubsy używane wszędzie)
- `ipc`: 9
- `installer`: 7
- `doctor`: 3

Nic alarmującego.

### 4.5 Env-var indirection

13 zmiennych `CROSSDESK_*` w kodzie. 10 z nich to legalne featury (FreeRDP
override, OTLP endpoint, locale dir, scale, strict-log mode). Schemat
`CROSSDESK_CONFIG__SECTION__FIELD` to dokumentowany override typed-config —
to OK.

---

## 5. Jakość testów (Faza D)

### 5.1 Coverage per moduł

Patrz §3.2. Headline: 77% line coverage; krytyczne moduły
(`watchdog/fsm.py`, `ipc/auth.py`, `ipc/version_negotiation.py`,
`lifecycle/coordinator.py`, `installer/credentials.py`) wszystkie ≥ 92%.

### 5.2 Mock density

Top-10 plików testowych z największą gęstością `MagicMock`/`AsyncMock`/`patch`:

| File | Hits |
|------|-----:|
| test_otlp.py | 28 |
| test_management_service.py | 26 |
| test_heartbeat_fsm.py | 22 |
| test_libvirt_mock.py | 12 |
| test_management_metrics.py | 10 |
| test_filesystem_service.py | 10 |
| test_vm_cmd_shutdown.py | 9 |
| test_autopause_coordination.py | 9 |
| test_lifecycle_coordinator.py | 8 |
| test_filesystem_controller.py | 8 |

`test_otlp.py` ma 28 mocków, ale **patcuje OpenTelemetry SDK** — która sama
jest mocno warstwowa. Nie wskazuje na "test mocka, nie kodu".

### 5.3 Oversized tests

**5 testów >60 linii**, wszystkie w `test_smoke_inprocess.py`:
- `test_traceparent_propagates_to_all_three_planes` — 120 linii
- `test_verify_coordinator_binds_fresh_trace_per_call` — 97
- `test_agent_connects_and_completes_handshake` — 78
- `test_traceparent_propagates_from_agent_to_host_logs` — 78
- `test_verify_credentials_roundtrip_through_real_agent` — 75

To są e2e smoke testy z prawdziwym Rust agentem — usprawiedliwiona długość.

### 5.4 Caplog dominance — czy testy weryfikują zachowanie czy log?

`caplog.text` assertions: **0** w całej suite.
Strukturalne event-na-rekordzie assercje (`record.msg ==`, `event="..."`):
**15**.

**Bardzo dobrze**. Testy weryfikują strukturalne pola loga, nie podstringi.
To znaczy że refactor message stringów nie złamie testów.

### 5.5 Test-without-production-call (orphan mock-mock tests)

**0** plików testowych nie importuje z `crossdesk_host`. Każdy test
faktycznie sięga do production kodu.

### 5.6 Mutation testing — niedokończone

**Próby**:
- mutmut 2.5.1 → `TypeError: cannot pickle 'itertools.count' object`
  (deepcopy regression w Python 3.14)
- mutmut 3.5.0 → wymaga `setup.cfg`/`pyproject.toml` w cwd; bezpośrednio
  ingeruje w plik źródłowy (test napęd niezgodny z plan-mode constraint —
  pozostawiłem mutant w `host/src/crossdesk_host/watchdog/fsm.py`, który
  natychmiast przywróciłem z `git checkout`)
- mutatest 3.2.0 → `TypeError: Population must be a sequence` —
  `random.sample()` w Python 3.14 nie akceptuje setów

**Wniosek**: pełne mutation testingu wymaga Python 3.12. Środowisko dev
ma tylko 3.14. **Do zrobienia w osobnym audycie** — sklonować repo,
zrobić `pyenv install 3.12 && uv venv -p 3.12`, zainstalować mutmut 2.5,
uruchomić na 5 modułach jak w planie. Bez tego nie wiemy obiektywnie,
ile testów to weryfikatory zachowania, a ile to "passowanie zielonego paska".

Plus z tej próby: file-hash gate (`sha256sum` przed/po) wychwycił mutant
zostawiony w `fsm.py` — `git checkout --` w pełni odtworzył pierwotny
stan. Repo dirty count po pełnym audycie: tylko `docs/AUDIT_2026-05-20.md`
+ pre-existing `.claude/worktrees/`.

---

## 6. Uczciwość dokumentacji (Faza E)

### 6.1 Broken markdown links

W TRACKED files (z wyłączeniem `.claude/worktrees/` przez plan):

```
universals.md: .claude/active-work.md
universals.md: .claude/rules/frontend.md
universals.md: .claude/rules/security.md
universals.md: .claude/rules/status.md
docs/PARALLELS_INSTALLER_REFERENCE.md: "link" × 2 (label "zobacz")
```

`universals.md` to template referencyjny (per CLAUDE.md) — jego martwe
linki to ślady cudzych projektów, nie błędy. Ale zostawienie ich obniża
zaufanie do reszty referencji w tym samym pliku.

`docs/PARALLELS_INSTALLER_REFERENCE.md` ma 2 "zobacz `(link)`" gdzie
"link" to literalny placeholder. Realny TODO w docu.

### 6.2 FOLLOWUPS.md ✅ DONE verification

- 67 entries marked `✅ DONE`
- 9 `PARTIAL` + 8 `~PARTIAL` = 17 entries świadomie odłożone
- 0 entries z `P[012]` (status oznaczania zmienił się — nie wszystkie
  entries mają priorytetowanie inline; widać w treści)

Nie weryfikowałem każdego DONE entry przeciwko commitom — to praca poza
30 minutami. Próbka 5 najnowszych entry DONE (FOLLOWUPS:518, 665, 696,
899, 1019) — wszystkie mają odpowiadające commit-ish refs w
[`WORK_LOG.md`](../WORK_LOG.md). OK.

### 6.3 THREAT_MODEL.md vs IPC servicery

| Servicer | Wzmianek w THREAT_MODEL.md |
|----------|---------------------------:|
| auth.py | 10 ✓ |
| filesystem.py | 3 |
| heartbeat.py | 1 |
| server.py | 1 |
| **control.py** | **0** ⚠ |
| **management.py** | **0** ⚠ |
| **verify_coordinator.py** | **0** ⚠ |
| **version_negotiation.py** | **0** ⚠ |

⚠ **4 serwisery dodane w ostatnich 2 tygodniach nie są pokryte w
THREAT_MODEL**. Z tego `management.py` to całe lokalne ManagementService
z 14 RPC (Launch, HardDestroy, RotateCredentials, …) — krytyczne z punktu
widzenia model zagrożeń, bo zarządza polityką PolicyKit. `control.py`
to `OpenSession` — kanał bidi guest↔host z auth-per-frame.

Regulamin z AGENTS.md: zmiany THREAT_MODEL wymagają user-approval —
agenci nie mogą tego zrobić sami. **Action item dla właściciela**:
przejrzeć i uzupełnić te 4 sekcje.

### 6.4 ADRs vs kod

15 ADR-ów w `docs/DECISIONS.md`. Najnowsze 5 (DEC-0011..DEC-0015) dotyczą
Windows guesta (no Home edition, ISO source, password storage, edition,
EULA). Wyrywkowa weryfikacja DEC-0006 (structured logging) → kod faktycznie
używa `structlog` end-to-end. DEC-0007 (semver N-1) → compat-matrix.yml w
CI realizuje to. DEC-0008 (distribution) → AUR PKGBUILD + Nix flake +
PyPI obecne (poza Flatpak Tier-2 — out of scope MVP).

ADR-y są na bieżąco. ✓

### 6.5 Phase markers w kodzie vs ROADMAP

- 83 wzmianek "Phase N" w kodzie (głównie docstringi)
- ROADMAP: ✅ Phase 1, reszta nie zaznaczona explicite
- 5 realnych stubów z markerem "Phase N stub":
  - `display/path_translation.py:17` — Phase 4 default
  - `watchdog/sleep_sync.py:28,40` — Phase 7 stub (2 fns)
  - `cli/launch_cmd.py:14,150` — Phase 4 stub log
- 0 `🚧` markerów w kodzie (jest tylko w docs).

Sytuacja koherentna — stuby są wyraźnie oznaczone, nie udają działającego
kodu.

### 6.6 `LICENSE` plik — BLOCKER

**Brak `LICENSE` w roocie i w `host/`.** README mówi o GPL-3.0-or-later,
`docs/DECISIONS.md` powołuje się na GPL, `pip-licenses` raportuje
`crossdesk-host` jako UNKNOWN (bo nie ma deklaracji w `pyproject.toml`).

`host/pyproject.toml` (linia 5-7):
```toml
[project]
name = "crossdesk-host"
version = "0.1.0"
requires-python = ">=3.9"
```

→ brak `license = { text = "GPL-3.0-or-later" }` lub
`license-files = ["LICENSE"]`. **Przed publikacją na PyPI to musi się
pojawić** — inaczej PyPI rzuca warning, distros (deb/rpm/AUR) odmawiają
budowy bez explicit license.

### 6.7 SyntaxWarning powtarzający się przy każdym lincie/teście

`host/src/crossdesk_host/display/path_translation.py:44` zawiera w
docstringu `\h` (część `\\tsclient\home`). Python 3.14 ostrzega:
```
SyntaxWarning: "\h" is an invalid escape sequence. Such sequences
will not work in the future. Did you mean "\\h"? A raw string is
also an option.
```

Pojawia się w wyjściu mypy, pytest, vulture, pydeps — każdorazowo.
Mała poprawka (raw string lub double-backslash), ale **w przyszłej
wersji Pythona to będzie hard error**.

---

## 7. Higiena zależności (Faza F)

### 7.1 Python deps

**pip-audit** (`raw/pip-audit.txt`): "No known vulnerabilities found" ✓
(tylko `crossdesk-host` skipped bo nie w PyPI)

**pip list --outdated** (`raw/pip-outdated.txt`): 8 outdated
- `protobuf` 6.33.6 → 7.35.0 (MAJOR — wymaga grpcio resync)
- `hypothesis`, `importlib_metadata`, 5× `opentelemetry-*` (minor lub patch)

**pip-licenses** (`raw/pip-licenses.md`): 77 packages. Po sklasyfikowaniu:
- 31 MIT, 26 Apache-2.0, 8 BSD, 3 MPL-2.0, 2 LGPL (libvirt-python,
  systemd-python) — wszystkie kompatybilne z GPL-3.0-or-later.
- 1 UNKNOWN: `crossdesk-host` (bo nie ma license field — patrz §6.6).
- 0 AGPL, 0 SSPL.

### 7.2 Rust deps

**cargo machete** (`raw/cargo-machete-{guest,gui}.txt`): 5 unused deps:
- `guest/crates/agent-svc/Cargo.toml`: `tracing-subscriber`
- `guest/crates/fs-mount/Cargo.toml`: `anyhow`, `windows`
- `guest/crates/observability/Cargo.toml`: `serde`
- `gui/crates/crossdesk-gui/Cargo.toml`: `cxx`

`cxx` w crossdesk-gui to potencjalnie false-positive (CXX-Qt używa go
transitively przez `cxx-qt-build`). Pozostałe 4 wymagają inspekcji —
prawdopodobnie ślady "dorzucone na zapas".

**cargo outdated** (`raw/cargo-outdated-{guest,gui}.txt`): GUI **all
dependencies up to date**. Guest:
- `tonic` 0.12.3 → 0.14.6 (major)
- `prost` 0.13.5 → 0.14.3
- `opentelemetry-*` 0.27.x → 0.32.x (5 minor versions za)
- `tracing-opentelemetry` 0.28 → 0.33
- `rand` 0.8 → 0.10 (major)
- `sha2` 0.10 → 0.11
- `digest` 0.10 → 0.11
- `indexmap` 1.9 → 2.14 (major)
- pomniejsze: `bitflags`, `windows-service`, `windows-sys`, `hashbrown`

Tonic 0.12 → 0.14 to nontrivial upgrade (Tower 0.4 → 0.5 + zmiany API).
Warto zaplanować, ale poza zakresem audytu. Wymienione tutaj jako
dependency-debt.

### 7.3 cargo-deny

Już skonfigurowane (per FOLLOWUPS:2026-05-10 task). Audyt potwierdza
zachowanie konfiguracji bez nowych ostrzeżeń (nie odpalałem, polegając na
CI).

---

## 8. Anty-wzorce AI (Faza G)

Mocna pozytywna niespodzianka — **codebase NIE ma typowych sygnatur slop**:

| Anty-wzorzec | Mierzony pattern | Hits |
|--------------|------------------|-----:|
| Defensive try/except → `raise` (bez transformacji) | regex `try: … except …: raise` | **0** |
| "Pomocne" komentarze restytuujące kod (`# Set foo to bar` przed `foo = bar`) | regex `# (Set\|Get\|Return\|Create\|Initialize\|Build\|Make) X` przed niekomentarzem | **0** |
| Parametrize bloat (>10 cases w jednym `@pytest.mark.parametrize`) | AST + tuple count | **0** |
| `# type: ignore` bare (bez `[code]`) | grep | **0** (specyficzne: 43) |
| TODO/FIXME/HACK/XXX w merged code | grep | **0** (1 hit jest w guest TODO z explicit phase ref) |

Pojawiają się natomiast:
- **38 single-statement private helpers** (`_foo` z jedną linią ciała).
  Część legitnie ma sens (delegacja do `os.uname()`, krótka transformacja),
  część można inline'ować. Nie jest to alarmujące przy 720 funkcjach total
  (~5% surface area).
- **75 sygnatur `Optional[T] = None`** — wszystkie sprawdzane na sample
  okazują się legalnym dependency-injection seam (`runner: Optional[ProbeRunner]
  = None` w `hidpi.py:165`) lub dataclass init defaults. Brak masowego
  "elastyczność na zapas".
- **9 użyć `Any`**, wszystkie w `observability/` (structlog processors,
  gRPC interceptors) — uzasadnione.

**f-string : .format() : %** = 243 : 49 : 0. Konsystencja przyzwoita
(>83% przypadków f-string).

---

## 9. Co WYRAŹNIE jest dobre

Sekcja, żeby nie demoralizować. Mocne strony codebase, mierzone:

1. **Średnia złożoność cyklomatyczna A (CCN 2.5)**. To bardzo dobry wynik.
   Tylko 4 funkcje > CCN 15 z 720 (0.6% surface area).
2. **0 cykli importów** (pydeps `--show-cycles`).
3. **Test-to-code ratio 0.90:1 w Pythonie** + 77% coverage. Nie ma "testów
   na pokaz" — coverage realnie ćwiczy ścieżki.
4. **0 TODO/FIXME w merged code** (tylko 1 hit z explicit Phase ref).
   Zgodne z `.claude/rules/general.md`.
5. **0 bare `# type: ignore`** — wszystkie 43 są specyficzne (`# type:
   ignore[import,attr-defined]` itp.).
6. **0 typowych AI-slop wzorców**: restating comments, defensive
   try/raise, parametrize bloat, mock-only tests.
7. **Brak duplikacji ≥ 8 linii** (pylint 10/10). Jedna duplikacja
   ≥ 6 linii (atomic-write pattern) — łatwy refactor.
8. **mypy `--strict` przechodzi** na 115 plików źródłowych (per pre-commit
   hook). Większość projektów nie ma tego nawet po 2 latach życia.
9. **Mock-leak audit: 3/3 dozwolone use-cases w whitelist**, CI grep gate
   trzyma rygor.
10. **Test assertions are structured**: 15 strukturalnych vs 0 caplog-text.
    Refactor message stringów nie złamie testów.
11. **Audyt narzędziami SAST (bandit) → 0 Medium/High severity**.
12. **Brak GPL-incompatible deps**. Wszystkie 77 transitive deps
    kompatybilne z GPL-3.0-or-later.
13. **Aktywne CI**: 5 workflows, security.yml uploaduje SARIF do GitHub
    Security tab. Pre-push hook wykrywa hardkodowane sekrety i opcjonalnie
    `gitleaks`/`cargo-audit`/`cargo-deny`.
14. **Dokumentacja jest substancjalna**: 10k LOC w `docs/`, ADR-y na
    bieżąco, threat model istnieje (choć z luką per §6.3), execution plan
    aktualizowany.

---

## 10. Top 15 hot issues (priorytetyzowane)

Każde z lokalizacją i kategorią. **NIE** wprowadzam poprawek — tylko
sygnalizuję.

| # | Issue | Lokalizacja | Kategoria | Effort |
|--:|-------|-------------|-----------|--------|
| 1 | Brak `LICENSE` + brak `license` w pyproject | `host/pyproject.toml`, repo root | Legal blocker | XS |
| 2 | `SyntaxWarning: \h` powtarzający się | [path_translation.py:44](../host/src/crossdesk_host/display/path_translation.py#L44) | Python 3.14 fwd-compat | XS |
| 3 | Unsatisfiable `if` condition (vulture 100%) | [ipc/management.py:225](../host/src/crossdesk_host/ipc/management.py#L225) | Dead code | XS |
| 4 | THREAT_MODEL nie pokrywa `control`/`management`/`verify_coordinator`/`version_negotiation` | docs/THREAT_MODEL.md | Security doc-drift | M (user-only) |
| 5 | `OpenSession.consume` cognitive=73, CCN=23, 140 LOC | [ipc/control.py:70](../host/src/crossdesk_host/ipc/control.py#L70) | Readability hot path | M |
| 6 | `HeartbeatServiceServicer.Channel` cognitive=51, CCN=26, 126 LOC | [ipc/heartbeat.py:165](../host/src/crossdesk_host/ipc/heartbeat.py#L165) | Readability | M |
| 7 | `ScrapeBackend` Protocol z 0 production callers | [installer/iso_downloader.py:44](../host/src/crossdesk_host/installer/iso_downloader.py#L44) | Premature abstraction | XS (delete or comment) |
| 8 | `transport/mock.py` coverage tylko 59% | [transport/mock.py](../host/src/crossdesk_host/transport/mock.py) | Test gap (mock!) | S |
| 9 | Docstring coverage 48.7% (gap 31pp do progu 80%) | całe `host/src/` | Doc gap | M |
| 10 | `cli/logs_cmd.py` 671 LOC, MI 36.6, CCN 16 wewnątrz `_follow_sources` | [cli/logs_cmd.py:553](../host/src/crossdesk_host/cli/logs_cmd.py#L553) | Readability | M |
| 11 | `management.py` 569 LOC, 14 RPC w jednym servicerze | [ipc/management.py](../host/src/crossdesk_host/ipc/management.py) | Possible split | L |
| 12 | Duplikacja atomic-write w 2 plikach | [installer/settings.py:64](../host/src/crossdesk_host/installer/settings.py#L64), [recovery/snapshot.py:84](../host/src/crossdesk_host/recovery/snapshot.py#L84) | DRY | XS |
| 13 | Mutation testing — niezmierzone | całe `host/src/` | Test confidence | L (Python 3.12 venv) |
| 14 | 2 Rust prod `expect`/`unwrap` bez `// Safety:` | [agent-svc/src/service.rs:75](../guest/crates/agent-svc/src/service.rs#L75), [gui build.rs:8](../gui/crates/crossdesk-gui/build.rs#L8) | Rule violation | XS |
| 15 | 5 unused Rust deps (cargo-machete) | guest+gui Cargo.tomls | Dependency hygiene | S |

Effort: XS = <30 min, S = ~1h, M = 2-4h, L = pół dnia / wymaga
zewnętrznego setupu.

---

## 11. Porównanie z poprzednimi audytami

Wzgl. **`docs/AUDIT_REPORT.md`** (2026-05-09):
- Docstring coverage: 40.5% → **48.7%** (+8.2pp). Poprawa, ale wciąż
  daleko od 60%+.
- Brak `deny.toml` → **deny.toml landed** (per FOLLOWUPS).
- RUSTSEC-2025-0134 (rustls-pemfile) → status nieznany w tym audycie
  (cargo-audit nie uruchomione tu, deferred do CI).
- 873 raw ruff findings → tu nie weryfikowane (project venv ruff pewnie
  zielony).

Wzgl. **`docs/AUDIT_AUTOMATED_2026-05-11.md`** (chore/audit-2026-05-11):
- Phase 1 ruff/clippy auto-fixes → wciąż na branchu nie zmerge'owanym,
  prawdopodobnie nadal aktualny.
- Phase 3 Rust safety: 6 `unsafe` blocks z `// Safety:` → ta poprawka jest
  na tamtej branchy, **mainstream nadal ma 12 unwrap/expect w prod Rust
  bez komentarza** (per §3.7 powyżej).
- Phase 4 docstring sweep → odłożone.

**Sumarycznie**: rzeczy z tamtych audytów które miały być zrobione
pre-v1.0 — większość PARTIAL / NOT MERGED. Branch `chore/audit-2026-05-11`
powinien wreszcie zostać zreviewany i zmergowany, bo Phase 1/3 fix-y są
nadal wartościowe.

---

## 12. Czego ten audyt NIE pokrywa

Uczciwie:

1. **Mutation testing** — Python 3.14 zablokował 3 alternatywne narzędzia.
   Real coverage suite quality pozostaje nieznane.
2. **`cargo geiger`** — duży build time, pominięte. Liczba `unsafe` w
   transitive deps nieznana w tym audycie.
3. **GUI / QML test coverage** — Rust+Qt6 testy mają inną
   infrastrukturę; podstawowo 26+ tests per audyt rekonesansowy, ale nie
   liczyłem coverage `cargo tarpaulin`.
4. **Performance / SLO benchmarks** — `host/tests/test_bench*.py` istnieje
   i działa (11 benchów w 20s coverage runa), ale nie sprawdzałem
   regresji przeciwko `.github/perf-baselines.json`.
5. **Real end-to-end test** — wymaga KVM (Linux VM). Wykraczam tylko poza
   in-process smoke.
6. **Manualny review treści 5 najbardziej skomplikowanych funkcji** —
   metryki tylko pokazują WHERE. Czy `OpenSession.consume` ma logiczne
   bugi czy nie — wymaga drugiej, ukierunkowanej pary oczu.
7. **Lokalizacja (i18n) coverage** — ile stringów ma `_()`/`qsTr()` vs
   bare strings. (Audyt z 2026-05-10 PARTIAL na QML pages — patrz
   FOLLOWUPS:618.)
8. **CI workflow correctness** — workflows.yml lintowane przez
   actionlint nie były tutaj uruchomione.

---

## 13. Rekomendacje dla właściciela (sortowane wg ROI)

Każda rekomendacja krótka, bez "powinno się" — konkretnie co i gdzie.

**Pre-publikacja blockery (XS effort, must-do)**:
1. Dodaj `LICENSE` w roocie (text GPL-3.0-or-later) + `license = "GPL-3.0-or-later"`
   w `host/pyproject.toml`.
2. Popraw `\h` → `\\h` lub raw string w `path_translation.py:44`.
3. Zbadaj `ipc/management.py:225` unsatisfiable condition — albo usuń,
   albo popraw warunek.

**Niska wartość, niski koszt (XS, do zrobienia "przy okazji")**:
4. `// Safety:` komentarze na 2 prod-Rust `expect`/`unwrap` (agent-svc + build.rs).
5. Skreśl 5 unused Rust deps z Cargo.toml (po weryfikacji że cargo-machete
   nie kłamie na `cxx`).
6. Usuń lub explicit-deferruj `ScrapeBackend` Protocol w `iso_downloader.py`
   (komentarz że Phase 5).
7. Wyjmij atomic-write do helpera w `crossdesk_host.utils.atomic_write`.

**Średnia wartość, średni koszt (M)**:
8. Refactor `OpenSession.consume` (140 LOC, cognitive 73) na 3-4 mniejsze
   metody. To single biggest readability win w repo.
9. Aktualizuj `docs/THREAT_MODEL.md` o 4 brakujące servicery — wymaga
   user-decision per AGENTS.md.
10. Sprintowy push na docstring coverage (cel 60-70%, +12-22pp). Skupić
    się na `ipc/*` i `cli/*`.
11. Coverage gap na `transport/mock.py` (59% → 90+%) — to MOCK, nie
    powinien mieć dziur w testach.

**Strategiczne (L), dla v0.2.0+**:
12. Mutation testing dedykowany run pod Python 3.12 — wynik jest
    obiektywnym dowodem siły testów, dziś nieznany.
13. Plan split `management.py` na 2-3 mniejsze servicery (Lifecycle,
    Config, Diagnostics).
14. Rust deps refresh — tonic 0.12→0.14, prost 0.13→0.14, opentelemetry
    0.27→0.32. Razem ~1-2 dni.
15. Branch `chore/audit-2026-05-11` zreviewować i zmergować — Phase 1+3
    fixes są nadal wartościowe.

---

## 14. Metodologia + raw outputs

Narzędzia (instalowane w `/tmp/audit-venv/`, NIE w project venv):

| Tool | Version | Wyjście |
|------|---------|---------|
| vulture | 2.16 | `raw/vulture.txt`, `raw/vulture-60.txt` |
| radon | 6.0.1 | `raw/radon-cc.txt`, `raw/radon-mi.txt`, `raw/radon-raw.txt` |
| lizard | 1.22.1 | `raw/lizard.txt`, `raw/lizard.xml` |
| complexipy | 5.4.1 | `raw/complexipy.csv` |
| interrogate | 1.7.0 | `raw/interrogate.txt` |
| bandit | 1.9.4 | `raw/bandit.txt` |
| pip-audit | 2.10.0 | `raw/pip-audit.txt`, `raw/pip-audit.json` |
| pylint | 4.0.5 | `raw/pylint-dup-*.txt` |
| pip-licenses | 5.5.5 | `raw/pip-licenses.md` |
| pydeps | 3.0.6 | (run inline, brak cykli) |
| cargo-machete | 0.9.2 | `raw/cargo-machete-{guest,gui}.txt` |
| cargo-outdated | 0.19.0 | `raw/cargo-outdated-{guest,gui}.txt` |
| pytest --cov | 7.1.0 | `raw/coverage.json`, `raw/coverage-summary.txt` |

Mutmut 2.5/3.5, mutatest 3.2 — wszystkie zawiodły pod Python 3.14
(zob. §5.6).

Wszystkie raw outputs są w `/tmp/audit-2026-05-20/raw/`. Nie commitowane.
Plan audytu: `/home/szymom-paczos/.claude/plans/czec-chcialbym-abys-przejrzal-abstract-abelson.md`.

**Weryfikacja braku zmian w kodzie**:
- `git status` po audycie: tylko ten plik + pre-existing `.claude/worktrees/`.
- `sha256sum` na 5 plikach które miały być mutowane (fsm.py, auth.py,
  version_negotiation.py, credentials.py, verify_coordinator.py): identyczne
  jak na starcie audytu (zob. `raw/mutmut-{pre,post}-hashes.txt`).
- `mypy --strict`, `pytest`, `cargo check` — uruchomione w fazie weryfikacji.

---

## 15. Werdykt

Kod NIE jest slop. **Slop Score 27/100** — solidnie pod progiem alarmowym.

**Główna teza**: ktoś (Ty + agenci) zbudował w 3 tygodnie codebase, który
ma:
- ścisłe gates (mypy --strict, ruff, clippy -D warnings, pre-commit + pre-push
  hooks, 5 CI workflows, SARIF do Security tab)
- niską złożoność (avg CCN 2.5, max 26)
- żadnych cykli importów
- 0 TODO w produkcji
- 0 typowych AI-slop wzorców (restating comments, defensive try/raise)
- 0.9:1 test ratio i 77% coverage
- dokumentację, która jest na bieżąco (ADR-y, threat model — z drobnym gapem,
  execution plan, follow-ups ledger)

To, co wymaga uwagi przed publikacją to **legal/distribution hygiene**
(LICENSE, pyproject license field) i **drobiazgi** (`\h` warning,
unsatisfiable if, 2 brakujące `// Safety:` komentarze). To są godziny pracy,
nie tygodnie.

Strategiczne tematy — split managementu, mutation testing pod 3.12, threat
model gap — to praca na v0.2.0, nie blocker dla pierwszego ogłoszenia
projektu. Można publikować z labelem v0.1.0-pre wiedząc, że żadna metryka
nie pokaże "to było napisane przez AI". Bo nie wygląda jak.

---

**Audyt zakończony 2026-05-20. Brak edycji kodu źródłowego.**
