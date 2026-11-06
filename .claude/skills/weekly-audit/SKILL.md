---
name: weekly-audit
description: Przeprowadza cotygodniowy/okresowy audyt jakości kodu projektu — czystość, dead code, bezpieczeństwo, pokrycie testów, drift dokumentacji, zgodność z decyzjami. Użyj gdy właściciel prosi o audyt, przegląd jakości, sprawdzenie stanu kodu, lub gdy minęło >7 dni od ostatniego wpisu w audit-log. EN — run a weekly or periodic code quality audit of one project; use when the owner asks for an audit, a quality review, a repo health check, or when more than seven days passed since the last audit-log entry.
compatibility: Wymaga bash i git; kroki korzystające z GitHuba wymagają zalogowanego gh. Zaprojektowane dla agentów czytających SKILL.md (Claude Code i pokrewne).
metadata:
  author: claude-toolkit
  version: "2026.11.07"
---

# Cotygodniowy audyt jakości kodu

Cel: jakość rośnie monotonicznie. **Audyt wykrywa → naprawiamy → ratchet
zamraża → trend mierzy.** Audyt sam niczego nie naprawia — kończy się raportem
i listą działań, decyzję podejmuje właściciel.

Każdy raport porównuje metryki z poprzednim. Naruszenie security/risk
invariantu albo uzgodnionego progu ma wpływ **high**; mały pojedynczy ruch
metryki bez potwierdzonego wpływu to `low`/NOTE, aby nie tworzyć alarm fatigue. Każdy
potwierdzony incydent prowadzi najpierw do oceny istniejącej ochrony. Nowy
stały punkt wymaga luki o powtarzalnym skutku, braku odpowiednika i sposobu
sprawdzenia; nieaktualne albo dublujące punkty mają propozycję usunięcia.

**Wymóg tygodniowy:** każdy audyt uruchamia niezależnego
`.claude/agents/security-reviewer.md`. Security Reviewer jest read-only, nie
naprawia swoich findings i kończy jednoznacznym verdict. Jeśli definicji lub
reguły brakuje, audyt raportuje `DEGRADED` i zapisuje zadanie do backlogu;
**nie kopiuje sam reguł bezpieczeństwa przed własną oceną**. Kopię/upgrade
wykonuje Builder w osobnym, reviewowanym commicie.

Projekt wybiera przy adopcji mechanizm przypomnienia zgodnie ze swoim
profilem CI (D-007 — profil ustala się pytaniem do właściciela, bez
założeń): local-first → preflight w pre-push sprawdzający datę albo
launchd/cron; hosted CI → workflow tworzący issue. Przy każdej zmianie
mutującej startup/merge preflight sprawdza datę. Jeśli minęło >7 dni, `READY_TO_MERGE` pozostaje
`BLOCKED` do Security Review albo jawnej decyzji właściciela o wyjątku.

## Krok 00 — Wersja toolkitu (ZAWSZE PIERWSZY)

Zapis `konwencja:<plik>.md` oznacza przyjętą kopię, nie literalną ścieżkę.
Dla każdego pliku znajdź w locku źródło `conventions/<plik>.md` (kolumna 3)
i odpowiadającą ścieżkę projektu (kolumna 2), pomocniczo mapę AGENTS.md.
Projekt może mieszać lokalizacje. Brak pliku, dwie kopie lub rozbieżność
mapy z lockiem są znaleziskiem; audyt nie migruje własnych instrukcji.

Zanim spojrzysz na kod. Audyt prowadzony na nieaktualnej checkliście sprawdza
wczorajsze ryzyka i melduje „czysto".

```sh
bash <toolkit>/scripts/toolkit-sync.sh check .
```

Reakcja zależy od wyniku, zgodnie z `conventions/toolkit-sync.md`:

