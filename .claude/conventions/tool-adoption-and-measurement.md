# Konwencja: adopcja narzędzi i optymalizacja po pomiarze

Stack-agnostic. Zakres: **kiedy wolno wziąć nowe narzędzie do produkcji, jak z
niego wyjść, i jak udowodnić, że zmiana coś przyspieszyła.** Plus podział
kontroli na etapy według budżetu czasu.

Rozdział ról:

- [`rules-as-gates.md`](rules-as-gates.md) — awans reguły na gate.
- [`ci-cd.md`](ci-cd.md) — lockfile, pinowanie, supply chain.
- [`ci-pipeline-architecture.md`](ci-pipeline-architecture.md) — topologia bramek.

Konkretne narzędzia i wersje żyją w `references/` z datą ważności, nie tutaj.
Ta konwencja opisuje **procedurę**, która ma przeżyć rotację narzędzi.

## 1. Jedna wersja toolchainu na repozytorium, deklaratywnie

Wersje języka, kompilatora i narzędzi są **zapisane w repozytorium** w formacie
czytanym automatycznie przez środowisko dewelopera i przez CI. Nie w README,
nie w głowie, nie w obrazie dockerowym jako jedyne miejsce.

Konsekwencje, których brak boli najczęściej:

- „u mnie działa" przestaje być hipotezą wymagającą śledztwa;
- podbicie wersji jest zmianą w PR, z przeglądem i możliwością cofnięcia;
- nowa osoba odtwarza środowisko jedną komendą, nie akapitem instrukcji.

## 2. Lockfile jest kontraktem reprodukowalności

Lockfile aplikacji jest commitowany i **nie jest edytowany ręcznie**. CI
instaluje w trybie, który **zawodzi**, gdy lockfile nie zgadza się z
manifestem, zamiast go po cichu zaktualizować. To rozróżnienie jest całą
wartością lockfile'a: bez trybu blokującego w CI masz plik, który dokumentuje
przeszłość, a nie kontrakt na przyszłość.

Szczegóły instalacji i łańcucha dostaw: [`ci-cd.md`](ci-cd.md) §3.

## 3. Formatter i linter to dwa różne narzędzia

Formatter rozstrzyga spory o styl bez dyskusji i jest deterministyczny.
Linter szuka błędów i wzorców. Mieszanie ról kończy się konfiguracją, w której
dwa narzędzia walczą o ten sam plik.

Reguły:

- w CI **oba** działają w trybie sprawdzającym, nie naprawiającym;
- konfiguracja jest w repozytorium, nie w ustawieniach edytora;
- **jedno narzędzie na rolę** — patrz §6.

Typy statyczne są trzecią, osobną warstwą obronną, nie ozdobą. Sprawdzanie
typów należy do bramki, nie do dobrej woli autora.

## 4. Statusy narzędzi i co z nich wynika

| Status | Kryterium | Co wolno |
|---|---|---|
| production default | producent ogłosił stabilność, jest ścieżka wsparcia | bramka blokująca w CI |
| dobra alternatywa | stabilne, ale wybrane inne jako domyślne | wolno, gdy zespół świadomie wybierze |
| emerging / experimental | producent oznacza alpha, beta, `0.0.x` lub „bez stabilnego API" | wyłącznie w trybie cienia (§5), nigdy jako bramka |
| legacy / avoid | wypierane, w trybie utrzymaniowym albo z lepszą ścieżką | dopuszczalne z zapisanym planem migracji |

**Etykietę bierze się od producenta, nie z entuzjazmu zespołu.** Jeśli
dokumentacja mówi „beta", to jest beta, niezależnie od tego, jak dobrze działa
na naszym repozytorium.

Cztery sygnały ryzyka, które trzeba czytać osobno od numeru wersji:

1. **Polityka patchowania.** Narzędzie łatające wyłącznie najnowszy minor,
   albo dopuszczające zmiany łamiące w patchu, nie nadaje się na bramkę.
2. **Sprzężone wersjonowanie.** Gdy narzędzie deklaruje zgodność z konkretną
   wersją innego (np. linter z kompilatorem), planuj ich aktualizacje razem —
   to jednocześnie sygnał jakości i ograniczenie swobody.
