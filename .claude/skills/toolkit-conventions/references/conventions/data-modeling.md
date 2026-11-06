# Konwencja: modelowanie danych trwałych

Stack-agnostic. Zakres: **co trafia do kolumny, a co do dokumentu, jak żyją
tabele rosnące bez końca, gdzie mieszka idempotencja i które osie wersji nie
wolno ze sobą mylić.**

Rozdział ról: [`backend-layers.md`](backend-layers.md) mówi, **kto** pisze do
bazy i gdzie leży granica transakcji; [`contract-canon.md`](contract-canon.md)
— skąd bierze się kształt. Ta konwencja mówi, **jak ten kształt wygląda
w schemacie**.

---

## 1. Kolumna czy dokument

- Wszystko, po czym się **filtruje, autoryzuje albo sprawdza integralność**,
  MUSI być kolumną: status, rodzaj, właściciel, wersje, identyfikator
  korelacji, znaczniki czasu.
- Treść natywnie dokumentowa (polimorficzna, o kształcie zależnym od rodzaju)
  MOŻE być dokumentem — **z wersją schematu i limitem rozmiaru**.
- Pole używane w warunku zapytania, które siedzi w dokumencie, jest zapachem:
  albo awansuje do kolumny, albo warunek jest w złym miejscu.
- Dokument bez zapisanej wersji schematu jest danymi, których nie da się
  bezpiecznie odczytać za rok. Wersja kosztuje jedno pole.

## 2. Tabele rosnące dostają retencję, zanim urosną

Historia zmian, zdarzenia, audyt, zapisy stanu procesów — wszystko, co jest
**append-only**, rośnie monotonicznie i nikt tego nie zauważa, dopóki nie
zauważy tego dysk.

- Polityka retencji lub kompaktowania MUSI powstać **razem z tabelą**, nie po
  roku. Dopisana później jest migracją terabajta pod presją.
- Kompaktowanie MUSI chronić rekordy, do których odwołuje się coś żywego —
  wiszące odwołanie do skompaktowanej historii to błąd, który ujawnia się
  tygodnie po kompaktowaniu.
- Migawka co N wersji jest optymalizacją odczytu, **nie zamiennikiem**
  przyrostów: przyrost niesie intencję zmiany, migawka tylko wynik.

## 3. Idempotencja mieszka w danych, nie w intencji

- Przejścia stanów MUSZĄ być jednokierunkowe i wymuszane **warunkiem
  w zapytaniu** (aktualizuj tylko ze stanu oczekiwanego, sprawdź liczbę
  zmienionych wierszy), nie sprawdzeniem w kodzie przed zapisem. Sprawdzenie
  przed zapisem jest wyścigiem z definicji.
- Operacje tworzące MUSZĄ przyjmować **klucz idempotencji** z ograniczeniem
  unikalności w bazie. Ponowienie po timeoucie, odświeżenie strony i druga
  karta to wtorek, nie przypadek brzegowy.
- Licznik wersji **nigdy się nie cofa**. Cofnięcie zmiany to nowa wersja
  będąca odwrotnością poprzedniej. Dzięki temu historia, odwołania do wersji
  bazowej i wszelkie przeliczenia składają się bez przypadków szczególnych.

## 4. Transakcja nie czeka na świat zewnętrzny

- Transakcja obejmuje **zapis agregatu, historii i zdarzenia wychodzącego** —
  i nic więcej.
- Otwarta transakcja podczas oczekiwania na sieć, zewnętrzny proces albo
  strumień jest zabroniona. Blokada trzymana przez czas cudzej odpowiedzi
  zamienia jeden wolny zewnętrzny system w awarię całej bazy.

## 5. Trzy osie wersji, których nie wolno mylić

| Oś | Czego dotyczy | Kto ją podbija |
| --- | --- | --- |
| wersja schematu treści | kształt dokumentu w kolumnie, per rodzaj | zmiana kształtu treści |
| wersja kontraktu | kanon i jego derywacje | zmiana kształtu na granicy |
| wersja migracji bazy | struktura tabel | zmiana DDL |

Każda ma własny migrator i własny moment podbicia. Pomylenie ich kończy się
migratorem uruchamianym na danych, których nie dotyczy. Tam, gdzie język na to
pozwala, osie MUSZĄ być rozdzielone **typami**, żeby pomyłka nie kompilowała
się w ogóle.

## 6. Identyfikatory i właściciel

- Identyfikator encji MUSI pochodzić z jednego generatora i być **sortowalny
  po czasie**. Identyfikator losowy bez porządku zamienia każde „ostatnie
  dwadzieścia" w sortowanie po kolumnie, która może być pusta.
- **Wymiar właściciela MUSI istnieć w zapytaniach od pierwszego commitu**,
  nawet gdy dziś przyjmuje jedną wartość. Dołożenie logowania to tydzień;
  dołożenie zakresu właściciela do zapytań, które go nie miały, to audyt
  każdego zapytania w aplikacji — i mechanizm, którym powstają wycieki między
  użytkownikami.
- Repozytorium NIE MOŻE wystawiać metody odczytu bez zakresu właściciela.
  Metoda „pobierz wszystko" istnieje po to, żeby ktoś jej kiedyś użył
  w handlerze.

## 7. Egzekwowanie

**Blokują:**

- warunek zapytania po polu wewnątrz dokumentu tam, gdzie istnieje kolumna;
- dokument zapisywany bez wersji schematu;
- przejście stanu realizowane odczytem i zapisem zamiast warunkiem w zapytaniu;
- metoda repozytorium bez zakresu właściciela;
- wywołanie sieciowe wewnątrz otwartej transakcji.

**Raportują:**

- tabela append-only bez zapisanej polityki retencji;
- operacja tworząca bez klucza idempotencji;
- kolumna wersji bez odpowiadającego migratora;
- identyfikator generowany w więcej niż jednym miejscu.

## 8. Sygnały maszynowe (tryb raportowy)

1. Zapytanie filtrujące po ścieżce w dokumencie.
2. Dokument bez pola wersji schematu w zapisie.
3. Aktualizacja stanu bez warunku na stanie poprzednim.
4. Nowa tabela append-only bez wpisu w polityce retencji.
5. Wywołanie klienta HTTP między otwarciem a zamknięciem transakcji.
6. Metoda repozytorium bez parametru właściciela.
7. Dwa generatory identyfikatorów w jednym module.

Powiązane: [`backend-layers.md`](backend-layers.md),
[`contract-canon.md`](contract-canon.md),
[`api-contract-design.md`](api-contract-design.md),
[`reliability-and-observability.md`](reliability-and-observability.md).
