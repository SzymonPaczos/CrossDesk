# references/ — materiały datowane

Katalog na wiedzę, która **traci ważność**: konkretne narzędzia, wersje,
statusy dojrzałości, migawki ekosystemu.

## Czym to się różni od `conventions/`

| | `conventions/` | `references/` |
|---|---|---|
| Treść | reguły i procedury | nazwy, wersje, statusy |
| Trwałość | lata | miesiące |
| Zmiana | przez decyzję | przez odświeżenie migawki |
| Użycie | wiążące | pomocnicze |

Konwencja mówi „narzędzie oznaczone przez producenta jako beta nie może być
bramką blokującą". Referencja mówi „to konkretne narzędzie było w becie w
sierpniu 2026". Pierwsze jest regułą, drugie faktem o przeszłości.

**Referencja nigdy nie nadpisuje konwencji.** Gdy migawka poleca narzędzie, a
konwencja zabrania danej klasy narzędzi w tym miejscu, wygrywa konwencja.

## Kontrakt każdego pliku w tym katalogu

Każdy plik zaczyna się nagłówkiem zawierającym:

1. **datę zebrania** materiału,
2. **datę przeglądu** — kiedy trzeba go zweryfikować,
3. **kto zebrał** i czy dane zostały niezależnie zweryfikowane,
4. **zasadę grounding**: skąd pochodzi każde twierdzenie.

## Cykl życia

- **do 6 miesięcy** — używaj, weryfikując wersje przed decyzją.
- **6–12 miesięcy** — traktuj jako wskazówkę kierunkową; wersje są nieaktualne.
- **powyżej 12 miesięcy** — materiał historyczny. Albo odśwież, albo przenieś
  do historii projektu; nie zostawiaj w obiegu bez adnotacji.

Odświeżenie jest osobnym zadaniem z własnym PR-em, nie poprawką przy okazji.

## Luki zostają lukami

Jeżeli źródła nie potwierdziły jakiejś informacji, plik zapisuje `n.a.`
zamiast uzupełniać ją z pamięci. Lista świadomych luk jest częścią materiału,
nie jego wadą — wskazuje, czego **nie wolno** cytować jako ustalonego.