| Wynik | Co robisz |
|---|---|
| kopie zgodne | prowadź audyt normalnie |
| **MASTER NOWSZY / ADOPCJA WYMAGANA** | odnotuj wersje i zakres zmian; audytuj rezultaty i bieżące ryzyka według przyjętej wersji, nowe zakresy oznacz jako niesprawdzone; upgrade jest osobnym zadaniem Buildera |
| **ADOPCJA NIEZAMKNIĘTA** | zgłoś niezamknięty upgrade; oceniaj niezależne zakresy, a zależne od niespójnych instrukcji oznacz jako niesprawdzone; nie kończ audytu samą aktualizacją reguł |
| **ZMIENIONY LOKALNIE** | nie nadpisuj. Zgłoś jako znalezisko: albo promocja do mastera, albo cofnięcie |
| brak `toolkit.lock` | projekt nigdy nie był stemplowany — `update` zakłada lock |

`check` porównuje **kopie**. Reguła dopisana do pliku, który kopią nie jest,
jest dla niego niewidzialna — tak checklista audytu urosła w jednym projekcie
z 14 do 17 pozycji przy zielonym `check` przez pięć tygodni. Dla plików, które
rozrosły się lokalnie (checklisty, rejestry, listy warstw), oraz dla repo,
w którym pracuje więcej niż jeden agent, mechanikę porównania i promocji
opisuje [`references/toolkit-sync-w-audycie.md`](references/toolkit-sync-w-audycie.md).
Wczytaj ten plik, gdy `check` pokaże cokolwiek poza „kopie zgodne".

### Źródło dokumentacji (zanim zaczniesz twierdzić o wersjach)

Sprawdź, czy masz podłączone **źródło aktualnej dokumentacji** — serwer MCP
typu Context7 albo równoważny. To jest sprawdzenie narzędzia audytu, dlatego
stoi tu, obok wersji checklisty: audyt orzekający o wersjach z pamięci modelu
melduje stan sprzed daty odcięcia i nie ma jak tego zauważyć od środka.

| Stan | Co robisz |
|---|---|
| **dostępne** | używasz go do **każdego** twierdzenia o API, konfiguracji i wersji — również gdy „znasz odpowiedź". Zapisujesz `DOCS_SOURCE: <nazwa>` |
| **niedostępne** | zapisujesz `DOCS_SOURCE: n/a (pamięć modelu, odcięcie <data>)`, **prosisz właściciela o udostępnienie źródła** i zapisujesz zadanie do backlogu |

Bez źródła audyt nadal jest ważny — traci tylko prawo do podawania numeru
wersji, daty wydania i statusu wsparcia **jako faktu**. Takie pozycje
raportujesz wtedy jako niesprawdzone, nie pomijasz ich po cichu.

## Krok 0a — Rezultaty pracy i ciągłość zadań

Sprawdź kierunek pracy przed szczegółową listą zgodności. Porównaj uzgodnione
cele, etapy odbioru, backlog i dowody dostarczenia z ostatnich 7 dni.
Przy zastoju lub niewyjaśnionym trendzie rozszerz historię rezultatów do
21 dni, bez ponawiania całej suity. Źródłem zakresu jest przyjęte zadanie lub brief;
git i artefakty potwierdzają wykonanie. Brak źródeł oznacza nieweryfikowany
zakres, nie brak problemu. Dla krótszego projektu podaj rzeczywiste okno.

Wynik obejmuje:

- oczekiwany rezultat, wykonane etapy, pozostałe ID, ostatni dowód i blokadę;
- deklarowane zamknięcia rodziców: porównanie ze wszystkimi etapami, także
  odłożonymi przy zmianie tematu; zieleń ostatniego etapu nie zamyka całości;
- czy zmiany instrukcji, audyty i powtórki testów wspierają uzgodniony cel,
  czy wypierają go bez decyzji właściciela. Historia ścieżek i liczby commitów
  są wskazówką do oceny, nie pomiarem czasu, wartości ani intencji;
- zasadność powtórek na próbce logów testów/CI: czy zmienił się kod, wykryto
  awarię lub pozostało ryzyko. Czas i koszt tylko z pomiaru; brak logów = `n/a`.
- przy zleceniu pracy rojem: czy gotowe, upoważnione zadania dostały
  rzeczywistych wykonawców (identyfikatory uruchomień), albo mają konkretny
  powód oczekiwania; sam plan przydziału nie potwierdza uruchomienia;
- po potwierdzonych scaleniach: czy integrator usunął czyste, nieużywane
  worktree zadania, a pozostawione mają powód i dalszego właściciela.
  Push i otwarty PR nie są scaleniem; brudnego lub używanego drzewa nie usuwaj.

