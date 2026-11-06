# Konwencja: nazewnictwo, jego wprowadzanie i pilnowanie

Stack-agnostic w warstwie zasad. Zakres: **jak nazywamy pliki, katalogi,
symbole w kodzie i byty na granicach systemu, jak wprowadza się konwencję do
kodu, który jej nie miał, i którą warstwą się jej pilnuje.**

Rozdział ról:

- [`code-structure.md`](code-structure.md) — **co** jest modułem, funkcją,
  klasą i jak są podzielone; tu chodzi wyłącznie o **nazwę**.
- [`change-provenance.md`](change-provenance.md) — format **commita**
  (typ, zakres, trailery). Ta konwencja go nie powtarza; dokłada wyłącznie
  nazwę **gałęzi**.
- [`rules-as-gates.md`](rules-as-gates.md) — procedura zamiany reguły
  w mechaniczny gate.
- [`repo-hygiene-gates.md`](repo-hygiene-gates.md) — pozostałe mechaniczne
  bramki higieny repozytorium.

Konkretne narzędzia, wersje i gotowe konfiguracje leżą w materiale datowanym
`references/naming-toolchain-2026-08.md`. **Nazwy narzędzi starzeją się
w miesiącach, kształty nazw w latach.**

---

## 1. Nazwa jest kontraktem czytanym częściej, niż pisanym

- Kształt nazwy (wielkość liter, separator, liczba mnoga) jest **decyzją
  jednorazową na całe repozytorium**. Spór o kształt kosztuje więcej niż każdy
  z rozstrzygnięć.
- **Obowiązuje przewodnik języka**, nie lokalna preferencja. Python pisze
  `snake_case`, Go `MixedCaps`, Rust `SCREAMING_SNAKE_CASE` dla stałych — nawet
  jeśli zespół woli inaczej. Kod niezgodny z przewodnikiem języka czyta się
  gorzej niż kod niezgodny z lokalną konwencją, bo czyta go też ktoś z zewnątrz.
- Gdy przewodniki dwóch języków w tym samym repozytorium mówią co innego,
  **każdy język zostaje przy swoim**. Ujednolicanie w poprzek języków jest
  najczęstszym źródłem konfiguracji lintera, której nikt nie umie obronić.
- Nazwa MUSI ujawniać intencję. Skrót, którego nie ma w leksykonie projektu
  (§5), jest nazwą prywatną autora.

## 2. Język identyfikatorów: angielski, bez wyjątku projektowego

**Identyfikatory w kodzie pisze się po angielsku** — nazwy funkcji, klas,
zmiennych, pól, modułów, tabel i kolumn. Reguła obowiązuje **nawet gdy projekt
ustalił inaczej**; jest to jedyne miejsce w tym korpusie, gdzie decyzja lokalna
nie ma pierwszeństwa, i warto powiedzieć wprost dlaczego.

Kod czyta więcej odbiorców, niż zakłada zespół, który go pisze. Czyta go
biblioteka, do której się go podłącza — a jej API jest angielskie. Czyta go
komunikat błędu, ślad stosu i zapytanie do wyszukiwarki. Czyta go narzędzie
statyczne, którego reguły są pisane pod angielskie rdzenie. I czyta go model
językowy, który zna angielskie wzorce nazewnicze nieporównanie lepiej niż
polskie — a w systemach agentowych to nie jest ciekawostka, tylko warunek
działania: agent, który ma odkryć operację po nazwie, odkryje `createOrder`,
a przy `utworzZlecenie` będzie zgadywał.

Mieszanie jest gorsze niż konsekwentna polskość. `zlecenieRepository`,
`getZlecenie`, `ZlecenieDTO` to trzy różne konwencje w jednej linii wywołania.

### Co pozostaje po polsku

- **Teksty widoczne dla użytkownika** — w języku produktu, patrz
  [`ui-copy.md`](ui-copy.md).
- **Komentarze i dokumentacja** — w języku zespołu; to one tłumaczą *dlaczego*,
  a nie *co*.
- **Terminy dziedzinowe bez angielskiego odpowiednika** — nazwy z prawa,
  administracji, kultury (`pesel`, `wojewodztwo`, `faktura_vat`). Każdy taki
  termin **musi być w leksykonie** (§5) z jednozdaniowym uzasadnieniem, że
  tłumaczenie zmieniłoby znaczenie. Leksykon jest tu bramką, nie ozdobą:
  bez niego „termin dziedzinowy" staje się furtką na wszystko.
- **Wartości danych** — to nie identyfikatory.

### Wprowadzenie

