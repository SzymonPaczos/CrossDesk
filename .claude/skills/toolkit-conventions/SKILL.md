---
name: toolkit-conventions
description: Korpus konwencji cross-project claude-toolkit — architektura, granice runtime, kontrakty API, formularze, bramki CI/CD i bezpieczeństwa, dowód z testu, gotowość PR, zgłoszenia, aktualność zależności, prywatność zasobów zewnętrznych. Ten skill jest mapą, nie streszczeniem — wskazuje, który plik reguł wczytać do danego zadania. Użyj gdy piszesz lub recenzujesz kod, projektujesz bramkę, przygotowujesz PR albo zgłoszenie i chcesz oprzeć decyzję na regule, a nie na wyczuciu. EN — cross-project engineering conventions as a router skill; each rule lives in its own reference file. Use when writing or reviewing code, designing a CI gate, preparing a pull request or an issue, and you need the written rule rather than an opinion.
compatibility: Same reguły są stack-agnostic; przykłady sięgają po TypeScript, Python i GitHub Actions. Nie wymaga narzędzi poza czytaniem plików.
metadata:
  author: claude-toolkit
  version: "2026.11.07"
---

# Korpus konwencji claude-toolkit

Ten skill **nie zawiera reguł — zawiera mapę**. Każda reguła żyje w jednym
pliku w [`references/conventions/`](references/conventions/), a szablony
w [`references/templates/`](references/templates/).

Streszczanie reguł w tym pliku jest zakazane. Dwa opisy tej samej reguły
rozjeżdżają się przy pierwszej zmianie, a czytający nie ma jak zauważyć,
który z nich jest nieaktualny.

## Jak tego używać

1. Wybierz z mapy plik dotyczący zadania i odczytaj jego aktualną treść.
2. Konwencje odsyłają do siebie nawzajem zwykłymi linkami. Idź za odsyłaczem,
   gdy zadanie dotyka granicy dwóch tematów.
3. Przy pracy nad bramką sprawdź zakres, kryteria dowodu i sposób egzekwowania
   opisany w danej konwencji. Sekcje mają nazwy właściwe dla tematu.
4. Projekt ma własne kopie w `.claude/conventions/` lub `.claude/rules/`. Kopia
   projektu wygrywa z tym skillem, bo mogła zostać świadomie zamrożona —
   rozstrzyga [`references/conventions/toolkit-sync.md`](references/conventions/toolkit-sync.md).

## Reguły według etapu zadania

| Plik | Kiedy |
| --- | --- |
| [`local-gate-orchestration.md`](references/conventions/local-gate-orchestration.md) | zamki klas, sloty ciężkich biegów i nadzór procesów na współdzielonej maszynie |
| [`change-provenance.md`](references/conventions/change-provenance.md) | każdy commit — `Intent` / `Task-Ref` / `Gates` |
| [`rules-as-gates.md`](references/conventions/rules-as-gates.md) | projektowanie, zmiana lub audyt bramki |
| [`instruction-style.md`](references/conventions/instruction-style.md) | zanim napiszesz lub zmienisz plik instrukcji dla agenta |
| [`quality-gates-and-dod.md`](references/conventions/quality-gates-and-dod.md) | zanim uznasz funkcjonalność za ukończoną |

## Mapa: zadanie → plik

**Projektowanie i struktura kodu**

| Zadanie | Plik |
| --- | --- |
| granica zmiany, granica zaufania, test decyzji projektowej | [`architecture-principles.md`](references/conventions/architecture-principles.md) |
| moduły, funkcje, klasy, cykle, abstrakcje przedwczesne | [`code-structure.md`](references/conventions/code-structure.md) |
| nazwy plików, katalogów i symboli, leksykon, wprowadzanie konwencji nazw | [`naming-conventions.md`](references/conventions/naming-conventions.md) |
| ścieżki importu, alias zamiast `../../`, konfiguracja aliasu w narzędziach | [`module-paths.md`](references/conventions/module-paths.md) |
| co należy do serwera, co do klienta, co trafia do bundla | [`runtime-boundaries.md`](references/conventions/runtime-boundaries.md) |
| warstwy backendu, domena, transakcje, outbox | [`backend-layers.md`](references/conventions/backend-layers.md) |
| warstwy frontendu, dekompozycja komponentów, rodzaje stanu | [`frontend-architecture.md`](references/conventions/frontend-architecture.md) |
| co się łączy, co się wyklucza, pary wykluczające się w stacku | [`stack-composition.md`](references/conventions/stack-composition.md) |
| zmiana architektury, migracja danych, taksonomia awarii przed decyzją | [`architecture-change.md`](references/conventions/architecture-change.md) |
| tryb strict, dane z granicy jako `unknown`, unie rozłączne | [`typescript-javascript.md`](references/conventions/typescript-javascript.md) |

