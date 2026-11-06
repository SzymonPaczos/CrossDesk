# Konwencja: moduły, funkcje, klasy i zależności

Stack-agnostic. Zakres: **struktura kodu poniżej poziomu architektury** — co
moduł eksponuje, kiedy funkcja, kiedy klasa, kiedy wspólna abstrakcja, i jak
utrzymać graf zależności acyklicznym.

Rozdział ról:

- [`architecture-principles.md`](architecture-principles.md) — granice i test
  decyzji projektowej.
- [`frontend-architecture.md`](frontend-architecture.md),
  [`backend-layers.md`](backend-layers.md) — warstwy w konkretnych
  środowiskach; ta konwencja obowiązuje wewnątrz każdej z nich.

---

## Moduły

- Moduł MUSI eksponować małe, jawne API i ukrywać szczegóły implementacji.
- Graf zależności produkcyjnych MUSI być acykliczny.
- Import MUSI wskazywać publiczne API właściciela, nie przypadkowy plik wewnętrzny.
- Ogólne barrel files z `export *` są zabronione. Jawny `public.ts` z ręczną
  listą eksportów jest dopuszczalny.
- Moduł `utils` lub `helpers` bez wyraźnego właściciela POWINIEN zostać
  zastąpiony nazwą opisującą odpowiedzialność.

## Funkcje

- Funkcja POWINNA działać na jednym poziomie abstrakcji i mieć jawne wejścia,
  wyjścia oraz efekty.
- Flagi zmieniające znaczenie funkcji są sygnałem do rozdzielenia przypadków użycia.
- Parametry należące do jednego pojęcia POWINNY tworzyć jawny command/value object.
- Ukryte odczyty czasu, losowości, środowiska i globalnego stanu POWINNY być
  wstrzykiwane, gdy wpływają na wynik lub testowalność.
- Nazwa MUSI opisywać intencję, np. `reserve_inventory`, nie mechanizm typu
  `process_data`.

## Komentarze

Komentarz krótko wyjaśnia powód lub ograniczenie niewidoczne z kodu.
Dokumentacja interfejsu podaje potrzebny odbiorcy kontrakt. Szczegóły
określa [`agent-communication.md`](agent-communication.md) §3.

Zgodność opisu sprawdza się w kodzie i odpowiednich testach; sam komentarz
nie potwierdza implementacji. Wymagane testy zachowują kryteria
z [`test-evidence.md`](test-evidence.md).

## Klasy

- Klasa MUSI reprezentować trwałą współpracę danych i zachowań albo stanowy cykl życia.
- Bezstanowe transformacje POWINNY być funkcjami, nie klasami `Manager`,
  `Helper` lub `Service` z samymi metodami statycznymi.
- Dziedziczenie POWINNO być używane tylko dla prawdziwego kontraktu
  podstawienia. Kompozycja jest domyślna.
- Konstruktor NIE POWINIEN wykonywać I/O.
- Klasa NIE MOŻE ukrywać globalnego service locatora ani dowolnie otwierać transakcji.

## Abstrakcje

Wspólna abstrakcja POWINNA powstać po trzecim stabilnym użyciu. Dwa podobne
przypadki pozostają jawne, dopóki nie jest znany trwały kontrakt. Wyjątek:
protokół zewnętrzny lub wymóg bezpieczeństwa może uzasadniać wspólną granicę
wcześniej.

Źle:

```ts
export * from "./api";
export * from "./components";
export * from "./internal";
```

Dobrze:

```ts
export { OrderListFeature } from "./list/OrderListFeature";
export type { OrderListFilter } from "./list/order-list.types";
```

## Egzekwowanie

Cykle, zakazane kierunki importów, `export *` oraz importy wewnętrzne MUSZĄ
blokować merge. Martwe eksporty i zależności POWINNY być raportowane, a
następnie usuwane w zmienianym obszarze.


Powiązane: [`architecture-principles.md`](architecture-principles.md),
[`rules-as-gates.md`](rules-as-gates.md).
