# Reguły audytu — nakładka CrossDesk

**Ten plik NIE jest checklistą audytu.** Checklista żyje w masterze
`claude-toolkit` i jest w repo jako kopia:

- procedura → [`.claude/skills/weekly-audit/SKILL.md`](../skills/weekly-audit/SKILL.md)
  (Kroki 00 → 5, obowiązkowy nagłówek raportu);
- **punkty kontroli głębokiej (1–26)** →
  [`.claude/skills/weekly-audit/references/kontrola-glebokosci.md`](../skills/weekly-audit/references/kontrola-glebokosci.md).
  **Wczytaj ten plik przed oceną** — ocena z pamięci pomija punkty dopisane
  po ostatnim postmortemie.

Tutaj jest **wyłącznie to, czego master wiedzieć nie może**: konkretne ścieżki,
grepy, decyzje i wyjątki CrossDeska. Mechanizm: **audyt wykrywa → naprawiamy →
ratchet zamraża → trend mierzy.** Audyt **nie naprawia nic sam** — właściciel
decyduje.

## Dwa skille, dwa różne uprawnienia

| Skill | Co robi | Kiedy |
|---|---|---|
| `weekly-audit` | **diagnozuje**; kończy raportem i listą P0/P1/P2 | domyślnie, kadencja 7 dni |
| `audyt-naprawczy` | to samo + **naprawia klasy dowodliwe bramką**, po commicie na klasę | tylko na wyraźne „audyt z naprawą" |

`audyt-naprawczy` (przyjęty 2026-08-21) nie powtarza procedury — wykonuje
Kroki 00–3 `weekly-audit` i dokłada gałąź, klasyfikację i naprawy. Kryterium
automatu jest jedno: **istnieje bramka czerwona przed i zielona po**, a zmiana
nie rusza zachowania widocznego dla użytkownika.

### Odstępstwa CrossDeska od tego skilla — obowiązują ponad master

