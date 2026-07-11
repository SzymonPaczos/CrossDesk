# Reguły audytu

Cotygodniowy audyt jakości. Mechanizm: **audyt wykrywa → naprawiamy →
ratchet zamraża → trend mierzy.** Kanoniczne źródło konwencji:
`~/DevProjects/claude-toolkit/NEW-PROJECT.md` §9.2 + skill
`.claude/skills/weekly-audit/SKILL.md`.

Audyt **nie naprawia nic sam.** Właściciel decyduje.

## Dwie warstwy

1. **Statyczna** — `.claude/audit.sh` liczy metryki (lint, mypy, tests,
   buf, qmllint, gitleaks, decisions count, drift). Bez LLM. Dopisuje
   sekcję `## Audyt YYYY-MM-DD` na górę `.claude/audit-log.md`.
2. **Głęboka** — agent ocenia (~20-40 min), zgodnie z procedurą poniżej.

> **Od 2026-07-12 (DEC-META-008):** procedura kanoniczna to skill
> `.claude/skills/weekly-audit/SKILL.md` (master toolkitu 2026-07-11).
> Dodaje: **Krok 0** (SAST + linter workflowów + Security Reviewer z
> `.claude/agents/security-reviewer.md` w niezależnym kontekście; Red
> Team miesięcznie / risk-triggered), punkty głębokie **8–13** (gate'y,
> supply chain, delivery, provenance zmian, vulnerability response,
> jedna derywacja stanu) i **obowiązkowy nagłówek raportu**
> (AUDITED_REVISION / TOOLS / SECURITY_REVIEW / …). Sekcje 1–8 poniżej
> pozostają CrossDesk-owym uszczegółowieniem punktów 1–7 skilla.

## Procedura (warstwa głęboka)

### 1. Bezpieczeństwo
Nowe API endpoints bez rate-limit / walidacji; `dangerouslySetInnerHTML`
/ `innerHTML` bez sanityzacji; raw SQL z user input; sekrety w repo
(`.env`, klucze API w historii). W CrossDesk szczególnie: gRPC servicery
bez timeoutów, mTLS misconfig, `unsafe` w Rust bez `// Safety:` komentarza,
proto edit bez aktualizacji `docs/THREAT_MODEL.md`.

### 2. Slop
Hardcoded dane w UI udające realne (głosy, %, nazwiska); mocki podane
jako prawdziwe dane; funkcje oznaczone "gotowe" gdy są zaślepkami. W
CrossDesk: zwracaj uwagę na `🚧 mock` markery — sprawdź czy są dalej
uzasadnione, czy zaległy w merge i zostały zapomniane.

### 3. Backend
Swallowed errors (`except: pass`, `except: return []`); brak walidacji
wejść zewnętrznych (boundary = gRPC servicer entry, libvirt response,
CLI user input); `datetime.now()` jako data dokumentu historycznego; ID
jako licznik zamiast hash. Asyncio specific: `while True: sleep()`
polling (zakazane), brak `timeout=` na HTTP/gRPC client calls.

### 4. Testy
Nie ile plików, lecz **co testują**: krytyczne ścieżki bez pokrycia
(mTLS handshake, AuthValidator, lifecycle FSM transitions); testy które
nic nie weryfikują (asserując return value bez side-effects); `skipped`
bez uzasadnienia. CrossDesk-specific: `test_smoke_inprocess.py` jako
boundary contract — pęknięcie tu = real bug.

### 5. Architektura
Drift `.claude/architecture.md` ↔ kod; duplikaty logiki; martwe pola
schema; niespójne wzorce. Konkretnie: czy nowe RPC honoruje proto-first
pattern (`AGENTS.md` "Patterns when contributing")? Czy abstrakcje
(`LibvirtController`, `FilesystemController`, `Transport`, `Notifier`)
są respektowane i nie ma bezpośrednich `import libvirt` poza
`real.py`?