Security, utrzymanie, testy i migracje mogą być uzgodnionym rezultatem.
Sam udział plików testowych lub brak nowej funkcji nie jest znaleziskiem.
Znalezisko wymaga wskazania niezrealizowanego celu, dowodów dryfu i jego
skutku; uzasadnioną blokadę raportuj osobno. Audyt proponuje najmniejszą
korektę procesu, bez automatycznego dokładania reguły lub kolejnej suity.
Nie wymaga przeglądania surowych rozmów ani kopiowania ich do repozytorium.

## Krok 0 — SAST i workflowy (jeśli dostępne)

- Uruchom projektowy CodeQL/Semgrep/SAST, jeśli jest skonfigurowany. Brak
  narzędzia raportuj jako `n/a`, nigdy jako zero findings.
- **Skan, który padł, nie ma prawa podać liczb.** „Brak narzędzia = n/a" nie
  łapie gorszego przypadku: skanu, który wystartował i umarł w połowie.
  Trzy niezależne guardy, bo każdy z osobna zawodzi: (a) kod wyjścia ≠ 0
  kończy audyt jako `BLOCKED`; (b) fatal w logu **mimo** kodu 0 (narzędzie
  potrafi zwrócić sukces po nieudanej analizie) też jest awarią; (c) plik
  wynikowy musi być świeży i parsowalny — inaczej podsumowanie policzy się
  z zeszłotygodniowego artefaktu i wygląda dokładnie jak czysty skan.
  Brak liczb to `BLOCKED`, nie „0 findings". (Wkład z JawnePanstwo,
  2026-08-19: fatal „Query pack cannot be found" + exit 0 + liczby ze
  SARIF-a z poprzedniego tygodnia; dziś pilnuje tego test na skrypcie skanu.)
- Jeśli istnieje `.github/workflows/`, uruchom `zizmor` (lub równoważny
  linter) i sprawdź: pełne SHA w `uses:`, minimalne `permissions`, expression
  injection, `pull_request_target`, sekrety w jobach z niezaufanym kodem.
- Sprawdź, czy dokumentacja triggerów zgadza się z realnym YAML-em. Wyłączony
  workflow opisywany jako „zawsze działa” ma wpływ `high`.
- Sprawdź CODEOWNERS/required review dla workflow/release, reusable workflows
  w `jobs.<id>.uses`, `workflow_run`, runner labels oraz repo Actions policy.
  Self-hosted runner z niezaufanym PR albo szerokie OIDC `sub`/`aud` ma wpływ
  co najmniej `high`.
- Uruchom Security Review niezależnym kontekstem. Dołącz verdict i findings z
  attack path do raportu. Jeśli minął miesiąc od ostatniego Red Team albo
  zmienił się auth/secrets/workflow/deploy/model zagrożeń, uruchom również
  `.claude/agents/red-team.md`. Brak definicji = `DEGRADED` + backlog task;
  nie kopiuj instrukcji podczas read-only audytu.

## Krok 1 — Warstwa statyczna

Jeśli projekt ma `.claude/audit.sh` — uruchom `bash .claude/audit.sh` w
worktree dokładnie ocenianego SHA. Brak zależności skonfiguruj przed audytem
albo raportuj `BLOCKED/n-a`; nie przełączaj się na inny working tree tylko
dlatego, że ma `node_modules`.
Jeśli nie ma — policz ręcznie: błędy lintera (eslint/ruff/...), liczba
TODO/FIXME, liczba plików testowych, moduły bez importera (`grep -rl`).

**Jakość suity testowej — własności, nie liczba plików.** Liczba plików
testowych mierzy pojemniki; o ochronie decydują WŁASNOŚCI suity. Przejdź
checklist z `konwencja:test-quality-baseline.md`. Brak przyjętej kopii
zgłoś jako niezweryfikowany zakres do adopcji przez Buildera; `update`
nie instaluje nieprzyjętej konwencji. Materiał obejmuje
14 własności, każda ze zmierzoną awarią za sobą: producent klasyfikujący
własną awarię, testy niemogące zniknąć po cichu, progi z pomiaru, meta-testy
bramek, lane split writerów, waity deterministyczne. Wynik jedną linią
w audit-log (`test-baseline: 1✓ 2✗(plan) …`). **Brak własności = ostrzeżenie
+ obowiązkowy wpis planu w backlogu projektu** — bez automatycznego
podnoszenia wpływu, ale
cisza czyta się jak zieleń. Świadome „nie dotyczy" z powodem zapisuje się raz.

