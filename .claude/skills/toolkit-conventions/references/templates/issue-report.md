# <jedno zdanie orzekające o defekcie, nie nazwa obszaru>

## Objaw

<co widzi użytkownik, jego słowami, bez przyczyny. Jeśli objaw bywa
niedeterministyczny — napisz to tutaj, nie w reprodukcji>

## Reprodukcja (<wersja>, `<commit>`)

<najkrótsza sekwencja, która jeszcze wywołuje objaw; komenda lub kod, nie proza.
Musi dać się wykonać bez maszyny zgłaszającego>

```
<kroki albo fragment kodu>
```

Wynik faktyczny:

```
<dosłownie>
```

Wynik oczekiwany:

```
<dosłownie>
```

## Środowisko

- Wersja / commit: <v0.0.0 / sha>
- System i środowisko wykonania: <OS, sesja graficzna / przeglądarka, runtime>
- Sposób instalacji: <pakiet | checkout | kontener>  ← pole pomijane najczęściej
  i najczęściej tłumaczące „u mnie działa"

## Diagnoza

<mechanizm: plik:linia, kolejność wywołań, cytat kodu. Może być błędna, ale musi
być sprawdzalna. Jeśli objaw odtwarza się bez współbieżności — napisz to wprost>

## Wpływ

<kogo dotyczy i jak często. Zaniżanie buduje wiarygodność szybciej niż
zawyżanie; napisz też, dlaczego dziś ekspozycja jest wąska, jeśli jest>

## Dowód

<zrzut „przed" dla defektu wizualnego; nagranie dla defektu widocznego w ruchu;
log jako tekst dla reszty. Ten sam rozmiar okna, motyw i dane co w „po".
Kadr zachowuje kontekst niosący dowód. Każdy obraz z tekstem alternatywnym.
Załącznik wyczyszczony z danych osobowych i sekretów>

Tekst alternatywny obrazu opisuje defekt, nie plik: „lista z jednym widocznym
wierszem mimo nagłówka mówiącego o dwóch", nie „zrzut ekranu 3".

Liczba, jeśli da się ją podać: <wysokość w px / liczba wierszy / czas w ms>

## Sugerowany kierunek

<kierunek, nie gotowa łatka; dwa warianty z kosztem każdego. Decyzja projektowa
należy do właściciela kodu>

## Powiązane utwardzenie (opcjonalnie)

<obserwacja poboczna — tutaj, nie w środku diagnozy. Osobny defekt = osobne
zgłoszenie>

<!--
Konwencja: conventions/issue-reporting.md
Zamknięcie potwierdza przejście powyższych kroków reprodukcji, nie merge.
Zmiana diagnozy trafia do komentarza; pierwszego posta się nie przepisuje.
-->
