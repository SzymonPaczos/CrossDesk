# Konwencja: obalanie PRZESŁANEK pozycji backlogu

Stack-agnostic. Wyekstrahowana 2026-09-07 z projektu civic-tech prowadzonego
tym toolkitem od maja, na polecenie właściciela („audyt powinien sprawdzać
backlog i jego twierdzenia, po to on jest").

Siostrzana wobec [`document-claim-drift.md`](document-claim-drift.md) i celowo
od niej oddzielona. Tamta łapie zdania, które **przestały** być prawdziwe.
Ta łapie zdania, które **nigdy nie były** — i nie sprawdza ich dla porządku,
tylko dlatego, że to z nich biorą się decyzje o tym, czego **nie robić**
i o co poprosić człowieka.

## Problem

Audyt umie sprawdzić kod i umie sprawdzić dane. Backlog jest trzecim
artefaktem, który kłamie, a kłamie najdrożej, bo jego zdania nie opisują
świata — one **zamrażają pracę**. Pozycja z fałszywą przesłanką albo stoi
w kolejce blokad, albo każe komuś zrobić rzecz niepotrzebną, albo pozwala
usunąć coś, co działa. Żadne z tego nie zapala się w testach.

Zmierzone jednego dnia, 2026-09-07, dwa razy i w dwie przeciwne strony:

| Przesłanka wpisu | Rzeczywistość | Koszt, gdyby przeszła |
|---|---|---|
| „siedem kolumn: 0 danych, **0 czytelników**" — na tej podstawie zatwierdzono `DROP` | pustka prawdziwa, brak czytelników **fałszywy dla 4 z 7**; dwie mają render w UI | skasowanie działającej funkcji na polecenie wydane na podstawie zdania nieprawdziwego |
| „przyczyny **nie da się ustalić bez właściciela**" — pozycja stała w kolejce blokad | jedno zapytanie do porannej kopii produkcji ją rozstrzygnęło: 1242 z 1244 wierszy miało komplet pozostałych liczników | człowiek trzyma na sobie zadanie, którego odpowiedź leży w naszych danych |

Obie przeżyły co najmniej jeden audyt. Żaden go nie przepuścił przez
niedbalstwo: **żadna warstwa nie miała backlogu w zakresie.**

Pierwsza pomyłka ma szczególnie pouczający mechanizm. Autor triażu **nazwał
klasę błędu we własnym komentarzu** („mierząc zły symbol udowodniłbym, że
żadnej kolumny nikt nie czyta") i mimo to w nią wpadł: grepował symbol tabeli,
a odczyty szły przez zmienną wiersza, bo ORM zwraca typ wiersza. Świadomość
pułapki nie jest kontrolą dodatnią.

## Czego NIE da się zmechanizować

Tego samego, czego nie da się w konwencji siostrzanej, i z tego samego
zmierzonego powodu: regex po prozie backlogu dał **79 trafień na 707 ścieżek,
w większości fałszywych**, bo backlog z natury opisuje pliki, które dopiero
mają powstać. Przesłanka to zdanie o zachowaniu kodu albo o dostępności
źródła. Nie ma wzorca, który odróżni ją od opisu planu.

Dlatego ta konwencja **nie dokłada bramki**. Dokłada obowiązkowy krok lektury
z określoną kolejnością, bo próbka bez priorytetu jest gorsza niż jej brak:
daje poczucie pokrycia i z definicji omija to, co najdroższe.

## Co działa

**Bierz zdanie, na którym stoi STATUS pozycji, nie pozycję.** Wpis ma
kilkanaście zdań; tylko jedno decyduje o tym, że pozycja jest zablokowana,
krytyczna albo gotowa do usunięcia czegoś. To jedno przelicz w HEAD.

Przesłanka ma jedną z czterech postaci i każda ma swoją metodę:

| Postać | Jak obalać |
|---|---|
| „nikt tego nie czyta / nie ma producenta" | grep po symbolu, którym kod **naprawdę** się posługuje (ORM zwraca typ wiersza, nie tabelę), plus kontrola dodatnia na siostrzanym polu |
| „nie da się bez człowieka / bez zewnętrznego źródła" | zapytaj najpierw to, co **już masz**: kopia produkcji, fixture'y, cache, ledger, logi |
| „to jest zepsute / tego brakuje" | policz w HEAD — mogło zostać naprawione przy okazji innej pracy |
| „X wymaga Y" | sprawdź, czy Y **nadal** jest warunkiem, czy tylko był w dniu pisania |

**Kolejność, bo czas audytu jest skończony:**

1. pozycje w stanie **`Czeka na decyzję`** (`project-state-layout.md`) —
   kosztują najwięcej i z definicji nikt ich nie rusza, więc ich przesłanki
   starzeją się bez świadka;
2. pozycje o najwyższej ważności — z nich biorą się decyzje nieodwracalne;
3. pozycje nietykane najdłużej.

**Druga metoda przy wyniku zerowym.** „Sprawdziłem, przesłanka się broni" jest
wart tyle, co komenda, którą to sprawdzono. Jeśli metodą był grep, kontrolą
dodatnią jest znalezienie tym samym wywołaniem czegoś, o czym wiesz, że jest.

## Egzekwowanie

Krok obowiązkowy audytu. **Obalona przesłanka to poprawka wpisu w tym samym
commicie co audyt** — raport o kłamstwie, które zostaje w pliku, jest tylko
niepokojem. Jeśli obalenie zdejmuje blokadę, pozycja **przenosi się do kolejki
roboczej** w tym samym commicie; inaczej audyt zauważył, że człowiek jest wolny,
i nikomu tego nie powiedział.

Wynik zapisuj jedną linią, w formie odróżniającej ciszę od braku pomiaru:

```
przesłanki: sprawdzono N pozycji (blokujących M), obalono K — <ID: co było fałszywe>
```

Zero obalonych zapisuje się **słowem**. „Było czysto" i „nie zaglądałem" muszą
się w logu różnić, inaczej za miesiąc nikt nie odróżni jednego od drugiego.

## Czego ta konwencja nie obiecuje

Nie wykrywa pozycji **brakujących** — rzeczy zepsutych, o których nikt nie
napisał wpisu. Na to są pozostałe warstwy audytu, które patrzą na kod i dane.
Ta patrzy wyłącznie na to, co backlog już twierdzi.

Nie zastępuje też rejestru decyzji. Przesłanka obalona w pozycji, która
realizuje decyzję kierunkową, wymaga wpisu tam, nie tylko poprawki wpisu.

## Sygnały maszynowe

- pozycja blokująca człowieka, której przesłanki nie przeliczono od jej powstania,
- przesłanka postaci „nie da się ustalić", gdy repo trzyma kopię produkcji
  albo fixture'y tej samej dziedziny,
- wniosek o braku czytelników oparty na grepie bez kontroli dodatniej,
- pozycja zamknięta z powodu przesłanki, której nie zmierzono w dniu zamknięcia.