**Trend zdrowia kodu między audytami.** Metryki wyżej są migawką; delta mówi
o kierunku. Jeśli projekt ma narzędzie deltowe (CodeScene `cs delta <base>
HEAD` albo równoważne), uruchom je **report-only** — degradację ocenia agent
warstwy głębokiej, nie próg: deklaratywna tabela konfiguracji to nie „chora
metoda", ale rosnąca złożoność cyklomatyczna w orkiestratorze już tak.
Narzędzia nie ma? Raport odpowiada wprost **mamy / planujemy / świadome
n/a** — ta sama zasada co przy SAST: przemilczenie czyta się jak zieleń.

## Krok 2 — Warstwa głęboka (osąd agenta)

Skrypt liczy, Ty oceniasz. Pełna lista punktów kontroli głębokiej — wraz
z uzasadnieniami i wkładami z konkretnych audytów — leży w
[`references/kontrola-glebokosci.md`](references/kontrola-glebokosci.md).
**Wczytaj ten plik przed oceną.** Ocena z pamięci listy pomija punkty dopisane
po ostatnim postmortemie, czyli dokładnie te, które ktoś już przerobił na
własnej szkodzie.

## Krok 2b — Kontrola nawrotów (pozycje zamknięte od ostatniego audytu)

Pozycja backlogu zamyka się dopiero, gdy jej `BRAMKA_ZAMYKAJACA` jest zielona,
a commit niesie `Task-Ref:` z jej identyfikatorem. To znaczy, że **domknięcie
da się sprawdzić ponownie** — i trzeba, bo naprawa bez testu regresji wraca.

Dla każdej pozycji dopisanej do `.claude/history/completed-work.md` po dacie
poprzedniego audytu:

1. odczytaj jej `BRAMKA_ZAMYKAJACA` z wpisu w historii;
2. uruchom tę komendę;
3. **czerwona = nawrót.** Pozycja wraca do `.claude/backlog.md` ze `STATUS:
   otwarte`, adnotacją „nawrót, poprzednio zamknięta <data>" i wpływem
   podniesionym o jeden stopień — problem, który wrócił, jest droższy niż
   problem, który nigdy nie został zamknięty;
4. odstępstwo po terminie `PRZEGLAD` traktuj tak samo jak czerwoną bramkę.

Sprawdzaj wyłącznie pozycje zamknięte **od poprzedniego audytu**. Ponowne
przemielenie całej historii przy każdym przebiegu jest kosztowne i szybko
zostanie wyłączone, a wyłączona bramka nie chroni przed niczym.

Brak `completed-work.md` albo brak zamkniętych pozycji → `CLOSURE_RECHECK: n/a`.
To nie jest błąd; projekt mógł niczego nie domknąć w tym tygodniu.

## Krok 3 — Raport wpływu + kolejka działań

- **critical** — luki bezpieczeństwa, utrata integralności danych, kod
  kłamiący użytkownika.
- **high** — dług blokujący rozwój, ciche błędy, brak testów krytycznych ścieżek.
- **medium** — potwierdzony problem o ograniczonym wpływie.
- **low** — dead code, drift i kosmetyka bez potwierdzonego większego wpływu.

Pozycja podaje stan, wpływ i dowód według `rules-as-gates.md` punkt 9.
Zdanie, tabela lub pola maszynowe mogą nieść te informacje; identyfikator
zostaje do odwołań i nie zastępuje opisu naruszenia.

Dopisz raport do `.claude/audit-log.md` (najnowszy na górze). Przedstaw listę
właścicielowi. Każde znalezisko i follow-up Security/Red Team **od razu**
deduplikuj i zapisz do `.claude/backlog.md`; nie czekaj, aż właściciel o to
poprosi. Ułóż `Do wykonania` według decyzji właściciela i zależności; gdy
zakres nie jest ustalony, użyj `Inbox`. Wpływ nie steruje automatycznie
kolejnością. Zapisanie nie uruchamia naprawy — **czekaj na decyzję
właściciela**, co implementujemy.
Kolejność w `Do wykonania` układa właściciel, a skill `plan-naprawy` ją
proponuje; audyt jej nie ustala.

