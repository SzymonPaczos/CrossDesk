# universals.md — Architektura Agentów Claude Code (Stack-Agnostic)

> **Co to jest:** samowystarczalny pojedynczy plik, który pozwala odtworzyć w dowolnym nowym repozytorium architekturę agentów wypracowaną w projekcie **OpenState**. Wkleja się tu wszystkie templates plików (`CLAUDE.md`, `.claude/*`, `.githooks/*`) jako fenced code blocks gotowe do skopiowania.
>
> **Jak używać:** masz dwie ścieżki — sekcja [0](#0-meta-prompt-dla-agenta-inicjującego) (oddaj robotę agentowi) lub sekcja [2](#2-quickstart-5-minut-człowiek) (zrób ręcznie w 5 min).
>
> **Język:** polski (jak w OpenState). Łatwo przetłumaczyć później.

---

## Spis treści

- [0. Meta-prompt dla agenta inicjującego](#0-meta-prompt-dla-agenta-inicjującego)
- [1. Co to jest i dlaczego](#1-co-to-jest-i-dlaczego)
- [2. Quickstart (5 minut, człowiek)](#2-quickstart-5-minut-człowiek)
- [3. Templates plików](#3-templates-plików)
  - [3.1 CLAUDE.md](#31-claudemd)
  - [3.2 .claude/active-work.md](#32-claudeactive-workmd)
  - [3.3 .claude/rules/general.md](#33-clauderulesgeneralmd)
  - [3.4 .claude/rules/frontend.md](#34-clauderulesfrontendmd)
  - [3.5 .claude/rules/backend.md](#35-clauderulesbackendmd)
  - [3.5.1 .claude/rules/rpc.md](#351-clauderulesrpcmd) *(opcjonalny — proto-first)*
  - [3.6 .claude/rules/security.md](#36-clauderulessecuritymd)
  - [3.7 .claude/rules/status.md](#37-clauderulesstatusmd)
  - [3.8 .claude/settings.json](#38-claudesettingsjson)
  - [3.9 .claude/architecture.md](#39-claudearchitecturemd)
  - [3.10 .claude/ignorefiles.md](#310-claudeignorefilesmd)
- [4. Git Hooks](#4-git-hooks)
- [5. Coordination Protocol (multi-agent + human)](#5-coordination-protocol-multi-agent--human)
- [6. Stack-Agnostic Universal Rules](#6-stack-agnostic-universal-rules)
- [7. Customizacja per stack — checklist](#7-customizacja-per-stack--checklist)
- [8. Limitacje (świadome)](#8-limitacje-świadome)

---

## 0. Meta-prompt dla agenta inicjującego

**Wklej poniższy prompt do Claude Code w nowym, świeżym repozytorium.** Agent wykona całą robotę za ciebie: zada pytania, utworzy strukturę, pokaże diff i poczeka na zatwierdzenie.

```text
Cześć. Mam tu plik universals.md (przeczytaj go w całości najpierw).

Twoje zadanie: postawić w tym repozytorium architekturę agentów Claude Code
opisaną w universals.md. Pracuj według tej procedury:

1. ZADAJ MI 5 PYTAŃ (przez AskUserQuestion, nie przez czat):
   a) Jaki jest stack frontend? (None / React-Next / Vue-Nuxt / SvelteKit /
      inny webowy / mobile / inne)
   b) Jaki jest stack backend? (None / Node-Express / Python / Go / Rust /
      Django/Rails / inne)
   c) Czy spodziewasz się równoległej pracy wielu agentów lub innych ludzi
      w tym repo? (Tak — pełny coord protokół / Tylko ja solo / Solo wiele
      agentów Claude / Mix)
   d) Czy chcesz hooki git (4 dostępne): pre-commit typecheck, pre-push security,
      post-commit auto-update, commit-msg Conventional Commits enforcement.
      Wszystkie 4 / tylko post-commit / żadnych / inny mix?
   e) Czy ten projekt ma JUŻ plik o roli "agent navigation + coding rules"
      (np. `AGENTS.md`, `CONTRIBUTING.md` z sekcjami dla AI, własny
      `.cursor-rules`)? Jeśli tak — `CLAUDE.md` zostanie zrobiony jako
      thin shim który `@`-referencuje istniejący plik (bez duplikowania
      treści). Jeśli nie — `CLAUDE.md` jest canonical entry point per
      sekcja 3.1.

   Sprawdź też **PRZED zadaniem pytań**: `cat .gitignore | grep -F .claude`
   — jeśli `.claude/` jest wholesale ignored, dorzuć do swojej procedury
   krok "naprawić .gitignore" (sekcja 2 quickstart krok 5) zanim spróbujesz
   `git add .claude`.

2. NA PODSTAWIE ODPOWIEDZI — utwórz strukturę plików zgodnie z sekcją 3
   universals.md. Skopiuj treści z fenced code blocks 1:1, z modyfikacjami:
   - W CLAUDE.md (sekcja 3.1): wstaw nazwę projektu (z `git config` lub
     basename `pwd`), priorytety zadań i listę path-specific rules wg stacku.
     **Jeśli odpowiedź na pytanie (e) była "tak, mam już AGENTS.md/podobny"** —
     zamiast pełnego CLAUDE.md zrób thin shim:

     ```markdown
     # CLAUDE.md
     Auto-load list. Canonical project knowledge: @AGENTS.md.
     - @AGENTS.md
     - @.claude/rules/general.md
     - @.claude/rules/<stack>.md
     - @.claude/architecture.md
     - @.claude/ignorefiles.md
     ```

     Nie duplikuj treści AGENTS.md w CLAUDE.md — tylko `@`-referencja.
   - W frontend.md/backend.md (sekcje 3.4/3.5): jeśli stack jest znany,
     odkomentuj/uzupełnij relevantne sekcje. Jeśli stack = None — pomiń ten
     plik całkowicie i usuń linkowanie z CLAUDE.md.
   - Jeśli stack ma proto-first IDL (gRPC/Connect/Twirp) — dodaj
     `.claude/rules/rpc.md` z sekcji 3.5.1.
   - **`.gitignore` check:** jeśli krok "Sprawdź też PRZED zadaniem pytań"
     wykrył `.claude/` w gitignore — zaaplikuj fix z sekcji 2 quickstart
     krok 5 PRZED `git add`, inaczej `git add .claude/` zafailuje cicho.

3. UTWÓRZ HOOKI zgodnie z sekcją 4 universals.md. W pre-commit odkomentuj
   wariant odpowiedni dla stacku (Wariant A-E dla single-stack, Wariant F
   dla hybrid monorepo). Daj `chmod +x .githooks/*`. Jeśli odpowiedź (d)
   wymagała commit-msg — dorzuć też `.githooks/commit-msg` z sekcji 4.4.

4. URUCHOM `git config core.hooksPath .githooks` (lokalna konfiguracja repo).

5. POKAŻ MI DIFF (`git status` + `git diff --stat`) i POCZEKAJ NA AKCEPTACJĘ.
   NIE COMMITUJ samodzielnie.

6. Po akceptacji — zaproponuj pierwszy commit:
   `chore: bootstrap claude-code agent architecture (from universals.md)`

7. Test: zrób `git commit --allow-empty -m "test: hook smoke"` i sprawdź,
   czy timestamp w `.claude/architecture.md` się zaktualizował. Jeśli nie —
   zdiagnozuj (najczęściej `core.hooksPath` lub `chmod +x`).

WAŻNE:
- Nie wymyślaj plików spoza universals.md.
- Nie dodawaj custom logiki "od siebie" do hooków — tylko skopiuj template
  i odkomentuj relevantne linijki.
- Nie commituj bez mojej akceptacji.
- Jeśli universals.md jest niejasne — zapytaj zamiast zgadywać.
```

> **Tip:** Jeśli używasz Claude Code wewnątrz IDE z otwartym repo i chcesz totalnego automatu — możesz zacząć od `/clear`, otworzyć `universals.md`, i wkleić powyższy prompt. Agent przejdzie przez kroki 1–7 sekwencyjnie.

---

## 1. Co to jest i dlaczego

Ta architektura rozwiązuje 5 problemów, które pojawiają się gdy Claude Code (lub kilku Claude'ów równolegle) pracuje na nietrywialnym repo dłużej niż jedną sesję:

1. **Drift kontekstu** — agent zapomina o decyzjach z poprzedniej sesji. Rozwiązanie: `CLAUDE.md` jako index + `.claude/rules/` jako trwałe reguły, które agent czyta na starcie.
2. **Kolizje wieloagent** — dwóch Claude'ów równolegle nadpisuje te same pliki na osobnych branchach. Rozwiązanie: `.claude/active-work.md` jako single-source-of-truth "kto pracuje nad czym".
3. **Drift architektury** — nowe pliki/routes/moduły powstają, a mapa projektu pozostaje w głowie. Rozwiązanie: `.claude/architecture.md` aktualizowany manualnie przy większych zmianach + post-commit hook bumpuje timestamp jako sygnał świeżości.
4. **Dead code rozpoznawany w kółko** — agent regularnie czyta i analizuje pliki, które już dawno są martwe. Rozwiązanie: `.claude/ignorefiles.md` jako manifest dead code.
5. **Hardcoded data, placeholdery, niedopowiedzenia** — agent wstawia mocki "tymczasowo" i one zostają. Rozwiązanie: explicit zakazy w `general.md` + status w `status.md` (broken features lista).

**Co to NIE jest:** to nie jest framework. Nie ma runtime'u. To zestaw konwencji + plików tekstowych + 3 git hooków. Wszystko jest plain markdown / shell. Działa cross-platform (macOS/Linux). Edytowalne ręcznie w każdej chwili.

---

## 2. Quickstart (5 minut, człowiek)

Jeśli wolisz zrobić to ręcznie zamiast przez agenta:

1. **Utwórz strukturę:**
   ```bash
   mkdir -p .claude/rules .githooks
   ```

2. **Skopiuj 10 plików** z [sekcji 3](#3-templates-plików) — po jednym `Write` na każdy:
   - `CLAUDE.md` (root)
   - `.claude/active-work.md`
   - `.claude/rules/general.md`
   - `.claude/rules/frontend.md` *(opcjonalnie)*
   - `.claude/rules/backend.md` *(opcjonalnie)*
   - `.claude/rules/security.md`
   - `.claude/rules/status.md`
   - `.claude/settings.json`
   - `.claude/architecture.md`
   - `.claude/ignorefiles.md`

3. **Skopiuj 3 hooki** z [sekcji 4](#4-git-hooks):
   - `.githooks/pre-commit`
   - `.githooks/pre-push`
   - `.githooks/post-commit`

4. **Zedytuj `<TODO>`** w `CLAUDE.md`, `frontend.md`, `backend.md`, `settings.json` (zastąp placeholdery prawdziwymi wartościami dla swojego projektu).

5. **Sprawdź `.gitignore` przed `git add`.** Częsty default (Claude Code init czasem to zakłada) to `.claude/` jako wholesale ignore — wtedy `git add .claude/` nie zadziała ("paths are ignored by .gitignore"). Negacja `!.claude/rules/` po `.claude/` **nie działa**, bo gitignore short-circuituje na excluded parent dir. Fix:

   ```diff
   -.claude/
   +.claude/settings.json
   +.claude/settings.local.json
   +.claude/state/
   +.claude/cache/
   +.claude/projects/
   ```

   To zostawia tracked: `.claude/rules/`, `.claude/architecture.md`, `.claude/ignorefiles.md` (shared agent rules) — a ignored: per-user/per-machine (settings z absolutnymi ścieżkami, state, cache, project history).

6. **Aktywuj hooki:**
   ```bash
   chmod +x .githooks/pre-commit .githooks/pre-push .githooks/post-commit
   git config core.hooksPath .githooks
   ```

7. **Pierwszy commit:**
   ```bash
   git add .claude CLAUDE.md .githooks .gitignore
   git commit -m "chore: bootstrap claude-code agent architecture"
   ```

8. **Test hooka:**
   ```bash
   git commit --allow-empty -m "test: post-commit hook smoke"
   grep "Last Updated" .claude/architecture.md
   # → powinno pokazać aktualny timestamp
   ```

**Done.** Od teraz Claude Code w tym repo czyta `CLAUDE.md` automatycznie, a ty masz konwencję dla siebie i ewentualnych innych agentów/ludzi.

---

## 3. Templates plików

> **Konwencja:** wszystkie poniższe bloki są gotowe 1:1 do skopiowania, **z wyjątkiem placeholderów** w formie `<TODO: opis>`. Te zastępujesz wartościami właściwymi dla projektu.

### 3.1 `CLAUDE.md`

Ścieżka: `<repo-root>/CLAUDE.md`

```markdown
# CLAUDE.md — Index Reguł (<TODO: nazwa projektu>)

Wszystkie szczegółowe reguły są w folderze `.claude/`. Ten plik to tylko index — agent zaczyna od niego.

## 📚 Pliki do czytania jako pierwsze

1. **[.claude/active-work.md](.claude/active-work.md)** 🔴 — KTO PRACUJE TERAZ
   - Czytaj na starcie sesji — jeśli inny agent/człowiek zadeklarował overlapping scope, zapytaj właściciela zamiast działać.
   - Twój wpis dopisz PRZED pierwszym `Edit`/`Write` (procedura w `.claude/rules/general.md`).
2. **[.claude/architecture.md](.claude/architecture.md)** ⭐ — Mapa projektu (struktura, moduły, data flow).
3. **[.claude/ignorefiles.md](.claude/ignorefiles.md)** — Dead code manifest (czego NIE czytać).

## 📋 Szczegółowe reguły (path-specific)

1. [.claude/rules/general.md](.claude/rules/general.md) — Zakazy, Commity, Komunikacja, Coordination
<!-- TODO: odkomentuj/usuń w zależności od stacku -->
2. [.claude/rules/frontend.md](.claude/rules/frontend.md) — Path: `<TODO: frontend/**>`
3. [.claude/rules/backend.md](.claude/rules/backend.md) — Path: `<TODO: backend/**>`
4. [.claude/rules/security.md](.claude/rules/security.md) — Stan zabezpieczeń, znane ryzyka
5. [.claude/rules/status.md](.claude/rules/status.md) — Broken features, Priorytety

## 🔄 Hooki git

- `.githooks/pre-commit` — typecheck/lint przed commitem
- `.githooks/pre-push` — security scan przed pushem
- `.githooks/post-commit` — auto-update timestamp w `.claude/architecture.md` i `.claude/ignorefiles.md`

Aktywacja jednorazowa po klonie: `git config core.hooksPath .githooks && chmod +x .githooks/*`

## Zasada pracy

1. Sprawdź `.claude/active-work.md` — czy ktoś już nie pracuje w twoim obszarze. Jeśli kolizja → zapytaj właściciela.
2. Załaduj `.claude/architecture.md`.
3. Czytaj `general.md` + path-specific rules.
4. Czytaj `.claude/ignorefiles.md` — żeby nie analizować dead code.
5. PRZED pierwszym `Edit`/`Write` → dopisz wpis do `## Active` w `active-work.md`.
6. Przy dużych zadaniach używaj `/clear` i zapisuj stan do plików.
7. Na zakończenie sesji (przy merge do mastera) → usuń własny wpis z `active-work.md`.

## Priorytety projektu

<!-- TODO: 3-5 punktów co jest najważniejsze TERAZ -->
1. <TODO: priorytet 1>
2. <TODO: priorytet 2>
3. <TODO: priorytet 3>
```

---

### 3.2 `.claude/active-work.md`

Ścieżka: `<repo-root>/.claude/active-work.md`

```markdown
# Active Work — koordynacja między agentami

**Cel:** kiedy właściciel odpala dwóch (lub więcej) agentów równolegle (np. jednego w foreground, drugiego w tle) — albo kiedy człowiek pracuje obok agenta — każdy widzi co robi drugi i nie wchodzi w te same pliki/obszary.

## Konwencja

**Na starcie sesji** — KAŻDY agent (foreground i background) ORAZ KAŻDY człowiek dopisuje wpis do sekcji `## Active` PRZED pierwszym `Edit`/`Write`. Wpis robi w oddzielnym pierwszym commicie sesji (lub tuż przed pierwszym właściwym commitem, jeśli sesja jest krótka).

**Przed dopisaniem** — czytasz pełną sekcję `## Active`. Jeśli ktoś inny zadeklarował overlapping scope → sygnalizujesz to właścicielowi i pytasz czy kontynuować mimo to / poczekać / zmienić scope.

**Na zakończenie sesji** — usuwasz swój wpis z `## Active` w tym samym commicie co finalny merge do mastera (lub w osobnym commicie tuż po). Jeśli przerywasz pracę bez merge, wpis zostaje — właściciel ręcznie purguje stale wpisy.

## Format wpisu

```text
- **[branch]** start: `YYYY-MM-DD HH:MM` — autor: `<git user.name lub "claude-<task>">`
  - scope: `<paths/areas>`
  - goal: `<one line>`
  - touches: `<key invariants this might affect>` (opcjonalnie)
```

## Przykład

```text
- **[fix/auth-callback]** start: `2026-05-07 14:00` — autor: `claude-foreground`
  - scope: `frontend/app/auth/`, `frontend/lib/auth.ts`
  - goal: naprawa OAuth callback redirect po login
  - touches: cookies session shape (jeśli zmieniam — rerun e2e auth specs)
```

## Active

<!-- Pusto gdy nikt nie pracuje. Agenci/ludzie dopisują tutaj. -->

## Notatka dla agenta-czytelnika

Jeśli widzisz wpis w `## Active` którego scope pokrywa twój zakres:

1. **Nie ruszaj tych plików** — drugi agent może nadpisać twoje zmiany przy mergu.
2. **Powiedz właścicielowi** — opisz konkretnie co miałeś robić i z czym się pokrywa, żeby zdecydował (czekać / zmienić scope / kontynuować mimo).
3. **Jeśli wpis ma >24h** — prawdopodobnie stale (agent crashed lub zapomniał posprzątać). Zapytaj właściciela o weryfikację `git log <branch>` zanim usuniesz cudzy wpis.

## FAQ

**Q: co jeśli dwóch agentów dopisuje równocześnie?**
A: trivial git merge conflict — konkatenacja list. Nie ma race.

**Q: co jeśli mój scope obejmuje cały repo (np. dependency upgrade)?**
A: deklaruj `scope: <all>` + opisz w goal — wtedy inni agenci wiedzą żeby zaczekać.

**Q: czy ten plik jest tracked w git?**
A: tak. Wpisy są w PRach (review trail) zamiast w stanie ulotnym (np. lokalnym pliku który ginie po crashu). Tradeoff: każde otwarcie/zamknięcie sesji = jeden mały commit.
```

---

### 3.3 `.claude/rules/general.md`

Ścieżka: `<repo-root>/.claude/rules/general.md`

**Ten plik jest uniwersalny — kopiuj 1:1 bez modyfikacji.**

```markdown
# General Rules & Core Prohibitions

## ZAKAZ ABSOLUTNY

- **NIGDY** nie wstawiaj hardcoded danych w komponentach UI (przykładowe statystyki, fake komentarze, „71%"). Renderuj `<EmptyState />` lub odpowiednik jeśli brak danych.
- **NIGDY** nie zostawiaj placeholderów typu "X KADENCJA", "AI · Placeholder", "W przygotowaniu" jako zastępstwa dla kodu. Jeśli funkcja nie jest gotowa — `EmptyState` z wyjaśnieniem stanu, nie tekst-zaślepka.
- **NIGDY** nie oznaczaj funkcji jako ZAKOŃCZONE w roadmapie/statusie, jeśli są to mocki lub dead code. „Done" = realnie działa na realnych danych.
- **NIGDY** nie dodawaj feature'ów AI/LLM po stronie klienta bez explicit zgody właściciela. AI client-side ma poważne implikacje (cost, latency, prompt injection) — wymaga decyzji architektonicznej.

## Komunikacja i Praca

- Format commitów: **Conventional Commits** (`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`, `style:`).
- Odpowiedzi: lakoniczne, inżynieryjne, bez "lania wody". Diff > narracja.
- Rozbijaj długie zadania na etapy, zapisuj stan do plików (np. progress note w `status.md`) i rób `/clear` między etapami.
- Język UI/komentarzy/commitów: <TODO: PL/EN — zdecyduj raz i trzymaj się>.

## Reguła oddzielnych gałęzi

Każda rozmowa / każdy agent **MUSI pracować na własnej gałęzi feature**. Nie dziel jednej gałęzi z innym agentem ani z drugą rozmową — to powoduje wymieszanie commitów i blokuje selektywny merge.

**Procedura na początku każdej sesji:**

1. Sprawdź `git branch --show-current`. Jeśli jesteś na `master`/`main` lub na cudzej gałęzi feature → **utwórz własną**: `git checkout -b feat/<topic>` lub `fix/<topic>` lub `chore/<topic>`.
2. Nazewnictwo: `feat/auth-callback`, `fix/api-validation`, `chore/cleanup-deps` — krótko opisuj zadanie.
3. Jeśli inny agent już na tej gałęzi pracuje (commity z innym Co-Authored-By), **NIE dorzucaj** swoich commitów tam — zrób własną gałąź od najnowszego mastera.
4. Po skończeniu zadania: merge do mastera (lub PR), drugi agent kontynuuje na nowej gałęzi z aktualnego mastera.

**Wyjątek:** jeśli właściciel projektu explicit prosi o pracę na konkretnej gałęzi (np. „dorób UI na branchu auth bo testujemy razem") — wtedy OK. Ale to musi być explicit decyzja, nie domyślne.

**Powód:** Mieszanie commitów dwóch agentów na jednej gałęzi uniemożliwia selektywny merge — albo idą razem, albo trzeba cherry-pickować z konfliktami. Osobne gałęzie = osobne PR-y = osobne review = czysta historia.

## Coordination protokół

Plik `.claude/active-work.md` jest single-source-of-truth dla "kto pracuje nad czym teraz". Każdy agent (foreground i background) oraz każdy człowiek-deweloper:

1. **Na starcie sesji** — przeczytaj sekcję `## Active` w `.claude/active-work.md`. Jeśli widzisz wpis z overlapping scope → **przerwij i zapytaj właściciela** co robić: czekać, zmienić scope, czy kontynuować mimo.
2. **Przed pierwszym `Edit`/`Write`** — dopisz własny wpis do `## Active`. Format w `.claude/active-work.md`. Commit ten plik osobno (`chore(coord): claim <branch>`) lub razem z pierwszym właściwym commitem.
3. **Na zakończenie sesji (przy merge do master)** — usuń własny wpis z `## Active` w finalnym commicie sesji.

Jeśli wpis ma >24h i nie wiesz czy autor dalej pracuje → zapytaj właściciela, nie usuwaj samodzielnie cudzych wpisów.

## Don't

- Nie dodawaj feature'ów, refactor'ów, abstrakcji ponad to, co wymaga zadanie. Bug fix nie potrzebuje cleanupów dookoła. Trzy podobne linijki są lepsze od premature abstraction.
- Nie dodawaj error handling, fallbacków ani walidacji dla scenariuszy które nie mogą się zdarzyć. Trust internal code. Waliduj tylko na granicach systemu (user input, external APIs).
- Domyślnie nie pisz komentarzy. Komentarz uzasadniony tylko gdy WHY jest non-obvious (ukryty constraint, subtelny invariant, workaround konkretnego buga). Komentarze typu "// fetch user data" są szumem.
- Nie wprowadzaj backwards-compatibility shims gdy możesz po prostu zmienić kod. Renamy `_unused` zmiennych, re-eksporty, `// removed`-komentarze — to drift.
```

---

### 3.4 `.claude/rules/frontend.md`

Ścieżka: `<repo-root>/.claude/rules/frontend.md`

**Szkielet — wypełnij sekcje pod swój stack po pierwszym dotknięciu UI.**

```markdown
# Frontend Rules

Paths: `<TODO: np. frontend/**/*, app/**/*, components/**/*>`
Stack: `<TODO: np. Next.js 16 + React 19 + Tailwind / SvelteKit / Vue Nuxt 3>`

## UI/UX (Design Rules)

<!-- TODO: wypełnij po pierwszym dotknięciu UI. Przykłady: -->
- **Komponenty główne:** używaj `<TODO: design system / component library>`.
- **Kolorystyka:** zmienne CSS (`--surface-color`, `--accent-blue`) z `<TODO: globals.css>`.
- **Empty States:** zawsze obsługuj brak wyników — explicit `<EmptyState />`, nie pusty div.
- **Filtrowanie:** każda lista MUSI mieć filtry (nie tylko search input). UX rule.
- **Loading states:** skeleton lub spinner — nigdy white screen.

## Kodowanie

<!-- TODO: dopasuj do stacku -->
- Interaktywne komponenty z stanem → `"use client"` (Next App Router) / `<script>` (Svelte) / `setup()` (Vue).
- Każda nowa strona z danymi musi mieć test e2e w `<TODO: e2e/data-integrity.spec.ts>`.
- Używaj `data-testid` na elementach list dla testów e2e.
- Język UI: <TODO: PL/EN>.

## Testy

- Unit tests: `<TODO: Jest/Vitest>` w `__tests__/` obok modułu.
- E2E: `<TODO: Playwright/Cypress>` w `e2e/`.
- Threshold pokrycia: <TODO: liczby z konfiga, np. 30% lines / 22% branches / 20% functions>.

## Anti-patterns (czerwone flagi)

- Hardcoded dane w komponencie ("71% poparcia", lista fake komentarzy) → użyj `EmptyState` lub realnych danych.
- `dangerouslySetInnerHTML` bez sanitizera → zawsze przez `sanitize-html` lub `DOMPurify`.
- `console.log` w prodzie → usuń przed pushem (pre-push hook to wyłapuje).
```

---

### 3.5 `.claude/rules/backend.md`

Ścieżka: `<repo-root>/.claude/rules/backend.md`

**Szkielet — wypełnij sekcje pod swój stack po pierwszym dotknięciu API/DB.**

```markdown
# Backend Rules

Paths: `<TODO: np. backend/**/*, server/**/*, api/**/*>`
Stack: `<TODO: np. Python 3.12 + FastAPI + SQLAlchemy / Node + Express + Prisma / Go + chi>`

## Walidacja danych

- Obowiązkowe użycie **<TODO: Pydantic v2 / Zod / class-validator / go-playground/validator>** do walidacji danych zewnętrznych (request body, third-party API responses) PRZED zapisem do DB.
- Schemy w `<TODO: backend/schemas/, lib/validation/>` — jedno źródło prawdy per encja.
- Nigdy nie używaj `datetime.now()` / `Date.now()` jako daty dokumentu pochodzącego z systemu zewnętrznego (parlament, API itp.) — używaj daty z payloadu.

## Obsługa błędów

- Nie zwracaj pustych list `[]` przy błędach scrapera/integracji — to ukryta awaria. Loguj ERROR z kontekstem (`url`, `status`, `payload[:200]`) lub rzucaj wyjątek.
- Fallback ID musi być hash'em (URL/content), nie liczbą porządkową — żeby był deterministyczny przy retry.
- Retry tylko na transient errors (5xx, timeouts, network). Nie retry na 4xx.

## Bezpieczeństwo zewnętrznych integracji

- Tokeny API: zawsze przez zmienne środowiskowe, nigdy hardcoded keys.
- HTTP client: timeouty domyślne (np. 30s connect, 60s read) — bez nich proces wisi w nieskończoność.
- SSRF: jeśli przyjmujesz URL od użytkownika (np. image-proxy) → whitelist domen + blokada prywatnych IP + wymóg `https`.

## ETL / Scrapery (jeśli dotyczy)

<!-- TODO: zostaw lub usuń tę sekcję jeśli nie masz ETL -->
- Każdy scraper ma własny test jednostkowy z fixture HTML/JSON.
- XPath/CSS selector ulepszenia wymagają testu z surowym HTML jako wejściem.
- Cache layer (RawCache lub odpowiednik) dla idempotentności i offline-rerun.

## Testy

- Unit tests: `<TODO: pytest / Jest / go test>` w `tests/` obok modułu.
- Integration tests (DB-bound): osobny marker (`pytest -m db`) — nie odpalają się domyślnie.
- Threshold pokrycia: <TODO: liczby z konfiga>.
```

---

### 3.5.1 `.claude/rules/rpc.md` (opcjonalny — projekty z proto-first IDL)

**Wyciąg dla projektów gdzie `proto/*.proto` (gRPC, Connect, Twirp) jest single source of truth.** Pomiń całkowicie jeśli nie używasz schema-first IDL.

```markdown
# RPC / Proto Rules

Paths: `<TODO: np. proto/**/*.proto>`
Stack: `<TODO: np. gRPC + tonic (Rust) + grpcio (Python) / Connect + connect-go>`

## Proto-first workflow

Każda nowa metoda RPC, **niezależnie od języka**:

1. Edytuj `<TODO: proto/foo/v1/<service>.proto>` — to jest single source of truth.
2. Regeneruj stuby: `<TODO: python build_proto.py>` dla serwera, `<TODO: cargo build>` dla klienta (tonic regeneruje przy buildzie).
3. Zaimplementuj servicer w `<TODO: backend/ipc/<service>.py>`.
4. Wepnij w state machine / lifecycle FSM jeśli RPC wpływa na stan połączenia (Hello, heartbeat, shutdown).

## Wire-format

- **Zmiana wire-formatu** (rename pola, zmiana typu, usunięcie pola) wymaga explicit zgody właściciela. Backwards-compat wymaga wersjonowania pakietu (`/v1/` → `/v2/`) lub flagi feature-gate.
- **Dodawanie pola** (`optional` w proto3, kolejny tag) jest backwards-compatible — OK bez review.
- Generated stubs (`*_pb2.py`, `*_pb2_grpc.py`, `*.pb.rs`) trafiają do `.claude/ignorefiles.md` — agent ich nie czyta.

## Auth & per-frame validation

Jeśli transport używa per-frame auth (peer-cert fingerprint + nonce + monotonic seq):

- Walidacja na **każdej** ramce, nie tylko Hello — defense in depth pod TLS-em.
- Mismatch → odrzuć ramę i zerwij stream (nie loguj wartości tokena, tylko fakt mismatch'a).
- Touch tego kodu wymaga update'u `<TODO: docs/THREAT_MODEL.md>` i ADR-a.

## Timeouty

Każdy gRPC call ma explicit `timeout=` (Python) lub `tonic::Request::set_timeout()` (Rust). Bez tego process wisi w nieskończoność na zerwanym streamie.
```

---

### 3.6 `.claude/rules/security.md`

Ścieżka: `<repo-root>/.claude/rules/security.md`

**Szkielet — wypełnij po pierwszym audycie bezpieczeństwa lub po incydencie.**

```markdown
# Security Rules

## Zakończone (sprawdzone audyty)

<!-- TODO: dopisuj tu po każdym audycie/fixie. Wzór: -->
<!-- - **SSRF**: `/api/image-proxy` ma whitelist domen + blokada prywatnych IP + wymóg https. -->
<!-- - **XSS**: wszystkie user-generated treści przez `sanitize-html`. Test coverage w `lib/__tests__/sanitize.test.ts`. -->
<!-- - **Rate-limit**: per-IP token bucket dla `/api/*` (60/min default). -->

## Otwarte ryzyka

<!-- TODO: lista znanych ryzyk z severity (LOW/MED/HIGH) i statusem -->
<!-- - **`.env` w repo (HIGH)**: plik główny `.env` w root zawiera kredencjale DB. Status: zakomitowany w historii. Rekomendacja: rotacja sekretów + `git filter-repo`. -->

## Standardy domyślne

- Tokeny API: zawsze przez `process.env` / `os.environ`. Nigdy hardcoded keys w kodzie.
- Sekrety w repo: `.env` w `.gitignore` od dnia 1. Jeśli wpadł — natychmiast rotuj + filter-repo.
- Walidacja inputów: każdy endpoint `/api/*` dostaje schemę walidacyjną (zod/pydantic).
- Rate-limit: każdy publiczny endpoint ma limit per-IP (default 60/min). Tylko per-instance — distributed limit wymaga Redis/KV.
- HTTPS: redirect HTTP→HTTPS na produkcji.
```

---

### 3.7 `.claude/rules/status.md`

Ścieżka: `<repo-root>/.claude/rules/status.md`

**Skeleton — wypełniasz w trakcie pracy.**

```markdown
# Project Status & Known Issues

## Złamane funkcje (do naprawy)

<!-- TODO: tabela funkcji które są w UI ale nie działają / są mockami -->
| Funkcja | Stan | Co trzeba |
|---------|------|-----------|
| <TODO: nazwa> | <TODO: EmptyState / Mock / Broken> | <TODO: co brakuje> |

## Priorytety (kolejność)

<!-- TODO: lista 3-5 priorytetów -->
1. <TODO: priorytet 1>
2. <TODO: priorytet 2>
3. <TODO: priorytet 3>

## Wycofane / Out of Scope

<!-- TODO: rzeczy świadomie wycięte z scope. Wzór: -->
<!-- - **AI client-side** — decyzja właściciela 2026-04-29. Wszystkie AI/LLM features po stronie frontendu wycofane. -->

## Posprzątane (historyczne)

<!-- TODO: lista zrealizowanych większych refaktorów / bugfixów. Pozwala nie wracać do tematu. -->
<!-- - <data> — <co naprawiono> (`<branch>`). -->
```

---

### 3.8 `.claude/settings.json`

Ścieżka: `<repo-root>/.claude/settings.json`

**Minimalny template. Rozbudowuj o domeny WebFetch i komendy Bash w miarę potrzeb (Claude Code zapyta o permission gdy zabraknie).**

```json
{
  "permissions": {
    "allow": [
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(git branch:*)",
      "Bash(git show:*)",
      "Bash(npm test:*)",
      "Bash(pytest:*)",
      "WebFetch(domain:github.com)",
      "WebFetch(domain:docs.anthropic.com)"
    ],
    "additionalDirectories": []
  }
}
```

> **Tip:** nie dodawaj `Bash(*)` ani `WebFetch(*)`. Każda zezwolona komenda powinna być explicit, żeby agent nie dostał za dużo. Claude Code zapyta o permission za każdym razem gdy spróbuje czegoś niezatwierdzonego — to feature, nie bug.

---

### 3.9 `.claude/architecture.md`

Ścieżka: `<repo-root>/.claude/architecture.md`

**Skeleton — wypełniasz po pierwszej iteracji repo. Hook `post-commit` aktualizuje tylko `Last Updated:` timestamp; treść tej mapy jest manualna.**

```markdown
# Architecture

**Last Updated:** 1970-01-01 00:00:00

> Mapa projektu dla agenta. Aktualizuj po większych zmianach (nowe routes, nowe moduły, refaktor architektury). Hook post-commit bumpuje timestamp jako sygnał świeżości — ale treść jest manualna.

## 📐 Stack & Core

<!-- TODO: 3-5 punktów co używamy -->
- Frontend: <TODO>
- Backend: <TODO>
- DB: <TODO>
- Hosting: <TODO>

## 📂 Struktura projektu

```text
<TODO: drzewo katalogów top-level + 1-zdaniowy opis każdego>
.
├── frontend/        — <TODO>
├── backend/         — <TODO>
├── db/              — <TODO>
├── .claude/         — reguły dla agenta
└── .githooks/       — git hooks
```

## 🔀 Data flow

<!-- TODO: jak dane wpadają i wypadają z systemu. Można ASCII diagram. -->

## 🌐 Routes / Endpoints

<!-- TODO: lista głównych routes/endpointów -->

## 📦 Kluczowe moduły

<!-- TODO: 5-10 najważniejszych plików/modułów które agent powinien znać -->
```

---

### 3.10 `.claude/ignorefiles.md`

Ścieżka: `<repo-root>/.claude/ignorefiles.md`

**Skeleton — wypełniasz w miarę odkrywania martwego kodu.**

```markdown
# Dead Code Manifest

**Last Updated:** 1970-01-01 00:00:00

> Pliki/moduły które są w repo ale są martwe lub deprecated. Agent NIE powinien ich czytać ani analizować — chyba że zadanie to explicit cleanup tych plików.

## ✅ Already Deleted (nie istnieją, ale były wspominane w starszych dokumentach)

<!-- TODO: lista plików które kiedyś były i mogą być wymieniane w PRach/notach -->

## ⚠️ Partially Broken / Deprecated (nadal w repo)

<!-- TODO: tabela: ścieżka | powód że dead | data oznaczenia -->
| Plik | Powód | Od kiedy |
|------|-------|----------|
| <TODO: backend/legacy/old_scraper.py> | <TODO: zastąpiony przez new_scraper.py> | <TODO: 2026-01-15> |

## 🔒 Security / Placeholder UI

<!-- TODO: rzeczy widoczne w UI ale niedziałające jako prawdziwe placeholdery -->
```

---

## 4. Git Hooks

Trzy pliki w `.githooks/`. Aktywacja: `git config core.hooksPath .githooks` + `chmod +x .githooks/*`.

### 4.1 `.githooks/pre-commit`

**Stack-agnostic szkielet z 3 wariantami typecheck/lint. Odkomentuj swój.**

```bash
#!/bin/sh
# Pre-commit hook: typecheck/lint przed commitem.
# Stack-agnostic szkielet — odkomentuj linijkę odpowiednią dla swojego stacku.

set -e

# Use nvm/pyenv jeśli są — dla poprawnej wersji Node/Python.
# Nie source'uj pełnych zshrc/bashrc (psują cd/zoxide w hookach).
export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin"
[ -s "$HOME/.nvm/nvm.sh" ] && . "$HOME/.nvm/nvm.sh" --no-use 2>/dev/null || true

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "🔍 Pre-commit: typecheck..."

# === ODKOMENTUJ JEDEN BLOK PONIŻEJ ===

# --- Wariant A: Node + TypeScript (Next.js, Vite, etc.) ---
# cd "$REPO_ROOT/frontend" || cd "$REPO_ROOT"
# npm run typecheck || { echo "❌ TypeScript: błędy. Napraw przed commitem."; exit 1; }

# --- Wariant B: Python + mypy ---
# .venv/bin/mypy backend/ || { echo "❌ mypy: błędy typów."; exit 1; }

# --- Wariant C: Go ---
# go vet ./... || { echo "❌ go vet: błędy."; exit 1; }

# --- Wariant D: Rust ---
# cargo check --quiet || { echo "❌ cargo check: błędy."; exit 1; }

# --- Wariant E: Brak typecheck (dynamic, brak stricte) ---
# echo "ℹ️  Pre-commit: brak typecheck dla tego stacku — pomijam."

# --- Wariant F: Hybrid (monorepo z różnymi stackami w podkatalogach) ---
# Per-file-type guards: typecheck odpala się tylko jeśli dotknięte pliki są
# w danym stacku. Bez tego docs-only commit czeka 30-60 s na mypy + cargo check.
#
# CHANGED="$(git diff --cached --name-only --diff-filter=ACM)"
# if echo "$CHANGED" | grep -qE '^host/.*\.py$'; then
#     ( cd "$REPO_ROOT/host" && mypy --strict src/ ) || { echo "❌ mypy"; exit 1; }
# fi
# if echo "$CHANGED" | grep -qE '^guest/.*\.rs$'; then
#     ( cd "$REPO_ROOT/guest" && cargo check --workspace --quiet ) || { echo "❌ cargo (guest)"; exit 1; }
# fi
# if echo "$CHANGED" | grep -qE '^gui/.*\.rs$'; then
#     ( cd "$REPO_ROOT/gui" && cargo check --quiet ) || { echo "❌ cargo (gui)"; exit 1; }
# fi
#
# Skopiuj sekcje które dotyczą twoich katalogów. Każdy `if` jest niezależny —
# możesz mieć Python+Rust+Go w trzech sub-treach, każdy zgardowany własnym
# regexem ścieżki.

echo "✅ Pre-commit OK."
exit 0
```

---

### 4.2 `.githooks/pre-push`

**Uniwersalny security scan (działa cross-stack — używa tylko `grep`).**

```bash
#!/bin/bash
# Pre-Push Hook: Security Review.
# Stack-agnostic — używa tylko grep. Nie wymaga node/python/go w PATH.

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "🔍 Pre-Push: Security Review..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Default branch detection (master/main)
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")

CHANGED_FILES=$(git diff --name-only HEAD "origin/$DEFAULT_BRANCH" 2>/dev/null || git diff --name-only HEAD)

if [ -z "$CHANGED_FILES" ]; then
    echo "ℹ️  Brak zmian do sprawdzenia."
    exit 0
fi

# === 1. Hardcoded secrets ===
echo "🔐 Sprawdzam hardcoded secrets..."
SECRET_PATTERNS='password\s*=\s*["'"'"'][^"'"'"']\{4,\}|api[_-]?key\s*=\s*["'"'"'][^"'"'"']\{8,\}|secret\s*=\s*["'"'"'][^"'"'"']\{8,\}'

# Filter: tylko zmienione pliki, exclude tests/mocks/.env
FOUND=$(echo "$CHANGED_FILES" | xargs -I{} grep -l -E "$SECRET_PATTERNS" {} 2>/dev/null | \
    grep -v -E "(node_modules|\.env|test|spec|mock|fixture)" || true)

if [ -n "$FOUND" ]; then
    echo "⚠️  UWAGA: potencjalne hardcoded secrets w:"
    echo "$FOUND"
    echo "     Usuń je przed pushem lub przenieś do .env"
    exit 1
fi

# === 2. console.log w prodzie (Node/TS) ===
echo "🖨️  Sprawdzam console.log..."
echo "$CHANGED_FILES" | grep -E '\.(ts|tsx|js|jsx)$' | \
    xargs -I{} grep -H -n -E 'console\.(log|debug|warn)' {} 2>/dev/null | \
    grep -v -E "(test|\.spec|mock|fixture)" | head -5 || true

# === 3. print() w hot path (Python) ===
# Tylko ostrzeżenie, nie blokujące — print() bywa legit w skryptach.
echo "🐍 Sprawdzam print() w Python..."
echo "$CHANGED_FILES" | grep -E '\.py$' | \
    xargs -I{} grep -H -n -E '^\s*print\(' {} 2>/dev/null | \
    grep -v -E "(test_|conftest|scripts/)" | head -5 || true

# === 4. TODO/FIXME w nowo dodanych liniach ===
echo "📝 Sprawdzam TODO/FIXME w diffie..."
git diff HEAD "origin/$DEFAULT_BRANCH" 2>/dev/null | \
    grep -E '^\+.*TODO|^\+.*FIXME' | head -10 || true

echo ""
echo "✅ Pre-Push checks zakończone."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit 0
```

---

### 4.3 `.githooks/post-commit`

**Auto-update timestamp w `.claude/architecture.md` i `.claude/ignorefiles.md`. Wykrywa OS dla poprawnego `sed -i`.**

```bash
#!/bin/bash
# Post-commit hook: auto-update timestamps w .claude/*.md.
# Cross-platform: BSD sed (macOS) vs GNU sed (Linux).

set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
ARCH_FILE=".claude/architecture.md"
IGNORE_FILE=".claude/ignorefiles.md"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}→ post-commit hook${NC}"

cd "$PROJECT_ROOT"

# Skip if .claude/ nie istnieje (pierwsze dni repo, hook setup)
if [ ! -f "$ARCH_FILE" ]; then
    echo -e "${YELLOW}⚠ $ARCH_FILE not found — pomijam.${NC}"
    exit 0
fi

# Cross-platform sed -i wrapper
sed_inplace() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

# === 1. Detect NEW FILES (info dla usera, nie auto-edit) ===
NEW_FILES=$(git diff-tree --no-commit-id --name-only -r HEAD --diff-filter=A 2>/dev/null || true)
if [ -n "$NEW_FILES" ]; then
    NEW_COUNT=$(echo "$NEW_FILES" | wc -l | tr -d ' ')
    echo -e "${GREEN}  + $NEW_COUNT nowych plików w tym commicie${NC}"
fi

# === 2. Detect DELETED FILES ===
DELETED=$(git diff-tree --no-commit-id --diff-filter=D --name-only -r HEAD 2>/dev/null || true)
if [ -n "$DELETED" ]; then
    DEL_COUNT=$(echo "$DELETED" | wc -l | tr -d ' ')
    echo -e "${YELLOW}  - $DEL_COUNT usuniętych plików${NC}"
fi

# === 3. Detect DEPRECATED markers w diffie ===
DEPRECATED=$(git diff HEAD~1 HEAD 2>/dev/null | grep -E "^\+.*# DEPRECATED|^\+.*# DEAD|^\+.*# TODO.*remove" | head -5 || true)
if [ -n "$DEPRECATED" ]; then
    echo -e "${BLUE}  ⓘ Wykryte DEPRECATED/DEAD markery — rozważ wpis do ignorefiles.md${NC}"
fi

# === 4. Update timestamp w obu plikach ===
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
sed_inplace "s/\*\*Last Updated:\*\* .*/\*\*Last Updated:\*\* $TIMESTAMP/" "$ARCH_FILE" 2>/dev/null || true

if [ -f "$IGNORE_FILE" ]; then
    sed_inplace "s/\*\*Last Updated:\*\* .*/\*\*Last Updated:\*\* $TIMESTAMP/" "$IGNORE_FILE" 2>/dev/null || true
fi

echo -e "${GREEN}✓ Timestamps zaktualizowane.${NC}"
exit 0
```

---

### 4.4 `.githooks/commit-msg` (opcjonalny — Conventional Commits enforcement)

**Trywialny hook (5 linii bash) blokujący literówki w typie commita.** Bez niego `general.md` mówi "Conventional Commits, bez wyjątków" ale tylko reviewer to wyłapuje.

```bash
#!/bin/sh
# commit-msg: Conventional Commits regex check.
# Akceptuje: feat, fix, chore, docs, refactor, test, style, build, ci, perf
# Opcjonalny scope w nawiasach. Reszta dowolna.

PATTERN='^(feat|fix|chore|docs|refactor|test|style|build|ci|perf)(\([^)]+\))?(!)?: .+'

if ! grep -qE "$PATTERN" "$1"; then
    echo "❌ commit message nie pasuje do Conventional Commits."
    echo "   Format: <type>(<scope>)?: <description>"
    echo "   Types: feat|fix|chore|docs|refactor|test|style|build|ci|perf"
    echo "   Przykład: fix(auth): handle null callback URL"
    exit 1
fi
exit 0
```

**Bypass:** `git commit --no-verify` (używać świadomie, np. WIP commit na własnym branchu).

**Edge case:** merge commits (`Merge branch '...'`) nie pasują do regexu. Albo dodaj `^Merge ` do alternacji, albo używaj `git merge --no-edit` które generuje predefiniowany message i pomija hook na niektórych git-versions. Najprościej: zaakceptuj że merge commit jest wyjątkiem — `git merge` używa flagi `--no-verify` automatycznie w nowszych gitach (>2.36), a w starszych — `git merge ... && git commit --no-verify --amend` jeśli hook się wpina.

---

### 4.5 Aktywacja hooków

**Po skopiowaniu plików do `.githooks/`:**

```bash
chmod +x .githooks/pre-commit .githooks/pre-push .githooks/post-commit
git config core.hooksPath .githooks
```

**Uwaga:** `core.hooksPath` jest **per-clone** (zapisuje się w `.git/config`, który nie jest w repo). Każdy nowy clone wymaga ponownego ustawienia. Sposób na auto-aktywację:

- Node: dodaj `"postinstall": "git config core.hooksPath .githooks && chmod +x .githooks/*"` do `package.json`.
- Python: dorzuć do `Makefile` target `setup` z tymi komendami i wymagaj `make setup` po klonie.
- Inne: po prostu instrukcja w README.

---

## 5. Coordination Protocol (multi-agent + human)

### Kiedy potrzebujesz tego protokołu

- Pracujesz solo, jeden Claude naraz → **NIE potrzebujesz**. Możesz uprościć: usuń `active-work.md`, zostaw tylko branch-per-agent w `general.md`.
- Pracujesz solo, ale często odpalasz dwa Claude'y równolegle (np. jeden w foreground, drugi w tle przez `run_in_background` agent) → **POTRZEBUJESZ**.
- Pracujesz z innymi ludźmi → **POTRZEBUJESZ**, plus dopisek że ludzie też się logują.
- Mix wieloagent + ludzie → **POTRZEBUJESZ pełny protokół**.

### Reguły

1. **Branch-per-agent.** Każda sesja = nowa gałąź. Nigdy nie dziel gałęzi z innym agentem (chyba że właściciel explicit prosi). Powód: mieszanie commitów blokuje selektywny merge.
2. **Ledger w `active-work.md`.** Każdy (agent + człowiek) loguje wpis przed pierwszym `Edit`/`Write`. Format w sekcji 3.2.
3. **Czytaj przed pisaniem.** Na starcie sesji czytasz `## Active`. Overlap → pytasz właściciela.
4. **Sprzątasz przy mergu.** Wpis usuwa się w finalnym commicie sesji (lub osobnym `chore(coord): release <branch>`).
5. **Ludzcy deweloperzy** używają tego samego ledgera. Autor = `git config user.name`. Format wpisu identyczny.

### Wyjątki

- **Hot fix** (production down) — pomijasz protokół, fixujesz, dopisujesz wpis post-factum z notą "hotfix bypass".
- **Tiny commit** (literówka, jednoznakowa zmiana) — możesz pominąć ledger, ale tylko jeśli scope to <5 linii w jednym pliku.

### Wariant: push-to-main ledger zamiast branch-tracked

Domyślny `active-work.md` jest **branch-tracked**: wpis żyje na feature branchu i jest niewidoczny dla równoległych agentów dopóki nie zmergeują (lub nie pushną branch'a do origin i ktoś go nie zfetchnie). Trade-off: chroni czystość mastera, ale opóźnia widoczność.

**Alternatywa** — `WORK_LOG.md` jako single-file exception od no-direct-main-push:

- Każdy agent commituje START/END entry **bezpośrednio na main** (jeden mały commit per claim, jeden per release), pushuje od razu do origin.
- Reszta pracy zostaje na feature branchu (normalny PR/merge flow).
- Race resolution: jeśli `git push origin main` jest rejected przez kogoś szybszego — `git pull --rebase` i retry. Konflikt na entry tego samego task'a → drugi agent wybiera inny task.

**Kiedy push-to-main ledger jest lepszy:**

- Wieloagent solo (ty + 2-3 Claude'y w tle) — natychmiastowa widoczność na każdym clone bez czekania na merge.
- Mały zespół (1-3 ludzi) gdzie main jest stabilny i jeden mały commit metadata nie psuje historii.

**Kiedy zostaw branch-tracked:**

- Średni/duży zespół z policy "linear main, no direct commits".
- CI walidujący każdy commit na main (pojedyncza linia w `.md` triggeruje pełen pipeline → marnotrawstwo).

W obu wariantach format wpisu może być identyczny (sekcja 3.2). Różnica jest tylko w *gdzie żyje plik* i *jak się commituje*.

---

## 6. Stack-Agnostic Universal Rules

Te reguły działają niezależnie od języka i frameworka. Są ekstraktem z OpenState `general.md` zgeneralizowanym do każdego projektu.

### Zakazy

- **Hardcoded data w UI.** Dotyczy każdego frameworka: React, Vue, Svelte, SwiftUI, mobile native — gdziekolwiek renderujesz dane, jeśli ich nie masz, użyj explicit `EmptyState` zamiast fake liczb/komentarzy.
- **Placeholder text jako kod.** "Coming soon", "TBD", "X KADENCJA" w UI to drift. Albo zaimplementuj, albo `EmptyState` z wyjaśnieniem stanu.
- **Mock oznaczony jako "done".** W roadmapie/`status.md` "✅ done" = realnie działa na realnych danych. Mock = `🚧 mock`.
- **AI/LLM client-side bez decyzji.** Wymaga explicit zgody właściciela (cost, latency, prompt injection).

### Konwencje

- **Conventional Commits.** `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`, `style:`. Bez wyjątków.
- **Lakoniczna komunikacja.** Diff > narracja. Krótkie odpowiedzi. Bez sumar po skończonym tasku ("oto co zrobiłem...") jeśli właściciel widzi diff.
- **Branch-per-feature.** Każdy task = nowa gałąź. Merge przez PR (nawet jeśli pracujesz solo — daje review trail).
- **Etapowanie.** Duże zadania → rozbij na 3-5 mniejszych, po każdym `/clear` i zapis stanu do `status.md` lub `active-work.md`.

### Anti-patterns

- **Premature abstraction.** Trzy podobne linijki są lepsze od fabryki. Czekaj do czwartej.
- **Fallbacks dla niemożliwych scenariuszy.** Internal code można trust. Waliduj tylko na granicach.
- **Komentarze "co robi kod".** Jeśli kod się tłumaczy nazwami zmiennych — komentarz to szum. Komentuj tylko WHY, gdy jest non-obvious.
- **Backwards-compat shims.** `_unused` rename, `// removed` komentarze, re-eksporty — usuń całkiem zamiast zostawiać driftu.

---

## 7. Customizacja per stack — checklist

Po setup'ie z sekcji 2, zrób te kroki w miarę potrzeb:

- [ ] **Pre-commit:** odkomentuj wariant typecheck dla swojego stacku w `.githooks/pre-commit` (sekcja 4.1).
- [ ] **`frontend.md`:** wypełnij sekcje UI/UX i Kodowanie po pierwszym dotknięciu UI.
- [ ] **`backend.md`:** wypełnij sekcje Walidacja i Obsługa błędów po pierwszym napisanym endpoincie.
- [ ] **`settings.json`:** dodaj domeny WebFetch po pierwszym `WebFetch` zablokowaniu przez Claude Code.
- [ ] **`security.md`:** wypełnij po pierwszym audycie lub po pierwszym security incidencie.
- [ ] **`status.md`:** wypełnij sekcję Priorytety na starcie projektu, resztę dopisuj w trakcie.
- [ ] **`architecture.md`:** wypełnij Stack & Core po setupie i dorzuć drzewko po pierwszym tygodniu.
- [ ] **`ignorefiles.md`:** wypełnij dopiero gdy realnie pojawi się dead code (nie pre-emptive).
- [ ] **Auto-aktywacja hooków po klonie:** dodaj `postinstall` (npm) lub `make setup` jeśli stack na to pozwala.

---

## 8. Limitacje (świadome)

Architektura jest celowo prosta. Świadome ograniczenia:

1. **Manualna, nie hookowana.** Agent musi pamiętać żeby czytać `active-work.md` na starcie. Nie ma auto-load przez Claude Code (path-rules nie są aktywowane przez `settings.json` — to konwencja, nie hook). To kompromis: prościej, ale wymaga dyscypliny.

2. **`architecture.md` aktualizuje tylko timestamp.** Hook nie modyfikuje treści — tylko bumpuje datę jako sygnał świeżości. Realna mapa jest manualna. Tradeoff: brak driftu z auto-generacji, kosztem dyscypliny.

   **Subtelność która gryzie:** post-commit fires PO commicie, więc bumpnięty timestamp ląduje jako unstaged modification w working tree — nie jest częścią żadnego commita. Sygnał świeżości jest *lokalny* (twój clone widzi 5 minut temu), teammate po `git pull` widzi stary timestamp. Trzy opcje jeśli chcesz to zmienić:
   - **(a)** Zostaw — udokumentuj jako "lokalny widok aktywności".
   - **(b)** Przenieś bumpa do **pre-commit** — timestamp ląduje w samym commicie (kosztem: każdy commit modyfikuje ten plik).
   - **(c)** Zlicz timestamp dynamicznie z `git log -1 --format=%cI -- .claude/architecture.md` przy czytaniu — plik jest static, hook usunięty.

3. **`core.hooksPath` per-clone.** Każdy nowy clone repo wymaga ręcznego setupu. Mitigation: `npm postinstall` / `Makefile setup`.

4. **Brak custom subagentów (`.claude/agents/`).** OpenState nie używa, więc template też nie zawiera. Jeśli potrzebujesz — to future extension, nie blocker.

5. **Brak lokalnego memory (`.claude/memory/`).** Memory siedzi w globalnym `~/.claude/projects/<path-hash>/memory/` per-user. Lokalne in-repo memory byłoby niestandardowe i kolidowałoby z systemem Claude Code.

6. **Pre-commit blokuje commit przy błędach typecheck.** Czasem chcesz scommitować WIP — wtedy `git commit --no-verify`. Ale tylko świadomie, nie domyślnie (zakaz `--no-verify` jest w `general.md`).

7. **Coordination ledger nie skaluje na duże zespoły (>5 ludzi).** Dla większych — potrzebujesz Linear/Jira + Slack. Ten protokół jest dla 1-3 osób + 1-3 agenty.

---

## Changelog tego pliku

- **2026-05-08** — Enrichment z bootstrap'a CrossDesk:
  - §0 meta-prompt: 5-te pytanie o istniejący AGENTS.md (CLAUDE.md jako
    thin shim zamiast duplikatu); pre-check `.gitignore` na `.claude/`.
  - §0 meta-prompt + §3 templates: warunkowy `.claude/rules/rpc.md`
    (proto-first), commit-msg jako 4-ty hook.
  - §2 Quickstart: nowy krok 5 — fix `.gitignore` (negacja `!.claude/rules/`
    nie działa, gdy parent jest excluded).
  - §3.5.1: nowy template `.claude/rules/rpc.md` dla projektów z
    `proto/*.proto` jako single source of truth.
  - §4.1 pre-commit: nowy Wariant F (hybrid monorepo z per-file-type guards).
  - §4.4: nowy hook commit-msg (Conventional Commits regex enforcement).
  - §5 Coordination: wariant push-to-main ledger (`WORK_LOG.md`-style)
    obok branch-tracked `active-work.md`.
  - §8 Limitacje: rozszerzenie #2 — post-commit timestamp jest local-only
    (3 opcje fix: zostaw / przenieś do pre-commit / dynamic z git log).
- **2026-05-07** — Pierwsza wersja, wyekstrahowana z architektury OpenState.

---

**Koniec `universals.md`.** Pojedynczy plik, wszystko w jednym miejscu, gotowe do skopiowania do nowego projektu.
