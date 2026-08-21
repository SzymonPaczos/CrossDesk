# Rejestr decyzji (META)

Decyzje META o procesie/workflow projektu. Status: **aktywna** chyba że
oznaczone inaczej.

> **Decyzje techniczne stacku** — patrz [`docs/DECISIONS.md`](../../docs/DECISIONS.md)
> (kanoniczny rejestr ADR `DEC-NNNN`). Plik ten trzyma TYLKO META-decyzje:
> jak pracujemy, gdzie żyje stan, jakie konwencje obowiązują. Boundary
> z `AGENTS.md` na `docs/DECISIONS.md` jest podtrzymane — edycja
> DEC-NNNN wymaga zgody właściciela.

---

## DEC-META-001 — Adopcja konwencji claude-toolkit §9.9

**Data:** 2026-05-23 · **Status:** aktywna

Projekt adoptuje układ plików stanu wg cyklu życia z
`~/DevProjects/claude-toolkit/conventions/project-state-layout.md` +
`NEW-PROJECT.md` §9.9. Konkretnie:

- `.claude/backlog.md` — jedyne źródło otwartej pracy (P0/P1/P2 +
  "czeka na decyzję" + "zablokowane"). FOLLOWUPS.md został tu
  sfoldowany; archiwum w `.claude/history/2026-05-23-followups-archive.md`.
- `.claude/status.md` — known-issues / bieżące breakages.
- `.claude/rules/` — TYLKO trwałe instrukcje (audyt, decisions, general,
  backend). Stan przejściowy poza `rules/`.
- `.claude/history/` — archiwum (`completed-work.md` append-only +
  raporty sesji z datą w nazwie).
- `WORK_LOG.md` — świadome odstępstwo (zob. DEC-META-003).

**Powód:** Spójność cross-projektowa, jeden punkt wejścia dla nowej sesji.

## DEC-META-002 — `docs/DECISIONS.md` pozostaje kanoniczny dla ADR

**Data:** 2026-05-23 · **Status:** aktywna

ADR `DEC-NNNN` żyją w `docs/DECISIONS.md` (techniczne decyzje stacku:
proto, transport, packaging, GPU passthrough itd.). Ten plik
(`.claude/rules/decisions.md`) trzyma TYLKO META-decyzje workflow'owe
(prefiks `DEC-META-NNN`).

**Powód:** `AGENTS.md` "File boundaries" zabrania edycji
`docs/DECISIONS.md` bez zgody właściciela. Duplikacja DEC-NNNN do
`.claude/` byłaby źródłem driftu. Separacja ról jest czystsza.

**Jak stosować:** Audyt sprawdza zgodność z **OBOMA** plikami (zob.
`.claude/rules/audit.md` §7).

## DEC-META-003 — `WORK_LOG.md` pozostaje w roocie

**Data:** 2026-05-23 · **Status:** wycofana (2026-07-12; bezprzedmiotowa
od 2026-07-05)

`WORK_LOG.md` (koordynacja multi-agent START/END) pozostaje w roocie
repo, nie jest przenoszony do `.claude/active-work.md` ani do
`.claude/history/` mimo że łamie regułę §9.9 "stan przejściowy poza
rooekm".

**Powód:** `AGENTS.md` workflow steps 6 i 13 definiują WORK_LOG.md jako
plik pushowany bezpośrednio do `main` (jedyny wyjątek od no-direct-main).
Przeniesienie wymusiłoby zmianę protocolu i conflict resolution dla
agentów już używających ścieżki w roocie. Trade-off zaakceptowany.

**Wycofanie:** właściciel wycofał całą ceremonię WORK_LOG START/END
2026-07-05 (solo owner + jeden agent; zob. `rules/general.md`
"Coordination protocol"), więc uzasadnienie (workflow steps 6/13)
przestało istnieć. Plik zostaje w roocie jako zamrożony artefakt;
ewentualna archiwizacja do `history/` = decyzja właściciela
(zaparkowane w `needs-owner.md`). Audyt nadal nie raportuje samego
pliku jako odstępstwa §9.9.

## DEC-META-004 — Inline `FOLLOWUPS:NNN` w kodzie zostają niezmienione

**Data:** 2026-05-23 · **Status:** aktywna

Po fold FOLLOWUPS.md → backlog.md komentarze w kodzie/testach typu
`# FOLLOWUPS:665` lub `(FOLLOWUPS:1019 follow-up)` **pozostają**.
Rozwiązują się przeciwko archiwum
`.claude/history/2026-05-23-followups-archive.md`.

