# Konwencja: rejestr weryfikacji negatywnej

Stack-agnostic. Wyekstrahowana z przebiegu naprawczego w trzech repozytoriach
produkcyjnych, w którym najliczniejszą klasą znalezisk (41 z 151) okazały się
**testy, których nikt nigdy nie widział na czerwono**.

[`test-evidence.md`](test-evidence.md) określa kryteria dowodu z testu.
Ta konwencja określa format i miejsce zapisu wyniku weryfikacji negatywnej.

---

## 1. Problem: zdanie zamiast pomiaru

„Test był czerwony bez poprawki" napisane w mapie wdrożenia, w opisie commita
albo w raporcie audytu jest twierdzeniem, którego **nikt nie może sprawdzić
tydzień później**. Skutki są mierzalne i wszystkie wyszły przy jednym audycie:

- w jednym repozytorium 128 z 391 zebranych testów nie miało ani jednego
  twierdzenia o czerwieni, w drugim około 346 z 423;
- z 347 unikalnych nazw funkcji testowych tylko 14 padało gdziekolwiek w mapie,
  w decyzjach albo w treści commita;
- sam wskaźnik „ile testów było czerwonych" był liczony **grepem po słowie
  „czerwon"** w dokumentach, czyli był proxy, nie pomiarem.

To nie znaczy, że te testy są złe. Znaczy, że **nikt nie wie, czy potrafią
zawieść** — a dopóki nie wie, cała reszta raportu stoi na czyimś słowie.

## 2. Rejestr jest danymi, a liczbę w nim produkuje przebieg

Jeden plik TSV na repozytorium, kolumny:

```
nodeid_or_label	commit	exit_code	date	note
```

- **`nodeid_or_label`** — identyfikator testu albo etykieta dowolnego innego
  sprawdzianu. Rejestr przyjmujący wyłącznie identyfikatory jednego runnera
  wypycha dowody bramek shellowych i suit frontendowych **z powrotem do prozy**,
  czyli do nawyku, który ten plik zastępuje.
- **`commit`** — drzewo, o którym mowa. Bez niego wiersz nie nazywa niczego.
- **`exit_code`** — **zaobserwowany**, nie zadeklarowany.
- **`note`** — która to strona sprawdzianu (`red:` / `green:`) i **co dokładnie
  cofnięto**. Notatka „red: poprawka cofnięta" jest bezużyteczna; notatka
  „red: składnik wysyłki usunięty z total()" da się powtórzyć.

Zasada nośna: **liczba w tym pliku powstaje w skrypcie zapisującym albo nie ma
jej w pliku w ogóle.** Wiersz wpisany ręcznie nie odpowiada na pytanie, po które
ten plik istnieje.

Jeden podmiot ma **dwa wiersze**: czerwony przy commicie z mutacją i zielony
przy commicie naprawy. Jeden wiersz jest twierdzeniem, dwa są pomiarem.
Wyjątkiem jest **kontrola pozytywna** — wiersz pokazujący, że sprawdzian nie
odrzuca wszystkiego; deklaruje się ją w notatce i jest zwolniona z wymogu pary.

**Czytaj `awk -F'\t'` albo `IFS=$'\t' read -r`, nigdy gołym `read`.** Tabulator
należy do domyślnego IFS-a, więc `read` skleja sąsiadujące tabulatory: pusta
kolumna znika, a wszystkie następne przesuwają się o jedno pole. Objaw jest
podstępny, bo dane nadal wyglądają sensownie — ten sam plik czytany `awk`-iem
i `read`-em dawał dwie różne prawdy o tym samym wierszu.

## 3. Skrypt zapisujący odmawia czterech rzeczy

Wzorzec: [`templates/negative-verification.sh`](../templates/negative-verification.sh)
w trybie `--zapisz`. Sam uruchamia sprawdzian i zapisuje kod wyjścia, który
zobaczył. Odmowy są tu istotą, nie ozdobą:

**Odmawia zapisu „czerwone" przy kodzie wyjścia 0** (kod wyjścia 3). Wiersz
mówiący `red:` obok zera to rejestr kłamiący o jedynej rzeczy, którą zapisuje.
Bierze się z **mutacji bez efektu** — pola, które w tym scenariuszu i tak było
puste, `rstrip` na łańcuchu bez kończącego ukośnika, albo mutacji wołającego
zamiast funkcji pod testem. W jednym z repozytoriów **trzy takie wiersze**
powstały w trakcie jednego przebiegu naprawczego, zanim odmowa je zatrzymała;
w całym przebiegu w trzech repozytoriach było ich siedem, w tym cztery u jednego
agenta, który wykrył je sam i **usunął własne wiersze**. To jest właściwa
reakcja: fałszywe twierdzenie ma zniknąć, a nie zostać z komentarzem.