**Kontrakty i dane**

| Zadanie | Plik |
| --- | --- |
| kontrakt API, kształt błędu, idempotencja, paginacja, wersjonowanie | [`api-contract-design.md`](references/conventions/api-contract-design.md) |
| formularz, walidacja, mapowanie błędów na pola, dostępność komunikatu | [`forms-and-validation.md`](references/conventions/forms-and-validation.md) |
| błędy, retry, timeouty, logi, trace, budżet błędu | [`reliability-and-observability.md`](references/conventions/reliability-and-observability.md) |
| kanon kształtu, derywacje, jedno źródło prawdy o kontrakcie | [`contract-canon.md`](references/conventions/contract-canon.md) |
| dane trwałe, retencja tabel rosnących, klucze i niezmienniki | [`data-modeling.md`](references/conventions/data-modeling.md) |
| praca długotrwała, dzierżawa zlecenia, cykl życia zadania w tle | [`background-work.md`](references/conventions/background-work.md) |

**Wygląd i zasoby zewnętrzne**

| Zadanie | Plik |
| --- | --- |
| tokeny, paleta, kontrast, dostępność jako wymóg | [`design-system-foundations.md`](references/conventions/design-system-foundations.md) |
| teksty interfejsu, zakazana nowomowa, dane których nie wolno wymyślić | [`ui-copy.md`](references/conventions/ui-copy.md) |
| fonty, ikony, CDN, RODO, self-hosting zasobów | [`third-party-assets-privacy.md`](references/conventions/third-party-assets-privacy.md) |

**Dowód, review, zgłoszenia**

| Zadanie | Plik |
| --- | --- |
| czy pojedynczy test cokolwiek dowodzi; weryfikacja negatywna | [`test-evidence.md`](references/conventions/test-evidence.md) |
| rejestr czerwieni jako dane, lista długu z sufitem, liczby generowane | [`negative-verification.md`](references/conventions/negative-verification.md) |
| czy CAŁA suita testowa chroni; 14 własności audytowanych co tydzień | [`test-quality-baseline.md`](references/conventions/test-quality-baseline.md) |
| zakres testów, powtórki i koszt kontekstu bez utraty dowodu | [`test-execution-economy.md`](references/conventions/test-execution-economy.md) |
| gotowość PR, preflight, odpowiedź na review | [`pull-request-review.md`](references/conventions/pull-request-review.md) |
| zgłoszenie defektu, reprodukcja, dowód przed/po | [`issue-reporting.md`](references/conventions/issue-reporting.md) |

**Bramki, CI/CD, wydania**

| Zadanie | Plik |
| --- | --- |
| bezpieczny baseline pipeline'u, SHA-pinning, lockfile, release | [`ci-cd.md`](references/conventions/ci-cd.md) |
| topologia bramek, podział twarde/miękkie, audyt pipeline'u | [`ci-pipeline-architecture.md`](references/conventions/ci-pipeline-architecture.md) |
| SAST, SCA, sekrety, IaC, DAST — co blokuje scalenie | [`security-verification-gates.md`](references/conventions/security-verification-gates.md) |
| EOL runtime'u, dystans wersji, źródło dokumentacji | [`dependency-currency.md`](references/conventions/dependency-currency.md) |
| katalog bramek, tryby, odstępstwa, definicja ukończenia | [`quality-gates-and-dod.md`](references/conventions/quality-gates-and-dod.md) |
| mechaniczne gate'y higieny repozytorium | [`repo-hygiene-gates.md`](references/conventions/repo-hygiene-gates.md) |
| canary, bake, SLO, metryki DORA | [`progressive-delivery.md`](references/conventions/progressive-delivery.md) |
| praca z produkcją, upoważnienie, runbooki | [`production-operations.md`](references/conventions/production-operations.md) |

**Proces i narzędzia**