**Powód:** ~30+ plików źródłowych miałoby line-number drift (numery linii
FOLLOWUPS:NNN nie mapują się 1-do-1 na nowy backlog). Adnotacje są
historyczne, nie load-bearing; agent grepujący "FOLLOWUPS:665" znajdzie
ten sam content w archiwum.

**Jak stosować:** Nowe komentarze referencyjne piszemy jako
`# backlog: <area> <pNN>` (np. `# backlog: peripherals P1 audio`)
zamiast line-numerów. Audyt nie raportuje istniejących FOLLOWUPS:NNN
adnotacji.

## DEC-META-005 — Skipped-on-purpose lista z FOLLOWUPS

**Data:** 2026-05-23 · **Status:** aktywna

Lista 8 pozycji "Skipped on purpose (do not implement)" z dawnego
FOLLOWUPS.md została wchłonięta tutaj. Te decyzje **NIE wracają jako
feature requests** bez decyzji właściciela. Pełne uzasadnienia w
[`docs/COMPARISON_WINAPPS.md`](../../docs/COMPARISON_WINAPPS.md) §7.

- Docker / Podman backends — kolizja z `qemu:///session` constraint
  (zob. DEC-0003).
- `dockur/windows` container image — j.w.
- Static `\\tsclient\home` mount — security regression vs JIT VirtioFS.
- Bash-driven control flow — niekompatybilne z async Python + mypy.
- `compose.yaml` — irrelevant bez Dockera.
- `renovate.json` / WinApps' `flake.nix` — różny packaging stack (nasz
  flake.nix jest osobnym artefaktem).
- Verbatim AGPLv3 file copies z `third_party/winapps/` —
  license-incompatible.
- Tiny11 / Tiny10 / community-modified ISOs — unauthorized MS source
  modification; superseded by Lean Windows profile.

**Jak stosować:** Jeśli ktoś zaproponuje którąkolwiek z tych ścieżek,
przekieruj do tej listy + COMPARISON_WINAPPS §7.

## DEC-META-006 — Wyjątek od „No polling" dla CLI file-tail

**Data:** 2026-05-31 · **Status:** aktywna

Reguła „No polling" (`AGENTS.md` „Coding rules" + `.claude/rules/general.md`)
celuje w **control-plane host↔guest** — tam obowiązują async gRPC streams
w obie strony, żaden `while True: sleep`. Zatwierdzony wyjątek:
`crossdesk logs --follow`
([`host/src/crossdesk_host/cli/logs_cmd.py`](../../host/src/crossdesk_host/cli/logs_cmd.py)
`::_tail_file`) używa pętli `while True: readline(); await asyncio.sleep(0.25)`
do tailowania pliku logu w trybie interaktywnym.

**Powód:** alternatywa (inotify/kqueue przez `asyncio.add_reader` na fd
inotify) dokłada zależność platformową i złożoność dla wygodowego
polecenia ops; interwał 0.25 s jest poniżej progu percepcji w trybie
interaktywnym. Polling lokalnego pliku nie dotyczy ścieżki krytycznej
ani transportu — nie ma związku z motywacją reguły (brak busy-waitu na
zdarzeniach RPC). Zatwierdzone przez właściciela 2026-05-31 (audyt
deep-layer, P1).

**Jak stosować:** Audyt (`.claude/rules/audit.md` §3/§7) **nie raportuje**
`_tail_file` jako naruszenia. Każdy NOWY `while True: sleep` poza tym
jednym call-site nadal jest naruszeniem wymagającym uzasadnienia.

## DEC-META-007 — whole-`$HOME` FS default zastępuje skip z DEC-META-005

**Data:** 2026-06-29 · **Status:** aktywna

DEC-META-005 listuje „Static `\\tsclient\home` mount — security regression
vs JIT VirtioFS" wśród pozycji skip-on-purpose. [`docs/DECISIONS.md`](../../docs/DECISIONS.md)
DEC-0018 czyni whole-`$HOME` **domyślnym** zakresem Stage B (decyzja
właściciela 2026-06-29; share jest opt-in, default OFF). Mechanizm różni się
od always-on WinApps (nasz share jest opt-in i etapowalny przez
`shared_folder_scope`), ale zakres jest porównywalny. Pozycja DEC-META-005
dla tego itemu jest **zastąpiona** przez DEC-0018.

