# Toolkit-sync w audycie — mechanika porównania i promocji

Materiał wczytywany na żądanie z Kroku 00 skilla `weekly-audit`. W ciele skilla
została decyzja („co robisz przy którym wyniku"); tutaj jest mechanika, której
nie potrzeba przy zielonym `check`.

## Pozycje dopisane lokalnie

Dla plików, które rozrosły się lokalnie (checklisty, rejestry, listy warstw),
uruchom:

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

Jeżeli **w trakcie audytu** wykryjesz potrzebę reguły, skilla albo szablonu,
zapisz propozycję i dowody w backlogu. Audyt nie tworzy ani nie promuje
własnych instrukcji. Zlecony Builder wprowadza sprawdzoną zmianę do mastera
i przygotowuje adopcję; nie jest to warunek oceny niezależnych ryzyk i rezultatów.

Błędu w regule nie naprawiaj w kopii projektu. Poprawka idzie do mastera
i wraca przez pełny protokół adopcji wersji; załatana kopia jest początkiem
następnego dryfu. Nowa wersja zastępuje poprzednią w zmienionym zakresie,
więc Builder wyszukuje i rozstrzyga sprzeczne lokalne instrukcje.