3. **Utrzymanie pasywne / „feature complete".** Dopuszczalne, ale z planem
   migracji; brak nowych funkcji oznacza, że wasz przypadek brzegowy nigdy nie
   zostanie obsłużony.
4. **Brak publicznego API.** Narzędzie bez stabilnego API nie może być bazą dla
   waszych wtyczek ani skryptów.

## 5. Tryb cienia i warunki awansu

Narzędzie ze statusu *emerging* uruchamia się **równolegle** do obecnego, w
zadaniu nieblokującym, a wyniki porównuje się automatycznie.

Awans do domyślnego wymaga **trzech** warunków naraz:

1. producent ogłosił stabilność;
2. co najmniej dwa tygodnie pracy w trybie cienia bez rozbieżności, których nie
   umiecie wyjaśnić;
3. **istnieje udokumentowana ścieżka powrotu** — konfiguracja poprzedniego
   narzędzia zostaje w repozytorium do czasu, aż nowe przetrwa jeden pełny
   cykl wydawniczy.

Warunek trzeci jest najczęściej pomijany i najdroższy w skutkach: migracja bez
ścieżki wyjścia zamienia awarię narzędzia w awarię dostawy.

## 6. Sprawdź nakładanie ról, zanim dodasz narzędzie

Zanim wejdzie kolejna zależność, odpowiedz: **jaką rolę przejmuje i co ją
oddaje?** Środowiska „wszystko w jednym" (runtime plus menedżer pakietów plus
test runner plus formatter) i osobne wyspecjalizowane narzędzia to dwie
strategie; mieszanie ich daje trzy konfiguracje robiące to samo, z których
każda jest źródłem prawdy w innym miejscu.

Praktyczny test: czy po dodaniu narzędzia któreś z obecnych można **usunąć**?
Jeśli nie, prawdopodobnie właśnie zwiększyłeś powierzchnię utrzymania bez
zysku.

## 7. Optymalizuj po pomiarze, nie po intuicji

Trzy kroki, w tej kolejności, zawsze:

1. **Baseline** — pomiar z powtórzeniami, zapisany do pliku w repozytorium
   albo w artefakcie przebiegu. Pojedynczy przebieg nie jest pomiarem.
2. **Profil** — wskaż punkt gorący, zamiast zgadywać. Profil próbkujący mówi,
   gdzie program spędza czas; nie mówi, dlaczego.
3. **Weryfikacja A/B** — porównanie przed i po, z miarą rozrzutu, nie z jedną
   liczbą.

Cztery zasady metodyczne, których złamanie unieważnia wynik:

- **Nie mierz wydajności w buildzie z sanitizerami ani pod narzędziem
  śledzącym pamięć.** Narzucają wielokrotne spowolnienie i zmieniają
  charakterystykę czasową; służą do poprawności, nie do pomiaru.
- **Nie wnioskuj o regresji z jednego przebiegu.** Profilery próbkujące i
  współdzielone runnery mają rozrzut większy niż typowa różnica, której szukasz.
- **Zmieniaj jedną rzecz naraz**, inaczej nie wiesz, co zadziałało.
- **Zapisz warunki pomiaru** — maszyna, obciążenie, wersje. Wynik bez warunków
  jest anegdotą.

Wynik optymalizacji trafia do opisu PR jako liczba z rozrzutem, nie jako
przymiotnik.

## 8. Etapy i budżety czasu

Każda kontrola ma swoje miejsce w cyklu, wyznaczone przez czas trwania i
determinizm. Zła kolokacja jest częstszym problemem niż brak kontroli.

| Etap | Budżet | Co tam należy |
|---|---|---|
| edytor / zapis pliku | milisekundy | formatter, szybki lint, serwer języka |
| pre-commit | sekundy | formatter i lint **na plikach w indeksie**, detekcja sekretów, lint komunikatu commita |
| pre-push | do minuty | szybkie testy zakresu zmian, sprawdzenie typów |
| pull request | minuty | pełny lint, testy, build artefaktu, skanery, bramki kontraktu |
| merge do głównej | minuty | publikacja artefaktu, SBOM, podpis, provenance |
| nocne / cron | godziny | fuzzing, testy przeglądarkowe, głęboka analiza, benchmarki regresyjne |
| wydanie | — | changelog, tag, wersjonowanie |

