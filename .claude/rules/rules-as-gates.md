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
9. Gate musi mieć własny test negatywny — dowód, że **blokuje**. „Przechodzi,
   gdy wszystko działa" nie jest dowodem na nic. Wzorzec:
   `templates/test-gates.sh`.

## Antywzorce z reprodukcją

Poniższe nie są teorią — każdy został odtworzony na działającym repozytorium.

### A1. Gate sprawdza working tree zamiast pushowanego commita

**Objaw:** `pre-push` czyta pliki z dysku (`grep ... "$file"`) i wyznacza zakres
z `HEAD`, a nie z refów podanych mu na stdin.

**Reprodukcja:** zacommituj plik z sekretem, popraw go **tylko w working tree**
bez commitowania, wypchnij. Gate melduje „czysto" i sekret ląduje na remote.

**Dlaczego umyka review:** hook działa poprawnie w każdym normalnym scenariuszu.
Rozjazd pojawia się wyłącznie wtedy, gdy working tree jest *czystszy* niż
commit — czyli dokładnie po ręcznej poprawce „na szybko".

**Naprawa:** czytaj `<local ref> <local sha> <remote ref> <remote sha>` ze
stdin, wyznacz zakres z `remote_sha..local_sha` (dla nowej gałęzi
`local_sha --not --remotes`) i odtwórz commit w tymczasowym
`git worktree add --detach`. Wzorzec: `NEW-PROJECT.md` §4.2.

**Skala:** wykryte niezależnym audytem w jednym projekcie, po weryfikacji
obecne w 5 na 5 repozytoriów z hookiem `pre-push` — bo wszystkie skopiowały
ten sam wadliwy szablon z tego toolkitu.

### A2. `set -e` + `pipefail` cicho ucinają kolejne warstwy gate'a

**Objaw:** gate kończy się sukcesem, wykonawszy tylko część checków.

**Reprodukcja:** w skrypcie z `set -euo pipefail` daj advisory pipeline
`grep ... | head -5`. Gdy grep nic nie znajdzie (exit 1) albo `head` zamknie
potok (SIGPIPE), `set -e` ubija skrypt **przed** kolejnymi warstwami. Wyjście
jest zerowe lub urwane, więc wygląda jak przebieg czysty.

**Naprawa:** każdy advisory pipeline zamknięty w `{ ...; } || true`; warstwy
blokujące ustawiają zmienną `STATUS`, a skrypt kończy się jednym
`exit "$STATUS"` na końcu — nie `exit` w środku pętli.

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