Jak każda konwencja obejmująca cały korpus: **baseline z zapadką**, nie
jednorazowe przepisanie. Zmierz liczbę deklaracji z polskim rdzeniem, zapisz
jako próg, ustaw nowy kod na zero. Zmiana nazwy publicznej idzie przez okno
wycofania (§6); zmiana prywatnej — przy najbliższym dotknięciu pliku.

Doświadczenie z trzech projektów tej floty: udział takich deklaracji wyniósł
**1–4%**, czyli znacznie mniej, niż sugerowało pierwsze wrażenie. Przed
decyzją, że „to za dużo, żeby zaczynać", policz.

## 3. Nazwy plików i katalogów: najpierw bezpieczeństwo, potem estetyka

Ta grupa reguł nie jest kwestią gustu — każda z nich odpowiada awarii, która
zdarza się przy przenoszeniu repozytorium między systemami plików:

- **Wyłącznie ASCII**: `[a-z0-9._-]`. Znaki narodowe i emoji łamią archiwa,
  klientów FTP, stare narzędzia CI i różnią się normalizacją Unicode między
  macOS a Linuksem (ten sam wyraz, dwa różne bajty).
- **Bez spacji.** Każdy skrypt bez cudzysłowu wokół zmiennej to błąd czekający
  na wywołanie.
- **Dwa pliki nie mogą różnić się wyłącznie wielkością liter.** Na macOS
  i Windowsie to jest ten sam plik; repozytorium przestaje dać się sklonować
  poprawnie i pojawiają się „zmiany", których nikt nie wprowadził.