Dwie reguły, które to spinają:

- **Hooki muszą być szybkie i deterministyczne.** Hook, który trwa minutę,
  zostanie obejty flagą pomijającą, a wtedy nie chroni niczego. Ciężkie
  kontrole należą do CI.
- **Hook nie jest bramką bezpieczeństwa.** Da się go ominąć i nie działa na
  zmianach botów. Bramką jest CI — patrz [`ci-cd.md`](ci-cd.md) §1.

## 8a. Liczba w dokumencie jest cytatem, nie zapisem z pamięci

Sześć wielkości miało w jednym dokumencie po kilka różnych wartości naraz:
zebrane testy 397 obok 393 i 399, przeanalizowane pliki 60 obok 58, rewizje
migracji 6 obok 5, tabele 20 obok 19 i 14. Żadna nie była napisana niedbale —
każda była poprawna w dniu, w którym ktoś ją wpisał.

**Liczby, której nikt nie umie odtworzyć, nie da się nazwać błędną w konkretnej
chwili — jest po prostu stara i nie widać po niej, jak bardzo.**

Mechanizm ma cztery warstwy i wszystkie są potrzebne:

1. **Jeden skrypt** produkuje wszystkie liczby, które dokumenty wolno cytować.
2. **Jeden śledzony artefakt** (`docs/ostatni-przebieg.txt`) je niesie, razem
   z hashem commita, znacznikiem czasu i wersjami narzędzi.
3. **Dokument cytuje** ten artefakt w oznaczonym bloku, wstawianym skryptem.
   Blok kopiowany ręcznie jest kopią, a kopia dryfuje.
4. **Bramka porównuje** cytat ze świeżym pomiarem.

Trzy szczegóły, bez których warstwa nie działa:

- **Pomiar, którego nie dało się wziąć, jest porażką, nie zerem.** Artefakt
  z dziurą jest dokładnie tym plikiem, który zaprasza, żeby dziurę wypełnić
  z pamięci.
- **Proweniencja jest wyłączona z porównania.** Hash commita i znacznik czasu
  zmieniają się w każdym przebiegu z założenia; porównywanie ich przewracałoby
  bramkę z jedynego powodu, który nic nie mówi o kodzie.
- **Licznik mierzący własny artefakt jest wyłączony z porównania.** Liczba
  wierszy rejestru weryfikacji negatywnej rośnie za każdym zapisem czerwieni,
  więc porównywanie jej przewracałoby przebieg **za sam akt użycia rejestru**
  ([`rules-as-gates.md`](rules-as-gates.md) §21).

Bramka jest celowo wąska: **nie zakazuje cyfr w prozie**, zakazuje cyfry, która
udaje pomiar rzeczy mierzonej przez skrypt.

Czym to sprawdzić: [`templates/document-numbers.sh`](../templates/document-numbers.sh).

## 9. Sygnały maszynowe (tryb raportowy)

1. Wersja narzędzia zadeklarowana w więcej niż jednym miejscu, bez kroku
   weryfikującego spójność.
2. Instalacja zależności w CI bez trybu zawodzącego przy niezgodnym lockfile.
3. Dwa narzędzia pełniące tę samą rolę w konfiguracji repozytorium.
4. Narzędzie oznaczone przez producenta jako alpha/beta/`0.0.x` użyte jako
   bramka blokująca.
5. Hook przekraczający ustalony budżet czasu.
6. Twierdzenie o wydajności w opisie PR bez liczby i rozrzutu.
7. Zależność w statusie *legacy* bez zapisanego planu migracji.

## 10. Zapis decyzji

Każdy wybór narzędzia o statusie innym niż *production default* trafia do
rejestru decyzji projektu z: rolą, statusem od producenta, powodem wyboru,
ścieżką wyjścia i datą przeglądu. Bez daty przeglądu „tymczasowo bierzemy
betę" jest permanentne.

Powiązane: [`rules-as-gates.md`](rules-as-gates.md), [`ci-cd.md`](ci-cd.md),
[`dependency-currency.md`](dependency-currency.md),
[`change-provenance.md`](change-provenance.md).