**Powód:** restrykcyjny JIT-per-file (Stage C) jest w większości niezbudowany;
pragmatyczny scoped folder już shipował. „Max usefulness, no paranoia"
(właściciel) dla same-user threat modelu, który `docs/THREAT_MODEL.md` §C7 już
traktuje jako out-of-scope.

**Jak stosować:** Audyt nie raportuje whole-`$HOME` jako naruszenia
DEC-META-005; zgodność sprawdza przeciw DEC-0018 + DEC-META-007.

## DEC-META-008 — Adopcja fali toolkitu 2026-07-11 (CI/CD, provenance, gate'y, role audytowe)

**Data:** 2026-07-12 · **Status:** aktywna

Re-adopcja delty względem `claude-toolkit` (stan `main` 2026-07-11,
`ADOPT.md`; polecenie właściciela 2026-07-12). Zaadoptowane:

- **Konwencje → `.claude/rules/`** (kopie masterów): `ci-cd.md`
  (baseline CI/CD + supply chain), `rules-as-gates.md`,
  `change-provenance.md`. Dolinkowane w load-liście `CLAUDE.md`.
- **Provenance commitów:** `.gitmessage` (template) + hook
  `.githooks/commit-msg` — subject Conventional Commits **blokująco**,
  trailery `Intent`/`Task-Ref`/`Gates` w **trybie raportowym** (WARN;
  ratchet do blokady = decyzja właściciela, zaparkowana). **Bez
  atrybucji AI** (D-006 toolkitu — spójne z rewrite'em historii
  CrossDesk 2026-07-07 i `settings.json`).
- **Role audytowe → `.claude/agents/`:** `security-reviewer.md`
  (skonkretyzowany sekcją CrossDesk) + `red-team.md`; wymagane przez
  zaktualizowany skill `weekly-audit` (Security Review min. co 7 dni,
  Red Team miesięcznie / risk-triggered).
- **Skill `weekly-audit`** zaktualizowany do mastera 2026-07-11 (Krok 0
  SAST/workflowy, punkty głębokie 8–13, obowiązkowy nagłówek raportu,
  Krok 5 aktualizacja masterów).
- **`multi-agent-delivery.md`** skopiowane do `rules/` jako referencja
  dla ról audytowych, ale **pełny kontrakt zespołowy NIEaktywny** —
  projekt = solo owner + jeden agent (spójnie z wycofaniem WORK_LOG
  2026-07-05). Aktywacja pełnego zespołu = decyzja właściciela.
- **Preflight świeżości audytu** w `.githooks/pre-push` — tryb
  raportowy (WARN gdy ostatni `## Audyt` >7 dni). Zgodne z etapowaniem
  `rules-as-gates.md` §3.

**Świadomie NIE zaadoptowane:**

- `production-operations.md` + `progressive-delivery.md` +
  `delivery-log.md` — projekt nie ma produkcji/serwisu (desktop app,
  pre-release). Wrócić przy pracach nad hostowanym repo pakietów
  (deb/rpm) lub pierwszym publicznym release.
- Hook `UserPromptSubmit` maksymalizacji promptów (§9.3) — koliduje z
  autonomiczną pętlą (`loop-spec.md`); zaparkowane w `needs-owner.md`.
- `active-work.md` / runtime ledger — bez równoległych Builderów zbędny;
  reguła branch-per-agent w `general.md` pokrywa rzadkie przypadki.

**D-007 (profil CI):** de facto **hybrydowy** — hosted GitHub Actions
(repo publiczne: `ci.yml`, `security.yml`, `release.yml`) + local-first
mirror (pre-push lustrzy pipeline). Formalne potwierdzenie właściciela
zaparkowane w `needs-owner.md`; po podpisie dopisać tu status.

**Jak stosować:** commit nietrywialnej zmiany ma trailery provenance;
audyt przechodzi rozszerzoną checklistę skilla (w tym gate'y, supply
chain, provenance); Security Reviewer uruchamiany przy każdym audycie
z `.claude/agents/security-reviewer.md` w niezależnym kontekście.

## DEC-META-009 — Adopcja toolkitu 2026.08.21: audyt jako nakładka na master

**Data:** 2026-08-21 · **Status:** aktywna · **Rozszerza:** DEC-META-008

Aktualizacja kopii toolkitu z `2026.08.06` → `2026.08.21` i przebudowa
wewnętrznego sposobu audytu. Polecenie właściciela 2026-08-21. Master zmieniał
się **w trakcie** tej pracy (2026.08.20 → 2026.08.21); adopcja została powtórzona
na wersji końcowej, a nie domknięta na migawce.

