# Konwencja: progressive delivery i pomiar dostarczania

Stack-agnostic. Dla projektu, który wdraża usługę, aplikację albo konfigurację
na produkcję. Skaluje praktyki Google SRE, AWS i Microsoft do wielkości
projektu — pojedynczy VPS nie potrzebuje infrastruktury hyperscalera, ale
potrzebuje tych samych decyzji: co wdrażamy, jak ograniczamy blast radius,
co mierzymy i kiedy automatycznie wracamy.

## 1. Małe partie i krótko żyjące gałęzie

- Jedna gałąź odpowiada jednemu małemu rezultatowi i ma jednego właściciela.
  Cel: merge tego samego dnia; twardy sygnał ostrzegawczy po 3 dniach.
- Utrzymuj nie więcej niż 3 aktywne gałęzie zmian na repo. Dla pracy solo
  domyślny limit WIP to 1 Builder; drugi tylko dla faktycznie rozłącznego
  zakresu.
- Niedokończoną funkcję integruj małymi, kompatybilnymi krokami za wyłączoną
  flagą albo jako niepodłączony komponent. Nie trzymaj wielotygodniowej
  gałęzi „aż będzie kompletna”.
- Gdy główna gałąź lub wymagany check jest czerwony, priorytetem jest szybki
  fix albo revert. Nie dokładaj kolejnych zmian do zepsutego baseline'u.
- Szybka ścieżka CI (lint/typecheck/unit/build) ma dawać użyteczny feedback
  docelowo w mniej niż 10 minut. Ciężkie testy mogą działać osobno, ale ich
  wymagany wynik musi być gotowy przed promocją artefaktu.

Branch-per-agent z [`multi-agent-delivery.md`](multi-agent-delivery.md) jest
zgodny z trunk-based development tylko wtedy, gdy gałęzie są małe i
krótkotrwałe. „Własna gałąź” nie oznacza długowiecznego równoległego trunku.

## 2. Build once, promote the same artifact

Pipeline ma jeden kanoniczny przepływ:

```text
source revision → verify → package once → pre-production → production
```

- Build tworzy raz niezmienny artefakt: obraz, paczkę albo binarium.
- Każda promocja wskazuje ten sam digest/checksum. Staging i produkcja nie
  przebudowują kodu ani nie rozwiązują ponownie zależności.
- Manifest wydania wiąże: task/intencję, commit SHA, builder/workflow identity,
  artifact digest, wynik gate'ów i konfigurację wdrożenia.
- Attestacja jest użyteczna dopiero z weryfikacją przed konsumpcją. Dla
  publikowanych artefaktów celem jest co najmniej SLSA Build L1; gdy hosted
  builder generuje i podpisuje provenance, można deklarować L2 dopiero po
  wdrożeniu weryfikacji oczekiwanej tożsamości buildera, repo i refu.
- Nie deklaruj poziomu SLSA na podstawie samej obecności pliku provenance.

## 3. Kontrakt gotowości do wdrożenia

Przed pierwszym automatycznym rolloutem projekt zapisuje:

```text
ARTIFACT: <commit SHA + digest>
CURRENT_GOOD: <poprzedni digest/tag>
HEALTH_SIGNALS: <błędy, latency, readiness, krytyczny synthetic check>
ABORT_THRESHOLDS: <konkretne progi i okno>
CANARY_SCOPE: <instancja/port/% użytkowników>
BAKE_CONDITION: <czas + minimalna liczba zdarzeń/requestów>
ROLLBACK: <automatyczna komenda/procedura + limit czasu>
OWNER_GATE: <czy potrzebna ręczna zgoda>
```

Brak sygnału lub brak danych to `INCONCLUSIVE` i zatrzymanie promocji, a nie
sukces. Health check sprawdzający wyłącznie, że proces żyje, nie wystarcza;
co najmniej jeden sygnał ma opisywać zachowanie widoczne dla użytkownika.

## 4. Najmniejszy sensowny rollout

### Poziom A — pojedynczy VPS

1. Uruchom kandydacki kontener/proces na drugim porcie bez przełączania ruchu.
2. Wykonaj readiness, migracyjny compatibility check i synthetic smoke test.
3. Jeśli proxy/load balancer to umożliwia, skieruj mały udział ruchu; jeśli
   nie — użyj krótkiego testu wewnętrznego, a przełączenie proxy traktuj jako
   atomową promocję.
4. Obserwuj zdefiniowane sygnały przez bake condition.
5. Przy przekroczeniu progu automatycznie przywróć poprzedni digest; przy
   niejednoznacznych danych zatrzymaj rollout.
6. Po sukcesie zachowaj poprzedni artefakt do szybkiego rollbacku i zapisz
   release evidence.

### Poziom B — wiele instancji lub kontrola ruchu

