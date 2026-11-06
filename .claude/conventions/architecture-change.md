# Konwencja: zmiana architektury i migracja danych

Stack-agnostic. Zakres: **co trzeba wiedzieć, zanim zapadnie decyzja o dużej
zmianie technicznej, dlaczego przepisanie systemu rzadko naprawia to, co miało
naprawić, i jak migruje się dane bez okresu, w którym żadna baza nie jest
prawdziwa.**

Rozdział ról:
[`architecture-principles.md`](architecture-principles.md) mówi, **jak podjąć
decyzję projektową**; ta konwencja — **jak podjąć decyzję o jej zmianie**.

---

## 1. Taksonomia awarii przed decyzją, nie po niej

Zanim zapadnie decyzja „zmieniamy stack / przepisujemy / przenosimy", MUSI
powstać **taksonomia awarii**: lista realnych, udokumentowanych awarii z
ostatniego okresu, z przyczyną źródłową każdej.

Potem zadaje się jedno pytanie: **które z tych awarii proponowana zmiana usuwa
przyczynowo?** Jeśli odpowiedź wymaga machania rękami, zmiana adresuje
estetykę, nie niezawodność — co bywa uzasadnione, ale wtedy trzeba to napisać
wprost, żeby koszt oceniano właściwą miarą.

Typowy wynik takiej taksonomii bywa zaskakujący: awarie, które „biorą się
z tego, że mamy dwa języki", po spisaniu okazują się rozjazdem dwóch list
w jednym module, brakiem opcji w konfiguracji, sprzecznością w instrukcji
i brakiem właściciela cyklu życia pracy w tle. Żadnej z nich nie usuwa
ujednolicenie stacku.

**Pomiar bije opinię; opinia z pomiarem bije opinię z pozycją.** Sprzeciw
zespołu poparty taksonomią awarii nie jest oporem przed zmianą — jest
najtańszym audytem architektury, jaki można dostać.

Wyzwalacz nie musi czekać na decyzję o przepisaniu. Trzecia nieudana
naprawa tego samego objawu, gdy każda odsłania sprzężenie w innym miejscu
albo wymaga „większej przebudowy", jest sygnałem do spisania taksonomii,
nie do czwartej naprawy. Trzy porażki z rzędu rzadko są trzema złymi
hipotezami; częściej są jedną złą granicą.

## 2. Granice bólu przeżywają przepisanie

Każdy system ma granice, na których żyje jego prawdziwa złożoność, i zwykle
**nie są to granice językowe**: klient↔serwer (stan, strumień, formularz),
serwer↔sterowany proces zewnętrzny, system↔dostawca zewnętrzny.

Po przepisaniu na jeden język te granice zostają dokładnie tam, gdzie były,
z tymi samymi klasami awarii — tyle że **bez dotychczasowych testów
regresyjnych**, które je pilnowały.

## 3. Przepisanie kasuje wiedzę wgraną w kod

Utwardzony kod zawiera dziesiątki niewidocznych decyzji: idempotentne etapy,
kaskadowe unieważnienia, zamrożenia stanu na granicach, obejścia błędów
zależności. Każda z nich została wgrana po jednej naprawie, zwykle bez
komentarza, bo w chwili naprawy była oczywista.

Przepisanie odtwarza **funkcje**, nie odtwarza **napraw**, których nikt już nie
pamięta. Dlatego zdrowa migracja klasyfikuje kod, zamiast dzielić go na „stare
złe" i „nowe dobre":

| Klasa | Znaczenie |
| --- | --- |
| ZOSTAJE | działa i nie stoi na drodze |
| ADAPTUJ | przenieś do właściwej roli bez przepisywania logiki |
| PORT | przepisz, bo wymaga tego reguła architektury |
| ODRZUĆ | świadomie porzuć, spisując wnioski, które w tym kodzie siedziały |

Kod bez przypisanej klasy nie jest gotowy do migracji — brak klasy znaczy, że
nikt go nie przeczytał.

## 4. Chroniczna niestabilność mieszka na krawędzi, nie w rdzeniu

Wzorzec „u nas zawsze coś nie działa" ma zwykle mierzalny mechanizm: rdzeń jest
zielony (setki testów przechodzą), a czerwień pochodzi z **na wpół wpiętych
dostawek** — kodu spekulatywnego, adapterów bez miejsca wywołania,
dokumentacji bez implementacji. Każda sesja dokłada powierzchnię szybciej, niż
domyka poprzednią.

Naprawa jest procesowa, nie technologiczna: **kod niedokończony żyje na
gałęzi; gałąź główna jest zielona zawsze; czerwony test wiszący dłużej niż
ustalony czas jest incydentem procesu, nie tłem.**

