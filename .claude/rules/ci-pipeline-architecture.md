# Konwencja: architektura pipeline'u i audyt CI/CD

Stack-agnostic. Zakres: **topologia bramek i ich egzekwowalność** — w jakiej
kolejności biegną, co blokuje, a co tylko raportuje, i jak sprawdzić, czy
istniejący pipeline faktycznie chroni to, co obiecuje.

Rozdział ról między konwencjami:

- [`ci-cd.md`](ci-cd.md) — bezpieczeństwo dostawy: uprawnienia, pinowanie,
  lockfile, sekrety, provenance, release. **Nie duplikuj tego tutaj.**
- [`test-evidence.md`](test-evidence.md) — czy pojedynczy test cokolwiek dowodzi.
- [`rules-as-gates.md`](rules-as-gates.md) — procedura zamiany reguły w gate.
- [`progressive-delivery.md`](progressive-delivery.md) — co dzieje się z
  artefaktem po zielonym pipelinie.

## 1. Pipeline jest grafem, nie listą

Ustaw joby w kolejności rosnącego kosztu i uczyń tanie **warunkiem** drogich.
Formatter i lint krytyczny biegną pierwsze i są `needs` dla testów; testy są
`needs` dla budowy artefaktu.

Konsekwencja jest celowa: czerwony formatter nie zgłasza uwagi obok wyników
testów — on **kasuje** resztę przebiegu. Autor dostaje jeden powód
niepowodzenia zamiast piętnastu krzyżyków, z których nie wynika, co jest
przyczyną, a co skutkiem.

Skutek uboczny, który trzeba znać i zaakceptować: PR z czerwonym linterem
wygląda na nieprzetestowany, bo joby testowe nigdy nie wystartowały. To jest
cecha, nie wada — ale wymaga, by dokumentacja mówiła wprost, że lint jest
warunkiem wstępnym, a nie równoległą opinią.

**Antywzorzec:** wszystkie joby równolegle, bez zależności. Pipeline jest
szybszy w scenariuszu, w którym wszystko przechodzi, i bezużyteczny
diagnostycznie w tym, w którym się psuje.

## 2. Detekcja zmian na wejściu grafu

Jeden tani job na starcie wylicza, których obszarów dotyczy zmiana; reszta
wisi na jego wyjściu. Dwie reguły, obie wyuczone na cudzych awariach:

1. **Filtr musi obejmować sam plik pipeline'u.** Inaczej zmiana definicji
   pipeline'u jest jedyną zmianą, której ten pipeline nie testuje.
2. **Nie filtruj triggerem, jeśli check jest wymagany.** Job pominięty przez
   filtr na poziomie zdarzenia zwykle nie raportuje statusu w ogóle, więc PR
   czeka w nieskończoność na check, który nigdy nie wystartuje. Filtruj
   warunkiem wewnątrz joba, żeby zawsze powstał wynik — choćby pusty sukces.

## 3. Ekonomia feedbacku

- **Anuluj nieaktualne przebiegi** per gałąź. Kolejna wersja poprawki
  unieważnia poprzednią; płacenie za obie jest czystą stratą.
- **Timeout na dwóch poziomach**: całego joba i pojedynczego testu/kroku.
  Brak timeoutu oznacza, że jedna zawieszona operacja zjada limit czasu, a
  logi nie mówią która. Timeout testu daje nazwę winowajcy.
- **Cache tylko deterministyczny** — kluczowany lockfile'em lub sumą
  kontrolną manifestu. Cache kluczowany gałęzią zamienia „czyste środowisko"
  w loterię i jest jedną z typowych przyczyn „u mnie w CI przechodzi".
- Pierwszy czerwony sygnał ma przyjść **przed** końcem długich jobów.

## 4. Macierz odpowiada na pytanie o wsparcie

Macierz nie jest miarą powagi projektu, tylko odpowiedzią na pytanie „co
deklarujemy, że wspieramy". Stąd:

- **Granice obowiązkowo**: najstarsza i najnowsza wspierana wersja
  runtime'u/systemu. Środek próbkuj — to tam awarie są najrzadsze.
