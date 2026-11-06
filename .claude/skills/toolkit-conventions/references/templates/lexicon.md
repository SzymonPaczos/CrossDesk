# Leksykon projektu — <nazwa>

Jedno pojęcie, jedno słowo. Ten plik rozstrzyga spory o nazwę **raz**, zamiast
przy każdym przeglądzie kodu.

Zasady użycia:

- Pojęcie wchodzi tu **razem z pierwszym kodem**, który go używa.
- Kolumna **odrzucone** jest obowiązkowa i jest tym, co czyni regułę
  mechaniczną: bramka szuka terminów odrzuconych, bo synonimów nie zgadnie.
- Zmiana terminu pociąga zmianę nazw w kodzie, osobnym commitem zmieniającym
  wyłącznie nazwy (`conventions/naming-conventions.md` §5).
- Skrót wolno stosować **tylko** wtedy, gdy stoi w tabeli skrótów niżej.

## Pojęcia domenowe

| Termin obowiązujący | Znaczenie | Odrzucone (nie używać) | Decyzja |
|---|---|---|---|
| `<termin>` | <jednozdaniowe znaczenie w tej domenie> | `<synonim>`, `<synonim>` | <data / ref decyzji> |
| | | | |

## Skróty dozwolone

| Skrót | Rozwinięcie | Gdzie wolno |
|---|---|---|
| `id` | identyfikator | wszędzie |
| `<skrót>` | <rozwinięcie> | <zakres> |

## Pojęcia świadomie rozróżniane

Pary, które wyglądają na synonimy, a nie są. Bez tej sekcji ktoś je „ujednolici".

| Termin A | Termin B | Na czym polega różnica |
|---|---|---|
| `<A>` | `<B>` | <różnica, przez którą scalenie ich byłoby błędem> |

## Terminy zakazane globalnie

Nazwy, które nic nie znaczą, niezależnie od domeny — nie wolno ich użyć jako
nazwy zmiennej, funkcji, pliku ani tabeli:

`data`, `info`, `manager`, `helper`, `util` (jako nazwa samodzielna), `tmp`,
`obj`, `val`, `handle`, `process` (jako rzeczownik), `stuff`, `misc`, `new`,
`old`, `test2`.

<!--
Bramka: przeszukanie kodu terminami z kolumny „odrzucone" i z listy zakazanych,
w trybie raportowym do czasu wyzerowania licznika. Reguła i tryb wprowadzenia:
conventions/naming-conventions.md §4 i §5.
-->
