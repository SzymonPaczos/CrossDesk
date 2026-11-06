# Konwencja: obalanie twierdzeń w dokumentach stanu

Stack-agnostic. Wyekstrahowana 2026-09-04 z projektu civic-tech prowadzonego
tym toolkitem od maja. Uzupełnia
[`project-state-layout.md`](project-state-layout.md) (gdzie co ma leżeć) —
ta konwencja mówi, **jak wyłapywać zdania, które przestały być prawdziwe**.

## Problem

Dokument stanu nie kłamie w chwili pisania. Kłamie później — kod się zmienia,
decyzja się zmienia, a zdanie zostaje. Zdanie, które przeżyło swoją
prawdziwość, jest **gorsze niż brak zdania**, bo następny czytelnik podejmie
na jego podstawie decyzję i nie będzie miał powodu go sprawdzać.

Zmierzone w jednym dniu (2026-09-04), każde twierdzenie przeżyło ≥1 audyt
próbkujący:

| Twierdzenie | Rzeczywistość | Koszt |
|---|---|---|
| „każda migracja rekreuje bazę produkcyjną” | poprawka w kodzie od 1.09; hash liczony z samego Dockerfile’a | rok odkładania migracji na „specjalne okna” |
| plik strategii: data startu, aktywny freeze, „funkcja odłożona” | wszystkie trzy nieaktualne o 5–6 tygodni | agent projektujący wbrew zniesionemu freeze’owi |
| „**59** migracji” | 60 (zmieniło się tego samego dnia) | drobny, ale to ta sama klasa |

Audyt mówił „wyrywkowo zweryfikuj liczby”. Próbka z definicji omija większość
zdań, a agent próbkuje to, co łatwe.

## Czego NIE da się zmechanizować (zmierzone, nie przypuszczane)

Zanim zbudujesz bramkę „każda liczba i każde zdanie”, zobacz pomiar z repo
o 1400-linijkowym backlogu:

- **ścieżki w backtickach: 79 trafień na 707** — i przewaga to **fałszywe
  alarmy**: backlog z natury opisuje pliki, które dopiero mają powstać
  (`worktree-setup.sh`, `verify_against_source.py`) oraz przykłady w szablonach
  (`foo.test.ts`);
- **skróty commitów: 4 na 14** — z czego jeden był **blobem**, nie commitem,
  a dwa należały do **innego repozytorium**;
- **liczby w tekście: ~1167** — górna granica tego, co człowiek musiałby
  przeczytać.

Bramka z takim szumem uczy obchodzenia, a bramka obchodzona nie istnieje.
Deklarowanie pokrycia, którego się nie ma, jest tą samą nieuczciwością, którą
konwencja miała zwalczać.

## Co działa

**Rejestr faktów przeliczalnych.** Fakty, które dokumenty powtarzają, a repo
umie policzyć: liczba warstw bramki, liczba migracji, liczba pozycji backlogu,
liczba kotwic spisu treści. Dla każdego: komenda pomiaru + ciasny wzorzec +
warunek kontekstu. Checker przelicza i wskazuje **każdy** dokument twierdzący
co innego — nie próbkę.

**Lista wartości wycofanych.** Klasa, której żadna komenda nie przeliczy: daty,
statusy, decyzje. Wpis = (wartość, wzorzec kontekstu, co ją zastąpiło).
Kontekst jest konieczny: wycofana data legalnie występuje jako znacznik pomiaru
(„zmierzone 2026-09-01”). **Wpis usuwa się, gdy sprzątanie skończone** — linia
zapalająca się zawsze przestaje być czytana.

**Rejestr decyzji jest wyłączony z obu list.** To miejsce, w którym zapisuje
się wycofanie; jego własna reguła brzmi „decyzji się nie usuwa, zmienia się
status”, więc wartości wycofane mają tam prawo żyć wiecznie.

**Dwa filtry cytowania, nie jeden.** Fakty przeliczalne filtruj **wąsko**
(przekreślenie, cudzysłów, „opisywało stan…”). Wartości wycofane — **szeroko**
(dodatkowo znacznik pomiaru, strzałka „A → B”, „usunięty”, „przeniesione z”).
Powód jest zmierzony sabotażem: pierwsza wersja wykluczała każdą linię ze
słowem „pomiar”, a konwencja prowieniencji liczb **wymaga**, by każda liczba
niosła obok komendę pomiaru — filtr pomijał więc niemal każde prawdziwe
twierdzenie i przemilczał dokument mówiący o 1 migracji przy 60.

## Decyzja, która przestała obowiązywać

Powyższe mówi, jak **wyłapać** zdanie, które przeżyło swoją prawdziwość. Ta
sekcja mówi, co z nim **zrobić**, gdy jest zapisem decyzji, odstępstwa albo
pozycji backlogu — czyli czymś, co z definicji ma się kiedyś zmienić.
Kształt pozycji backlogu opisuje [`backlog-contract.md`](backlog-contract.md);
pola commita, w których decyzję się cytuje —
[`change-provenance.md`](change-provenance.md).

