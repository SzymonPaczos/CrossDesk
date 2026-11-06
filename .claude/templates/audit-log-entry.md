## Audyt RRRR-MM-DD

Nagłówek maszynowy — bez niego nie da się później stwierdzić, co ten audyt
w ogóle obejmował. Brak narzędzia raportuj jako `n/a`, **nigdy** jako zero
findings; „nie sprawdzono" i „sprawdzono, czysto" to dwa różne stany.

```text
TOOLKIT_VERSION:      <wersja z .claude/toolkit.lock | brak locka>
AUDITED_REVISION:     <pełny SHA HEAD w chwili audytu>
PREVIOUS_AUDIT:       <SHA poprzedniego | pierwszy audyt>
DIFF_RANGE_OR_SCOPE:  <prev..head — pełny diff, nie lista wybranych plików>
TOOLS:                <uruchomione narzędzia + wersje | n/a>
EXCLUSIONS_OR_NA:     <czego nie dało się uruchomić i dlaczego>
THREAT_MODEL_VERSION: <data/wersja modelu zagrożeń | brak>
SECURITY_REVIEW:      PASS | DEGRADED <powód> | NOT_TRIGGERED <powód>
RED_TEAM:             <data ostatniego | n/a>
BACKLOG_WRITE:        <ile pozycji dopisano>
DEEP_REVIEW:          <tak/nie — czy była warstwa osądu, nie tylko grep>
CONTEXT:              <zawsze ładowane B, handoff B, mediany wejścia Codex/Claude, MCP nieużywane | n/a>
DELIVERY_REVIEW:      <okno 7/21 dni, uzgodnione cele, dowody, pozostałe etapy, blokady | UNVERIFIED z powodem>
TASK_COMPLETENESS:    <zamknięcia rodziców vs wszystkie etapy | UNVERIFIED | n/a z powodem>
PROCESS_DRIFT:        <dryf celu i skutek | CLEAR z dowodami | UNVERIFIED z powodem>
VERDICT:              PASS | FAIL <powód>
```

**Zakres deep-review to pełny diff od poprzedniego audytu, nie enumeracja
plików z promptu.** Enumeracja przepuszcza znaleziska w plikach, których nikt
nie wymienił — sprawdzone boleśnie. Security review skanuje invarianty w
**całym repo**, nie tylko w diffie: poświadczenie na granicy okna diffu ucieka
dokładnie tą szczeliną.

## Znaleziska

| ID | Sev | Rzecz | Dowód | Status |
|---|---|---|---|---|
| AUD-001 | critical | <co> | `plik:linia` + komenda | otwarte / naprawione `<sha>` |

## Zweryfikowane i czyste

<co sprawdzono i wyszło dobrze — inaczej następny audyt sprawdzi to od zera>

## Czego NIE sprawdzono (wprost)

<jawny inwentarz luk audytu z powodem. „Dynamiczne wyczerpanie rate-limitu —
odmówione: wymagałoby ruchu na produkcji". Ta sekcja jest obowiązkowa;
audyt bez listy własnych ograniczeń udaje kompletność>

## Metryki i trend

| Metryka | Poprzednio | Teraz |
|---|---|---|
| otwarte critical | | |
| testy | | |
| dryf kopii vs master | | |
| uzgodnione rezultaty i pozostałe etapy (7/21 dni) | | |

Ścieżki i liczby commitów pomagają wybrać próbkę do oceny; nie mierzą czasu
ani wartości. Testy, security i utrzymanie mogą być celem. Znaleziskiem jest
udowodnione wypieranie uzgodnionego rezultatu albo fałszywe domknięcie, nie
sam udział plików testowych. Niezweryfikowany zakres nie jest zaliczeniem.

## Wiarygodność tego raportu

<kto oceniał. Jeśli naprawy oceniał ten sam agent, który je wykonał — napisz
to wprost. Samoprzegląd nie jest sign-offem, a werdykt traci ważność z chwilą
zmiany ocenianego SHA>

## Ratchet

<które progi zamrozić, skoro osiągnięto zero findings w danej klasie>
