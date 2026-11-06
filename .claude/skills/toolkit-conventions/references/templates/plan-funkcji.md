# Plan funkcji — <nazwa>

**Task-Id:** <slug>
**Klasa:** architektoniczna (skill `petla-dostarczenia`, krok 1)
**Decyzja:** <ścieżka do zgłoszenia lub wpisu w decisions.md, z którego plan wynika>
**Gałąź:** `<typ>/<slug>` od `<baza>`
**Evidence sink:** <PR + required check | `.claude/reviews/<sha>.md`>
**Ledger:** `<ścieżka ledgeru postępu w katalogu runtime>`

Plan argumentuje z decyzji: decyzja jest źródłem wymagań, plan jej
wykonaniem. Konflikt między nimi rozstrzyga decyzja, a rozjazd wraca do
właściciela. Wykonawca czyta jedno zadanie naraz, więc każde zadanie
zawiera wszystko, czego potrzebuje.

**Cel:** <jedno zdanie, co powstaje>
**Architektura:** <dwa lub trzy zdania o podejściu>

## Ograniczenia globalne

<Wymagania z decyzji obowiązujące każde zadanie, po jednym w linii,
wartości przepisane dosłownie: wersje minimalne, limity zależności, reguły
nazw i tekstów, platformy.>

## Zadania

Lista odbioru poniżej jest kanoniczna; skopiuj ją do briefu zadania albo
trzymaj plan jako brief wskazany z backlogu. Nie utrzymuj drugiej kopii.
Odhaczenie wymaga odsyłacza do dowodu. Liczba etapów wynika z uzgodnionego
zakresu, a nie z liczby komend lub commitów.

## Etapy odbioru

- [ ] X1 — <pierwszy rezultat> | NASTEPNY_KROK: <czynność>
- [ ] X2 — <drugi rezultat>

## Szczegóły zadań

### Zadanie 1 — <nazwa składnika>

- **Pliki:** utwórz `<ścieżka>`; zmień `<ścieżka>:<linie>`; test `<ścieżka>`
- **Interfejsy:** konsumuje <sygnatury z wcześniejszych zadań>; produkuje
  <nazwy funkcji, parametry, typy zwracane, na których polegają późniejsze
  zadania>
- **Kryteria odbioru:** <sprawdzalne, nie „działa">
- **Bramki:** <komendy, które muszą przejść>

Kroki:

- [ ] Jeden przykład zachowania: wejście, obserwowalny wynik i ryzyko,
      które sprawdza. Plan nie powiela kodu testu ani implementacji.
- [ ] Dla ustalonego kontraktu lub regresji: zapisz mały test tego zachowania.
- [ ] Uruchom: `<komenda>`. Oczekiwany wynik: porażka na wskazanej asercji.
- [ ] Minimalna implementacja w zakresie tego zachowania.
- [ ] Uruchom: `<komenda>`. Oczekiwany wynik: PASS, pozostałe testy bez zmian.
- [ ] Uprość kod i test, jeśli wymaga tego wynik; potwierdź istotne kontrole
      po zmianie. Powtarzaj małymi fragmentami dla następnych zachowań.
- [ ] Commit z `Intent`, `Task-Ref`, `Gates`.
- [ ] Linia w ledgerze: `Zadanie 1: complete <sha>`.

### Zadanie 2 — <nazwa>

<jak w zadaniu 1, z sygnaturami z zadania 1 przepisanymi w „konsumuje">

## Kolejność i zależności

<które zadanie blokuje które; co można wykonać niezależnie>

## Poza zakresem

<czego plan świadomie nie obejmuje; chroni przed rozszerzaniem w trakcie>

## Przegląd planu przed wykonaniem

- [ ] Każda sekcja decyzji ma zadanie, które ją realizuje; luki wypisane.
- [ ] Brak wypełniaczy (lista niżej).
- [ ] Nazwy, sygnatury i typy w późniejszych zadaniach zgadzają się
      z wcześniejszymi.

## Czego w planie nie ma

Każdy z tych zapisów jest wadą planu, nie skrótem: „do ustalenia", „TBD",
„dodaj walidację", „obsłuż przypadki brzegowe", „testy jak wyżej" bez
konkretnego wejścia i wyniku, „jak w zadaniu N" zamiast potrzebnego
kontraktu, odwołanie do funkcji lub typu, którego żadne zadanie nie definiuje.
Nie wymagaj gotowego kodu w planie. Gdy kontrakt jest nieznany, wyznacz
krótkie rozpoznanie z pytaniem i limitem; potem ustal odbiór i zabezpieczenia
według `conventions/quality-gates-and-dod.md`, zamiast testować zgadywany projekt.

Wielu Builderów o rozłącznych zakresach dostaje `work-graph.md`; ten plan
odpowiada jednemu nodowi i zachowuje jego pola (scope, inputs, acceptance,
gates, depends_on).