Pozycja zapisywana do backlogu ma kształt z `backlog-contract.md`: nagłówek
`### <ID> — <tytuł>` i siedem pól. Dwa z nich audyt wypełnia z tego, co i tak
właśnie zmierzył: `DOWOD` to komenda albo ścieżka z linią, którą znalazłeś,
a `BRAMKA_ZAMYKAJACA` to komenda, która jest teraz czerwona i zzielenieje po
naprawie. Wpisanie ich później kosztuje drugie przejście przez kod.

Raport zawiera obowiązkowo:

```text
AUDITED_REVISION: <full SHA>
DIFF_RANGE_OR_SCOPE: <...>
PREVIOUS_AUDIT: <date/ref>
TOOLS: <commands + versions + evidence URLs>
DOCS_SOURCE: <nazwa serwera dokumentacji | n/a (pamięć modelu, odcięcie <data>)>
DEPENDENCY_CURRENCY: OK | REPORT <n przeterminowanych> | EOL <runtime> | n/a
EXCLUSIONS_OR_NA: <reasoned list>
THREAT_MODEL_VERSION: <ref>
SECURITY_REVIEW: PASS | FAIL | ACCEPTED_RISK <decision-id> | BLOCKED
RED_TEAM: PASS | FINDINGS | NOT_DUE <last-run-date>
SAST: <tool+version, findings> | BLOCKED <reason> | n/a (not configured)
CODE_HEALTH_DELTA: <tool, delta vs previous audit> | planned | n/a (no tooling)
BACKLOG_WRITE: recorded <task refs> | none
CLOSURE_RECHECK: <n sprawdzonych>, <n nawrotów> | n/a (brak zamkniętych pozycji)
SUPERSEDED: <n pozycji unieważnionych decyzją, każda ze wskazaniem która decyzja> | brak
UI_COPY: BLOCKING <n>, REVIEW <n>, FABRICATED <n> | n/a (brak warstwy widoku)
AGENTIC_PITFALLS: <sprawdzonych>/8; trafienia opisane ZDANIEM, nie numerem
AGENTIC_STACK: <odchylenia od tabeli zaleceń, każde jednym zdaniem „używaj X zamiast Y, bo Z" | zgodny>
DOMAIN_CONTRACT: <n miejsc opisujących jeden byt> | n/a
STOS: <pełna tabela z stan-stosu.sh — także wiersze BRAK>
STOS_ODSTEPSTWA: <każde jednym zdaniem „używaj X…" | brak — stos zgodny z zasadami>
REJESTR_REGUL: <n> reguł: <n> sprawdzonych bramką (<n> czerwonych), <n> czytanych, <n> nie dotyczy
CONTEXT: zawsze <N> B, handoff <N> B/<n> sekcji, Codex mediana <N>/żądanie (sesje >60: <n>), Claude mediana <N>, MCP nieużywane: <lista> | n/a <powód>
DELIVERY_REVIEW: <okno 7/21 dni, cele, dowody, pozostałe etapy, blokady> | UNVERIFIED <brak źródeł>
TASK_COMPLETENESS: <sprawdzone zamknięcia rodziców, otwarte etapy> | UNVERIFIED <powód> | n/a <brak zamknięć>
PROCESS_DRIFT: <dryf celu i skutek, uzasadnione utrzymanie, zbędne powtórki> | CLEAR <dowody> | UNVERIFIED <powód>
```

Cztery pola agentowo-interfejsowe wypełnia się z kontroli głębokiej, punkty
27–30.

**Raport nie jest listą braków.** Braki wychodzą z audytu; raport ma pokazać
stan faktyczny — czym ten projekt jest napisany i co która reguła w nim
zobaczyła. Właściciel kilku dużych repozytoriów nie pamięta, w którym stoi
Astro, a w którym Next, gdzie jest Pydantic, a gdzie sam TypeScript. Raport,
który o tym milczy, bo „wszystko w porządku", każe pracować w ciemno.