### Co się zmieniło mechanicznie

- **7 kopii zsynchronizowanych** przez `toolkit-sync.sh update`
  (`skills/weekly-audit/SKILL.md`, `agents/{security-reviewer,red-team}.md`,
  `rules/{ci-cd,change-provenance,multi-agent-delivery,rules-as-gates}.md`).
- **Nowa referencja:** `skills/weekly-audit/references/kontrola-glebokosci.md` —
  master wyniósł checklistę głęboką z ciała skilla i rozszerzył ją **14 → 25**
  punktów.
- **`.claude/toolkit.local`** — nowy plik zadeklarowanych odstępstw. Jeden wpis:
  `agents/security-reviewer.md`, bo master **wymaga** sekcji projektowej.
  Bez tego wpisu `update` ją kasuje — i skasował 2026-08-21: lock zgadzał się
  z plikiem, więc skrypt uznał kopię za nietkniętą. Odtworzone z `git show`
  i przy okazji zaktualizowane (accepted-risk wskazywał DEC-0018, który
  DEC-0019 zastąpił 2026-07-19).

### `rules/audit.md` przestaje być drugą checklistą

Plik trzymał własną, równoległą listę 8 punktów. `toolkit-sync.sh contrib`
pokazał **16 pozycji po stronie projektu wobec 8 w masterze** przy `check`
świecącym na zielono — bo ten plik kopią nie jest, więc manifest go nie widzi.
Master urósł w tym czasie do 25 punktów.

Od teraz `rules/audit.md` jest **nakładką**: konkretyzuje punkty mastera
ścieżkami, grepami i wyjątkami CrossDeska, i nie trzyma własnej numeracji.
Reguła ogólna wypracowana w projekcie idzie do mastera przez `promote`, nie
tutaj. `promote` **na tym pliku jest zabroniony** — utworzyłby
`conventions/audit.md` obok `skills/weekly-audit/SKILL.md`, czyli drugi master
jednego dokumentu (skrypt sam to blokuje).

### Zaadoptowane konwencje (8, decyzja właściciela 2026-08-21)

Punkty 15 i 20–25 nowej checklisty odsyłały do plików, których projekt nie
miał — checklista z wiszącym odsyłaczem nie jest checklistą. Przyjęte
**wszystkie osiem**: `dependency-currency`, `quality-gates-and-dod`,
`security-verification-gates`, `test-evidence`, `ci-pipeline-architecture`,
`repo-hygiene-gates`, `pull-request-review`, `issue-reporting`.

Do load-listy `CLAUDE.md` weszły **dwie** — `quality-gates-and-dod` i
`test-evidence` — bo zmieniają sposób wykonania **każdego** zadania (definicja
ukończenia, dowód z testu). Pozostałe sześć są czytane przy audycie i pracy nad
bramkami; trzymanie ~1300 linii w każdym kontekście sesji byłoby kosztem bez
pokrycia. To ten sam wzorzec, co `multi-agent-delivery.md` w DEC-META-008.