- **Wyłącz przerywanie po pierwszej porażce.** Różnica między „pęka na jednej
  wersji" a „pęka na wszystkich" to różnica między błędem kompatybilności a
  zwykłym bugiem — i jest widoczna wyłącznie wtedy, gdy pozostałe komórki
  dobiegły do końca. Przerywanie oszczędza minuty i kosztuje diagnozę.
- Deklarowana macierz i deklaracja wsparcia w dokumentacji to ten sam zbiór.
  Rozjazd oznacza, że jedno z dwóch jest nieprawdą.

## 5. Twarde bramki i sygnały miękkie

Trzy pytania decydują, czym coś ma być:

1. Czy sygnał jest **deterministyczny** — ten sam wynik dla tego samego commita?
2. Czy **fałszywy alarm jest tani** do rozpoznania i naprawy?
3. Czy autor może go **naprawić bez cudzej infrastruktury**?

Trzy razy „tak" → twarda bramka. Choć jedno „nie" → sygnał raportowy.

Typowo twarde: formatowanie, lint błędów krytycznych, testy jednostkowe,
budowa artefaktu, spójność wersji i lockfile'a.

Typowo miękkie: macierz środowisk zewnętrznych, pokrycie, benchmarki,
skanery o wysokim odsetku fałszywych trafień.

**Zasada spójności deklaracji z egzekucją.** To, co w pipelinie jest miękkie,
nie może być w dokumentacji opisane jako wymagane. Rozjazd jest gorszy niż
brak reguły: nowy współpracownik czyta „wymagamy X", zakłada że platforma go
przypilnuje, i nikt nie sprawdza X. Albo egzekwuj, albo napisz „staramy się".

Miękki sygnał bez właściciela i bez rytmu przeglądu jest szumem — po miesiącu
nikt nie odróżnia stałego ostrzeżenia od nowego. Nadaj mu przegląd albo usuń.

Procedurę awansu miękkiego sygnału na twardy opisuje
[`rules-as-gates.md`](rules-as-gates.md).

## 6. Artefakt weryfikuj poza hostem, który go zbudował

Host budujący ma przypadkiem zainstalowane wszystko, czego projekt kiedykolwiek
potrzebował. Użytkownik nie ma nic. To jest klasa błędu niewykrywalna testem
jednostkowym i najczęstsze źródło „u nas działa, u nich się nie uruchamia".

**Wzorzec:** każdy dystrybuowany artefakt dostaje smoke test w tym samym
przebiegu, który go zbudował, przy odciętych zasobach hosta. Warianty, od
najtańszego:

- uruchomienie w czystym kontenerze bazowego systemu, bez zależności
  deweloperskich;
- odcięcie sieci na czas smoke testu (artefakt nie może dociągać brakujących
  części w locie);
- przesłonięcie systemowych ścieżek wyszukiwania pustym katalogiem, tak by
  jedynym źródłem zależności był bundle;
- uruchomienie w **najstarszym** deklarowanym wspieranym środowisku.

Smoke test ma sprawdzać uruchomienie i inicjalizację realnych podsystemów, nie
istnienie pliku. „Artefakt się zbudował" nie jest twierdzeniem o tym, że działa.

## 7. Konfiguracja i skrypty budowy są kodem — i mają swoje testy

Regresje w pipelinie i pakowaniu wracają dokładnie tak samo jak regresje w
kodzie, a nie chroni ich żaden test jednostkowy. Wzorzec, który to domyka:
**test czytający plik konfiguracyjny lub skrypt budowy i asertujący na jego
zawartości**, z komentarzem wskazującym incydent, który tę asercję wymusił.

Taki test pilnuje niezmienników typu „ta lista zależności musi zawierać X, bo
jej przycięcie zepsuło platformę Y" albo „ten krok nie może zostać usunięty".
Kosztuje kilka linii, żyje w zwykłej suite i broni się sam przy przeglądzie,
bo niesie numer zgłoszenia.

