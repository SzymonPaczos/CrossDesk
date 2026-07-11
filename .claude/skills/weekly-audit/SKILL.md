---
name: weekly-audit
description: Przeprowadza cotygodniowy/okresowy audyt jakości kodu projektu — czystość, dead code, bezpieczeństwo, pokrycie testów, drift dokumentacji, zgodność z decyzjami. Użyj gdy właściciel prosi o audyt, przegląd jakości, sprawdzenie stanu kodu, lub gdy minęło >7 dni od ostatniego wpisu w audit-log.
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

## Krok 0 — SAST i workflowy (jeśli dostępne)

- Uruchom projektowy CodeQL/Semgrep/SAST, jeśli jest skonfigurowany. Brak
  narzędzia raportuj jako `n/a`, nigdy jako zero findings.
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

## Krok 2 — Warstwa głęboka (osąd agenta)

Skrypt liczy, Ty oceniasz. Przejrzyj i oceń:

1. **Bezpieczeństwo** — nowe endpointy bez rate-limit/walidacji, XSS (HTML
   z bazy renderowany bez sanityzacji), sekrety w repo, raw SQL z interpolacją
   user-inputu.
2. **Slop** — hardcoded dane w UI udające prawdziwe, mocki podane jako dane,
   funkcje oznaczone "gotowe" gdy są zaślepkami. Dla każdego trwałego
   `EmptyState` prześledź producer chain: UI → query → DB → loader; brak
   producenta danych jest tym samym kłamstwem piętro niżej. Odróżniaj
   fallback tymczasowy (producent istnieje, dane w drodze) od stanu
   permanentnego (producenta NIE MA — wydmuszka udająca gotową funkcję).
3. **Jakość testów** — nie *ile*, ale czy testują **właściwe** rzeczy:
   krytyczne ścieżki bez pokrycia, testy które nic nie weryfikują, skipped
   bez uzasadnienia.
4. **Architektura** — drift dokumentacja↔kod, duplikaty, martwe pola schematu,
   nieużywane eksporty, niespójne wzorce.
5. **Dead code** — zweryfikuj heurystykę skryptu greppem (sub-agenty mylą
   base-classy z dead code — zawsze potwierdź).
6. **Zgodność z rejestrem decyzji** (`decisions.md`) — złamana decyzja = P0/P1.
7. **Skille / MCP** — czy pojawiło się coś nowego co przyspieszy pracę.
8. **Gate'y** — czy `SKIP_*` jest per-warstwa; czy `exit 0` nie omija dalszych
   checków; czy gate sprawdza zmianę, a nie dowolny istniejący test; czy brak
   narzędzia/DB nie daje fałszywego sukcesu. Porównaj z
   `.claude/rules/rules-as-gates.md`.
9. **Supply chain** — lockfile, dependency bot/cooldown, secret protection,
   OIDC/trusted publishing i release/deploy według `.claude/rules/ci-cd.md`.
10. **Delivery** — wiek aktywnych branchy/WIP, szybki lane CI (<10 min jako
    cel), build-once/same digest, poprzedni artifact, health gate, bake,
    rollback drill, feature-flag expiry, SLO/error budget i release evidence.
    Porównaj z `.claude/rules/progressive-delivery.md`.
11. **Provenance zmiany** — próbka nietrywialnych commitów zawiera `Intent`,
    `Task-Ref`, `Gates`; task brief zgadza się z diffem, a review
    record/check jest związany z niezmienionym SHA. Sprawdź też, czy do
    commitów nie wróciła atrybucja AI (`AI-Contribution`, `Co-Authored-By`)
    wbrew D-006 — chyba że projekt ma zapisany wyjątek we własnym
    `decisions.md` (np. JawnePanstwo jawnie deklaruje użycie AI); wtedy
    pilnuj odwrotnie: atrybucja MA być. **Raz w miesiącu** zadaj
    właścicielowi pytanie, czy chce zmienić politykę oznaczania udziału AI;
    odpowiedź (także „nie") zapisz w `decisions.md` z datą.
12. **Vulnerability response** — kanał disclosure, wspierane wersje, owner
    triage, otwarte advisories i root-cause→test/gate po incydencie. Dla
    prywatnego repo dopuszczalny jest prywatny runbook zamiast `SECURITY.md`.
13. **Jedna derywacja + uczciwe procenty** — byt renderowany w ≥2 widokach
    czerpie stan z JEDNEJ kanonicznej funkcji derywacji, nie liczy go osobno
    per widok (osobne wyliczenia = widoki, które się rozjadą). Każdy procent
    bez mianownika renderuje „Brak danych" — nigdy `x/0` ani `NULL→0`
    udające zero. (Wkład z audytu JawnePanstwo, 2026-07-11.)

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
EXCLUSIONS_OR_NA: <reasoned list>
THREAT_MODEL_VERSION: <ref>
SECURITY_REVIEW: PASS | FAIL | ACCEPTED_RISK <decision-id> | BLOCKED
RED_TEAM: PASS | FINDINGS | NOT_DUE <last-run-date>
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