Szablon czyści bytecode przed przebiegiem, aby próba używała aktualnego kodu.
To rozwiązanie tego skryptu, nie wymóg kasowania cache każdego runnera.
Inna implementacja może zapewnić świeżość przez odizolowane artefakty lub
sprawdzone unieważnianie cache; wymaganie określa `test-evidence.md`.

Trzecie uszczelnienie jest drobne i konieczne: **`set -e` nie może połknąć
porażki, którą przyszliśmy zapisać** — uruchomienie stoi między `set +e`
a `set -e`, a kod wyjścia zbierany jest jawnie.

**Czerwień z błędu składni to czerwień z niewłaściwego powodu.** Mutacja, która
psuje parsowanie pliku, kończy bieg kodem wyjścia kolekcji, nie asercji — a to
wygląda w rejestrze identycznie jak trafienie. Runner odróżnia te dwa stany
własnym kodem wyjścia (pytest: 4 i 2 to błąd użycia i przerwanie, 1 to porażka
testu); zapisywać wolno **wyłącznie porażkę testu**. Cztery takie wiersze
powstały w jednym przebiegu, zanim ktokolwiek spojrzał na kod wyjścia; usunięcie
ich jest tą samą reakcją co przy mutacji bez efektu.

**Celem mutacji nie może być plik, do którego skrypt dopisuje.** Harness zwykle
czyta plik, podmienia fragment, uruchamia zapis i **przywraca kopię**. Gdy
mutowanym plikiem jest sam rejestr — bo test orzeka o jego kształcie — kopia
przywraca stan sprzed dopisania i kasuje właśnie zapisany wiersz `red:`. Zostaje
sama zieleń, czyli wiersz mówiący, że test nigdy nie był czerwony. Rejestr,
lista długu i konfiguracja sufitu MUSZĄ być dla harnessu **niedotykalne**; fakt
o ich kształcie czerwieni się mutacją czytnika, nie danych.

## 4. Lista długu z sufitem-zapadką

Plik testowy, którego nikt nie widział na czerwono, ma dwie dopuszczalne drogi:
wiersz w rejestrze albo wiersz na **liście długu** z powodem.

```
# sufit: 12
test_file	reason
tests/live/test_provider.py	oznaczony live: przebieg kosztuje tokeny dostawcy i wymaga klucza, wiec czerwieni nie da sie wyprodukowac na runnerze
```

Cztery własności, każda wyuczona na konkretnej pomyłce:

1. **To lista długu, nie lista zwolnień.** Każdy wiersz to plik, o którym nic
   nie wiadomo — nie plik, o którym postanowiono nie wiedzieć.
2. **Sufit jest zapadką: może maleć, nigdy rosnąć.** Podniesienie sufitu jest
   decyzją o zaprzestaniu pomiaru i ma tak wyglądać — w commicie, z powodem.
   Bez sufitu lista długu w ciągu miesiąca staje się listą zwolnień.

   Jeden wyjątek, wąski i rozpoznawalny: **sufit wolno przestawić w górę, gdy
   w tym samym diffie wyostrzył się licznik.** Nic wtedy nie przybyło — zmieniło
   się to, co licznik widzi. Odróżnia go od zwykłego podniesienia obecność
   poprawki miary w tym samym commicie i lista bytów, które stały się widoczne,
   wymieniona z nazwy. Bez obu tych rzeczy jest to zwykłe zaprzestanie pomiaru.
   Zmierzone: dopasowanie po samej nazwie funkcji ustąpiło dopasowaniu
   uwzględniającemu ścieżkę, dług skoczył 1698 → 1703, a różnicą było dziesięć
   testów jeżdżących na cudzym dowodzie.
3. **Sufit mieszka w pliku, którym rządzi.** Trzymanie go w teście oddalonym
   o dwa katalogi znaczy, że wiersz i próg zmieniają się w różnych diffach.
4. **Powód musi być zdaniem.** Próg długości (rzędu 30 znaków) odróżnia powód od
   odhaczenia pola: „ui", „n/a", „później" nie mówią następnemu czytelnikowi nic.

Plik nie może być jednocześnie w rejestrze i na liście długu — wtedy jedna
z dwóch deklaracji jest nieaktualna i z plików nie wynika która.

## 5. Bramka nad rejestrem

Bramką jest [`templates/negative-verification.sh`](../templates/negative-verification.sh).
Rozstrzyga cztery rzeczy i każda z nich była w polu naruszona:

