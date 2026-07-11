# Konwencja: reguły jako gate'y

Stack-agnostic. Wyekstrahowana z JawnePanstwo i CrossDesk.

## Problem

Reguła opisana wyłącznie prozą z czasem przestaje działać, szczególnie gdy:

- jest regularnie łamana przez ludzi lub agentów;
- naruszenie jest wykrywalne mechanicznie;
- skutek pojawia się dopiero później (drift docs, brak testu interakcji,
  zależność zła dla produkcji);
- review polega na pamięci autora.

## Procedura

1. Zapisz konkretny incydent i regułę, która nie zadziałała.
2. Zdefiniuj minimalny sygnał maszynowy. Gate ma sprawdzać dokładnie tę klasę
   błędu, nie heurystyczne „wszystko”.
3. Najpierw uruchom w trybie raportowym i policz false positives.
4. Gdy sygnał jest wiarygodny, zamień go w gate blokujący.
5. Uruchamiaj szybki check zawsze, ciężki tylko po zmianie odpowiednich ścieżek.
6. Brak wymaganego środowiska blokuje z instrukcją — nie kończy się cichym
   sukcesem.
7. Escape hatch jest nazwany per warstwa (`SKIP_DOC_DRIFT=1`), drukuje głośne
   ostrzeżenie i służy tylko awarii. Jedna flaga nie wyłącza innych gate'ów.
8. Dodaj stały audyt samego gate'a: czy testuje zmianę, a nie dowolny istniejący
   artefakt; czy nie ma `exit 0` omijającego kolejne warstwy; czy opis zgadza
   się z realnym triggerem.

## Dobre kandydatury

- routes w kodzie ↔ tabela routes w dokumentacji;
- nowy publiczny moduł ↔ test;
- migracja ↔ lint i schema-drift test;
- interaktywny komponent ↔ test klik/fill + assert po interakcji;
- zakaz importu konkretnej implementacji ↔ grep/AST check;
- wygenerowany plik ↔ deterministyczna regeneracja i czysty diff.

## Złe kandydatury

Nie blokuj na osądzie estetycznym, review AI, liczbie komentarzy ani szerokiej
heurystyce z dużą liczbą false positives. Taki check zostaje advisory i trafia
do audytu głębokiego.

## Ratchet

Gate jest podłogą, nie sufitem. Gdy repo osiąga zero findings lub wyższy próg
coverage, usuń `|| true` i zamroź poziom. Każdy nowy incydent dopisuje stały
punkt do checklisty audytu — audyt rośnie z postmortemów.