### 6. Dead code
Zweryfikuj greppem heurystyki audit.sh — base-classy mylą się z dead
code. Listę "0 production callers" zawsze przepuszczaj przez
`grep -rn '<Name>' --include='*.py'` po całym repo. Patrz
`.claude/ignorefiles.md` "Partially broken / deprecated" — pozycje
oznaczone tam są świadomie dead, nie raportuj.

### 7. Zgodność z `.claude/rules/decisions.md` + `docs/DECISIONS.md`
Czy kod nie łamie aktywnej decyzji (status: aktywna w `decisions.md`
META **lub** ADR `DEC-NNNN`)? Złamanie = **P0** (security/compliance)
lub **P1** (architectural drift). Sprawdź przykłady regresji:
- "No Docker" (DEC-0003) — sprawdź czy nie pojawił się `Dockerfile` /
  `compose.yaml`.
- "No polling" (`.claude/rules/general.md`) — grep za `while True`
  + `sleep`.
- "mTLS leaves gitignored" (`.claude/rules/backend.md`) — sprawdź
  `infra/certs/pki/` w git tree.

### 8. Skille / MCP
- Pojawiło się coś nowego w `~/DevProjects/claude-toolkit/skills/`
  od ostatniego audytu? Skopiuj zaktualizowane wersje do
  `.claude/skills/` (model kopiowania §9.5). Jeśli w projekcie powstał
  generyczny skill — promuj do toolkit.
- Stan MCP — sprawdź `.mcp.json` (lub `~/.claude.json`); hasła
  bywają nieaktualne; serwery w `~/.claude/mcp-servers.json` są
  ignorowane (§9.6).

## Priorytety

- **P0** — krytyczne: luki bezpieczeństwa, utrata integralności danych,
  kod kłamiący użytkownika, złamanie aktywnej decyzji o
  bezpieczeństwie/threat model, proto edit bez THREAT_MODEL update.
- **P1** — ważne: dług blokujący rozwój, swallowed errors, brak testów
  krytycznych ścieżek, architectural drift, hardcoded values
  w produkcji (poza świadomymi mock'ami).
- **P2** — porządkowe: dead code, drift dokumentacji, kosmetyka,
  odstępstwa od §9.9 layout, brakujące docstrings.

## Wynik

Sekcja w `.claude/audit-log.md` kończy się **listą P0/P1/P2**. Po
zaakceptowaniu przez właściciela pozycje są dodawane do
`.claude/backlog.md` w odpowiednie sekcje.

## Ratchet

Naprawione = natychmiast zamrożone. Konkretne ścieżki:
- Linter dochodzi do 0 błędów → usuń `|| true` z odpowiedniego gate'a
  w `.githooks/pre-push` lub `.github/workflows/ci.yml`.
- Coverage wzrósł → podnieś próg w `pyproject.toml` / `Cargo.toml`.
- Nowa abstrakcja wprowadzona → dodaj do `audit.sh` grep gate
  zabraniający bezpośrednich importów.

Raz osiągnięty poziom = podłoga, nie sufit.

## Czego NIE robić w audycie

- Nie naprawiaj niczego z własnej inicjatywy. Audyt **diagnozuje**, nie
  naprawia.
- Nie commituj poza `audit-log.md` (na branchu adopcji `audit.sh`
  może też dodać wpis — dopuszczalne).
- Nie przebudowuj struktury plików (to robi `ADOPT.md`, nie audyt).
- Nie dotykaj boundary plików z `AGENTS.md` "File boundaries"
  (proto, THREAT_MODEL, DECISIONS, REQUIREMENTS, MVP_SCOPE, GOALS,
  ROADMAP, AGENTS.md) — flaguj jako P0/P1 jeśli wymagają zmiany,
  właściciel decyduje.
- Nie pomijaj `docs/DECISIONS.md` ani `.claude/rules/decisions.md` —
  zgodność z aktywnymi decyzjami to twardy gate.
