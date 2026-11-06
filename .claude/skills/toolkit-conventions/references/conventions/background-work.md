# Konwencja: praca długotrwała i jej cykl życia

Stack-agnostic. Zakres: **kto jest właścicielem pracy, która trwa dłużej niż
żądanie, jak się ją zatrzymuje, jak przeżywa restart i skąd wiadomo, że
postępuje.**

Rozdział ról: [`reliability-and-observability.md`](reliability-and-observability.md)
mówi o **retry, timeoutach i śladach**; [`backend-layers.md`](backend-layers.md)
— gdzie leży granica transakcji. Ta konwencja mówi o **cyklu życia jednostki
pracy**.

---

## 1. Jedna przyczyna źródłowa całej klasy awarii

Największa pojedyncza grupa awarii systemów z pracą w tle ma wspólny mianownik:
**praca żyła w cyklu życia żądania HTTP albo otwartej karty przeglądarki, więc
w momencie, w którym żądanie się kończyło, nikt nie był jej właścicielem.**

Objawy wyglądają na pięć niezależnych błędów i są jednym: „zatrzymanie nie
działa", „przebieg ginie przy restarcie", „proces został, choć nikt na niego
nie czeka", „nie widać żadnego postępu", „po ponownym połączeniu zrobiło się
dwa razy".

Naprawa jest jedna: **zlecenie jest bytem trwałym**, z własnym rekordem,
stanem i właścicielem — niezależnym od tego, kto je zlecił i czy nadal patrzy.

## 2. Kolejka jest tabelą, dopóki pomiar nie powie inaczej

- Pobranie zlecenia MUSI być atomowe i pomijać wiersze zajęte przez innych
  (blokada z pominięciem zablokowanych). To jest kilkaset linii, nie nowy
  system.
- Kolejka na tabeli jest **języko-neutralna** (każdy wykonawca czyta ją tym
  samym SQL-em) i **transakcyjna razem z domeną** — zlecenie powstaje w tej
  samej transakcji, co decyzja, która je wywołała.
- Dedykowany broker wchodzi **po pomiarze**, nie po przeczuciu: konkretna
  liczba zleceń na sekundę, przy której baza przestaje wyrabiać. Broker dodany
  „na wyrost" to druga infrastruktura do utrzymania, backupu i debugowania.

## 3. Dzierżawa zamiast własności

- Wykonawca dostaje **dzierżawę z terminem**, nie własność zlecenia, i
  **odnawia ją biciem serca**.
- Śmierć wykonawcy → dzierżawa wygasa → zlecenie wraca do puli. Zawieszenie →
  bicie serca ustaje → to samo. Restart całego systemu → nic nie ginie.
- To jest cała odporność na awarię wykonawcy, i dlatego dzierżawa MUSI mieć
  termin krótszy niż tolerancja użytkownika na ciszę.

## 4. Zatrzymanie jest przejściem stanu, nie sygnałem do procesu

- Anulowanie MUSI ustawiać stan w bazie. Wykonawca sprawdza go przy biciu
  serca i przerywa, sprzątając po sobie.
- Sygnał wysłany do procesu może nie dojść: proces mógł się przenieść, zawiesić
  albo już nie istnieć. Stan w bazie dostaje każdy wykonawca, zawsze, także po
  restarcie.
- Przejścia stanów przebiegu MUSZĄ być jednokierunkowe i wymuszane warunkiem
  w zapytaniu — patrz [`data-modeling.md`](data-modeling.md) §3.

## 5. Postęp jest wierszem stanu, nie strumieniem wiadomości

- Wykonawca aktualizuje **pole postępu** (etap, licznik, znacznik czasu);
  interfejs renderuje jedną kartę z projekcji tego pola.
- Dzięki temu postęp jest **odtwarzalny po odświeżeniu** i nie zależy od tego,
  czy ktoś patrzył, gdy się działo.
- „Dziesiątki wiadomości o tym, że trwa" i „brak jakiegokolwiek śladu postępu"
  to dwa końce tej samej pomyłki: postęp potraktowany jako komunikacja zamiast
  jako stan.

## 6. Tworzenie jest idempotentne, awaria jest stanem

- Zlecenie MUSI powstawać z **kluczem idempotencji**. Ponowienie, odświeżenie
  i druga karta nie tworzą drugiego zlecenia — a przy pracy kosztownej drugie
  zlecenie to podwojony rachunek, nie tylko duplikat.
- Wyjątek w wykonawcy kończy przebieg stanem **niepowodzenia z klasą błędu
  i skrótem przyczyny** (bez sekretów), widocznym dla użytkownika razem
  z akcją ponowienia. Awaria bez stanu jest tajemnicą, a tajemnicę zgłasza się
  jako „czasem nie działa".