Zasada nadrzędna: **awaria u użytkownika kończy się gate'em, nie komentarzem
w kodzie.** Komentarz „nie usuwaj tego" jest prośbą; test jest bramką.

## 8. Jedno źródło prawdy dla wersji

Wersja żyje w jednym pliku. Każde inne miejsce, które ją powtarza — manifesty
pakietów, strona, metadane, dokumentacja — jest z niego **generowane albo
weryfikowane** w CI.

Krok porównujący wersję z tagiem wydania działa fail-closed. Podmiana wersji
w wielu plikach bez takiej weryfikacji cicho się rozjeżdża: ostrzeżenie w
logu, którego nikt nie czyta, jest równoważne jego brakowi.

## 9. Kanały wydań to etykiety, nie osobne skrypty

Stabilny (z taga), nocny (z harmonogramu), preview (z gałęzi) — wszystkie
przechodzą **tą samą ścieżką budowy**, różniąc się wyłącznie sposobem
wyliczenia identyfikatora wersji i miejscem publikacji. Osobny skrypt dla
nightly gwarantuje, że nightly przestanie odzwierciedlać release.

Kanał ciągły ma **retencję i sprzątanie starych wydań** wpisane w ten sam
workflow. Bez tego rośnie w nieskończoność, a lista wydań przestaje być
czytelna.

## 10. Konfiguracja repozytorium jest częścią pipeline'u

Bramki żyjące poza plikami workflow, a decydujące o jakości tak samo:

- **jedna dozwolona metoda scalania** — historia jest albo liniowa, albo nie;
- **automatyczne kasowanie gałęzi po scaleniu**;
- **unieważnianie zatwierdzeń po nowym pushu** — inaczej approval dotyczy
  kodu, którego już nie ma w PR;
- **lista wyjątków od reguł jest pusta albo zapisana w decyzjach**.

Reguła nadrzędna: **właściciel podlega tym samym bramkom.** Jeśli maintainer
wypycha na chronioną gałąź z pominięciem procesu, bramka nie istnieje —
istnieje tylko dla obcych, a przy jednoosobowym projekcie to znaczy, że nie
istnieje wcale. Praktyczny test: czy w historii chronionej gałęzi są commity
bez numeru PR i kto je tam umieścił.

## 11. Procedura audytu istniejącego CI/CD

Kolejność od egzekwowalności do treści — bo najdroższe pomyłki to nie „brak
testu X", tylko „gate, którego nikt nie włączył".

1. **Co jest naprawdę wymagane?** Zestaw listę zdefiniowanych jobów z listą
   checków wymaganych przez regułę scalania. Pusta lista wymaganych checków
   przy rozbudowanym pipelinie to najczęstsza pojedyncza luka.
2. **Kto może ominąć?** Wyjątki od reguł plus dowód z historii: commity na
   chronionej gałęzi bez śladu PR.
3. **Czy dokumentacja obiecuje więcej, niż pipeline egzekwuje?** Wypisz każdą
   deklarację „wymagamy" i zaznacz, która ma odpowiednik w konfiguracji.
4. **Czy któryś wymagany check może nigdy nie wystartować?** Filtry na
   poziomie zdarzenia przy wymaganym checku blokują PR na zawsze.
5. **Czy gate'y są fail-closed?** Brak narzędzia, brak usługi, brak
   poświadczeń — blokuje z instrukcją, czy przechodzi na zielono? Szukaj
   wymuszania sukcesu i wyciszania kodów wyjścia w krokach bramkowych.
6. **Czy artefakt jest weryfikowany poza hostem budującym?** (§6)
7. **Wypisz ścieżkę „zielone CI, zepsuty produkt".** Zawsze jakaś istnieje;
   chodzi o to, by była znana i zapisana, a nie odkrywana po wydaniu.
8. **Ile trwa feedback do pierwszego czerwonego sygnału?**
9. **Czy przebieg odtwarza się lokalnie jedną komendą?** Jeśli nie, każda
   diagnoza wymaga cyklu push-czekaj.