1. **Boundary files są wyłączone z automatu — także z „napraw literówki i
   zepsute odsyłacze".** Master dopuszcza tę klasę, bo w typowym repo
   dokumentacja nie jest kontraktem. Tu jest: `AGENTS.md`, `docs/DECISIONS.md`,
   `docs/THREAT_MODEL.md`, `docs/REQUIREMENTS.md`, `docs/MVP_SCOPE.md`,
   `docs/GOALS.md`, `ROADMAP.md`, `proto/**` zmienia **wyłącznie właściciel**
   (`AGENTS.md` „File boundaries"). Zepsuty odsyłacz w tych plikach idzie do
   raportu jako P0/P1 razem z gotowym brzmieniem poprawki — nie jako commit.
   Bramka potrafi udowodnić, że link działa; **nie potrafi udowodnić, że wolno
   go było ruszyć**.
2. **Gałąź.** Skill zakłada `audyt/RRRR-MM-DD`. `general.md` zna prefiksy
   `feat|fix|chore|docs`; `audyt/` jest **piątym, dozwolonym wyłącznie dla tego
   skilla** (DEC-META-009) i nigdy nie merguje się bez zgody właściciela.
   Skill nie pushuje i nie otwiera PR-ów — tu również nie.
3. **Baseline bramek na tym Macu bywa zwodniczy.** Pełny `pytest` wiesza się
   ~6% przebiegów (wątek `_poll_wrapper`, backlog P2) — **zawieszenie to nie
   jest czerwony test**. Zawis w Kroku 1 raportuj jako `n/a (środowisko)`
   i policz baseline na boxie Linux, zamiast interpretować go jako regresję.
4. **Klasy realnie dowodliwe w CrossDesku:** `ruff --fix` + `ruff format`
   (host), `cargo fmt` (guest/gui), `buf format -w` (proto), martwe pliki
   wskazane narzędziem **po** weryfikacji greppem (punkt 5). `mypy --strict`
   **nie jest** klasą automatu — poprawka typów zmienia kod, nie formatowanie.
5. **Czego nie ruszać mimo zielonej bramki:** `.githooks/**`, `.github/**`,
   progi w `pyproject.toml`/`deny.toml`, `.claude/rules/decisions.md`. To jest
   ratchet albo konfiguracja bramki — master też tego zabrania (Krok 5:
   „ratchet przygotuj jako propozycję").

> **Dlaczego przepisane (2026-08-21).** Ten plik trzymał własną, równoległą
> listę 8 punktów. `toolkit-sync.sh contrib` pokazał rozjazd: 16 pozycji po
> stronie projektu wobec 8 w masterze, przy `check` świecącym na zielono —
> bo plik nie jest kopią, więc manifest go nie widział. Master urósł tymczasem
> do 25 punktów. Równoległa lista starzeje się cicho; nakładka nie ma jak.
> Zasada: **nowa reguła OGÓLNA idzie do mastera przez `promote`, nie tutaj.**
> `promote` na tym pliku jest zabroniony — utworzyłby `conventions/audit.md`
> obok istniejącego `skills/weekly-audit/SKILL.md`, czyli drugi master jednego
> dokumentu (skrypt sam to blokuje, patrz `conventions/toolkit-sync.md` w masterze).

---

## Krok 00 w warunkach CrossDeska

Master każe zacząć od `toolkit-sync.sh check .` — przed czytaniem kodu.

```sh
TK=../claude-toolkit          # ta maszyna; na boxie Linux toolkit NIE ISTNIEJE
bash "$TK/scripts/toolkit-sync.sh" check .
```

- **Toolkit obok repo** (`../claude-toolkit`) jest warunkiem Kroku 00. Gdy go
  nie ma — Krok 00 jest `DEGRADED`, nie „pominięty": zapisz to w raporcie
  (`TOOLKIT_VERSION: brak mastera do porównania`) i dopisz zadanie do backlogu.
  Znany stan: na boxie Linux toolkit nie był sklonowany (backlog P2, audyt
  2026-07-22).
- **Odstępstwa zadeklarowane** żyją w [`.claude/toolkit.local`](../toolkit.local).
  Dziś jeden wpis: `agents/security-reviewer.md` — master **wymaga** sekcji
  projektowej, więc rozjazd jest trwały z definicji. Bez tego wpisu `update`
  ją kasuje: zdarzyło się 2026-08-21, lock zgadzał się z plikiem, więc skrypt
  uznał kopię za nietkniętą i nadpisał ją razem z 37 liniami konkretyzacji.
- **`check` widzi tylko kopie.** Pliki CrossDeska, które regułami są, a kopiami
  nie — przepuść przez `contrib`, bo tylko tam rośnie niewidzialny dryf:

  | Plik projektu | Odpowiednik w masterze |
  |---|---|
  | `.claude/rules/audit.md` (ten plik) | `skills/weekly-audit/SKILL.md` |
  | `.claude/rules/general.md` | `NEW-PROJECT.md` §3.3 |
  | `.claude/rules/backend.md` | `NEW-PROJECT.md` §3.5 |
  | `.claude/rules/decisions.md` | `NEW-PROJECT.md` §9.1 |
  | `.claude/audit.sh` | `NEW-PROJECT.md` §9.2 (szablon) |

- **Przecięcia claimów** (`check-active-overlap.sh`) — CrossDesk to solo owner
  + jeden agent (DEC-META-008), więc domyślnie `NOT_TRIGGERED`. Uruchom, gdy
  realnie działają dwie sesje / worktree.
- **`DOCS_SOURCE`** — bez podłączonego źródła dokumentacji audyt **nie ma prawa**
  podawać numerów wersji, dat wydania ani statusu wsparcia **jako faktu**.
  Dotyczy wprost punktu 15 (EOL Pythona, EOL Rusta, wersje FreeRDP/QEMU/libvirt).

## Warstwa statyczna

`bash .claude/audit.sh` — liczby, zero osądu LLM. Skrypt sam dopisuje sekcję
`## Audyt YYYY-MM-DD` na górę [`audit-log.md`](../audit-log.md) wraz z nagłówkiem
maszynowym. Wzorzec pełnego wpisu: [`.claude/templates/audit-log-entry.md`](../templates/audit-log-entry.md).

Środowisko: narzędzia Pythona żyją w `host/.venv` (skrypt sam dokłada je do
`PATH`). Brakujące narzędzie = `n/a`, **nigdy zero findings** — a skan, który
**wystartował i padł**, jest `BLOCKED`, nie „0" (Krok 0 mastera, trzy guardy).

---

## Konkretyzacja punktów 1–26 dla CrossDeska

Numeracja = `references/kontrola-glebokosci.md`. Punkt bez wiersza tutaj
stosuje się wprost z mastera.

### 1. Bezpieczeństwo
Granice walidacji to **wyłącznie**: wejście servicera gRPC
(`host/src/crossdesk_host/ipc/*.py`), parsowanie odpowiedzi libvirt
(`libvirt_ctl/`), input użytkownika w CLI (`cli/`). Wewnętrzne helpery ufają
wywołującym — brak walidacji wewnętrznej **nie jest** findingiem. Dodatkowo:
servicer bez `timeout=`, `unsafe`/`unwrap()`/`expect()` w Rust bez komentarza
`// Safety:` / `// Infallible because:`, edycja `proto/**` bez aktualizacji
`docs/THREAT_MODEL.md`. Model zagrożeń: `docs/THREAT_MODEL.md` (guest = TA2;
same-user host compromise **out of scope** per §C7 — nie zgłaszaj).

### 2. Slop
Markery `🚧 mock` i `[~PARTIAL]` — sprawdź, czy **nadal są uzasadnione**, czy
zaległy po merge'u. Świadome zaślepki są spisane w
[`ignorefiles.md`](../ignorefiles.md) („Security / placeholder UI",
„Partially broken / deprecated") — tych **nie raportuj**. Producer chain
CrossDeska: CLI/GUI → RPC daemona → abstrakcja (`abstractions/`) → `real.py`.
Brak realnej implementacji na końcu łańcucha przy powierzchni ogłoszonej jako
gotowa = ten sam fałsz piętro niżej.

### 3. Jakość testów
Ścieżki krytyczne, które **muszą** mieć pokrycie: handshake mTLS
(`test_mtls_handshake.py`), `AuthValidator` (`test_auth_validator.py`,
`test_auth_rejection_paths.py`, `test_security_edges.py`), przejścia FSM
lifecycle. `test_smoke_inprocess.py` jest kontraktem boundary — pęknięcie tam
to realny bug, nie flake. Sprawdź też, czy żyje autouse-guard w `conftest.py`
blokujący realne libvirt: bez niego test potrafi zdestruować żywą domenę
(incydent 2026-07-05).

### 4. Architektura + **dryf twierdzeń liczbowych**
Drift `.claude/architecture.md` ↔ kod. Osobno: **przelicz liczby w prozie
komendą, nie przepisuj ich z dokumentu**. Bieżące liczby load-bearing i czym
je mierzyć:

```sh
# „20 subpackages" (AGENTS.md „Repository layout")
find host/src/crossdesk_host -mindepth 1 -maxdepth 1 -type d ! -name __pycache__ | wc -l
# „8 z 12 kryteriów ✅ live" (PLAN.md, tabela akceptacji)
grep -cE '^\| *[0-9]+ \|.*✅ live' PLAN.md
# ADR-y i META-decyzje
grep -cE '^## DEC-[0-9]+' docs/DECISIONS.md; grep -cE '^## DEC-META-[0-9]+' .claude/rules/decisions.md
```

Rozjazd w `AGENTS.md` = **boundary** (nie poprawiaj — flaguj). Precedens:
„22 subpackages" żyło w AGENTS.md, realnie było 20 (audyt 2026-07-07).

### 5. Dead code
Każdą listę „0 production callers" przepuść przez
`grep -rn '<Nazwa>' --include='*.py'` po całym repo — base-classy i Protocol-e
mylą się z martwym kodem. Pozycje z [`ignorefiles.md`](../ignorefiles.md)
„Partially broken / deprecated" są świadomie martwe: **nie raportuj**.

### 6. Zgodność z rejestrem decyzji
**Dwa** rejestry, oba twarde: `.claude/rules/decisions.md` (META, proces) i
`docs/DECISIONS.md` (ADR `DEC-NNNN`, stack). Złamanie = **P0** (bezpieczeństwo
/ compliance) albo **P1** (architectural drift). Regresje do sprawdzenia:

```sh
ls Dockerfile compose.yaml docker-compose.yml 2>/dev/null   # DEC-0003 „No Docker"
grep -rn 'while True' --include='*.py' host/src | grep -i sleep  # „No polling"
git ls-files infra/certs/pki/                               # leaf-certy MUSZĄ być puste
grep -n 'shared_folder_scope' host/src/crossdesk_host/config/peripherals.py  # DEC-0019: documents
```

Jedyny zatwierdzony wyjątek od „No polling" to `cli/logs_cmd.py::_tail_file`
(**DEC-META-006**) — nie raportuj. Każdy NOWY `while True: sleep` jest
naruszeniem.

### 7. Skille / MCP
**Zastąpione przez Krok 00.** Ręczne „skopiuj nowsze wersje z toolkitu" było
tą regułą, która trzy razy z rzędu przegrała, bo nikt nie miał czym porównać —
dziś robi to `toolkit-sync.sh`. Zostaje: stan MCP (`.mcp.json` /
`~/.claude.json`; serwery w `~/.claude/mcp-servers.json` są **ignorowane**)
oraz pytanie, czy w projekcie nie powstał skill wart promocji do mastera.

### 8. Gate'y — **mierz, nie czytaj**
Warstwy: `.githooks/pre-commit`, `pre-push`, `commit-msg`, `post-commit`
(aktywne dopiero po `git config core.hooksPath .githooks` — per-klon!).
Lektura hooka wykrywa to, czego się spodziewasz. Dowód wymagany:

```sh
bash ../claude-toolkit/templates/test-gates.sh .githooks/pre-push   # cel: 6/6
```

**Zmierzone 2026-08-21: `4 zdanych, 2 niezdanych` — i wynik jest SKAŻONY**,
więc nie czytaj go jako 4/6. Dwie rzeczy naraz:

- **P0 potwierdzony lekturą, nie testem.** `pre-push:222-228` skanuje sekrety
  przez `grep … "$f"` **z dysku**, z gardą `[ -f "$f" ] || continue`. Lista
  plików pochodzi z commita (`git diff -z --name-only origin/main...HEAD`), ale
  treść już nie — więc sekret zacommitowany i posprzątany **tylko w working
  tree** przechodzi na `origin`. Hook nie czyta refów ze stdin ani nie odtwarza
  commita w `git worktree`. Wzorzec naprawy: `NEW-PROJECT.md` §4.2.
- **Harness nie jest w stanie tego zmierzyć**, dopóki warstwa 5 nie odróżnia
  awarii narzędzia od znaleziska: `pre-push:323` robi
  `(cd "$REPO_ROOT/guest" && cargo audit …) || { echo "znaleziono podatności"; exit 1; }`.
  W fixture bez katalogu `guest/` przewraca się samo `cd`, a hook melduje
  **„found vulnerabilities"** i kończy 1. Stąd test 2 (zdrowy commit) i 3
  (usunięcie gałęzi) padają, a test 1 **„przechodzi" z tego samego powodu** —
  hook zwrócił 1, tyle że nie za sekret. To jest dokładnie klasa z Kroku 0
  mastera: skan, który padł, nie ma prawa podać wyniku.

Dopóki `test-gates.sh` nie daje **6/6 z niesprzecznych powodów**, raport **nie
ma prawa** twierdzić, że bramka sekretów jest egzekwowana.

### 9. Supply chain
Wg [`ci-cd.md`](ci-cd.md). CrossDesk: konwencja pinowania jest maszynowa
(`.github/zizmor.yml` — third-party = pełny SHA, `actions/*` i `github/*` mogą
zostać na tagu). To **świadome odstępstwo** od `ci-cd.md` §2, zaparkowane w
[`needs-owner.md`](../needs-owner.md) („hash-pin first-party?") — nie
raportuj ponownie jako nowe. Otwarte: brak lockfile'a Pythona (P2).

### 10. Delivery
Wersja pełna (`progressive-delivery.md`) **nie obowiązuje** — CrossDesk nie ma
produkcji ani serwisu (DEC-META-008 świadomie jej nie zaadoptował). Stosuje się
tylko część niezależna od deploymentu: wiek aktywnych gałęzi/WIP i szybki lane
CI. Analogonem „deploymentu" jest tu pipeline `crossdesk install`.

### 11. Provenance zmiany
Trailery `Intent` / `Task-Ref` / `Gates` — **tryb raportowy** (`commit-msg`
WARN-uje, nie blokuje). Ratchet do blokady czeka na właściciela
([`needs-owner.md`](../needs-owner.md)). **D-006: bez atrybucji AI** — obecność
`Co-Authored-By` / `AI-Contribution` w nowych commitach JEST findingiem
(historia przepisana 2026-07-07). Kadencja miesięczna pytania o zmianę tej
polityki obowiązuje.

### 13. Jedna derywacja + uczciwe procenty
CrossDeskowy wariant „uczciwych procentów" to **percentyle z histogramów, nie
EWMA**: `heartbeat_rtt_seconds` istniał jako nazwa w `MetricNames` bez
zapisującego, a FSM zwijał RTT do średniej i gubił rozkład (naprawione
`eca3a0c`). Sprawdzaj, czy metryka ma producenta i czy p50/p95 liczą się z
realnych próbek.

### 14. Higiena repo i ekspozycja na utratę danych
Sygnały mechaniczne: [`repo-hygiene-gates.md`](repo-hygiene-gates.md); liczby
zbiera `audit.sh`. Znane, otwarte pozycje CrossDeska — **nie zgłaszaj jako
nowe**: sprzątanie zmergowanych gałęzi na `origin` i gałęzi `ratunek/stash-*`
(oba czekają na decyzję właściciela — akcja na współdzielonym remote,
[`needs-owner.md`](../needs-owner.md)).

**Liczby z backlogu przelicz, nie przepisuj.** Wpis „17 zmergowanych gałęzi"
pochodzi z 2026-07-14; pomiar 2026-08-21 daje **2** (`git branch -r --merged`
minus `HEAD`/`main`) przy 26 refach zdalnych. Ten sam punkt 4 („dryf twierdzeń
liczbowych") stosuje się do backlogu, nie tylko do dokumentacji.
Punkt 14d (integralność referencyjna) ma tu precedens: `handoff.md` był
nietrackowanym scratchem i wypadł z drzewa, zostawiając martwe cytaty §2.7/§2.8
w `status.md` i `backlog.md`.

### 15. Aktualność zależności i runtime'ów
Reguły: [`dependency-currency.md`](dependency-currency.md). Bramka:
`bash .claude/templates/dependency-currency.sh` (szkielet — dopisz ekosystemy).
**Runtime po EOL = P0.** CrossDesk deklaruje `requires-python` na poziomie 3.9;
sprawdź **datę EOL wobec dzisiejszej** i czy deklaracja jest jedna
(`host/pyproject.toml` vs matryca CI vs box). Rust: baseline duplikatów to
`guest cargo-deny = 24` po bumpie otel (backlog P1) — wzrost względem
poprzedniego audytu to P2 z zapadką.

### 16. / 17. / 18. — wariant CrossDeska
Master pisze o deployu, dokumentach dziedzinowych i backupie bazy; CrossDesk
nie ma żadnego z nich, ale ma ich **odpowiedniki**, i to nie jest `n/a`:

- **16 (smoke musi móc zafailować)** → `install` deklarujący sukces, gdy domena
  tylko `is_running()`, jest dokładnie tym rytuałem (backlog P1: brak
  post-install wait). Asercja ma dotyczyć markera od agenta (Hello/heartbeat),
  nie faktu, że coś wstało.
- **17 (czy artefakt jest KANONICZNY)** → czy zmierzyliśmy to, co obiecuje
  kryterium. Precedens wzorcowy: `launch_duration_seconds` mierzy host-side
  **7,5 ms**, a kryterium #2 obiecuje użytkownikowi **2,75 s** do okna. Liczba
  była prawdziwa i **nie była tą liczbą**.
- **18 (czy kopia jest kopią)** → dysk VM i `export-state`. Precedens:
  30 GB backup leżał **wewnątrz** state-diru, który `uninstall()` kasuje
  `rmtree` — kopia ginęła razem z oryginałem (wykryte 2026-07-14, przeniesiona).

### 19. Druga opinia spoza pipeline'u
Wyrocznią CrossDeska są **budżety 12 kryteriów akceptacji** z
`docs/MVP_SCOPE.md` (≤3 s p50 launch, <20 ms p50 heartbeat, ≤90 s recovery,
≤25 min install). Baseline microbencha **musi być zmierzony**, nie wymyślony:
6 z 11 baseline'ów miało `0` (collect-only), a reszta do 66% luzu — bramka nie
bramkowała niczego (naprawione `7ee8b60`). Regresja +25% ma być łapana; jeśli
nie jest, to nie jest bramka.

### 26. Dane, które cicho kłamią — **punkt promowany stąd**

Ten punkt trafił do mastera **z CrossDeska** (2026-08-21): połknięte błędy
(`except: pass`), czas wykonania podany jako czas zdarzenia (`datetime.now()`
jako data dokumentu historycznego) i identyfikator jako licznik zamiast skrótu
żyły w starej, projektowej checkliście — czyli w pliku, którego `check` nie
widzi, bo nie jest kopią. Przy przepisywaniu na nakładkę wróciły do mastera
przez `promote`, więc obowiązują teraz całą flotę i wracają tu przez `update`.

To jest wzorzec do naśladowania: reguła ogólna **nie zostaje** w nakładce.

### 20.–25. Nowe warstwy (adopcja 2026-08-21)
- **20** [`quality-gates-and-dod.md`](quality-gates-and-dod.md) — katalog bramek
  z trybem i właścicielem; „gotowe" bez spełnionej definicji ukończenia to
  finding. Zestaw z tabelą 12 kryteriów w `PLAN.md`.
- **21** [`security-verification-gates.md`](security-verification-gates.md) —
  CrossDesk ma 7 skanerów (semgrep, CodeQL, gitleaks, bandit, pip-audit,
  cargo-audit, cargo-deny). Pytanie audytu brzmi **która z nich blokuje merge**,
  a która tylko raportuje. Otwarte: `gitleaks-action` v3 niepotwierdzona jako
  fail-closed (SEC-01, kanarek nieprzejechany) — do czasu przejazdu **nie
  twierdzimy**, że skanowanie sekretów jest egzekwowane.
- **22** [`test-evidence.md`](test-evidence.md) — projekt nazywa to
  „sentinel-verified": cofnij naprawę, test MUSI zrobić się czerwony. Stosowane
  m.in. przy `1b9c6f1` (spaced-filename) i A5 (freeze-test). Rób próbkę z
  ostatniego okresu.
- **23** [`pull-request-review.md`](pull-request-review.md) — CrossDesk merguje
  lokalnie, bez PR-ów i Issues na GitHubie (`AGENTS.md`). Czytaj przez
  odpowiedniki: śladem review jest commit merge'a + trailer `Gates:`, a scalenie
  bez zielonych bramek jest tym samym naruszeniem co merge bez review.
- **24** [`ci-pipeline-architecture.md`](ci-pipeline-architecture.md) — profil
  CrossDeska jest **hybrydowy** (hosted Actions + local-first mirror w
  `pre-push`; D-007 czeka na formalny podpis). Czytaj przez **§11a**, inaczej
  zaraportujesz „brak bramek" repo, które ma ich kilkanaście.
- **25** [`issue-reporting.md`](issue-reporting.md) — defekty CrossDeska trafiają
  do [`backlog.md`](../backlog.md) i [`status.md`](../status.md), nie do
  trackera. Wymóg reprodukcji i dowodu przed/po obowiązuje tam tak samo:
  pozycja bez kroków reprodukcji wraca do zgłaszającego, nie do backlogu.

---

## Priorytety

- **P0** — luki bezpieczeństwa, utrata integralności danych, kod kłamiący
  użytkownika, złamanie aktywnej decyzji o bezpieczeństwie/threat model, edycja
  proto bez aktualizacji THREAT_MODEL, **runtime po EOL**.
- **P1** — dług blokujący rozwój, ciche błędy (`except: pass`), brak testów
  ścieżek krytycznych, architectural drift, hardcoded values w produkcji (poza
  świadomymi mockami).
- **P2** — dead code, drift dokumentacji, kosmetyka, brakujące docstringi.

Każdy P0/P1/P2 i follow-up Security/Red Team **od razu** deduplikuj i zapisz do
[`backlog.md`](../backlog.md) (niejasny priorytet → `Inbox`). Zapis **nie jest**
rozpoczęciem naprawy.

## Ratchet — konkretne ścieżki

- Linter dochodzi do 0 → usuń `|| true` z odpowiedniego gate'a w
  `.githooks/pre-push` lub `.github/workflows/ci.yml`.
- Coverage wzrósł → podnieś próg w `pyproject.toml` / `Cargo.toml`.
- Nowa abstrakcja → dodaj do `audit.sh` grep-gate zabraniający bezpośrednich
  importów implementacji (wzorzec: licznik `libvirt_call`).
- Klasa higieny repo schodzi do zera → zamień `WARN` na blokadę
  ([`repo-hygiene-gates.md`](repo-hygiene-gates.md) „Ratchet").

Raz osiągnięty poziom = **podłoga, nie sufit**.

## Czego NIE robić w audycie

- Nie naprawiaj niczego z własnej inicjatywy. Audyt **diagnozuje**.
- Nie commituj poza `audit-log.md` (na branchu adopcji `audit.sh` może dodać
  wpis — dopuszczalne).
- Nie przebudowuj struktury plików (to robi `ADOPT.md`).
- Nie dotykaj boundary z `AGENTS.md` „File boundaries" (proto, THREAT_MODEL,
  DECISIONS, REQUIREMENTS, MVP_SCOPE, GOALS, ROADMAP, AGENTS.md) — flaguj jako
  P0/P1, właściciel decyduje.
- **Nie łataj kopii toolkitu w projekcie.** Poprawka idzie do mastera i wraca
  przez `update`. Nie dopisuj też reguł ogólnych do tego pliku — to jest
  nakładka, nie master.