- wiersz, w którym notatka i kod wyjścia mówią co innego;
- wiersz o innej liczbie kolumn niż nagłówek (czyli wiersz, który dwa narzędzia
  przeczytają inaczej);
- lista długu ponad sufit;
- **plik testowy cytowany w mapie wdrożenia jako dowód, którego nie ma ani
  w rejestrze, ani na liście długu.** To jest reguła mapy zastosowana do mapy:
  kolumna „przetestowano" znaczy „widziano na czerwono", więc wpis bez pokrycia
  w rejestrze jest deklaracją, nie dowodem.

Do tego wymóg wobec samej bramki: **musi zobaczyć materiał.** Reguła kształtu
„ten zbiór minus tamten jest pusty" jest spełniona przez zepsuty czytnik, więc
pierwszy sprawdzian w każdym takim pliku jest sprawdzianem czytnika, z dolnym
progiem liczbowym. Nazwa robocza tego wzorca to *strażnik strażnika*.

## 5.1. Czym wiersz łączy się z testem

Rejestr trzyma **nazwę**, suita trzyma **byty**, a bramka musi je skojarzyć.
Wybór klucza jest regułą, nie szczegółem implementacji, i myli się w obie strony.

**Sama nazwa funkcji rozdaje darmowe przepustki.** Test o nazwie, która już
w rejestrze występuje, dziedziczy dowód nagrany dla **innego** testu w **innym**
pliku. Zmierzone: dziesięć takich par w jednym drzewie, m.in.
`test_rejecting_a_proposal_leaves_the_book_alone` z parą w suicie jednostkowej
i bez pary w integracyjnej — liczone jako pokryte. Każdy, kto powtórzy nazwę,
przechodzi przez tę dziurę bez wysiłku.

**Sam pełny identyfikator przestrzeliwuje w drugą stronę.** Obserwacja dotyczyła
testu, nie jego ścieżki, więc test, który **zmienił plik**, zachowuje swój dowód;
żądanie zapisanej ścieżki zgłasza udowodnione testy jako dług. To jest fałszywy
alarm, czyli kierunek, w którym bramka psuje się najdrożej.

**Reguła:** dopasowanie po nazwie tam, gdzie nazwa jest w suicie **jednoznaczna**,
i po pełnym identyfikatorze tam, gdzie nie jest. Liczbę nazw niejednoznacznych
bramka **wypisuje** — jest to mianownik jej własnej dokładności i zmienia się
bez niczyjej decyzji.

## 6. Czego rejestr nie umie i trzeba o tym pamiętać

Rejestr wykrywa brak czerwieni, ale nie rozstrzyga przyczyny porażki.
Notatka wskazuje mutację oraz asercję odpowiadającą badanemu błędowi.
Liczba czerwonych testów jest wskazówką diagnostyczną; sama nie potwierdza
ani nie podważa trafności mutacji.

Rejestr jest też **append-only** i nie ma kolumny statusu. Odwołanie wiersza
polega na jego usunięciu w commicie, który mówi dlaczego.

I trzecia rzecz, tym razem o czytającym, nie o pliku: **uczciwy przedział błędu
nie jest tolerancją.** „Prawdziwy dług leży między 1698 a 1708" bywa poprawnym
pomiarem i **złą** odpowiedzią — bo skoro znasz szerokość przedziału, znasz też
mechanizm, który go rozszerza, a mechanizm da się usunąć. Zmierzone: ta sama
liczba podana raz jako przedział („znana niedokładność, myli się w stronę
pokryte") i raz jako defekt z listą dziesięciu bytów, które przez nią
przechodzą. Pierwsza wersja zamyka temat, druga go naprawia. Przedział podany
zamiast poprawki jest **odroczeniem opisanym jako pomiar**.

## 7. Egzekwowanie

**Blokują:**

- wiersz „czerwone" przy kodzie wyjścia 0 i odwrotnie;
- wiersz o niepełnej liczbie kolumn;
- plik jednocześnie w rejestrze i na liście długu;
- lista długu przekraczająca zapisany sufit;
- plik testowy bez wiersza w którymkolwiek z dwóch plików, gdy oba istnieją;
- liczba w dokumencie podana jako dowód zamiast identyfikatora sprawdzianu.

**Raportują:**

- podmiot występujący wyłącznie z kodem 0 (nigdy nie widziany na czerwono);
- notatka bez wskazania pliku i linii mutacji;
- wiersz starszy niż ostatnia zmiana pliku, którego dotyczy.

Powiązane: [`test-evidence.md`](test-evidence.md),
[`rules-as-gates.md`](rules-as-gates.md),
[`pull-request-review.md`](pull-request-review.md),
[`tool-adoption-and-measurement.md`](tool-adoption-and-measurement.md).