Dwie z nich CrossDesk czyta **przez odpowiedniki**, nie dosłownie:
`pull-request-review` (merge lokalny + trailer `Gates:` zamiast PR-a) oraz
`ci-pipeline-architecture` **§11a** (profil local-first/hybrydowy — bez tego
audyt zaraportuje „brak bramek" o repo, które ma ich kilkanaście).

**Nadal NIE zaadoptowane** (bez zmian wobec DEC-META-008): `progressive-delivery`,
`production-operations`, `delivery-log` — brak produkcji. Punkt 10 checklisty
stosuje się więc tylko w części niezależnej od deploymentu.

### `audit.sh` — trzy stany zamiast jednego

Skrypt statyczny nie odróżniał „narzędzie nie znalazło nic" od „narzędzie
padło": `cmd | grep -c` gubi kod wyjścia w potoku, więc crash lintera
raportował się jako **0 findings** — nie do odróżnienia od czystego repo.
Krok 0 mastera nazywa to wprost. Teraz każdy pomiar ma trzy stany: liczba ·
`n/a` (narzędzia nie ma) · `BLOCKED` (wystartowało i padło). Doszły też:
nagłówek maszynowy (`TOOLKIT_VERSION`, `AUDITED_REVISION`, `DIFF_RANGE`),
Krok 00 jako pierwsza sekcja, higiena repo (punkt 14), aktualność runtime'ów
(punkt 15), przeliczanie liczb load-bearing z prozy (punkt 4) oraz tryb
`CROSSDESK_AUDIT_DRYRUN=1`.

### Drugi skill audytowy: `audyt-naprawczy` (nowy w 2026.08.21)

Przyjęty w całości (D-015: skill jest jednostką niepodzielną). Robi to, czego
`weekly-audit` **nie robi z założenia** — wprowadza zmiany, ale wyłącznie
w klasach, dla których istnieje bramka czerwona przed i zielona po. Uruchamiany
tylko na wyraźne polecenie „audyt z naprawą".

**Trzy odstępstwa CrossDeska, zapisane w `rules/audit.md`:**

1. **Boundary files wypadają z automatu** — w tym z masterowej klasy „literówki
   i zepsute odsyłacze w dokumentacji". W typowym repo dokumentacja nie jest
   kontraktem; tutaj `AGENTS.md`, `docs/{DECISIONS,THREAT_MODEL,REQUIREMENTS,
   MVP_SCOPE,GOALS}.md`, `ROADMAP.md` i `proto/**` są. Bramka udowodni, że link
   działa — **nie udowodni, że wolno go było ruszyć**.
2. **`audyt/RRRR-MM-DD` to piąty dozwolony prefiks gałęzi**, wyłącznie dla tego
   skilla (`general.md` zaktualizowany). Nigdy nie merguje się bez zgody
   właściciela; skill sam nie pushuje.
3. **Zawis `pytest` na macOS to `n/a (środowisko)`, nie czerwony test** —
   baseline z Kroku 1 liczony na zawieszonej suicie jest nieinterpretowalny.

### Świadomie NIE zaadoptowane z fali 2026.08.21

`conventions/naming-conventions.md` i `conventions/module-paths.md`
(+ `templates/{lexicon.md,import-depth.sh}`) — realne konwencje kodu, ale
**checklista audytu ich nie dereferencjonuje** (punkty 1–25 bez zmian w tej
fali), a zadanie brzmiało „zaktualizuj sposób audytu". Do osobnej decyzji;
zapisane w `backlog.md`, żeby nie zniknęły.

### Usterki mastera — naprawione u źródła, nie załatane lokalnie

`scripts/toolkit-sync.sh:240` używa GNU-owego `find -printf '%f\n'`. Na macOS
(BSD find) kończy się `find: -printf: unknown primary or operator`, więc **nowy
check kompletności skilli (D-015) nie wykonuje się na maszynie właściciela** —
a `check` i tak kończy się zielono, czyli awaria wygląda jak brak znalezisk.
Zgodnie z protokołem (`toolkit-sync.md` pkt 4) poprawka poszła **do mastera**,
nie do kopii — gałąź `fix/sync-nie-kasuje-scalonej-kopii` (niezmergowana).

Przy okazji wyszła usterka **poważniejsza**: `update` kasował ręcznie scaloną
kopię, co ten projekt odczuł na własnej skórze. Lock trzymał jedną sumę — kopii
w projekcie — więc plik stemplowany **po** scaleniu zgadzał się ze swoim lockiem
i wyglądał jak nietknięty master. Zabezpieczenie `purely_outdated`, napisane
dokładnie dla ról, które master każe skonkretyzować, było nieosiągalne po
pierwszym ostemplowaniu. Lock ma teraz **drugą sumę** (mastera z chwili
stemplowania), a `validate-toolkit.sh` test negatywny potwierdzony sentinelem.
Nasz `toolkit.local` zostaje mimo naprawy — rozjazd jest trwały z definicji,
więc deklaracja jest właściwszą formą niż powtarzane `POMINIĘTO`.

**Promocja w drugą stronę:** trzy sygnały ze starej checklisty projektowej
(połknięte błędy, `datetime.now()` jako data zdarzenia, ID jako licznik) weszły
do mastera jako **punkt 26** i wróciły tu przez `update` — checklista ma dziś
**26 punktów**, nie 25.

**Jak stosować:** audyt zaczyna się od `toolkit-sync.sh check .`; ocena
głęboka wczytuje `references/kontrola-glebokosci.md`, a `rules/audit.md`
czyta się **razem z nim**, nie zamiast niego. Naprawa idzie przez
`audyt-naprawczy` tylko wtedy, gdy właściciel o nią poprosi.
