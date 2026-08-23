# Handoff — remediacja audytu 2026-08-23 (dla pętli Opusa)

> Autor: sesja audytowa 2026-08-23. Odbiorca: autonomiczna pętla Opusa.
> **Kontrakt operacyjny bez zmian** — obowiązuje [`loop-spec.md`](loop-spec.md)
> (per-iteration algorithm, toggles PUSH=ON / ENV=box, guardrails, Loop log).
> Ten plik dokłada **jedną rzecz**: uporządkowaną kolejkę remediacji świeżego
> audytu, bo żywy queue v0.1.0 (C4–C8) jest w całości zaparkowany.

## Dlaczego nowa kolejka, a nie C4–C8

Audyt 2026-08-23 (pełny raport: [`audit-log.md`](audit-log.md) górna sekcja;
findingi zdeduplikowane do [`backlog.md`](backlog.md) P1/P2) potwierdził, że
**żywe pozycje v0.1.0 nie nadają się teraz na autonomiczną pętlę**:

- **C4 (#3 FS Stage B)** — strona GOŚCIA nie istnieje (WinFsp + viofs + VirtioFsSvc
  niezbudowane; `domain_xml.py:123` sam to mówi). Park, `loop-spec` 2026-07-25.
- **C5 (#5 suspend/resume)** — owner-eyeball (system-bus, root, zawiesza box). Runbook w `needs-owner.md`.
- **C6 (#12 packaging)** — Ubuntu box bez `makepkg`/`pacman` + brak tagu `v0.1.0`. Env-gate.
- **C7 (#11 real README run)** — destrukcyjny + eyeball.
- **C8 (M5 burn-in)** — destrukcyjny + eyeball.

Za to audyt wyprodukował **deterministyczny kod host-side** — dokładnie to, co
pętla robi najlepiej (branch → gate → commit → merge → push → record).

## Kolejka remediacji (rób top-down; jeden item = jedna iteracja)

### R1 · SEC-02 (MEDIUM) — JIT-lite dzieli całe `$HOME`, po cichu, bez ostrzeżenia

**Znaleziony przez DWA niezależne agenty** (Security Review F-1 + Red Team A) i
**zweryfikowany w kodzie przez sesję audytową**. Realny bypass „loud opt-in" DEC-0019.

- **Pliki:** [`host/src/crossdesk_host/ipc/management.py`](../host/src/crossdesk_host/ipc/management.py)
  `_jitlite_flags` (l. 563-598) · [`host/src/crossdesk_host/jit_mount/path_validation.py`](../host/src/crossdesk_host/jit_mount/path_validation.py)
  `parent_share_path` (l. 104-111).
- **Defekt:** `_jitlite_flags` wołane bezwarunkowo (`management.py:452`), także przy
  `shared_folder_enabled=False`; dla pliku w korzeniu `$HOME` (`~/x.txt`)
  `parent_share_path` zwraca `Path.home()` → gość dostaje `/drive:CrossDesk,/home/<user>`
  = **całe `$HOME` R/W** (`~/.ssh` + klucz mTLS + hasło VM). Ścieżka NIE woła
  `home_scope_warning()` (emitowany tylko z `_peripheral_flags`, `management.py:538-540`),
  a kontrakt „caller must re-validate" z docstringu `parent_share_path` jest niespełniony.
- **Fix:** w `_jitlite_flags` po wyliczeniu `parent`: jeśli `parent == Path.home()`
  (lub dowolny `allowed_root` z `path_validation`) → `return None` (fallback do
  persistent scoped share) LUB wymuś `home_scope_warning`. Re-waliduj `parent` przez
  `validate_mount_path(str(parent))` per kontrakt helpera. Emituj ostrzeżenie, gdy
  wyprodukowany share == `$HOME`.
- **Test regresji (napisz):** `_jitlite_flags("/home/<u>/x.txt")` NIE zwraca cicho
  `/drive:...,/home/<u>` (albo `None`, albo z logiem `shared_folder_home_scope`);
  `_jitlite_flags("/home/<u>/Documents/x.txt")` NADAL zwraca `/drive:...,{$HOME}/Documents`.
- **Uwaga boundary:** jeśli fix odsłoni potrzebę zmiany `docs/THREAT_MODEL.md` /
  `MVP_SCOPE.md` — **NIE dotykaj**, wrzuć draft do `needs-owner.md` i oznacz ⏸.
  Sam kod fixu + test to NIE boundary — rób.

### R2 · Red-Team Finding B (LOW dziś / latent-MEDIUM) — `ShareChannel` token + nieescapowany XML

Sink dziś nieosiągalny (`trigger_mount` bez produkcyjnego callera), ale **musi paść
PRZED Stage B** (kryt. #3) — hardening z wyprzedzeniem.

- **Pliki:** [`host/src/crossdesk_host/ipc/filesystem.py`](../host/src/crossdesk_host/ipc/filesystem.py)
  (`_token_ok` l. 128-139; `release_ack` l. 107-117; `trigger_mount` l. 141+) ·
  [`host/src/crossdesk_host/libvirt_ctl/real.py`](../host/src/crossdesk_host/libvirt_ctl/real.py)
  (`attach_virtiofs`/`detach_virtiofs` l. 255-289, f-string device XML).
- **Fix (dwie warstwy — możesz je rozbić na dwie iteracje, jeśli jedna nie zmieści się w gate):**
  1. **XML-escaping (tanie, bezpieczne):** buduj `<filesystem>` device XML przez
     `xml.sax.saxutils.quoteattr` / `ElementTree` zamiast surowego f-stringa;
     waliduj `share_id` regexem UUID przed libvirt.
  2. **Token-authz:** przechowuj mintowany `mount_token` per `share_id` w
     `trigger_mount`; w `_token_ok` porównuj wartością przez `hmac.compare_digest`;
     odrzuć `share_id` spoza `active_shares` **przed** `detach_share`.
- **Test regresji:** `release_ack` ze złym 32B tokenem i/lub nieznanym `share_id`
  NIE woła `detach_virtiofs`; `share_id` z `'`/`<` odrzucony przed wywołaniem XML.

### R3 · Security Review F-2 (P2/NOTE) — `AuthValidator._active_streams` leak

- **Pliki:** [`host/src/crossdesk_host/ipc/auth.py`](../host/src/crossdesk_host/ipc/auth.py)
  (`remove_stream`) · `ipc/heartbeat.py` (blok `finally` `Channel`) ·
  `ipc/filesystem.py` (`ShareChannel`).
- **Defekt:** `remove_stream` wołane tylko w `control.py:291`; heartbeat i filesystem
  rejestrują nonce, nigdy nie zdejmują → wzrost pamięci per reconnect. Nie eksploit (mTLS-gated), czysty dług.
- **Fix:** wołać `auth_validator.remove_stream(stream_nonce)` w blokach `finally`
  obu kanałów (wzór: `control.py`).
- **Test:** po zamknięciu N kanałów `len(validator._active_streams) == 0`.

### R4 · P0 pre-push gate — antywzorzec A1 (backlog TOP; **spróbuj OSTATNI, uważnie**)

Backlog TOP §1 + `rules-as-gates.md` „Antywzorce A1". Hook liczy zmiany z *working
tree*, nie z pushowanego commita.

- **Plik:** [`.githooks/pre-push`](../.githooks/pre-push) (dziś: `git diff …origin/$DEFAULT_BRANCH...HEAD`
  + czyta pliki z dysku, l. 52/63/222…; nie czyta refów ze stdin).
- **Fix (wzór A1):** czytaj `<local ref> <local sha> <remote ref> <remote sha>` ze
  stdin; zakres `remote_sha..local_sha` (nowa gałąź: `local_sha --not --remotes`);
  odtwórz commit przez `git worktree add --detach` i skanuj pliki TAM.
- **⚠️ RYZYKO / ograniczenie dowodu:** kanoniczny dowód domknięcia
  (`bash <toolkit>/templates/test-gates.sh .githooks/pre-push → 6/6`) jest
  **NIEWYKONALNY** — toolkit nieobecny na boxie (`~/DevProjects/claude-toolkit`
  nie istnieje). Więc: (a) zrekonstruuj wzór z opisu A1 w `rules-as-gates.md`, nie
  z brakującego szablonu; (b) napisz własny sentinel-test w istniejącym
  [`host/tests/test_pre_push_hook.py`](../host/tests/test_pre_push_hook.py) —
  commit z sekretem, poprawka TYLKO w working tree bez commitowania, push →
  stary hook przepuszcza, nowy blokuje. **Jeśli nie da się zrobić czysto +
  udowodnić w dwóch próbach → PARK z tekstem błędu** (loop-spec krok 4).

## Persystencje — NIE rób sam, tylko trzymaj na radarze

Zaparkowane owner/env-gate (raport audytu je wylicza): SEC-01 (kanarek gitleaks v3),
brak `SECURITY.md`, brak lockfile'a Pythona (uv vs pip-tools = decyzja właściciela),
Krok 00/05 DEGRADED (toolkit nieobecny), `cargo-deny` 24→25 (duplikaty otel),
`audit.sh` quirk detekcji kadencji. Wszystkie w `backlog.md` / `needs-owner.md`.

## Zasady (przypomnienie z loop-spec)

- Jeden item = jedna iteracja. Branch z świeżego `main`, bez drive-by refactorów.
- Gate: `ruff check src/ tests/` · `mypy --strict src/` · `pytest` (host). Zielono lub park; **nigdy `--no-verify`**.
- Commit: Conventional Commits + trailery `Intent:`/`Task-Ref:`/`Gates:` (change-provenance). **Zero atrybucji AI** (D-006). Bez backticków w `-m`.
- Merge `--no-ff` → push (PUSH=ON) → **zweryfikuj `gh run list --branch main`** (lokalne bramki to lustro, nie prawda — krok 7). Czerwony `main` = następny item.
- Record: `backlog.md` (oznacz finding zrobiony) · `status.md` jeśli partial się zmienił · jedna linia w Loop log w `loop-spec.md`.
- Boundary (`proto/**`, `docs/{THREAT_MODEL,DECISIONS,REQUIREMENTS,MVP_SCOPE,GOALS}.md`, `ROADMAP.md`, `AGENTS.md`) → **draft do `needs-owner.md`, park**, nie aplikuj.
- Po wyczerpaniu R1–R4: jeśli nic nieowner-gated/nie-destrukcyjnego nie zostało, **stop i raportuj** (queue drained) — nie ruszaj C4–C8 sam.