10. **Czy zmiana samego pipeline'u przechodzi przez ten pipeline?**

## 11a. Profil local-first — jak czytać tę konwencję bez hosted CI

Powyższe zakłada serwer CI z regułą scalania. Część projektów świadomie
wybiera profil **local-first** (`D-007` w rejestrze decyzji projektu):
pipeline lustrzy się w hookach `pre-commit`/`pre-push` i w skrypcie
lokalnego przebiegu, a nie w usłudze. Ta konwencja obowiązuje ich tak samo —
zmienia się tylko nośnik bramki.

| Pojęcie z tej konwencji | Odpowiednik local-first |
|---|---|
| lista checków wymaganych przez regułę scalania | warstwy w `pre-push`, wypisane w jednym miejscu z nazwami |
| kto może ominąć (wyjątki) | zmienne `SKIP_*` — per warstwa, nigdy jedna globalna |
| filtr zdarzenia blokujący start checku | warunek wczesnego `exit 0` w hooku |
| job weryfikujący artefakt poza hostem budującym | osobny przebieg na czystym klonie/kontenerze |
| historia przebiegów | log lokalnego przebiegu odkładany do artefaktu audytu |

Procedura audytu z §11 stosuje się punkt po punkcie, z jedną poprawką
metodologiczną: **warunki wczesnego wyjścia wyciągaj z żywego pliku hooka**,
nie z jego lektury — lektura wykrywa to, czego się spodziewasz. Test ma
sprawdzać, że lista warunków `exit 0` wymienia każdą flagę, na którą reaguje
którakolwiek warstwa niżej.

Czego profil local-first świadomie nie ma i co należy zapisać w decyzji:
bramek na zmianach wprowadzanych przez boty, czystego środowiska przy każdym
przebiegu oraz checków wymuszanych po stronie serwera, których nie da się
pominąć lokalnie. Audyt, który zastosuje §11 do projektu local-first bez tej
poprawki, zaraportuje „pusta lista wymaganych checków, brak bramek" o repo,
które ma ich kilkanaście.

## 12. Sygnały maszynowe (tryb raportowy)

Tanie, deterministyczne checki do preflightu audytu:

1. Aktywna reguła ochrony gałęzi z **pustą** listą wymaganych checków.
2. Job opisany w dokumentacji jako wymagany, a oznaczony jako
   niepowodujący błędu.
3. Wymuszanie sukcesu w krokach bramkowych: dopisane „lub prawda", flagi
   zerujące kod wyjścia, wyłączone przerywanie skryptu.
4. Job bez limitu czasu; workflow bez anulowania nieaktualnych przebiegów.
5. Reguła wymagająca przeglądu właścicieli kodu przy **nieistniejącym** pliku
   właścicieli.
6. Commity na chronionej gałęzi bez numeru PR (próg: dowolny po dacie
   włączenia reguły).
7. Artefakt publikowany bez kroku smoke testu w tym samym przebiegu.
8. Wersja występująca w więcej niż jednym pliku bez kroku weryfikującego
   spójność.

## 13. Metryki, które warto liczyć

- odsetek PR-ów scalonych z czerwonym lub pominiętym wymaganym checkiem —
  cel zero, każde wystąpienie ma wyjaśnienie;
- czas do pierwszego czerwonego sygnału (nie: czas całego przebiegu);
- odsetek zmian kodu produkcyjnego z towarzyszącym testem — szczegóły
  w [`test-evidence.md`](test-evidence.md);
- odsetek przebiegów niestabilnych (ten sam commit, różny wynik) — powyżej
  kilku procent zespół przestaje ufać czerwonemu i pipeline traci funkcję.

Metryki wdrożeniowe (lead time, częstotliwość, MTTR, change failure rate)
opisuje [`progressive-delivery.md`](progressive-delivery.md).

Powiązane: [`ci-cd.md`](ci-cd.md), [`rules-as-gates.md`](rules-as-gates.md)
oraz [`test-evidence.md`](test-evidence.md) i
[`pull-request-review.md`](pull-request-review.md).
