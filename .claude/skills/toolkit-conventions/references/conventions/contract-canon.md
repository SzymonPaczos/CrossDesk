# Konwencja: kanon kontraktu i derywacje

Stack-agnostic. Zakres: **jedno miejsce, w którym kształt danych jest
definiowany ręcznie, i mechaniczna generacja wszystkich pozostałych jego
postaci — także przez granicę języków.**

Rozdział ról:

- [`api-contract-design.md`](api-contract-design.md) — kontrakt **między
  usługami**: błędy, idempotencja, paginacja, wersjonowanie.
- [`forms-and-validation.md`](forms-and-validation.md) — szczególny przypadek:
  formularz i endpoint z jednego schematu.
- [`typescript-javascript.md`](typescript-javascript.md) — dane z granicy
  zaufania jako `unknown` i walidacja runtime w ogóle.
- Ta konwencja — **skąd bierze się każda postać kształtu** i dlaczego drugą
  pisze się kodem, a nie ręką.

---

## 1. Trzy pojęcia, które trzeba nazwać

**Kanon** — jedyne miejsce, w którym kształt danych jest definiowany ręcznie.

**Derywacja** — każda inna postać tego kształtu: schemat dla zewnętrznego
konsumentu, typ statyczny, model w drugim języku, kolumny, propsy komponentu,
DTO komendy. Generowana kodem, nigdy przepisana.

**Lustro** — druga ręczna kopia kształtu. To jest nazwa kategorii błędu, nie
metafora. Lustro w chwili powstania jest identyczne z oryginałem, **więc
przechodzi review**; rozjeżdża się przy trzeciej zmianie, o której autor
lustra nie wiedział, bo nikt mu nie powiedział, że jest drugim właścicielem.

Objawy lustra są zawsze te same i zawsze wyglądają na trzy różne błędy:
„panel pokazuje co innego niż backend", „zapis przeszedł, ale rekord jest
inny niż formularz", „konsument woła pole, którego serwer nie zna".

## 2. Lustro eliminuje lint, nie dyscyplina

- Konstruktory schematów opisujące domenę MUSZĄ być dozwolone **wyłącznie
  w module kanonu**. Wszędzie indziej — import i derywacja (wybór pól,
  rozszerzenie, pominięcie).
- Reguła „pamiętajmy, żeby nie kopiować" nie działa: lustro powstaje najczęściej
  pod presją terminu, w pliku, którego autor nie wie o istnieniu kanonu.
- Lustra powstają **także wewnątrz jednego języka** — dwie listy stałych w tym
  samym backendzie, trzy kopie rejestru. Ujednolicenie stacku nie usuwa tej
  klasy błędu; usuwa ją wyłącznie jedno źródło plus generacja.

## 3. Granica języków

Wzorzec: **kanon → eksport schematu neutralnego (krok builda) → generacja
modeli w drugim języku → walidacja po obu stronach granicy.** Każda strona
waliduje to, co wysyła, i to, co odbiera; „druga strona już to sprawdziła"
jest założeniem, nie kontraktem.

- Kod wygenerowany jest **artefaktem builda**: commitowany, żeby był widoczny
  w review i w diffie, ale **nigdy edytowany ręcznie**. Edycja generatu to
  lustro z opóźnionym zapłonem — znika przy najbliższej regeneracji.
- Kierunek generacji MUSI być **jeden**. Dwa kierunki to dwa kanony, czyli
  zero kanonów.
- Kanon mieszka tam, gdzie żyje bramka i konsument o najostrzejszych
  wymaganiach; reszta jest po stronie odbiorczej.

**Test parytetu jest obowiązkowy.** Zestaw ładunków poprawnych i niepoprawnych
przechodzi w CI przez oba walidatory; wyniki MUSZĄ się zgadzać. Łapie dryf
generatora — formaty dat, unie, pola opcjonalne, wartości puste — zanim złapie
go produkcja.

## 3a. Siedem postaci tego samego bytu

Rozdział modeli nie jest estetyką warstw — jest **listą miejsc, w których ten
sam byt jest zapisany**, i tylko jedno z nich wolno pisać ręcznie. W trzech
repozytoriach produkcyjnych ten sam byt miał od pięciu do sześciu zapisów:

| postać | gdzie mieszka | kto ją pisze |
|---|---|---|
| domenowa | `domain/` — niezmienniki, przejścia stanów | **człowiek (kanon)** |
| bazodanowa | `adapters/db/tables.py` — kolumny, typy, indeksy | człowiek, sprawdzana testem równości |
| migracja | `migrations/versions/` — zapis historyczny | generator narzędzia migracji |
| API | `apps/api/schemas.py` — model żądania i odpowiedzi | derywacja z domenowej |
| kolejka | ładunek zlecenia — referencja, nie zawartość | derywacja z domenowej |
| narzędzia agenta | `tools/` — schemat wywołania i **opis** | derywacja z domenowej |
| interfejs | `api-types.d.ts` — typ w drugim języku | **generowana, nigdy pisana** |

Audyt pokazał, co się dzieje bez tej dyscypliny. Jeden byt: pięć zapisów po
dziewięć pól i **szósty, skrócony do sześciu** — w narzędziu, przez które
patrzy agent, więc agent nie widział ani pary wariantów, ani daty pozyskania.
Inny: pole obecne w domenie i w bazie, **nigdy niewychodzące przez API**.
Trzeci: cztery kształty tego samego przebiegu, z których API gubiło operatora
i obie daty, a wynik uruchomienia agenta miał siedem pól z siedemnastu.

Reguła: **każda postać poza kanonem jest albo generowana, albo ma test równości
z kanonem.** Test równości jest tani i natychmiastowy — to jedna asercja
porównująca zbiory pól — i jest właściwą odpowiedzią na czas, w którym scalenie
kopii jest jeszcze przed nami.