Dlatego dwa pola są **pełne, nie skrócone do znalezisk**:

- `STOS` to cała tabela z `stan-stosu.sh`, **razem z wierszami BRAK**. „Prisma
  BRAK" jest wiadomością tak samo jak „Drizzle JEST".

  **Nigdy nie skracaj tej tabeli** — ani do „najciekawszych wierszy", ani do
  porównania między projektami, ani do samych odstępstw. Przy kilku
  repozytoriach właściciel czyta ją, żeby sprawdzić, czy w tym konkretnym jest
  TypeScript, Pydantic i czym stoi widok; wiersz wycięty jako „nieciekawy" to
  dokładnie ten, po który sięgnął. Tabela porównawcza między projektami może
  stać obok, ale **nie zamiast** trzech pełnych tabel — jedna na projekt.
- `REJESTR_REGUL` obejmuje wszystkie konwencje z `rejestr-regul.sh` i zachowuje
  ich rzeczywiste statusy. Raport odróżnia zaliczenie, naruszenie, brak
  wykonania i brak zastosowania oraz wskazuje metodę: bramka lub review.
  `BRAK BRAMKI`, `NIE DOKONCZYLA` i `DO ZROBIENIA` nie są zaliczeniem.
  `CZYTANA` oznacza przypisanie do oceny przez czytanie. Wykonany przegląd
  ma wskazanego oceniającego i sprawdzony materiał; sam status go nie potwierdza.

Liczba reguł czytanych, a nie sprawdzanych bramką, jest **sama w sobie
pomiarem** — mówi, ile z tego raportu stoi na czyimś słowie.

**Te pola pisze się zdaniem, nie kodem.** `AGENTIC_PITFALLS: trafienia #1, #5`
nie mówi nic czytelnikowi, który nie ma przed sobą listy — a raport czyta się
tydzień później, bez niej. Zamiast tego: „dwa runtime'y agenta trzymają stan
w osobnych magazynach" oraz „schemat stanu grafu nie ma wersji, więc zmiana
pola urwie trwające wątki". Ta sama zasada dotyczy wpływu: `critical` w tabeli
jest w porządku, ale zdanie obok ma mówić, **co się stanie**, a nie jak bardzo
boli w skali. `AGENTIC_PITFALLS` mniejsze niż 8 przy istniejącym agencie znaczy, że
lista nie została przejrzana — a nie że pułapek nie ma. `DOMAIN_CONTRACT`
większe niż 1 znaczy konteksty zamiast kontraktu i jest znaleziskiem samo
w sobie, nawet gdy nic jeszcze nie boli.

Accepted risk ma właściciela, uzasadnienie oraz expiry/review date. Bez zakresu,
SHA i dowodów raport nie może zakończyć się `PASS`.
`UNVERIFIED`, `SKIP` i brak wykonania nie są zaliczeniem. Werdykt wymienia
sprawdzone zakresy; luka w ocenie dostarczania pracy wyklucza ogólne „projekt
zdrowy”, nawet gdy uruchomione bramki kodu są zielone. To nie nakaz
zatrzymania niezależnej pracy nad produktem.

## Krok 4 — Ratchet (po naprawie)

Po naprawie dobierz ochronę dla przyczyny awarii. Zaostrzenie bramki wymaga
sprawdzenia skuteczności i kosztu; sam wzrost coverage lub liczby testów nie
jest poprawą. Zachowaj wymagane kontrole bezpieczeństwa i kontraktów, oceniaj
usunięcie dublujących prób według `test-execution-economy.md`.

## Krok 5 — Aktualizacja masterów (osobna zmiana, nie część read-only audytu)

Porównaj kopie skilli, agentów i konwencji z lokalnym `claude-toolkit`.
Nie wykonuj automatycznego `git pull` ani nadpisania podczas audytu. Zapisz
różnice do backlogu; zatwierdzony upgrade realizuje Builder na własnej gałęzi,
z review diffu. To chroni projekt przed automatycznym wstrzyknięciem zmienionych
instrukcji z toolkitu.

Pełna baza: `NEW-PROJECT.md` sekcja 9.2 oraz
`konwencja:rules-as-gates.md` (master w claude-toolkit).