**ADR i backlog istnieją po to, żeby je zmieniać.** Zapis decyzji nie jest
zobowiązaniem na zawsze i NIE WOLNO traktować go jak ograniczenia, którego nie
da się podważyć. Założenie, które w trakcie pracy okazało się złe, zmienia się
w trakcie, w granicach upoważnienia: **powiedz o tym wtedy, kiedy to
robisz**, w tej samej rozmowie albo w tym samym commicie, jednym zdaniem o tym,
co się zmieniło i dlaczego. Milcząca zmiana założenia jest tym, co kosztuje;
sama zmiana nie. „Tak było ustalone" nie jest argumentem — argumentem jest
powód, dla którego ustalono, i on albo dalej obowiązuje, albo nie.
Samo poinformowanie nie upoważnia do zmiany celu, zawężenia zakresu ani
zmiany kryteriów odbioru lub decyzji zastrzeżonej dla właściciela;
stosuje się istniejące upoważnienie według `agent-communication.md` §4.

**Odstępstwo zapisane MUSI zostać zrewidowane w commicie, który je cofa.**
„Zrobiliśmy X zamiast Y, celowo, bo Z" jest dobrym zapisem i miną z opóźnionym
zapłonem naraz: opisuje stan, który ma się zmienić, i nic nie pilnuje momentu
zmiany. Zmierzone: trzy odstępstwa zapisane 2026-09-05, wszystkie cofnięte
nazajutrz, żaden zapis nietknięty — dokument twierdził, że klatka robi się po
geście, gdy kod robił ją przed. Zapis nie znika, bo odstępstwo skreślone bez
śladu wygląda jak decyzja, której nikt nie podjął; zostaje **przekreślone,
z nazwą tego, co je zniosło**.

**„Zmienia się status" ma trzy stany, nie dwa.** Reguła z sekcji „Co działa"
wymaga, żeby każdy wpis niósł jeden z nich:

| Status | Znaczenie |
|---|---|
| obowiązuje | opisuje kod, który jest |
| zniesiona przez #N | inna decyzja ją zastąpiła; #N mówi czym i dlaczego |
| wycofana | przestała obowiązywać i nic nie weszło w jej miejsce |

Decyzja znosząca cytuje znoszoną z numeru, a znoszona dostaje odsyłacz
w drugą stronę — bez tego czytający idący od starego wpisu nigdy nie trafi na
nowy, a wpis sprzeczny z kodem, stojący nieoznaczony obok wpisów aktualnych,
jest gorszy niż jego brak.

**Zapis zależny od stanu świata dostaje datę przeglądu.** „Zostaje, aż retencja
zdejmie ostatnie wiersze", „tymczasowo bierzemy wersję beta" — bez daty
„tymczasowo" jest permanentne (ta sama reguła co w
[`tool-adoption-and-measurement.md`](tool-adoption-and-measurement.md) §10).
Data jest lepsza od warunku prozą, bo da się ją posortować; wpisy z datą
w przeszłości są raportem, nie blokadą.

## Egzekwowanie

Krok **obowiązkowy** audytu, nie próbka. **Rozjazd naprawia się w tym samym
commicie co audyt** — raport o kłamstwie, które zostaje w pliku, to tylko
niepokój. Tryb raportujący wystarcza: bramka blokująca push nie jest potrzebna,
bo dokument stanu nie psuje builda, tylko następną decyzję.

Checker ma **własny meta-test** (patrz [`test-evidence.md`](test-evidence.md)),
a ten test musi dowieść obu rzeczy naraz:

1. **cisza na czystym drzewie** — narzędzie, które zawsze coś zgłasza,
   przestaje być czytane (ta sama klasa co alert stale czerwony);
2. **czerwień na sabotażu** — wstrzyknięta zła liczba, zły licznik i wskrzeszona
   wycofana data muszą zapalić; check, który nie może paść, nie jest checkiem.

Ten drugi punkt nie jest formalnością: przy pisaniu tej konwencji sabotaż
wykrył **dwie realne wady** świeżego checkera (za szeroki filtr cytowania oraz
porównanie kontekstu wrażliwe na wielkość liter), zanim trafił do repo.

## Czego ta konwencja nie obiecuje

Twierdzeń o **zachowaniu** kodu („producent pisze X przy każdym syncu”, „smoke
trafia w aplikację”) nie sprawdzi żaden regex — zostają lekturą. Różnica wobec
stanu sprzed konwencji jest taka, że lektura zaczyna się od listy, którą
maszyna już przemieliła, a narzędzie **mówi wprost, czego nie sprawdza**,
zamiast sugerować pokrycie, którego nie ma.

## Sygnały maszynowe

- dokument stanu powtarzający liczbę, którą repo umie policzyć, bez komendy obok,
- wpis na liście wartości wycofanych, który nie ma już żadnego trafienia
  (do usunięcia),
- checker bez meta-testu na ciszę **i** na sabotaż,
- wpis rejestru decyzji bez pola statusu, albo „zniesiona przez #N" cytująca
  numer, którego w pliku nie ma,
- odstępstwo lub wpis „tymczasowo" z datą przeglądu w przeszłości.