Koszt dodatkowy wiszącej czerwieni jest psychologiczny i realny: przestaje się
odróżniać „zepsułem coś" od „to zawsze było czerwone", więc każdy przebieg
wygląda jak porażka i przestaje być czytany.

## 5. Decyzja dostaje sygnał rewizji, nie wieczność

- Każda decyzja architektoniczna MUSI mieć zapisany **mierzalny sygnał
  rewizji**: obserwację, po której wraca na stół („odsetek konfliktów zapisu
  powyżej progu", „drugi użytkownik", „debugowanie jednego przebiegu regularnie
  ponad pół godziny").
- Sygnał jest **liczbą albo zdarzeniem**, nie odczuciem. „Gdy zacznie
  przeszkadzać" nie jest sygnałem.
- To samo dotyczy decyzji **odmownych**: rzecz świadomie niewdrożona ma powód
  i sygnał powrotu w rejestrze decyzji, żeby za pół roku nikt nie rekonstruował,
  czy to był wybór, czy przeoczenie.

### Nowsza decyzja zastępuje wcześniejszą i zabiera ze sobą to, co z niej wisiało

Decyzja podjęta w audycie **nadpisuje wcześniejsze rozstrzygnięcia o tej samej
rzeczy** i unieważnia pozycje, które istniały wyłącznie dlatego, że tamta rzecz
stała. „Widok stoi na Next" nie stoi obok „Astro zostaje" jako druga opcja —
kasuje ją, a razem z nią wszystko, co było o Astro. Bez tej reguły rejestr
rośnie o warianty, których nikt nie wybrał, i po kilku audytach nie wiadomo,
co jest w mocy.

Przy zapisywaniu decyzji, która coś zastępuje, wypisz **trzy rzeczy**:

1. **Co przestaje obowiązywać** — z numerem wcześniejszej decyzji albo pozycji.
2. **Które pozycje znikają razem z nią** — te, które istniały tylko przez
   zastąpioną technologię. Pozycja o dziurze w `login.astro` nie znika, bo
   dziura jest dziś; pozycja o konfiguracji Astro znika, bo nie będzie czego
   konfigurować.
3. **Czego decyzja NIE obejmuje** — domysł, że obejmuje wszystko dookoła, jest
   równie kosztowny jak domysł, że nie obejmuje niczego.

Odwrotny kierunek też jest regułą: **decyzja unieważnia wcześniejsze odrzucenie**
tej samej rzeczy. Pozycja odrzucona jako „nie warto" wraca jako część nowej
decyzji, a nie jako nowe znalezisko w następnym audycie — inaczej audyt melduje
ją co tydzień, a rejestr co tydzień ją odrzuca.

Zastąpienia nie wolno zostawić domyślnym. Wcześniejsza decyzja **nie wygasa
sama przez to, że powstała nowsza** — dopóki nikt nie napisał, co ją zastępuje,
obie są w mocy i sprzeczne.

## 6. Koszt zwłoki jest różny dla różnych decyzji

To jest rozróżnienie, które decyduje o kosztach na lata:

| Klasa | Charakterystyka | Sposób obsługi |
| --- | --- | --- |
| tanio odraczalna | ma naturalny punkt rozszerzenia (pole rodzaju, interfejs, alias) | zostaw furtkę, decyduj później |
| nieodraczalna | przenika każdą jednostkę kodu (tożsamość, korelacja, wersjonowanie, wymiar właściciela) | musi być od pierwszego commitu |

Heurystyka: jeśli dołożenie tego później wymaga przejrzenia **każdego**
zapytania, handlera albo wpisu logu — jest nieodraczalne. Jeśli wymaga
dołożenia wariantu do jednej unii — jest odraczalne i nie warto o nim dyskutować
przed czasem.

## 7. Dowolność przez regułę, nie przez brak reguły

Gdy zespoły potrzebują autonomii, nie rozdaje się wyjątków — definiuje się
**regułę kształtu** (test rozstrzygający), wewnątrz której autonomia jest
pełna. Lider dostaje realną władzę nad **zawartością**, architektura zachowuje
niezmienniki co do **wpięcia**; przykład takiej reguły:
[`background-work.md`](background-work.md) §8.

Reguła kształtu MUSI wymuszać granice logiczne i kontrakty, **nie strukturę
katalogów**. Spór o nazwy folderów odciąga uwagę od rzeczy, które naprawdę
psują systemy.

## 8. Dokument nakazowy, który zespół egzekwuje

Punkt dokumentu działa, gdy ma trzy części: **wymaganie** (co ma być),
**dlaczego** (jaki konkretny błąd — najlepiej z własnej historii — eliminuje)
i **jak sprawdzić** (mechanicznie, w CI).

- Wymaganie bez „dlaczego" zostaje zignorowane przy pierwszym konflikcie
  z terminem.
- Wymaganie bez „jak sprawdzić" jest spełniane deklaratywnie.
- Antywzorce dokumentuje się **indeksem objaw → zasada**: od objawu, który
  zespół pamięta, do reguły, która mu zapobiega. Pamięć incydentu jest
  najsilniejszym nośnikiem reguły.
- Dokument MUSI mieć klauzulę pierwszeństwa (co nadpisuje) i procedurę
  odstępstwa, inaczej konkuruje z historią ustaleń zamiast ją zamykać.

## 9. Migracja danych

- Migracja jest **kodem z testami**, nie jednorazowym skryptem: idempotentna
  (N uruchomień daje ten sam wynik), z raportem wyjątków i osobnym skryptem
  weryfikacji (liczności, sumy kontrolne, próbka porównana polami).
- Rekord niezgodny z docelowym schematem trafia **do raportu z powodem**,
  nie do cichego pominięcia. Decyzję o każdej klasie takich rekordów podejmuje
  człowiek: napraw w źródle, napraw w mapowaniu, porzuć świadomie.
- **Zapis do dwóch źródeł naraz jest zabroniony.** W każdym momencie jeden
  zbiór danych ma jedno źródło prawdy; okres, w którym obie bazy są „trochę
  prawdziwe", jest okresem, w którym żadna nie jest.
- Historia zastana jest **archiwizowana jako artefakt**, nie konwertowana na
  struktury docelowe na siłę.
- Sekrety są **rotowane przy migracji**, nie kopiowane.
- Wycofanie jest **przećwiczone przed przełączeniem**, nie opisane w planie.

## 10. Egzekwowanie

**Blokują:**

- decyzja o zmianie stacku lub przepisaniu bez zapisanej taksonomii awarii;
- migracja danych bez skryptu weryfikacji i bez przećwiczonego wycofania;
- równoległy zapis do starego i nowego źródła prawdy;
- czerwona gałąź główna dłużej niż ustalony czas.

**Raportują:**

- decyzja architektoniczna bez sygnału rewizji;
- kod niedokończony scalony do gałęzi głównej;
- wpis w rejestrze decyzji bez sekcji „świadomie tracimy";
- reguła w dokumencie bez sposobu sprawdzenia.

## 11. Sygnały maszynowe (tryb raportowy)

1. Wpis decyzji bez pola sygnału rewizji.
2. Skrypt migracji bez odpowiadającego skryptu weryfikacji.
3. Moduł zapisujący do dwóch źródeł tego samego faktu.
4. Test oznaczony jako pomijany bez daty wygaśnięcia.
5. Katalog lub moduł bez żadnego miejsca wywołania.
6. Gałąź główna z czerwonym przebiegiem starszym niż próg.
7. Dokument reguł bez klauzuli pierwszeństwa.


## Egzekwowanie: rozstrzyga czytanie

**Tej reguły nie egzekwuje żaden skrypt.** Klasyfikacja kodu na ZOSTAJE/ADAPTUJ/PORT/ODRZUĆ, rozróżnienie decyzji tanio odraczalnych od nieodraczalnych i rozstrzygnięcie, co robić z rekordami niezgodnymi z docelowym schematem, są osądem o konkretnym systemie. Skrypt umie policzyć, czy migracja ma parę weryfikacyjną — nie umie powiedzieć, czy zmiana usuwa przyczynę awarii, czy tylko ją przesuwa.

W rejestrze reguł (`templates/rejestr-regul.sh`)
ta konwencja stoi w koszyku `czytanie` i pokazuje się w raporcie audytu jako
CZYTANA — czyli reguła, która stoi na czyimś słowie, a nie na kodzie wyjścia.
Zapisane jest to jawnie, bo reguła wyglądająca na egzekwowaną, a nieegzekwowana,
jest dokładnie tą miękkością, o którą chodzi: brzmi tak samo stanowczo jak
`code-structure.md`, a nikt jej nie sprawdza.

Zmiana tego stanu wymaga napisania bramki i przeniesienia wiersza do koszyka
`bramka` w tym samym commicie. Dopóki tego nie ma, „MUSI" w tym pliku znaczy
„MUSI, a sprawdzi to człowiek".

Powiązane: [`architecture-principles.md`](architecture-principles.md),
[`stack-composition.md`](stack-composition.md),
[`quality-gates-and-dod.md`](quality-gates-and-dod.md),
[`rules-as-gates.md`](rules-as-gates.md),
[`background-work.md`](background-work.md).