| Zadanie | Plik |
| --- | --- |
| role delivery team, izolacja kontekstów, dane vs polecenie | [`multi-agent-delivery.md`](references/conventions/multi-agent-delivery.md) |
| statusy narzędzi, tryb cienia, optymalizacja po pomiarze | [`tool-adoption-and-measurement.md`](references/conventions/tool-adoption-and-measurement.md) |
| układ plików stanu projektu wg cyklu życia | [`project-state-layout.md`](references/conventions/project-state-layout.md) |
| co ładuje się do każdej sesji, gdzie umieścić regułę, start sesji, handoff, builder nieinteraktywny | [`context-budget.md`](references/conventions/context-budget.md) |
| kształt pozycji backlogu, kolejka, warunek domknięcia | [`backlog-contract.md`](references/conventions/backlog-contract.md) |
| język odpowiedzi, dowody, komentarze w kodzie i komunikowanie zmian zakresu | [`agent-communication.md`](references/conventions/agent-communication.md) |
| twierdzenia w dokumentach stanu, które przestały być prawdziwe | [`document-claim-drift.md`](references/conventions/document-claim-drift.md) |
| przesłanki pozycji backlogu, które nigdy nie były prawdziwe | [`backlog-premise-audit.md`](references/conventions/backlog-premise-audit.md) |
| wersjonowanie kopii toolkitu, `check` / `update` / `promote` | [`toolkit-sync.md`](references/conventions/toolkit-sync.md) |

## Szablony

Gotowe artefakty leżą w [`references/templates/`](references/templates/):
rejestr decyzji, wpis audytu, zapis review, log delivery, szkielet zgłoszenia,
szablon commita, `plan-funkcji.md` (plan jednego wykonawcy o polach noda),
`scenariusz-presji.md` (pomiar reguły pod presją),
`codex-builder/` (launcher buildera nieinteraktywnego i szablon preambuły),
`test-gates.sh` (testy samych bramek),
`push-lock.sh`, `heavy-slot.sh` i `heavy-slot.py`
(orkiestracja lokalnych bramek),
`dependency-currency.sh` (bramka aktualności), `import-depth.sh` (głębokość
ścieżek importu), `identifier-language.sh` (język identyfikatorów),
`ui-copy-lint.sh` (teksty interfejsu), `backlog-lint.sh` i `backlog-migrate.sh`
(kontrakt backlogu; migracja bezstratna albo przerywa).
`task-completion.py` sprawdza strukturę etapów odbioru przed zamknięciem
zadania wieloetapowego; nie ocenia prawdziwości dowodów ani zgody na zmianę
zakresu (`backlog-contract.md` §6a).
`agent-runtime/` i `agent-runtime.py` wykonują kolejkę, zdarzenia/ack oraz
cleanup po potwierdzonej integracji; adapter platformy wymaga sprawdzenia.
`security-check.py` i `security/` zbierają ograniczone dowody skanerów,
`bootstrap/` wspiera generator profili, a `adopt-and-audit.md` jest gotowym
zleceniem dla agenta aplikacji. Pełny skill Cloudflare to osobny katalog
`security-audit`, z własną licencją i pochodzeniem.

Dwa z nich nie są bramkami i **nigdy nie kończą się czerwono**, bo opisują stan,
a nie go oceniają: `stan-stosu.sh` wypisuje, czym projekt jest napisany —
z pozycjami BRAK włącznie — i zaznacza odstępstwa od zasad stosu zdaniem
(„nie używaj Astro w aplikacji — widok ma stać na Next"). `rejestr-regul.sh`
wypisuje **wszystkie** konwencje z tego repozytorium i przy każdej mówi, czy
sprawdziła ją bramka, czy rozstrzygnęło czytanie, czy nie dotyczy tego
projektu. Bez nich raport pokazuje wyłącznie to, co się zepsuło, a reguła
zielona i reguła nigdy nieuruchomiona wyglądają w nim tak samo.

## Materiały datowane

[`references/references/`](references/references/) trzyma fakty, które tracą
ważność: wersje, statusy narzędzi, migawki ekosystemu. **Referencja nigdy nie
nadpisuje konwencji** — cykl życia opisuje
[`references/references/README.md`](references/references/README.md).

Przy ocenie instrukcji: [źródła i granice pomiaru](references/references/instruction-evidence.md).

## Czego w tym skillu nie ma

Definicje agentów (`agents/`), baseline globalnej konfiguracji
(`global-claude/`) i ścieżki wejścia (`NEW-PROJECT.md`, `ADOPT.md`) nie są
skillami i standard ich nie obejmuje. Dostarcza je bootstrap toolkitu przez
kopiowanie plików — patrz README repozytorium.

## Wersja

`metadata.version` odpowiada plikowi `VERSION` w repozytorium i jest jedynym
sygnałem dla `toolkit-sync.sh check`. Katalog `references/` jest **generowany**
przez `scripts/build-skills.sh`; nie edytuj go ręcznie — poprawka idzie do
źródła w korzeniu repo.
