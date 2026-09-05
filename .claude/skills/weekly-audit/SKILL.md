---
name: weekly-audit
description: Przeprowadza cotygodniowy/okresowy audyt jakości kodu projektu — czystość, dead code, bezpieczeństwo, pokrycie testów, drift dokumentacji, zgodność z decyzjami. Użyj gdy właściciel prosi o audyt, przegląd jakości, sprawdzenie stanu kodu, lub gdy minęło >7 dni od ostatniego wpisu w audit-log. EN — run a weekly or periodic code quality audit of one project; use when the owner asks for an audit, a quality review, a repo health check, or when more than seven days passed since the last audit-log entry.
compatibility: Wymaga bash i git; kroki korzystające z GitHuba wymagają zalogowanego gh. Zaprojektowane dla agentów czytających SKILL.md (Claude Code i pokrewne).
metadata:
  author: claude-toolkit
  version: "2026.09.06"
---

# Cotygodniowy audyt jakości kodu

Cel: jakość rośnie monotonicznie. **Audyt wykrywa → naprawiamy → ratchet
zamraża → trend mierzy.** Audyt sam niczego nie naprawia — kończy się raportem
i listą działań, decyzję podejmuje właściciel.

Każdy raport porównuje metryki z poprzednim. Naruszenie security/risk
invariantu albo uzgodnionego progu jest **P1**; mały pojedynczy ruch metryki
bez potwierdzonego wpływu to P2/NOTE, aby nie tworzyć alarm fatigue. Każdy
potwierdzony incydent dopisuje stały punkt do checklisty — audyt rośnie z
postmortemów.

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

Zanim spojrzysz na kod. Audyt prowadzony na nieaktualnej checkliście sprawdza
wczorajsze ryzyka i melduje „czysto".

```sh
bash <toolkit>/scripts/toolkit-sync.sh check .
```

Reakcja zależy od wyniku, zgodnie z `conventions/toolkit-sync.md`:

| Wynik | Co robisz |
|---|---|
| kopie zgodne | prowadź audyt normalnie |
| **MASTER NOWSZY** | najpierw `update` osobnym commitem, potem audyt na nowej checkliście |
| **ZMIENIONY LOKALNIE** | nie nadpisuj. Zgłoś jako znalezisko: albo promocja do mastera, albo cofnięcie |
| brak `toolkit.lock` | projekt nigdy nie był stemplowany — `update` zakłada lock |

`check` porównuje **kopie**. Reguła dopisana do pliku, który kopią nie jest,
jest dla niego niewidzialna — tak checklista audytu urosła w jednym projekcie
z 14 do 17 pozycji przy zielonym `check` przez pięć tygodni. Dlatego dla
plików, które rozrosły się lokalnie (checklisty, rejestry, listy warstw),
uruchom też:

```sh
bash <toolkit>/scripts/toolkit-sync.sh contrib . <plik> [plik-w-masterze]
```

Zestawia tytuły pozycji po obu stronach i pokazuje, co ma tylko jedna.
Dopasowanie jest po tytule, więc przeredagowany nagłówek wygląda na nowy —
to sygnał do przeczytania, nie werdykt. Pozycja, która wyszła tylko po
stronie projektu, wraca do mastera przez `promote` (flagi: `--yes` bez
terminala, `--into` dla innego celu, `--new` dla świadomie nowego artefaktu).

**Przecięcia claimów.** Jeśli w repo pracuje więcej niż jeden agent, uruchom
także `bash <toolkit>/scripts/check-active-overlap.sh .` — claim scommitowany
na gałęzi feature jest niewidoczny z innej gałęzi aż do merge'a. Przecięcie =
przerwij i zapytaj, zanim dotkniesz tych plików.

Jeżeli **w trakcie audytu** powstanie nowa reguła, skill albo szablon, wykonaj
`promote` do mastera i podbij `VERSION` **w tej samej sesji**. Odłożona
promocja nie następuje — tak powstały trzy równoległe wersje jednego skilla.

Błędu w regule nie naprawiaj w kopii projektu. Poprawka idzie do mastera
i wraca przez `update`; załatana kopia jest początkiem następnego dryfu.

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
  workflow opisywany jako „zawsze działa” jest P1.
- Sprawdź CODEOWNERS/required review dla workflow/release, reusable workflows
  w `jobs.<id>.uses`, `workflow_run`, runner labels oraz repo Actions policy.
  Self-hosted runner z niezaufanym PR albo szerokie OIDC `sub`/`aud` to P1.
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
checklist z konwencji `test-quality-baseline.md` — w projekcie żyje jako reguła
(`.claude/rules/` albo `.claude/conventions/`); jeśli projekt jej nie ma,
dociągnij ją `toolkit-sync.sh update` (Krok 00), bo bez niej ta warstwa leci z pamięci
(14 własności, każda ze zmierzoną awarią za sobą: producent klasyfikujący
własną awarię, testy niemogące zniknąć po cichu, progi z pomiaru, meta-testy
bramek, lane split writerów, waity deterministyczne…). Wynik jedną linią
w audit-log (`test-baseline: 1✓ 2✗(plan) …`). **Brak własności = ostrzeżenie
+ obowiązkowy wpis planu w backlogu projektu** — nie automatyczne P1, ale
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

## Krok 3 — Raport + lista P0/P1/P2

- **P0** — krytyczne: luki bezpieczeństwa, utrata integralności danych, kod
  kłamiący użytkownika.
- **P1** — ważne: dług blokujący rozwój, ciche błędy, brak testów krytycznych ścieżek.
- **P2** — porządkowe: dead code, drift, kosmetyka.

Dopisz raport do `.claude/audit-log.md` (najnowszy na górze). Przedstaw listę
właścicielowi. Każdy P0/P1/P2 i follow-up Security/Red Team **od razu**
deduplikuj i zapisz do `.claude/backlog.md`; nie czekaj, aż właściciel o to
poprosi. Jeśli priorytet jest niejasny, użyj `Inbox`. Zapisanie nie uruchamia
naprawy — **czekaj na decyzję właściciela**, co implementujemy.

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
```

Accepted risk ma właściciela, uzasadnienie oraz expiry/review date. Bez zakresu,
SHA i dowodów raport nie może zakończyć się `PASS`.

## Krok 4 — Ratchet (po naprawie)

Gdy coś naprawione, natychmiast zamroź: usuń `|| true` z gate'a w pre-push gdy
linter dochodzi do 0; podnieś próg coverage; zapisz decyzję do `decisions.md`.
Raz osiągnięty poziom = podłoga, nie sufit.

## Krok 5 — Aktualizacja masterów (osobna zmiana, nie część read-only audytu)

Porównaj kopie skilli, agentów i konwencji z lokalnym `claude-toolkit`.
Nie wykonuj automatycznego `git pull` ani nadpisania podczas audytu. Zapisz
różnice do backlogu; zatwierdzony upgrade realizuje Builder na własnej gałęzi,
z review diffu. To chroni projekt przed automatycznym wstrzyknięciem zmienionych
instrukcji z toolkitu.

Pełna baza: `NEW-PROJECT.md` sekcja 9.2 oraz
`.claude/rules/rules-as-gates.md` (master w claude-toolkit).
