# Audit Log

Newest audit first. Format: each run dopisuje sekcję `## Audyt YYYY-MM-DD` na górę.

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