- **Nazwy zarezerwowane systemowo** (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`,
  `LPT1`–`LPT9`) są zabronione, także z rozszerzeniem.
- **Bez kropki i spacji na końcu nazwy** — Windows je cicho obcina, więc plik
  po sklonowaniu ma inną nazwę niż w repozytorium.
- **Długość ścieżki** ma limit ustalony w projekcie; głębokie drzewa katalogów
  wywracają się na najmniej wygodnym systemie, jaki ktoś kiedyś podłączy.
- **Daty w nazwie wyłącznie w formacie ISO 8601** (`RRRR-MM-DD`), na początku,
  jeśli porządek chronologiczny ma znaczenie. Każdy inny format nie sortuje się
  leksykograficznie, czyli nie sortuje się w ogóle.
- **Numery sekwencyjne z zerami wiodącymi** (`001_`, nie `1_`) z tego samego
  powodu.

Katalogi:

- Podział **po obszarze funkcjonalnym, nie po rodzaju kodu**. Katalog
  `komponenty/` obok `serwisy/` rozrzuca jedną funkcjonalność po całym drzewie,
  więc każda zmiana dotyka pięciu miejsc oddalonych od siebie.
- **Bez katalogów autorskich** (`jan-kowalski/`, `stare/`, `nowe/`). Nazwisko
  w ścieżce jest deklaracją, że nikt inny tego nie utrzymuje.
- Głębokość zagnieżdżenia ma **ustalony limit**; przekroczenie jest sygnałem
  o podziale, nie o potrzebie kolejnego poziomu.

## 4. Kształty per rodzaj bytu

Tabela jest **domyślna**; przewodnik języka ma pierwszeństwo tam, gdzie mówi
inaczej (§1).

| Byt | Kształt | Uwaga |
| --- | --- | --- |
| plik modułu | zgodnie z językiem (`snake_case`, `kebab-case`) | spójnie w obrębie języka |
| plik z jedną klasą lub komponentem | jak nazwa tej klasy | żeby import zgadzał się ze ścieżką |
| katalog | `kebab-case` | jeden obszar funkcjonalny |
| zmienna, parametr | zgodnie z językiem | |
| funkcja, metoda | **czasownik lub fraza czasownikowa** | rzeczownik jako nazwa funkcji ukrywa efekt |
| funkcja zwracająca wartość logiczną | `is` / `has` / `can` | nazwa ma dać się przeczytać jako zdanie twierdzące |
| typ, klasa, interfejs | `PascalCase`, **rzeczownik** | prefiks `I` tylko tam, gdzie wymaga go przewodnik języka |
| stała | zgodnie z językiem | nie każdy język używa wersalików |
| klasa CSS | `kebab-case` albo pełny wzorzec blokowy | jeden wybór na repozytorium, nie na plik |
| tabela bazy | `snake_case`, **liczba mnoga** | |
| kolumna bazy | `snake_case`, **liczba pojedyncza** | wartość logiczna `is_`/`has_`, czas `_at` |
| klucz obcy | `<tabela_pojedyncza>_id` | |
| indeks, ograniczenie | `<rodzaj>_<tabela>_<kolumny>` | nazwa generowana automatycznie utrudnia diagnozę |
| zasób API | **rzeczownik**, liczba mnoga, małe litery | `GET /users`, nigdy `GET /getUsers` |
| pole ładunku API | jeden kształt w całym API | rozjazd między zasobami jest droższy niż każdy z wyborów |
| zmienna środowiskowa | `SCREAMING_SNAKE_CASE`, `[A-Z0-9_]` | prefiks dostawcy; jednostka w nazwie, gdy nieoczywista (`_MS`, `_BYTES`) |
| gałąź | `<rodzaj>/<kebab-case>` | rodzaje ustalone listą, w tym gałęzie narzędzi agentowych |
| commit | patrz [`change-provenance.md`](change-provenance.md) | |

## 5. Jedno pojęcie, jedno słowo — leksykon

Najdroższa klasa błędu nazewniczego nie jest łamaniem kształtu, tylko
**synonimią**: `user`, `account`, `member` i `principal` w jednym systemie,
każde znaczące to samo albo prawie to samo, i nikt już nie wie, które „prawie".

- Projekt MUSI mieć **leksykon**: plik z listą pojęć domenowych, po jednym
  słowie na pojęcie, wraz z terminami odrzuconymi. Szablon:
  [`../templates/lexicon.md`](../templates/lexicon.md).
- Termin odrzucony jest w leksykonie **wymieniony z nazwy** — dopiero to czyni
  regułę mechaniczną: gate szuka odrzuconych, nie zgaduje synonimów.
- Nowe pojęcie wchodzi do leksykonu **razem** z pierwszym kodem, który go
  używa, nie po fakcie.
- Skrót jest dozwolony wyłącznie wtedy, gdy jest w leksykonie. To jedyny sposób
  na odróżnienie skrótu przyjętego w domenie od prywatnego skrótu autora.
- Zmiana terminu w leksykonie pociąga **zmianę nazw w kodzie** — inaczej
  leksykon staje się historią tego, co kiedyś planowano.

## 6. Wprowadzenie konwencji do kodu, który jej nie miał

To jest część, w której najczęściej ginie cała inicjatywa. Włączenie reguły na
całym repozytorium daje tysiące naruszeń, więc ktoś ją wyłącza tego samego dnia
i nikt nie włącza jej ponownie.

- **Baseline i zapadka.** Reguła wchodzi w trybie raportowym z zapisanym stanem
  wyjściowym; blokuje wyłącznie **wzrost** liczby naruszeń względem gałęzi
  bazowej. Tryb blokujący włącza się, gdy licznik dojdzie do zera — patrz
  [`rules-as-gates.md`](rules-as-gates.md).
- **Nowy kod od pierwszego dnia, stary przy dotknięciu.** Reguła obowiązuje
  bezwarunkowo pliki nowe i zmieniane; nie wymusza obchodu całego repozytorium.
- **Zmiana nazw jest osobnym commitem** i nie zawiera zmian zachowania.
  Commit mieszający zmianę nazwy ze zmianą logiki jest nierecenzowalny: różnica
  pokazuje setki linii, z których dwie mają znaczenie.
- **Masowa zmiana nazw dostaje wpis w pliku ignorowanych rewizji** dla
  narzędzia przypisującego autorstwo linii. Bez tego jedno sprzątanie kasuje
  historię autorstwa całego pliku i następne dochodzenie „kto i po co to
  napisał" kończy się na commicie „rename".
- **Nazwa publiczna nie zmienia się z dnia na dzień**: nowa nazwa wchodzi jako
  aliasowana obok starej, stara zostaje oznaczona jako wycofywana z datą
  usunięcia. Dotyczy pól API, zmiennych środowiskowych, nazw tabel i wszystkiego,
  co czyta ktoś, kto nie czyta tego repozytorium.
- **Zmiana automatyczna przed ręczną.** Zmiana nazwy zrobiona narzędziem jest
  odwracalna i kompletna; zrobiona wyszukiwaniem i zamianą zostawia wystąpienia
  w łańcuchach znaków, komentarzach i migracjach.
- **Wielkość liter zmienia się dwoma commitami** na systemach plików, które jej
  nie rozróżniają: najpierw nazwa pośrednia, potem docelowa. Jeden commit bywa
  cicho pomijany.

## 7. Pilnowanie: cztery warstwy, jedna bramka

| Warstwa | Rola | Czy jest gwarancją |
| --- | --- | --- |
| edytor (konfiguracja wspólna) | poprawia w locie, zanim powstanie różnica | nie |
| hook lokalny | łapie przed commitem, szybka pętla zwrotna | **nie** — da się pominąć jednym przełącznikiem |
| CI na pull requeście | jedyne miejsce, którego autor zmiany nie ominie | **tak** |
| ochrona gałęzi | wymusza, że wynik CI ma znaczenie | tak |

Zasady:

- **Hook to wygoda, CI to bramka.** Reguła istniejąca wyłącznie w hooku jest
  regułą opcjonalną — pominięcie weryfikacji lokalnej jest jedną flagą.
- Ochrona gałęzi MUSI wymieniać **konkretne** wymagane sprawdzenia. Pusta lista
  wymaganych sprawdzeń przy włączonej ochronie wygląda jak zabezpieczenie
  i nim nie jest.
- Ochrona MUSI obejmować **też administratorów**, inaczej opisuje zwyczaj,
  a nie mechanizm.
- Każda reguła nazewnicza ma **jednego właściciela mechanicznego**: konkretne
  narzędzie i konkretny plik konfiguracji. Reguła opisana wyłącznie prozą
  w dokumencie jest spełniana deklaratywnie.
- Reguła, której **nie da się** sprawdzić mechanicznie, MUSI być oznaczona
  w dokumencie jako „brak automatycznej weryfikacji — przegląd kodu".
  Przemilczenie zamienia listę bramek w listę życzeń.

## 8. Czego nie da się zautomatyzować

Pokrycie mechaniczne kończy się w okolicach dwóch trzecich reguł. Uczciwa lista
tego, co zostaje przeglądowi — po to, żeby nie udawać, że bramka wystarcza:

1. Czy nazwa **ujawnia intencję**, czy tylko spełnia wzorzec (`data`, `mgr`,
   `helper` przechodzą każdy lint).
2. Czy w całej zmianie użyto **jednego słowa na pojęcie** (leksykon zmniejsza
   ten problem, nie usuwa).
3. Czy klasa jest rzeczownikiem, a metoda czasownikiem **w sensie**, nie tylko
   w kształcie.
4. Czy podział na katalogi odpowiada realnym obszarom domeny.
5. Czy stała powinna być stałą, a nie wartością wyliczaną.
6. Czy nazwa pliku odpowiada jego zawartości po ostatnich pięciu zmianach.

**Wniosek jest częścią reguły, nie zastrzeżeniem do niej:** automat pilnuje
kształtu, człowiek pilnuje znaczenia. Projekt, który zakłada, że linter
wystarczy, dostaje kod poprawny formalnie i nieczytelny.

## 9. Egzekwowanie

**Blokują:**

- nazwa pliku lub katalogu spoza dozwolonego zbioru znaków, ze spacją, ze
  znakiem narodowym albo zakończona kropką lub spacją;
- dwa pliki różniące się wyłącznie wielkością liter;
- nazwa zarezerwowana systemowo;
- naruszenie kształtu wymaganego przez linter języka na pliku nowym lub
  zmienionym;
- wzrost liczby naruszeń względem gałęzi bazowej przy regule w trybie zapadki;
- nazwa gałęzi spoza ustalonej listy rodzajów.

**Raportują:**

- termin odrzucony leksykonem użyty w kodzie;
- skrót spoza leksykonu w nazwie publicznej;
- data w nazwie pliku w formacie innym niż ISO 8601;
- głębokość katalogów powyżej ustalonego limitu;
- reguła nazewnicza bez przypisanego narzędzia i pliku konfiguracji.

## 10. Sygnały maszynowe (tryb raportowy)

1. Plik trackowany ze spacją, znakiem spoza ASCII albo końcową kropką w nazwie.
2. Dwie ścieżki identyczne po sprowadzeniu do małych liter.
3. Katalog o nazwie będącej imieniem, nazwiskiem albo określeniem czasowym
   (`stare`, `nowe`, `tmp`).
4. Commit zmieniający nazwy i zachowanie jednocześnie (zmiana nazwy pliku
   z modyfikacją treści powyżej progu).
5. Masowa zmiana nazw bez wpisu w pliku ignorowanych rewizji.
6. Termin z listy odrzuconych leksykonu obecny w kodzie.
7. Ochrona gałęzi z pustą listą wymaganych sprawdzeń.
8. Reguła w dokumencie konwencji bez odpowiadającego wpisu w konfiguracji
   któregokolwiek narzędzia.

Powiązane: [`code-structure.md`](code-structure.md),
[`rules-as-gates.md`](rules-as-gates.md),
[`repo-hygiene-gates.md`](repo-hygiene-gates.md),
[`change-provenance.md`](change-provenance.md),
[`quality-gates-and-dod.md`](quality-gates-and-dod.md),
[`contract-canon.md`](contract-canon.md).
