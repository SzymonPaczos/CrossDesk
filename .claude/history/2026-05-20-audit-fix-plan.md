# Plan naprawy: CrossDesk Slop Score 27 → 0 + lokalne CI

**Powiązany audyt**: [`docs/AUDIT_2026-05-20.md`](AUDIT_2026-05-20.md).
Slop Score 27/100 z 14 hot issues + niesprawne GitHub CI.

Ten plan ma dwie części:
1. **Slop Score → 0** — uczciwa droga do score'u tak nisko, jak to obiektywnie
   możliwe (~6/100 to praktyczny floor; pełne 0 wymagałoby usunięcia stub'ów Phase 5+).
2. **Lokalne CI** — zastąpienie failującego GitHub Actions pre-push hookiem
   uruchamiającym to samo co CI, plus opcjonalne wyłączenie GH CI do czasu
   stabilizacji.

> **Zasady wykonania:** atomic commits, każda sekcja → osobny branch
> `feat/audit-fix-<topic>`, Conventional Commits, każda zmiana z testem
> jeżeli pasuje. Każdy commit musi przejść lokalne CI (zob. Część 2)
> ZANIM trafi do push. Branche merge'owane sekwencyjnie po review.

---

## Część 1 — Slop Score → 0

### Realistyczny floor: ~6/100, nie 0/100

Score = 0 wymagałoby:
- 0% modułów MI<65 → niemożliwe (radon flaguje legitnie złożone moduły
  jak `cli/logs_cmd.py` 671 LOC, multi-source log reader — splitowanie
  obniży MI ale wprowadzi nowe pliki o niskim MI bo CLI jest skomplikowane)
- Coverage 100% → niemożliwe (Linux-only moduły: `libvirt_ctl/real.py`,
  `lifecycle/dbus_listener.py`, `transport/real.py` nie da się testować
  pod dev-machine bez KVM)
- Mutation kill rate 100% → niemożliwe (część mutantów to "equivalent
  mutants" — semantycznie identyczne ze źródłem)
- Top cognitive complexity = 0 → niemożliwe (każdy gRPC dispatch + state
  machine ma irreducible complexity)

**Realistyczny target po wykonaniu tego planu: ~6 / 100**:
- Rule violations: 0
- % CCN>15: 0 (po §1.2)
- % MI<65: ~15% (down from 31%, niemożliwy zero)
- Top cognitive: <25 (down from 73)
- Mutation kill: ≥85% (mierzalne pod 3.12)
- Docstring coverage: 80%+ (target hit)
- Coverage: 88-92% (po dotestowaniu mocków, dalej Linux-bound items pozostaną)
- Doc drift: 0
- Premature abstractions: 0
- Outdated deps + bandit: 0

---

### Sekcja 1A — Pre-publikacja blockery (XS, ~2h total)

Branch: `fix/audit-prep-pre-publication`

| # | Issue | Plik | Zmiana |
|--:|-------|------|--------|
| 1 | LICENSE missing | `LICENSE` (nowy) | Dodaj plik z pełnym tekstem GPL-3.0-or-later z [gnu.org](https://www.gnu.org/licenses/gpl-3.0.txt) |
| 2 | License w pyproject | `host/pyproject.toml:5-9` | Dodaj `license = "GPL-3.0-or-later"` + `license-files = ["../LICENSE"]` (lub kopiuj `LICENSE` do `host/`) |
| 3 | `\h` SyntaxWarning | `host/src/crossdesk_host/display/path_translation.py:44` | Zamień `\\tsclient\home` → `\\tsclient\\home` w docstringu (lub r-string) |
| 4 | Unsatisfiable if | `host/src/crossdesk_host/ipc/management.py:225` | Otwórz plik, sprawdź warunek, usuń lub popraw (vulture 100% conf — to nie false-positive) |
| 5 | `// Safety:` brakuje | `guest/crates/agent-svc/src/service.rs:75` | Dodaj `// Safety: Tokio runtime creation only fails on OS-level resource exhaustion; daemon is unusable in that state anyway, so panic is acceptable.` |
| 6 | `// Safety:` brakuje | `gui/crates/crossdesk-gui/build.rs:8` | Dodaj `// Safety: cargo always sets CARGO_MANIFEST_DIR when invoking build scripts.` |

**Akceptacja**: `cargo clippy -- -D warnings` zielony, `pip-licenses` raportuje
`crossdesk-host` jako `GPL-3.0-or-later`, `python3 host/src/crossdesk_host/display/path_translation.py`
bez SyntaxWarning, `vulture host/src/crossdesk_host/ipc/management.py` bez
"unsatisfiable" entry.

**Slop Score delta**: -3.7 (rule violations 1.7→0, doc drift 7.0→5.0).

---

### Sekcja 1B — Premature abstractions + duplikacje (XS, ~1h)

Branch: `chore/audit-fix-abstractions`

| # | Issue | Plik | Zmiana |
|--:|-------|------|--------|
| 1 | ScrapeBackend Protocol 0 callers | `host/src/crossdesk_host/installer/iso_downloader.py:44` | **Opcja A** (preferred): usuń `ScrapeBackend` Protocol + `HttpScrapeBackend`; zostaw goły `download_iso()` z `urllib.request`. Test `_ScriptedBackend` przerób na patch `urllib`. **Opcja B** (jeśli phase-5 planowane wcześnie): zostaw, ale dodaj nad klasą komentarz "Phase 5 placeholder — no production caller yet" i ZAREJESTRUJ w `.claude/ignorefiles.md` żeby vulture nie pluła |
| 2 | atomic-write duplikacja | nowy: `host/src/crossdesk_host/utils/atomic_write.py` | Wyciągnij `flush+fsync+rename+cleanup` z `installer/settings.py:64-74` i `recovery/snapshot.py:84-102` do helpera. Sygnatura: `def atomic_write(path: Path, data: bytes \| str) -> None`. Test `tests/test_atomic_write.py` z mock os.rename failure |
| 3 | 5 unused Rust deps | `guest/crates/{agent-svc,fs-mount,observability}/Cargo.toml`, `gui/crates/crossdesk-gui/Cargo.toml` | Usuń: `tracing-subscriber` z agent-svc; `anyhow` i `windows` z fs-mount; `serde` z observability. `cxx` z crossdesk-gui — **najpierw zweryfikuj**: jeśli cxx-qt-build potrzebuje, dodaj do `[package.metadata.cargo-machete] ignored=["cxx"]` zamiast usuwać |
| 4 | Phase-5 stuby explicit-defer | `host/src/crossdesk_host/watchdog/sleep_sync.py:28,40` | Dodaj komentarz przy module: `# Phase 7 — these are deliberate stubs, real impl gated on libvirt connection landing.` żeby vulture/audyt rozpoznał |

**Akceptacja**: `cargo machete` zielony (lub explicit `ignored`),
`pytest tests/test_atomic_write.py` zielony, `tests/test_iso_downloader_edges.py`
nadal zielony.

**Slop Score delta**: -5 (premature abstractions 5.0 → 0).

---

### Sekcja 1C — `transport/mock.py` coverage gap (S, ~1h)

Branch: `test/transport-mock-coverage`

Coverage 59% na mocku jest podejrzane. Brakujące linie wg `coverage.json`:
prawdopodobnie `fail_next_connect` injection paths i `call_count` increment
edge cases.

**Plan**:
1. `pytest --cov=crossdesk_host.transport.mock --cov-report=term-missing host/tests/`
2. Dla każdej missed linii: dodać przypadek testowy w
   `host/tests/test_transport_mock.py`
3. Target ≥95% (nie 100% — może być defensywny code dla unreachable, OK)

**Akceptacja**: `transport/mock.py` ≥95% w `pytest --cov`.

**Slop Score delta**: -0.5 (coverage gap 1.3 → 0.8).

---

### Sekcja 1D — Czterej najbrzydsi (cognitive complexity refactor) (M, ~6h razem)

Cztery branche, każdy osobno bo to refactor hot paths.

#### 1D.1 — `OpenSession.consume` — cognitive 73 → <25

Branch: `refactor/open-session-decompose`

Plik: `host/src/crossdesk_host/ipc/control.py:70-221` (140 LOC).

Strategia: ekstrakcja per-message-type handlerów do osobnych metod.

```python
class ControlServiceServicer:
    async def OpenSession(self, request_iterator, context):
        # entry guards (auth, version)
        async for frame in request_iterator:
            await self._handle_client_frame(frame, context)

    async def _handle_client_frame(self, frame, context):
        if frame.HasField('hello'):
            return await self._handle_hello(frame.hello, context)
        if frame.HasField('window_event'):
            return await self._handle_window_event(frame.window_event)
        # ...
```

Cel: każda metoda `_handle_*` ma cognitive <15.

**Akceptacja**: `complexipy host/src/crossdesk_host/ipc/control.py` →
brak funkcji powyżej 25. `pytest tests/test_control_service.py` zielony.
Coverage `control.py` nadal ≥88%.

#### 1D.2 — `HeartbeatServiceServicer.Channel` — cognitive 51 → <25

Branch: `refactor/heartbeat-channel-decompose`

Plik: `host/src/crossdesk_host/ipc/heartbeat.py:165-323`.

Strategia: ekstrakcja `_handle_pong`, `_handle_miss`, `_arm_recovery`,
`_destroy_path` z głównego `Channel` async loop. Każdy pod 30 LOC.

**Akceptacja**: complexipy bez funkcji powyżej 25 w heartbeat.py.
`pytest tests/test_heartbeat_fsm.py tests/test_heartbeat_boot_probe.py`
zielone.

#### 1D.3 — `check_gpu_passthrough` — cognitive 23, CCN 21

Branch: `refactor/doctor-gpu-check`

Plik: `host/src/crossdesk_host/doctor/checks.py:298-419`.

Strategia: ekstrakcja `_check_iommu`, `_check_lspci`, `_check_kernel_cmdline`
do helperów; główna funkcja staje się compositorem.

**Akceptacja**: `complexipy host/src/crossdesk_host/doctor/checks.py` < 25
najwyższy. `pytest tests/test_doctor_checks.py` zielony.

#### 1D.4 — `_follow_sources` w logs_cmd.py — cognitive 28

Branch: `refactor/logs-follow-sources`

Plik: `host/src/crossdesk_host/cli/logs_cmd.py:553-618`.

Strategia: ekstrakcja generatora per-source (`_follow_journal`,
`_follow_file`, `_follow_libvirt`, `_follow_freerdp`) i `_merge_streams`.

**Akceptacja**: `complexipy` < 25 najwyższy. `pytest tests/test_logs_cmd.py`
zielony.

**Slop Score delta razem dla 1D**: -7 (top cognitive 8.0 → 1.0).

---

### Sekcja 1E — `management.py` split (L, ~4h)

Branch: `refactor/management-split`

Plik: `host/src/crossdesk_host/ipc/management.py` — 569 LOC, 14 RPC. To god
servicer.

**Plan**: NIE rozcinamy gRPC service — to byłaby breaking change w proto.
Zostawiamy `ManagementService` jako proto interface, ALE servicer rozdzielamy
na 3 mixiny (Pythonowy inheritance + composition):

```python
# host/src/crossdesk_host/ipc/management_lifecycle.py
class ManagementLifecycleMixin:
    async def Launch(self, ...): ...
    async def Suspend(self, ...): ...
    async def Resume(self, ...): ...
    async def HardDestroy(self, ...): ...

# host/src/crossdesk_host/ipc/management_config.py
class ManagementConfigMixin:
    async def UpdateSettings(self, ...): ...
    async def ReadSettings(self, ...): ...
    async def RotateCredentials(self, ...): ...

# host/src/crossdesk_host/ipc/management_diagnostics.py
class ManagementDiagnosticsMixin:
    async def Status(self, ...): ...
    async def ListApps(self, ...): ...
    async def ListDiscoveredApps(self, ...): ...
    async def ListMounts(self, ...): ...
    async def RunDiagnostics(self, ...): ...
    async def ExportDiagnosticBundle(self, ...): ...
    async def GetMetrics(self, ...): ...

# host/src/crossdesk_host/ipc/management.py
class ManagementServiceServicer(
    ManagementLifecycleMixin,
    ManagementConfigMixin,
    ManagementDiagnosticsMixin,
    mgmt_pb2_grpc.ManagementServiceServicer,
):
    """Composes all RPC handlers via mixins."""
```

Każdy mixin <250 LOC, MI > 65.

**Akceptacja**: `mypy --strict` zielony, wszystkie testy `test_management_*.py`
zielone, `radon mi host/src/crossdesk_host/ipc/` → wszystkie ≥65.

**Slop Score delta**: -2.5 (% MI<65 z ~31% do ~22%, daje 3.1 → 0.6).

---

### Sekcja 1F — Docstring coverage 48.7% → 80%+ (M, ~6h)

Branch: `docs/audit-docstrings`

Strategia: zacząć od najbardziej publicznych modułów.

| Priorytet | Moduł | Aktualnie | Target |
|-----------|-------|-----------|-------:|
| P0 | `host/src/crossdesk_host/ipc/*.py` | ~30-50% | 90% |
| P0 | `host/src/crossdesk_host/abstractions/*.py` | ~80% | 100% (Protocol API) |
| P1 | `host/src/crossdesk_host/cli/*.py` | ~20-40% | 70% |
| P1 | `host/src/crossdesk_host/watchdog/*.py` | ~70% | 90% |
| P1 | `host/src/crossdesk_host/installer/*.py` | ~40% | 80% |
| P2 | `host/src/crossdesk_host/observability/*.py` | ~60% | 80% |
| P2 | `host/src/crossdesk_host/integrations/keyring/*.py` | ~50% | 80% |

Reguły:
- Tylko publiczne API (funkcje/klasy bez `_` prefix)
- Docstring `"""Co robi w jednym zdaniu.\n\nOpcjonalny akapit gdy WHY non-obvious.\n"""`
- NIE dokumentować `__init__` jeśli klasa ma sensowny docstring
- NIE dokumentować generated `_pb2*.py` (vulture/interrogate ignoruje per config)

**Akceptacja**: `interrogate host/src --fail-under 80` zielony.

**Slop Score delta**: -3.5 (docstring gap 3.9 → 0.4).

---

### Sekcja 1G — Doc drift (Manuel + L, ~2-4h, część user-only)

Dwie sekwencje — pierwsza może być zrobiona przez agenta, druga musi być przez
właściciela (zob. AGENTS.md "File boundaries").

#### 1G.1 — Agent-doable

Branch: `docs/audit-fix-broken-links`

| # | Issue | Plik | Zmiana |
|--:|-------|------|--------|
| 1 | Broken links w `universals.md` | repo root `universals.md:?` | Dodaj komentarz na górze: `<!-- Template reference file. Some links point to sub-files not present in CrossDesk (frontend.md/security.md/status.md), kept for traceability. -->` ALBO usuń linie nieistniejących linków |
| 2 | Broken "zobacz `(link)`" | `docs/PARALLELS_INSTALLER_REFERENCE.md` | Otwórz, znajdź placeholder, albo wypełnij prawdziwym linkiem albo usuń wzmiankę |
| 3 | Phase markers w kodzie konsystencja | `host/src/crossdesk_host/cli/launch_cmd.py:14,150`, `watchdog/sleep_sync.py:28,40`, `display/path_translation.py:17` | Dodaj nagłówek pliku z explicit Phase status (3 linie max) — żeby audyt automatyczny wiedział co to stub a co prod |

#### 1G.2 — User-only per AGENTS.md "File boundaries"

| # | Issue | Plik | Akcja właściciela |
|--:|-------|------|-------------------|
| 1 | THREAT_MODEL.md nie pokrywa control/management/verify_coordinator/version_negotiation | `docs/THREAT_MODEL.md` | Właściciel pisze 4 sekcje STRIDE + Trust Boundary. Agent może draftować w nowym pliku `docs/THREAT_MODEL_DRAFT_4_SERVICERS.md` i właściciel kopiuje |
| 2 | ROADMAP Phase status update | `ROADMAP.md` | Właściciel zaznacza Phase 2 (transport) jako 🔄 in-progress vs ✅ done po zaakceptowaniu audytu |

**Slop Score delta**: -5 (doc drift 7.0 → 2.0 — pozostałe 2.0 to license file
juz zrobione w §1A; po finalizacji 1G.2 spadnie do 0).

---

### Sekcja 1H — Outdated deps + bandit cleanup (S, ~2h)

Branch: `chore/audit-deps-refresh`

#### 1H.1 — Python deps (~30 min)

```bash
cd host
pip install -e '.[mock,dev,linux]' --upgrade
# Bumps in pyproject.toml deps lines:
#   protobuf 6.x → 7.x (uwaga: wymaga grpcio resync — może wymagać też grpcio-tools update)
#   opentelemetry-api/sdk/exporter-otlp 1.41 → 1.42
#   hypothesis>=6.150 → bump
```

Po bumpie: `pytest -q`, jeśli zielony — commit z `chore(deps): bump
protobuf 6→7, opentelemetry minor, hypothesis patch`.

#### 1H.2 — Rust deps (Direct deps tylko) (~1h)

```bash
cd guest
# Direct deps z workspace Cargo.toml:
#   tonic 0.12 → 0.14   (BREAKING — tower 0.4→0.5, async-trait removed)
#   tonic-build 0.12 → 0.14
#   prost 0.13 → 0.14
#   opentelemetry-otlp 0.27 → 0.32
#   tracing-opentelemetry 0.28 → 0.33
cargo update
cargo check --workspace
cargo clippy --workspace -- -D warnings
cargo test --workspace --features ipc-vsock/mock
```

⚠️ Tonic 0.12→0.14 wymaga API changes — to nie jest auto bump. Rozważ split:
- `chore(deps): bump prost 0.13→0.14 + tracing-opentelemetry minor` (low risk)
- `feat(deps): migrate tonic 0.12→0.14` (separate, possibly L effort)

#### 1H.3 — Bandit 36 Low findings (~30 min)

Większość to `B603 subprocess_without_shell_equals_true` — legitne dla daemonu
wywołującego libvirt/freerdp. Plan:

1. W `host/pyproject.toml [tool.bandit]`: dodaj `skips = ["B603", "B607", "B404"]`
   z komentarzem: `# B603/B607/B404 — subprocess to legitimate gRPC daemon
   pattern; per-file ignore noisier than skip.`
2. Dla pozostałych (B110 try/except/pass, B101 assert): per-line `# nosec`
   z explanatorem.

**Akceptacja**: `bandit -r host/src -ll` (Medium+) zielony, `cargo audit`
zielony.

**Slop Score delta**: -2 (outdated+bandit 2.0 → 0).

---

### Sekcja 1I — Mutation testing baseline pod Python 3.12 (L, ~4-6h)

Branch: `test/audit-mutation-baseline`

⚠️ Wymaga zewnętrznego setup: `pyenv install 3.12` LUB Docker container z Python 3.12.

```bash
# 1. Setup Python 3.12 venv (poza projektem)
pyenv install 3.12.7
pyenv virtualenv 3.12.7 crossdesk-mutation
pyenv activate crossdesk-mutation

# 2. Install project + mutmut 2.5 (które działa pod 3.12)
cd host
pip install -e '.[mock,dev]'
pip install mutmut==2.5.1

# 3. Run na 5 modułach z planu audytu
mutmut run --paths-to-mutate=src/crossdesk_host/watchdog/fsm.py \
    --runner='pytest -x --tb=no -q tests/test_heartbeat_fsm.py'
mutmut results > /tmp/mutmut-fsm.txt

# Powtórz dla auth.py, version_negotiation.py, credentials.py, verify_coordinator.py
```

Target: ≥80% killed mutants per moduł. Surviving mutants → analizować
case-by-case:
- Equivalent mutant (semantycznie identyczny) → skip + komentarz
- Genuine test gap → dopisać test

Po wykonaniu: dopisać `docs/MUTATION_BASELINE_2026-XX-XX.md` z kill rate
per moduł.

**Akceptacja**: 5/5 modułów ≥80% kill rate, raport spisany.

**Slop Score delta**: -5 (mutation kill rate neutral 5.0 → 0).

---

### Sekcja 1J — Vulture cleanup przy 60% confidence (S, ~2h)

Branch: `chore/audit-vulture-60`

153 hitów przy 60% — większość Pydantic `model_config`, ale część realna:

1. `host/src/crossdesk_host/abstractions/filesystem.py:48` — `list_active_shares`
   metoda Protocol bez callera → usuń ALBO dodaj caller (zob. `management.py`
   ListMounts może powinien tego używać)
2. `host/src/crossdesk_host/abstractions/libvirt.py:75,87` — `set_memory`,
   `get_memory_stats` bez callera → usuń (balloon hook wciąż wystarcza)
3. `host/src/crossdesk_host/abstractions/freerdp.py:66` — `is_alive` bez
   callera → usuń lub dodaj health check
4. `host/src/crossdesk_host/catalog/curated.py:21,26,28` — unused fields
   `executable`, `known_issues`, `localized_name` → zweryfikuj czy nie
   konsumowane przez `cli/apps_cmd.py`, jeśli nie — usuń z dataclass

**Akceptacja**: `vulture host/src --min-confidence 60` <40 hitów (down from 153,
target głównie false positives).

**Slop Score delta**: pośrednio przez doc-drift i MI improvement; ~-0.5.

---

### Sekcja 1K — Verification suite — odpalenie wszystkiego razem

Branch: nie potrzeba — to gate przed merge'em każdego z powyższych.

Po każdej sekcji 1A-1J:
```bash
# Lokalne odpalenie ZAMIAST GitHub CI (zob. Część 2)
bash .githooks/full-local-ci.sh    # nowy skrypt z Części 2
```

Po wszystkich sekcjach:
1. Świeży audyt: powtórz wszystkie pomiary z `docs/AUDIT_2026-05-20.md`
2. Zapisz `docs/AUDIT_2026-XX-XX.md` z porównaniem
3. Jeśli Slop Score < 10 — claim victory i tag `v0.1.0-pre1`

---

### Łączny effort dla Części 1

| Sekcja | Branch | Effort | Slop delta |
|--------|--------|-------:|-----------:|
| 1A | fix/audit-prep-pre-publication | 2h | -3.7 |
| 1B | chore/audit-fix-abstractions | 1h | -5.0 |
| 1C | test/transport-mock-coverage | 1h | -0.5 |
| 1D.1 | refactor/open-session-decompose | 1.5h | -4.0 |
| 1D.2 | refactor/heartbeat-channel-decompose | 1.5h | -2.0 |
| 1D.3 | refactor/doctor-gpu-check | 1h | -0.5 |
| 1D.4 | refactor/logs-follow-sources | 1h | -0.5 |
| 1E | refactor/management-split | 4h | -2.5 |
| 1F | docs/audit-docstrings | 6h | -3.5 |
| 1G.1 | docs/audit-fix-broken-links | 1h | -3.0 |
| 1G.2 | (user-only) THREAT_MODEL + ROADMAP | 2h user | -2.0 |
| 1H | chore/audit-deps-refresh | 2h | -2.0 |
| 1I | test/audit-mutation-baseline | 5h | -5.0 |
| 1J | chore/audit-vulture-60 | 2h | -0.5 |
| **RAZEM** | | **~31h (4 dni)** | **-34.7** |

Punkt startowy: 27. Po wszystkich sekcjach: 27 - 34.7 = **ujemne**, ale
metryka nie schodzi poniżej 0. Realistycznie wynik 4-6 (kilka resztkowych
"nie da się dokładnie 0").

---

## Część 2 — Lokalne CI zamiast GitHub Actions

### Diagnoza: co konkretnie wywala się na GH

Ostatni failed run (CI #26143893989, 2026-05-20 06:44):
1. **`Python host (mypy + pytest) macos-latest`** — wisiało 6h, timeout.
   Prawdopodobnie wheel build `libvirt-python` na macos nie idzie (header
   `libvirt/libvirt.h` szuka przez Homebrew). Lokalnie ten test nigdy się
   nie powtarza bo macos workflow buduje w cold env, lokalnie masz cached.
2. **`Rust GUI qmllint`** — failuje na Ubuntu 24.04 (Qt 6.4.2). Lokalnie
   może być Qt 6.5+.
3. **`i18n string extraction check`** — `.pot` nie zsynchronizowany.
   Lokalnie xgettext nie odpalał się przed pushem.

**Plus deprecation warnings**: `actions/checkout@v4`, `actions/setup-python@v5`
używają Node.js 20, deprecated od czerwca 2026.

### Stan obecny pre-push hook

[`.githooks/pre-push`](../.githooks/pre-push) sprawdza:
- ✅ Hardcoded secrets (HARD FAIL)
- ⚠️ console.log/print() (WARN only — info)
- ✅ qmllint (HARD FAIL when tool present)
- ⚠️ TODO/FIXME (info)
- ✅ cargo audit (HARD FAIL when tool present)
- ✅ cargo deny (HARD FAIL when tool present)
- ✅ gitleaks (HARD FAIL when tool present)
- Opt-in: pip-audit + bandit przez `CROSSDESK_FULL_AUDIT=1`

**NIE robi**: ruff, mypy, pytest, cargo check, cargo clippy, cargo test,
buf lint, i18n .pot synchronization. Czyli WSZYSTKIE rzeczy które CI sprawdza
poza bezpieczeństwem.

### Plan — pre-push hook robi to co CI

Branch: `chore/local-ci-mirror`

**Filozofia**: pre-push hook musi być wystarczająco szybki żeby nie
demotywować (< 60s na typowym diff). Ale wystarczająco kompletny żeby push
do origin był 99% wolny od CI-failure.

#### 2A — Rozszerzenie `.githooks/pre-push`

Dodaj po sekcji `=== 1. Hardcoded secrets ===`:

```bash
# === 2A. Python: ruff + mypy --strict + pytest (HARD FAIL) ================
# Mirror ci.yml job python-host. Run only if host/ files changed.
if echo "$CHANGED_FILES" | grep -q "^host/"; then
    if [ -d "$REPO_ROOT/host/.venv" ]; then
        echo "🐍 ruff check src/ ..."
        (cd "$REPO_ROOT/host" && .venv/bin/ruff check src/) || {
            echo "❌ ruff found issues. Fix locally before pushing."
            exit 1
        }

        echo "🐍 mypy --strict src/ ..."
        (cd "$REPO_ROOT/host" && .venv/bin/mypy --strict src/) || {
            echo "❌ mypy --strict failed. Fix locally before pushing."
            exit 1
        }

        echo "🐍 mock-import gate ..."
        bad=$(cd "$REPO_ROOT/host" && grep -rE "from crossdesk_host\\.[^[:space:]]+\\.mock import" src/ \
                | grep -v "src/crossdesk_host/integrations/keyring/__init__\\.py:" \
                | grep -v "src/crossdesk_host/filesystem_ctl/__init__\\.py:" \
                | grep -v "src/crossdesk_host/daemon\\.py:" \
                || true)
        if [ -n "$bad" ]; then
            echo "❌ production code imports a mock module outside the whitelist:"
            echo "$bad"
            exit 1
        fi

        echo "🐍 pytest (fast subset) ..."
        # -x: stop on first failure, -q: quiet, --ignore=benches/: skip benchmark suite
        # tests/test_smoke_e2e.py: skip e2e (needs PKI), conftest.py picks marker
        (cd "$REPO_ROOT/host" && .venv/bin/pytest -x -q --ignore=benches/ tests/) || {
            echo "❌ pytest failed. Fix locally before pushing."
            exit 1
        }
    else
        echo "⚠️  host/.venv not found — skip Python gates (run 'pip install -e host/[mock,dev]')"
    fi
fi

# === 2B. Rust guest: cargo check + clippy + test (HARD FAIL) ==============
# Mirror ci.yml job rust-guest-cross-compile.
if echo "$CHANGED_FILES" | grep -qE "^guest/|^proto/"; then
    if command -v cargo >/dev/null 2>&1; then
        echo "🦀 cargo check (guest, native host arch) ..."
        (cd "$REPO_ROOT/guest" && cargo check --workspace --quiet) || {
            echo "❌ cargo check failed in guest workspace."
            exit 1
        }

        echo "🦀 cargo test (guest, native host arch, mock feature) ..."
        (cd "$REPO_ROOT/guest" && cargo test --workspace --features ipc-vsock/mock --quiet -- --quiet) || {
            echo "❌ cargo test failed in guest workspace."
            exit 1
        }

        echo "🦀 cargo clippy (guest) ..."
        (cd "$REPO_ROOT/guest" && cargo clippy --workspace --quiet -- -D warnings) || {
            echo "❌ cargo clippy found issues in guest workspace."
            exit 1
        }
    fi
fi

# === 2C. Rust GUI: cargo check + clippy + test ============================
if echo "$CHANGED_FILES" | grep -qE "^gui/|^proto/"; then
    if command -v cargo >/dev/null 2>&1; then
        echo "🦀 cargo check (gui) ..."
        (cd "$REPO_ROOT/gui" && cargo check --workspace --quiet) || {
            echo "❌ cargo check failed in gui workspace."
            exit 1
        }
        # cargo test on GUI workspace
        (cd "$REPO_ROOT/gui" && cargo test --workspace --quiet -- --quiet) || {
            echo "❌ cargo test failed in gui workspace."
            exit 1
        }
    fi
fi

# === 2D. Proto buf lint + format check (HARD FAIL if buf installed) =======
if echo "$CHANGED_FILES" | grep -q "^proto/"; then
    if command -v buf >/dev/null 2>&1; then
        echo "📦 buf lint ..."
        (cd "$REPO_ROOT/proto" && buf lint) || {
            echo "❌ buf lint failed."
            exit 1
        }
        echo "📦 buf format check ..."
        (cd "$REPO_ROOT/proto" && buf format --diff --exit-code) || {
            echo "❌ buf format: run 'cd proto && buf format -w' to normalize."
            exit 1
        }
    fi
fi

# === 2E. i18n .pot synchronization (HARD FAIL) ============================
# Mirror ci.yml job i18n-extract. Run only when host/cli or gui/qml changed.
if echo "$CHANGED_FILES" | grep -qE "^host/src/crossdesk_host/cli/|^gui/.*\.qml$|^gui/.*\.rs$"; then
    if command -v xgettext >/dev/null 2>&1; then
        echo "🌍 i18n .pot extraction check ..."
        bash "$REPO_ROOT/scripts/i18n.sh" extract --quiet 2>/dev/null || \
            bash "$REPO_ROOT/scripts/i18n.sh" extract
        if ! git diff --exit-code -- i18n/crossdesk-host.pot \
                gui/crates/crossdesk-gui/i18n/crossdesk_en.ts \
                gui/crates/crossdesk-gui/i18n/crossdesk_pl.ts >/dev/null 2>&1; then
            echo "❌ i18n translation files have uncommitted changes."
            echo "   Run 'bash scripts/i18n.sh extract' and commit the result."
            exit 1
        fi
    fi
fi
```

Total dodanych ~80 linii. Czas wykonania na typowym diff:
- ruff: 1-2s
- mypy: 3-5s (incremental cache)
- pytest 751 testów: 20s
- cargo check + test guest: 10-30s zależnie od cache
- cargo check + test gui: 5-20s
- buf lint: 1s
- i18n extract: 2-3s

**Łącznie ~45-60s** na pełen diff. Skip selektywny (per-changed-path) → typowy
diff w 1 obszarze: 10-20s.

#### 2B — Nowy helper `bash scripts/local-ci.sh`

Dla pełnego runu CI on-demand (poza pre-push):

```bash
#!/bin/bash
# scripts/local-ci.sh — odpalenie WSZYSTKIEGO co CI sprawdza, bez push.
# Użycie: bash scripts/local-ci.sh
set -e
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "════════════════════════════════════════════════"
echo " CrossDesk local CI (mirror GitHub Actions)"
echo "════════════════════════════════════════════════"

# Sekwencja jak w ci.yml, ale parallel gdzie się da
FAILED=()

run_job() {
    local name="$1"; shift
    echo ""
    echo "── ${name} ──"
    if "$@"; then
        echo "✅ ${name}"
    else
        echo "❌ ${name}"
        FAILED+=("$name")
    fi
}

run_job "python-host: ruff" bash -c "cd host && .venv/bin/ruff check src/"
run_job "python-host: mypy" bash -c "cd host && .venv/bin/mypy --strict src/"
run_job "python-host: pytest" bash -c "cd host && .venv/bin/pytest -q --ignore=benches/"
run_job "rust-guest: cargo test" bash -c "cd guest && cargo test --workspace --features ipc-vsock/mock --quiet"
run_job "rust-guest: cargo clippy" bash -c "cd guest && cargo clippy --workspace --quiet -- -D warnings"
run_job "rust-gui: cargo test" bash -c "cd gui && cargo test --workspace --quiet"
run_job "proto: buf lint" bash -c "command -v buf >/dev/null && cd proto && buf lint || echo 'buf not installed; skipping'"
run_job "i18n: extract check" bash -c "bash scripts/i18n.sh extract && git diff --exit-code -- i18n/ gui/crates/crossdesk-gui/i18n/"

# microbench: tylko on-demand, ~30s
if [ "${RUN_MICROBENCH:-0}" = "1" ]; then
    run_job "microbench" bash -c "cd host && .venv/bin/pytest benches/ --benchmark-only --benchmark-json=bench-results.json -q && python scripts/bench_check.py --baseline ../.github/perf-baselines.json --results bench-results.json"
fi

echo ""
echo "════════════════════════════════════════════════"
if [ ${#FAILED[@]} -eq 0 ]; then
    echo "✅ Local CI green. Safe to push."
    exit 0
else
    echo "❌ Local CI failed in: ${FAILED[*]}"
    exit 1
fi
```

#### 2C — Disable failing GitHub workflows do czasu stabilizacji

Opcja **A** (zalecana — utrzymaj security.yml, zatrzymaj zawodne):

Edytuj `.github/workflows/ci.yml`:
- Usuń `macos-latest` z `python-host.strategy.matrix.os` (libvirt-python
  wheel build nie idzie na macos w cold env) — zostaw tylko `ubuntu-latest`
- Usuń `macos-latest` z `rust-guest-cross-compile.strategy.matrix.os`
- W `i18n-extract`: dodaj `continue-on-error: true` (.pot drift nie powinien
  blockować merge — to push fix-up commit)
- W `rust-gui.steps[qmllint]`: dodaj `continue-on-error: true` do czasu
  upgradu runnera Qt 6.5+

Opcja **B** (drastyczna — wyłącz CI total):

```yaml
# .github/workflows/ci.yml header:
on:
  workflow_dispatch:   # tylko manual trigger
```

Tj. tymczasowo zatrzymaj automatyczne CI; właściciel klika "Run workflow"
tylko gdy chce. Local CI staje się jedynym gate'em do merge'a.

**Rekomendacja**: Opcja A. Ucinają się zawodne joby, security.yml leci
osobno, manual override przez `workflow_dispatch`.

#### 2D — Update Node.js 20 deprecation

Każda akcja w `.github/workflows/*.yml`:
```yaml
# Zmień:
- uses: actions/checkout@v4         # uses Node 20
- uses: actions/setup-python@v5     # uses Node 20

# Na:
- uses: actions/checkout@v5         # uses Node 24
- uses: actions/setup-python@v6     # uses Node 24
```

(Jeśli v5/v6 dostępne — sprawdź marketplace.)

ALBO opt-in flag (per deprecation message):
```yaml
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
```

---

### Łączny effort dla Części 2

| Sekcja | Effort | Zysk |
|--------|-------:|------|
| 2A — Rozszerz .githooks/pre-push | 1.5h | Mirror GH CI lokalnie, ~60s per push |
| 2B — scripts/local-ci.sh | 30 min | On-demand pełen run |
| 2C — Disable failing GH workflows | 30 min | Stop spamu zielonych/czerwonych |
| 2D — Node.js 24 upgrade | 15 min | Out of deprecation |
| **RAZEM** | **~2.5h** | Lokalne push = wiarygodny zielony |

---

## Sekwencja wykonania (jeśli decydujesz się ruszyć)

Sugerowana kolejność:

**Tydzień 1 — bazowa stabilność**:
1. Część 2 całość (2.5h) — żeby przestał spamować GH i mieć wiarygodne local gate
2. Część 1A (2h) — pre-publication blockers, błyskawiczne wins
3. Część 1H (2h) — deps refresh, removes 36 bandit warnings

**Tydzień 2 — readability**:
4. Część 1B (1h) — abstractions cleanup
5. Część 1D.1 (1.5h) — OpenSession (biggest single readability win)
6. Część 1D.2 (1.5h) — Channel
7. Część 1C (1h) — transport/mock coverage

**Tydzień 3 — głębsza praca**:
8. Część 1D.3 + 1D.4 (2h) — pozostałe complex functions
9. Część 1E (4h) — management split
10. Część 1J (2h) — vulture cleanup

**Tydzień 4 — uczciwość + długie ogony**:
11. Część 1F (6h) — docstring sweep
12. Część 1G.1 (1h) — broken links
13. Część 1I (5h) — mutation testing pod Python 3.12

**User-only** (kiedykolwiek, nieblokujące dla agenta):
14. Część 1G.2 — THREAT_MODEL update for 4 servicers

**Po wszystkim**: świeży audyt (powtórzenie metryk) → spodziewany Slop Score ~5.

---

## Co NIE jest w zakresie tego planu

- **Hardware-gated work** (Linux+KVM smoke testy, real libvirt wiring) —
  to Phase 2-3 roadmap items, czekają na sprzęt
- **API stability promises** — gdyby pre-v1 wymagał stabilnego proto API,
  trzeba osobnej rozmowy o `breaking: FILE` vs `WIRE_JSON` w buf.yaml
- **Self-hosted CI runner** — pending user-decision per AGENTS.md
- **Code signing strategy** — pending user-decision

---

**Plan stworzony 2026-05-20. Brak edycji kodu, tylko dokumentacja.**
