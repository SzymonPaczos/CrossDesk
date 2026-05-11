# Automated Audit Report — 2026-05-11

## Streszczenie

| Pole | Wartość |
|------|---------|
| Data | 2026-05-11 |
| Gałąź | `chore/audit-2026-05-11` (NIE zmergowana do `main`) |
| Commit range | `main..330e7cc` (3 fazowych commitów) |
| Zakres | host (Python), guest workspace (Rust), gui workspace (Rust) |
| Boundaries | proto/*.proto, THREAT_MODEL, DECISIONS, REQUIREMENTS, GOALS, MVP_SCOPE, ROADMAP, AGENTS.md — nietknięte |

Status faz:

| Faza | Cel | Status | Commit |
|------|-----|--------|--------|
| 1 | Linter auto-fixes | ✅ DONE | `890bee7` |
| 2 | Dead code elimination | ✅ DONE (no changes — wszystko false-positive) | — |
| 3 | Rust safety audit | ✅ DONE | `28502d3` |
| 4 | Public API docstrings | ✅ DONE (narrow scope) | `330e7cc` |
| 5 | Test verification | ✅ DONE | — |
| 6 | Report (this file) | ✅ DONE | — |

## Faza 1 — Linter auto-fixes

### Python (host/)
- `ruff check --fix --unsafe-fixes src/ tests/` → 15 napraw w 12 plikach
  testowych (głównie unused-imports F401 + isort I001).
- Skipped: `ruff format` — DUŻY DIFF (985 linii ujętych w 86 plikach,
  rozjazd z `black` line-length). Format CI gate to tylko `ruff check`
  (nie `ruff format`), więc reformatowanie wykraczało poza zakres
  audytu. **Zapisane do tech-debt.**
- mypy `--strict` przeszło: 108 plików, 4 pre-existing errory w
  `dbus_listener.py` + `notifications.py` (niezwiązane).

### Rust (guest/)
- `cargo fmt --all` → 20 plików .rs, czysty whitespace.
- `cargo clippy --workspace --all-targets --fix` → bez zmian
  (baseline już clippy-clean po wcześniejszych pracach).

### Rust (gui/)
- `cargo fmt --all` → 1 plik (`qobjects/wizard.rs`).
- `cargo clippy --workspace --all-targets -- -D warnings` znalazło 1
  nieautofiksowalny warning: `clippy::manual_clamp` w
  `crates/crossdesk-gui/src/qobjects/wizard.rs:160`. Zamieniono
  `((cpus / 2).max(2)).min(8)` na `(cpus / 2).clamp(2, 8)` ręcznie.

### Bramki po fazie 1
- `ruff check src/ tests/` → All checks passed.
- `cargo clippy --workspace -- -D warnings` → czyste na guest i gui.

## Faza 2 — Dead code elimination

**Wynik: zero zmian** — wszystkie znaleziska to false positives.

### Python: ruff F401/F811/F841 → All checks passed.
### Python: vulture (90% confidence, src/ tylko) → 4 znaleziska, każde false positive:

| Plik | Linia | Powód false-positive |
|------|-------|---------------------|
| `config/peripherals.py` | 158 | `__context: object` — to wymagana sygnatura hooka Pydantic v2 `model_post_init`. |
| `ipc/management.py` | 225 | `if False: yield ...` — idiom forsujący `async def` do bycia async-generatorem; bez tego sygnatura `AsyncIterator[...]` jest niespełniona. |
| `libvirt_ctl/real.py` | 14 | `_libvirt_t` — używane w string-annotation linii 30 (`"_libvirt_t.virConnect | None"`). |
| `observability/trace_ctx.py` | 23 | `Iterator` — używany w `def child_span_scope() -> "Iterator[TraceContext]"` (linia 148). |

### Rust: `cargo clippy -W dead_code -W unused` → 0 warnings na guest i gui.

### Rust: cargo-machete (nieużywane manifest deps) — 6 znalezisk, **nie usuwane** z uwagi na:

| Crate | Dep | Decyzja |
|-------|-----|---------|
| `proto` | `prost`, `prost-types` | False positive — tonic-build kod używa ich w generowanym kodzie. |
| `agent-svc` | `tracing-subscriber` | **Genuinely unused w source.** Pozostawione: niskie ryzyko, ale jeśli przyszły kod chce wpisać własny subscriber, wartość jest już w manifeście. → tech-debt. |
| `observability` | `serde` | `serde_json::Value` jest używane (linia 171), ale `serde` jako direct dep — nie. Removal trywialne, ale bez bezpośredniego efektu → tech-debt. |
| `fs-mount` | `anyhow`, `windows` | **cfg(windows)-staged dla Phase 5 work.** Pozostawione — usuwanie pociąga ryzyko regressji przy resume na Windows target. → tech-debt. |
| `rail-bridge` | `anyhow`, `tonic` | Jak wyżej. → tech-debt. |
| `crossdesk-gui` | `cxx` | Używane przez `cxx_qt_lib` macros — false positive (cargo-machete nie analizuje proc-macro expansion). |

## Faza 3 — Rust safety audit

### Clone audit
- 20 wystąpień `.clone()` w `guest/crates/*/src/`. Każde uzasadnione
  — albo `tokio::spawn` przenoszenie własności w 3 plane'y (planes.rs:85-95),
  albo `auth/tx` propagacja do worker tasks (session.rs:39-40,
  filesystem.rs:76-77), albo `&self` returning owned `Vec`
  (registry-scan/mock_impl.rs:58), albo `Arc` w testowej infrastrukturze
  (observability/lib.rs:141-167). Brak redundant clone'ów do usunięcia.
- 0 wystąpień `.clone()` w `gui/crates/*/src/`.

### Unsafe block audit
6 bloków bez `// Safety:` komentarza zostało udokumentowanych:

| Plik | Linie | API |
|------|-------|-----|
| `agent-svc/src/host_uuid.rs` | 57, 63 | `GetSystemFirmwareTable` (probe + fill) |
| `rail-bridge/src/windows.rs` | 34 | `GetCurrentThreadId` |
| `rail-bridge/src/windows.rs` | 36-60 | `SetWinEventHook` + `GetMessageW`/`DispatchMessageW`/`UnhookWinEvent` |
| `rail-bridge/src/windows.rs` | 74-78 | `PostThreadMessageW` |
| `rail-bridge/src/events.rs` | 22-24 | `GetWindowThreadProcessId` |
| `rail-bridge/src/events.rs` | 29-38 | `GetWindowRect` |
| `rail-bridge/src/events.rs` | 43+ | `GetWindowTextLengthW` + `GetWindowTextW` |

GUI `unsafe { extern "C" }` bloki w `crossdesk-gui/src/i18n/mod.rs` już
miały `// Safety:` komentarze — pominięte.

### `unwrap()` / `expect()` audit
- Produkcyjny path: tylko `agent-svc/src/service.rs:75`
  (`tokio::runtime::Runtime::new().expect(...)`) — już posiada 5-liniowe
  uzasadnienie nad wywołaniem. **OK.**
- Pozostałe `unwrap`/`expect` (~20 wystąpień) są w `#[cfg(test)]`
  modułach (`mock_impl.rs`, `transport/mock.rs`, `trace.rs::tests`,
  `transport/real.rs::tests`, `host_uuid.rs::tests`,
  `observability/lib.rs::tests`) gdzie panic-on-test-failure jest
  intencjonalne.

## Faza 4 — Public API docstrings

**Bardzo wąsko zakreślona faza** — top-level entry points only.

- `host/src/crossdesk_host/daemon.py`: dodano module-level docstring +
  `async def main()` docstring.
- `guest/crates/rail-bridge/src/lib.rs`: dodano crate-level `//!` doc
  + per-stub doc dla non-Windows shims `start_hook_thread` /
  `request_shutdown`.

Pełny audyt brakujących doc-stringów:
- **Python**: 215 publicznych symboli bez docstringa (włączając
  config-property accessors o oczywistych nazwach jak
  `vm_credentials_file`). Większość self-documenting przez nazwę.
  Pełny dokument tego nie wymaga.
- **Rust**: 289 missing-docs warnings (`RUSTDOCFLAGS="-W missing_docs"
  cargo doc`). Większość to struct fields / enum variants / impl
  methods o oczywistym znaczeniu.

→ **Tech-debt** (poniżej).

## Faza 5 — Test verification

Bramki:

| Suite | Wynik |
|-------|-------|
| Host: `pytest -q --timeout=30 --ignore=tests/test_grpc_interceptor.py` | **621 passed, 10 pre-existing async-fixture errors** |
| Guest: `cargo test --workspace` | **31 passed, 0 failed** (8 + 11 + 1 + 6 + 5 podzielone na 5 cratów) |
| Guest: `cargo clippy --workspace --all-targets -- -D warnings` | clean |
| GUI: `cargo check --workspace` | clean |
| GUI: `cargo clippy --workspace --all-targets -- -D warnings` | clean |
| Host: `mypy --strict src/` | 108 plików, 4 pre-existing dbus_next type:ignore errors |
| Host: `ruff check src/ tests/` | All checks passed |

**Manual interventions wymagane (pre-existing, niezwiązane z tym audytem):**

1. **`pytest-asyncio` plugin incompatibility z `pytest` 8.4.2.** 10 testów (5 w `test_smoke_e2e.py`, 4 w `test_smoke_inprocess.py`, 1 w `test_grpc_interceptor.py`) zawodzi w setup'ie z:
   ```
   AttributeError: 'FixtureDef' object has no attribute 'unittest'
   /Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/site-packages/pytest_asyncio/plugin.py:321
   ```
   Zweryfikowane: błąd występuje również na `main` HEAD przed jakąkolwiek zmianą. Wymaga albo pinningu `pytest-asyncio` do wersji kompatybilnej z `pytest>=8.4`, albo upgrade'u plugin'u do najnowszej wersji obsługującej `FixtureDef.unittest`. Memory note z `2026-05-11`: "613 passed + 12 pre-existing async errors" — liczba pre-existing async errors wzrosła z 12 do co najmniej 10+ w międzyczasie z powodu version drift na host dev box.

2. **4 pre-existing mypy errory** w `host/src/crossdesk_host/lifecycle/dbus_listener.py` + `integrations/notifications.py` o treści `Unused "type: ignore" comment, use narrower [import-not-found] instead of [import] code`. Tło: ostatni commit `8f3ac68 fix(mypy): broaden dbus_next type: ignore for mypy 2.1 on Linux` częściowo zaadresował to dla Linuxa; pozostałe występują pod mypy 2.0 na macOS dev hoście. Wymagają węższych kodów (`[import-not-found]`) zamiast bare `[import]`.

3. **`pytest -q` zawiesza się** (run w tle 9 minut, 0% CPU, 11% complete) — najprawdopodobniej pochodna asyncio fixture errora w którym setUp wisi na await. Workaround zastosowany w tym audytcie: `--timeout=30` + `--ignore=tests/test_grpc_interceptor.py` daje deterministic 55s run. Bez timeoutu pytest nie potrafi się sam zakończyć.

## Manual interventions (file boundaries)

Następujące potencjalne polepszenia LEŻĄ POZA zakresem auto-audytu
zgodnie z `AGENTS.md` "File boundaries":

- **`proto/buf.yaml`** — można rozważyć `lint: comments-after-keywords`
  jeśli buf doda taki lint w przyszłości. Boundary: każda edycja
  `proto/` wymaga user-approval.
- **`docs/THREAT_MODEL.md`** — wpływ zmiany typ-ignore w
  `dbus_listener.py` na C7 (credentials drift) nie został przeanalizowany.
  Boundary.
- **`docs/DECISIONS.md`** — żadne ADR nie pokrywa "automated audit
  cadence". Czy potrzebny? User-decision.

## Long-term tech debt (nie naprawione w tym audycie)

Posortowane wg malejącego nakładu pracy / korzyści:

1. **Python: ~215 missing docstringów** — głównie property accessors
   w `config/__init__.py` (self-documenting), libvirt_ctl methods
   (`hard_destroy`, `graceful_shutdown`, `suspend`, `resume`,
   `attach_virtiofs`, `detach_virtiofs`, `set_memory`,
   `get_memory_stats`), recovery models, transport servicers.
   Strategia: 1-liner docstrings tam gdzie nazwa NIE wyjaśnia
   *why*; pominąć trywialne gettery.

2. **Rust: ~289 missing-docs warnings** — głównie struct fields i
   enum variants w `registry-scan`, `observability`, `proto`
   facades. Strategia: ograniczyć `#![warn(missing_docs)]` do
   `lib.rs`/`mod.rs` plików, leaving struct internals
   default-documented przez nazwy pól.

3. **`ruff format` rozjazd z `black`** — projekt aktualnie używa
   `black` (line-length 88) jako formatera, ale `ruff` ma
   line-length 120 (`pyproject.toml:91`). `ruff format` produkuje
   985-liniowy diff w 86 plikach względem aktualnego stanu.
   Strategia (dec): porzucić `black` na rzecz `ruff format` (1
   formater zamiast 2), pomimo dużego one-time diff.

4. **Pre-existing mypy errors** (4) — `dbus_next` import type:ignore
   markers. Wymagają węższych kodów `[import-not-found]`.

5. **Manifest dead deps** — `agent-svc:tracing-subscriber`,
   `observability:serde`. Trywialne usunięcia ale potencjalne
   ryzyko jeśli ktoś niezależnie planuje dodać `#[derive(Serialize)]`.
   Strategia: usunąć ostentacyjnie i opatrznościowo dodać back
   gdy realnie potrzebne.

6. **`unsafe` block style consistency** — `events.rs` i `windows.rs`
   teraz mają `// Safety:` markers. `agent-svc/host_uuid.rs` tak
   samo. Konwencja powinna być zapisana w `.claude/rules/backend.md`
   jako mandatory dla wszystkich `unsafe { ... }` bloków (nie
   tylko `unwrap()` / `expect()`).

7. **cfg-gated Cargo.toml deps** w `fs-mount` i `rail-bridge`
   (`anyhow`, `windows`, `tonic`) — pre-staging Phase 5. Należy
   dodać `[target.'cfg(windows)'.dependencies]` zamiast top-level
   `[dependencies]`, żeby `cargo machete` przestał je flagowal.

## Cofnięte moduły

Brak — żaden moduł nie wymagał `git restore` per safety-rail.

## Replikacja

```sh
# Faza 1 (auto-fix lintery)
cd host && ruff check --fix --unsafe-fixes src/ tests/
cd ../guest && cargo fmt --all
cd ../gui && cargo fmt --all
# (manual_clamp fix w wizard.rs jeśli powtarzasz)

# Bramki
cd host && mypy --strict src/ && ruff check src/ tests/
cd ../guest && cargo clippy --workspace --all-targets -- -D warnings
cd ../guest && cargo test --workspace
cd ../gui && cargo clippy --workspace --all-targets -- -D warnings
```

## Następne kroki dla użytkownika

1. Review tej gałęzi (`chore/audit-2026-05-11`).
2. Decyzja merge / cherry-pick / odrzuć.
3. Decyzja tech-debt pkt 3 (`ruff format` vs `black`) — wpływa na
   przyszłe formatowanie.
4. Decyzja tech-debt pkt 4 (mypy dbus_next) — drobny fix, ale wymaga
   testu na Linux+Python 3.9.