## 3b. Parytet porównuje OPISY, nie tylko nazwy

Test parytetu sprawdzający wyłącznie **zbiory nazw** przepuścił rozjazd opisów
**trzech narzędzi z sześciu** — a opis narzędzia jest częścią deklaracji, którą
czyta model przy decyzji, czy je wywołać. Jedna strona podawała modelowi
konkretną trasę, przez którą jedzie decyzja człowieka; druga mówiła „trasa
backendowa". To nie jest różnica kosmetyczna: to dwie różne instrukcje
operacyjne dla tego samego narzędzia, zależne od tego, która strona je
zarejestrowała.

Parytet ma porównywać **pełną definicję**: nazwę, opis i nazwy argumentów.
A ponieważ opis po drugiej stronie granicy czyta się zwykle regeksem po źródle,
przed porównaniem stoi **strażnik parsera** — asercja, że parser znalazł tyle
definicji, ile ich jest. Parser, który znalazł zero, daje porównanie puste,
a puste czyta się jak zgoda.

## 3c. Strażnik generatu porównuje z COMMITEM, nie z indeksem

`git diff -- <plik>` porównuje drzewo robocze z **indeksem**. Zacommitowany
kontrakt może być wtedy nieaktualny, a `git add` na zregenerowanym artefakcie
ucisza strażnika — bramka melduje zgodność, której nigdy nie sprawdziła.
Właściwa forma to `git diff --exit-code HEAD -- <plik>`.

Dwa dopełnienia z tego samego incydentu: **wywołanie bez listy ścieżek nic nie
porównuje** i ma być odmową, nie sukcesem; a **generat, którego git nie śledzi,
jest dla `git diff` niewidzialny** — bramka wtedy milczy zamiast czerwienić,
co jest gorsze niż jej brak.

Czym to sprawdzić: [`templates/contract-enums.sh`](../templates/contract-enums.sh).

## 4. Martwy plik kontraktu

Nieużywany wyeksportowany schemat, nieodświeżana specyfikacja, plik generowany
raz w zeszłym kwartale — to nie jest drobiazg do posprzątania. To **wakat na
najważniejszym stanowisku granicy**: granica bez żywego kontraktu produkuje
lustra z definicji, bo każda strona musi zgadnąć kształt drugiej.

Plik kontraktu MUSI mieć w CI dowód życia: albo jest regenerowany i porównywany
z commitowanym, albo nie ma go w repozytorium.

## 5. Zasady przekrojowe

- **Wersjonuje się kanon**; derywacje dziedziczą wersję. Jedna stała wersji
  kontraktu, podbijana przy każdej zmianie kształtu i zapisywana przy każdej
  operacji, która z niej korzystała. Bez tego pytanie „czemu wczoraj działało
  inaczej" nie ma odpowiedzi możliwej do udzielenia.
- **Migrator treści** jest częścią kontraktu: dane zapisane pod starszą wersją
  przechodzą migrację przed walidacją i użyciem. Klasyczny objaw braku:
  „działało w dev, produkcja rzuca przy otwarciu starego rekordu" — dev nie
  miał starych danych.
- **Limity są częścią schematu**, nie umowy ustnej: maksymalna długość,
  liczność, rozmiar ładunku. Limit w schemacie jest egzekwowalny, limit
  w głowie nie.
- **Opisy w schemacie są dokumentacją wykonawczą**, jeśli czyta je maszyna albo
  generator. Nieaktualny opis jest wtedy błędem zachowania, nie literówką.
- **Kontrakt błędów** jest kontraktem: jedna zamknięta lista błędów domenowych
  i jedna tabela mapowania na kody transportu. Komunikaty dostawców zewnętrznych
  MUSZĄ być sanityzowane przed zwróceniem — odpowiedzi 401/403 potrafią
  odbić fragment klucza.
- **Wpis logu też jest kontraktem**: wspólny zestaw pól dla wszystkich
  producentów, łącznie z przeglądarką. Identyfikator korelacji rodzi się przy
  geście użytkownika i płynie przez wszystkie procesy — jedna oś czasu zamiast
  czterech formatów do sklejania ręcznie.

## 6. Egzekwowanie

**Blokują:**

- ręczna definicja kształtu poza modułem kanonu, gdy kanon dla niego istnieje;
- ręczna edycja pliku oznaczonego jako generowany;
- brak testu parytetu na granicy dwóch języków dzielących kształt;
- rozbieżność między commitowanym generatem a wynikiem regeneracji w CI.

**Raportują:**

- plik kontraktu bez konsumenta w repozytorium;
- schemat bez limitu długości lub liczności dla pola tekstowego i kolekcji;
- zmiana kształtu bez podbicia wersji kanonu;
- ładunek walidowany tylko po jednej stronie granicy.

## 7. Sygnały maszynowe (tryb raportowy)

1. Dwie definicje tego samego kształtu w dwóch modułach.
2. Konstruktor schematu poza modułem kanonu.
3. Plik generowany zmodyfikowany commitem bez zmiany generatora.
4. Eksport kontraktu starszy niż kanon, z którego pochodzi.
5. Typ zadeklarowany ręcznie obok istniejącego schematu tego samego kształtu.
6. Generacja w dwie strony między tą samą parą języków.
7. Stała wersji kontraktu niezmieniona przy zmianie pliku kanonu.

Powiązane: [`api-contract-design.md`](api-contract-design.md),
[`forms-and-validation.md`](forms-and-validation.md),
[`typescript-javascript.md`](typescript-javascript.md),
[`code-structure.md`](code-structure.md),
[`rules-as-gates.md`](rules-as-gates.md).