- Zadeklarowane **zdolności wykonawcy** (czy wspiera wznowienie, ponowienie
  etapu, rozgałęzienie) sterują tym, co pokazuje interfejs. Przycisk
  „wznów", który po cichu startuje od zera, jest okłamywaniem interfejsem.

## 7. Wejścia przez referencję, wynik jako nowa wersja

- Wejściem zlecenia MUSI być **referencja** (identyfikator plus wersja plus
  tryb dostępu), nie zawartość. Zawartość w ładunku zlecenia znaczy brak
  wersjonowania, brak audytu i pełny rozmiar w każdej próbie.
- Plik wejściowy jest **niemutowalny**; wynik powstaje jako nowa wersja albo
  różnica. Zdanie „narzędzie zepsuło mi plik" prawie zawsze znaczy „narzędzie
  pracowało na oryginale".
- Wykonawca pracuje w **izolowanym obszarze roboczym**: jawnie przekazane
  pliki, minimalne uprawnienia, kontrola sieci, limity i sprzątanie zgodne
  z retencją.

## 8. Reguła kształtu wykonawcy

Test rozstrzygający, gdzie kończy się wykonawca, a zaczyna drugi backend
tylnymi drzwiami. Czy ten kod potrzebuje:

1. własnego punktu HTTP?
2. sesji użytkownika?
3. własnych migracji schematu?
4. decyzji domenowej (autoryzacja, polityka)?

**Jedno „tak" oznacza, że to nie jest wykonawca.** Reguła daje zespołowi pełną
dowolność co do **zawartości** wykonawcy i zero dowolności co do jego
**wpięcia** — patrz [`architecture-change.md`](architecture-change.md) §6.

## 8a. Praca wykonana albo zasób zwolniony

Między zajęciem zlecenia a końcem funkcji rejestr idempotencji twierdzi, że
**ktoś tę pracę wykonuje**. Każde wyjście, które zostawia zajęcie bez
odpowiedzi, jest zniknięciem zadania: ponowienie trafia na „już zajęte", wraca
bez pracy i zostaje potwierdzone jako cichy sukces. Nic nie rzuca, nic nie
czerwienieje, a zlecenie stoi w stanie „zatwierdzone" na zawsze.

Reguła jest strukturalna, bo defekt jest strukturalny: **po zajęciu zasobu
każda ścieżka wyjścia leży w obsłudze**, a każda obsługa albo zwalnia zajęcie,
albo zapisuje porażkę (i wtedy sama zwalnia). Trzecia odpowiedź — złap,
zaloguj, jedź dalej — zostawia rejestr twierdzący, że praca trwa.

Reprodukcja z pola i powód, dla którego to jest bramka, a nie punkt przeglądu:
audyt wskazał **jedną** taką ścieżkę — rzucenie wyjątku o nieznalezionym
zleceniu przed blokiem `try`. Bramka strukturalna napisana na jej podstawie
pokazała przy pierwszym uruchomieniu **trzy**: do tamtej doszły dwa zapisy
wprowadzające zlecenie w stan uruchomiony. **Wyjście, którego nikt nie
przewidział, jest też wyjściem, dla którego nikt nie napisał testu** — i to
jest dokładnie ta część, której test zachowaniowy zrobić nie może.

Czym to sprawdzić: [`templates/claim-release.sh`](../templates/claim-release.sh).

## 9. Egzekwowanie

**Blokują:**

- praca długotrwała uruchamiana synchronicznie w obsłudze żądania;
- anulowanie zaimplementowane jako sygnał do procesu bez stanu w bazie;
- tworzenie zlecenia bez klucza idempotencji;
- zawartość pliku w ładunku zlecenia zamiast referencji;
- wykonawca spełniający którykolwiek warunek z §8.

**Raportują:**

- przebieg bez pola postępu;
- dzierżawa bez bicia serca albo bez terminu;
- niepowodzenie bez klasy błędu;
- obszar roboczy wykonawcy bez retencji.

## 10. Sygnały maszynowe (tryb raportowy)

1. Wywołanie długotrwałej operacji w handlerze żądania bez zlecenia.
2. Tabela zleceń bez kolumny terminu dzierżawy.
3. Anulowanie bez zapisu stanu.
4. Ładunek zlecenia z polem binarnym lub tekstem powyżej ustalonego limitu.
5. Punkt HTTP zdefiniowany w module wykonawcy.
6. Migracja schematu w repozytorium wykonawcy.
7. Przebieg w stanie uruchomionym bez odświeżenia bicia serca dłużej niż termin.

Powiązane: [`reliability-and-observability.md`](reliability-and-observability.md),
[`data-modeling.md`](data-modeling.md),
[`backend-layers.md`](backend-layers.md),
[`architecture-change.md`](architecture-change.md).