- Zacznij od jednej instancji lub maksymalnie 5–10% ruchu (canary), reszta to
  control na poprzedniej wersji.
- Porównuj canary z control; nie oceniaj wyłącznie absolutnego wykresu canary.
- W danym serwisie oceniaj jeden canary naraz, aby nie zanieczyścić sygnału.
- Po udanym bake time promuj falami, np. `10% → 33% → 100%`. Każda fala ma
  własny health gate i możliwość automatycznego rollbacku.
- Wielkość i czas wynikają z natężenia ruchu oraz SLO. „10 minut” bez
  wystarczającej liczby zdarzeń nie jest dowodem.

## 5. Deploy to nie release: feature flags

- Flaga oddziela obecność kodu od ekspozycji funkcji. Rozszerzaj ekspozycję:
  autor/testerzy → wybrana kohorta → rosnący procent → wszyscy.
- Każda flaga ma właściciela, wartość bezpieczną, kill switch, termin usunięcia
  i test obu stanów. Po pełnym rolloutcie usuń flagę oraz martwą ścieżkę.
- Zmiana flagi lub konfiguracji produkcyjnej przechodzi review, historię i te
  same guardy/rollback co kod. Panel bez audytowalnego śladu nie jest pipeline.
- Flaga nie maskuje niekompatybilnej migracji. Kod przed i po przełączeniu
  musi współistnieć z bieżącym schematem i formatem danych.

## 6. SLO i error budget jako release gate

- Dla usługi z realnymi użytkownikami zdefiniuj przynajmniej jeden SLI/SLO
  opisujący rezultat użytkownika, np. odsetek poprawnych odpowiedzi w czasie.
- Jeśli usługa przekroczyła error budget w przyjętym oknie, zatrzymaj zwykłe
  wydania i zmiany danych. Dozwolone są poprawki incydentów krytycznych,
  security fix oraz prace
  przywracające niezawodność.
- Error budget nie jest karą ani ręcznym argumentem przeciw zmianie. To jawna,
  wcześniej uzgodniona polityka równoważenia rozwoju i stabilności.
- Projekt bez wiarygodnego SLO zaczyna od alertów użytkownikowych i rejestru
  nieudanych wdrożeń; nie wymyśla precyzyjnego budżetu z przypadkowych danych.

## 7. Pięć metryk DORA — lekki zapis miesięczny

Mierz osobno dla jednej aplikacji/usługi i obserwuj trend:

1. change lead time;
2. deployment frequency;
3. failed deployment recovery time;
4. change fail rate;
5. deployment rework rate.

Nie używaj ich do rankingu agentów, ludzi ani różnych projektów. Metryka nie
jest celem; nie wymuszaj sztucznej liczby deployów. Dla małego projektu
wystarczy miesięczny wpis w `delivery-log.md` wyliczony z tagów, deploy logu i
incydentów. Raz na kwartał narysuj value stream jednej zmiany i popraw
największe opóźnienie albo źródło reworku.

Minimalny wpis:

```markdown
## YYYY-MM — <service>
- Change lead time (median / p90):
- Deployment frequency:
- Failed deployment recovery time (median / p90):
- Change fail rate:
- Deployment rework rate:
- Największe ograniczenie i jedna planowana poprawa:
```

## 8. Release evidence

Każdy rollout zapisuje maszynowo lub w lekkim logu:

```text
RELEASE: <tag>
SOURCE: <commit SHA>
ARTIFACT: <digest>
PROVENANCE_VERIFY: PASS | N/A <reason>
PRE_PROD_GATES: <links/commands>
CANARY: PASS | SKIPPED <reason>
BAKE: PASS <window + event count>
ROLLOUT: <waves>
ROLLBACK_TARGET: <digest/tag>
DEPLOYED_AT: <timestamp>
VERDICT: HEALTHY | ROLLED_BACK | INCONCLUSIVE
```

## Źródła referencyjne

- DORA: [Continuous delivery](https://dora.dev/capabilities/continuous-delivery/)
- DORA: [Trunk-based
  development](https://dora.dev/capabilities/trunk-based-development/)
- DORA: [Software delivery performance metrics](https://dora.dev/guides/dora-metrics/)
- Google SRE: [Canarying releases](https://sre.google/workbook/canarying-releases/)
- Google SRE: [Error budget policy](https://sre.google/workbook/error-budget-policy/)
- AWS Builders' Library: [Automating safe, hands-off
  deployments](https://aws.amazon.com/builders-library/automating-safe-hands-off-deployments/)
- Microsoft: [Progressive experimentation with feature
  flags](https://learn.microsoft.com/en-us/devops/operate/progressive-experimentation-feature-flags)
- SLSA 1.2: [Build track basics](https://slsa.dev/spec/v1.2/build-track-basics)
- SLSA 1.2: [Verifying artifacts](https://slsa.dev/spec/v1.2/verifying-artifacts)
