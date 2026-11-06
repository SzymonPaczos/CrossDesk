# Backlog — <projekt>

Kontrakt pozycji: `conventions/backlog-contract.md`. Sprawdzenie:
`bash <toolkit>/templates/backlog-lint.sh .`

Zapisanie pozycji nie jest zgodą na implementację. Pozycja znika stąd dopiero
po domknięciu (commit z `Task-Ref:`, zielona bramka, wpis w
`history/completed-work.md`).

Czytaj przez `grep -n '^### <ID>'` i spis treści (dodaj go, gdy pozycji
jest kilkadziesiąt), nie w całości. Pozycja ma do 1 500 B, notka stanu do
4 linii; przebieg wykonania idzie do `history/`.
Agent główny zapisuje także przyjętą pracę bieżącą. Zadanie wieloetapowe ma
jeden plan odbioru w pozycji albo w `BRIEF` (`backlog-contract.md` §6a).
Przy zmianie tematu zachowuje pozostałe etapy i następny krok; część nie
zamyka całości. Handoff i ledger wskazują ID zamiast dublować plan.

<!-- Wzór pozycji — skopiuj i wypełnij. Klucz bez wartości jest błędem,
     nie wartością domyślną.

### <ZRODLO>-<RRRR-MM-DD>-<nn> — <krótki tytuł>

WPLYW: critical | high | medium | low | —
STATUS: otwarte | w trakcie | zaparkowane
ZRODLO: audyt <data> | rozmowa | zgloszenie <ref> | review <sha>
DOWOD: <komenda, ścieżka:linia albo cytat — dlaczego to jest problem>
BRAMKA_ZAMYKAJACA: <komenda czerwona teraz, zielona po naprawie>
                   albo: odstepstwo: <powód> (wtedy PRZEGLAD obowiązkowa)
PRZEGLAD: <RRRR-MM-DD> | —
BRIEF: task-briefs/<id>.md | —

<proza: kontekst, propozycja, konsekwencje>
-->

## Do wykonania (kolejność = decyzja właściciela)

_(pusto — pozycje w kolejności wykonania; kolejność proponuje `/plan-naprawy`,
ustala właściciel)_

## Inbox

_(pusto — pozycje zapisane automatycznie, do sklasyfikowania)_

## Poza kolejką (świadomie, z datą przeglądu)

_(pusto — pozycje odłożone z powodem; różnią się od przeoczonych tym, że mają
`PRZEGLAD`)_

## Czeka na decyzję właściciela

_(pusto)_

## Zablokowane (infra / zależności)

_(pusto)_
