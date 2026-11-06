# Konwencja: praca z produkcją

Stack-agnostic. Dla każdego projektu mającego produkcyjną bazę, serwer,
chmurę, DNS albo publiczne wydanie. Wyekstrahowana z projektu z produkcyjną
bazą, własnym DNS-em i publicznymi wydaniami.

## 1. PROD-DECLARE

Agent wykonuje akcję mutującą produkcję wyłącznie po **jednoznacznym poleceniu
właściciela w bieżącej rozmowie**. Zgoda na implementację, audyt lub deploy z
poprzedniej sesji nie jest zgodą na następną akcję produkcyjną.

Bezpośrednio przed zmianą agent pisze:

```text
🔴 PROD: <cel>, <system>, <dokładne działania>, <rollback>.
```

Read-only diagnostyka jest oznaczana `🟡 PROD (read-only):`. Produkcji nie
wolno przemycać jako pobocznego kroku innego zadania. Gdy zakres zmienił się
z read-only na mutujący, potrzebne jest nowe upoważnienie.

## 2. Wydanie i rollback

- Deploy wyłącznie z taga/release, który przeszedł CI; nie automatycznie po
  każdym merge do głównej gałęzi.
- Wdrażaj ten sam immutable artifact digest, który przeszedł CI i
  pre-production. Nie buduj ponownie na serwerze.
- Jeden główny branch + tagi. Osobny długowieczny branch produkcyjny zwykle
  tworzy drift i wymaga osobnej, zapisanej decyzji.
- Rollback jest częścią procedury przed deployem. Domyślnie: ponowny deploy
  poprzedniego, znanego dobrego taga; migracje destrukcyjne wymagają osobnego
  planu restore/forward-fix.
- Po deployu uruchom mały smoke test oraz zapisz dowód: tag/SHA, wynik i czas.
- Produkcyjny rollout ma etapy `preflight → najmniejszy blast radius → health
  gate → bake → fale → success/rollback`. Na pojedynczym VPS-ie baseline to
  kandydat na drugim porcie/kontenerze, smoke, przełączenie ingressu i szybki
  powrót do poprzedniego digestu. Pełny kontrakt i release evidence:
  [`progressive-delivery.md`](progressive-delivery.md).
- Brak telemetryki lub ruchu to `INCONCLUSIVE`, nie `PASS`. Automatyczna
  promocja wymaga automatycznego zatrzymania/rollbacku na wiarygodnym alarmie.
- Jeden serwis ma tylko jeden rollout/canary naraz. Emergency release może
  skrócić approval/bake, ale nie pomija identyfikacji artefaktu, krytycznego
  smoke, rollback target ani zapisu decyzji.

## 3. Server as code

- Kanoniczny stan maszyny żyje w playbooku/konfiguracji IaC. Ręczna zmiana na
  serwerze jest awaryjna i musi zostać natychmiast odtworzona w kodzie.
- Definicja maszyny jest oddzielona od deployu aplikacji.
- Przed zastosowaniem zmian infrastruktury użyj trybu plan/check/diff.
- DB i aplikacja nie wystawiają portów publicznie bez potrzeby; jeden jawny
  ingress. Limity zasobów i guardy mają komentarz `WHY` opisujący mechanizm,
  nie kronikę sesji.

## 3a. Byt adresuje się nazwą, którą sam deklaruje

Skrypt operacyjny odwołuje się do **usługi**, nie do nazwy, którą orkiestrator
akurat wygenerował. `docker exec platforma-v2-dp-api-1` jest poprawne dokładnie
do momentu, w którym ktoś podniesie drugi stos, zmieni nazwę projektu albo
compose przenumeruje repliki — a wtedy krok pada z „no such container", zwykle
w nocy i zwykle jako warunek wejścia wszystkiego, co po nim.

Poprawnie: `docker compose -f <plik> -p <projekt> ps -q <usługa>`, czyli pytanie
o **zadeklarowany** byt, z jawnym sprawdzeniem pustej odpowiedzi i komunikatem,
co podnieść. Ta sama reguła obejmuje adresy w konfiguracji: nazwa usługi
i port z pliku, nie z pamięci autora.

Testowalne: zmień nazwę projektu albo dołóż replikę i uruchom skrypt ponownie.
Odwołanie po usłudze przeżyje; odwołanie po wygenerowanej nazwie padnie — i to
jest cały sprawdzian.

## 4. Sekrety i dostęp

- Osobny użytkownik i klucz deployu per projekt; least privilege, bez
  współdzielonego prywatnego klucza administratora.
- `.env.example` jest śledzony i zawiera instrukcje generowania wartości;
  prawdziwe sekrety nie trafiają do repo, obrazu, logów ani rozmowy.
- Konfiguracja startuje fail-hard przy braku wymaganej zmiennej
  (`${VAR:?message}` lub odpowiednik).
- OIDC zastępuje długowieczne klucze, gdy dostawca je wspiera. Klucze bez OIDC
  są rotowane i mają ograniczenie źródła/komendy.

## 5. Baza danych

- Jedno narzędzie migracyjne i jeden ledger są źródłem prawdy. ORM auto-push
  jest dozwolony tylko dla wyrzucalnej lokalnej bazy.
- Zaaplikowanych migracji się nie edytuje. Zmiana = nowa migracja.
- Migracja produkcyjna ma timeouty blokad/statement, plan na duże indeksy,
  ścieżkę resumable i strategię expand→migrate→contract dla zmian niszczących.
- Test wdrożenia obejmuje współistnienie starej i nowej wersji, upgrade oraz
  rollback/forward-fix. Tymczasowa kompatybilność jest obowiązkowa dla
  rolling/progressive rollout i ma osobne zadanie usunięcia po pełnej promocji.
- Backup bez sprawdzonego restore nie jest backupem. Runbook podaje kolejność,
  wymagania i spodziewane failure modes każdego kroku.

## 6. Release a ekspozycja funkcji

- Dla ryzykownej lub niekompletnej funkcji oddziel deployment od release przez
  feature flag. Flaga ma właściciela, bezpieczny default, telemetrykę, kill
  switch, plan kohort/procentów i termin usunięcia.
- Testuj oba stany do chwili usunięcia flagi. Flaga nie zastępuje autoryzacji
  ani kompatybilnej migracji danych.
- Zmiana flagi/konfiguracji jest audytowalnym deploymentem z review i
  rollbackiem, nie niewidzialnym kliknięciem w panelu.

## 7. SLO i error budget

Publiczna usługa ma co najmniej jeden user-facing SLI/SLO albo zapisane `N/A`
z uzasadnieniem i planem telemetryki. Po wyczerpaniu error budget zwykłe
feature releases i zmiany danych są wstrzymane; dozwolone pozostają poprawki
incydentów krytycznych, security fix i prace przywracające niezawodność. Politykę oraz pięć metryk
DORA opisuje [`progressive-delivery.md`](progressive-delivery.md).

## 8. Launch

- Launch definiuje **zamknięta lista warunków krytycznych + feature freeze + data**. Nowe
  znaleziska (także z audytu) domyślnie idą do backlogu post-launch; do listy
  launchowej wchodzą wyłącznie jawną decyzją właściciela — inaczej lista
  rośnie w nieskończoność i launch nie następuje.
- Go/no-go jest osobną, zapisaną decyzją: data, stan warunków krytycznych, znane
  zaakceptowane ryzyka.
- Bezpośrednio po launchu: okno obserwacji z progami/health signals według
  [`progressive-delivery.md`](progressive-delivery.md) i wpis release evidence.

## 8a. Drill odtworzenia, który potrafi powiedzieć PORAŻKA

Kopia zapasowa jest kopią dopiero wtedy, gdy odtworzenie zostało **odczytane
z powrotem** i **odrzuciło podrobiony manifest**. Drill, który przechodzi
wyłącznie szczęśliwą ścieżką, dowodzi, że skrypt umie wypisać OK — nie że umie
wypisać FAIL.

Reprodukcja: stara wersja drilla meldowała powodzenie **na pustej bazie**,
porównując zero z zerem. Naprawa ma trzy części i każda jest osobną asercją:

1. **Odmowa na pustym źródle.** Liczba wierszy większa od zera **przed** kopią,
   a przy artefaktach binarnych osobno liczba bajtów — inaczej połowa kopii
   jedzie niesprawdzona.
2. **Podrobione manifesty z oczekiwanym kodem 1.** Każde fałszerstwo na kopii,
   nie na oryginale, i z asercją, że fałszerstwo **w ogóle coś zmieniło** —
   podmiana, która nic nie zmieniła, daje sprawdzian spełniony na pusto.
3. **Asercja, że drill się wykonał.** Licznik wykonanych sprawdzeń porównany
   z liczbą oczekiwaną; zero znaczy „pominięte", nie „przeszły".

Do tego dwie rzeczy wyuczone na własnych błędach: porównuj liczby **per tabela**,
bo suma ukrywa błędy kompensujące (utrata wszystkich propozycji plus tyle samo
nowych wierszy kontrolnych daje sumę zgodną); oraz zasiewaj przez **produkcyjne
repozytoria**, nie ręcznymi wstawkami, żeby drill nie odjechał od schematu,
którego ma bronić.

Ten sam kształt ma bramka odwracalności migracji: **musi startować na pustej
bazie** i wchodzić po historii rewizja po rewizji, bo `w górę → w dół do zera →
w górę` nie widzi zepsutego zejścia w rewizji dodającej tylko kolumny.

## Egzekwowanie: rozstrzyga czytanie

**Tej reguły nie egzekwuje żaden skrypt.** Rytuał PROD-DECLARE wymaga jednoznacznego polecenia właściciela w bieżącej rozmowie przed każdą akcją mutującą. Tego nie zastąpi żaden skrypt: bramka mogłaby najwyżej sprawdzić, czy komunikat został wypisany, a nie czy padła zgoda. Go/no-go, plan restore i decyzja o feature freeze przed launchem są w tej samej klasie.

W rejestrze reguł (`templates/rejestr-regul.sh`)
ta konwencja stoi w koszyku `czytanie` i pokazuje się w raporcie audytu jako
CZYTANA — czyli reguła, która stoi na czyimś słowie, a nie na kodzie wyjścia.
Zapisane jest to jawnie, bo reguła wyglądająca na egzekwowaną, a nieegzekwowana,
jest dokładnie tą miękkością, o którą chodzi: brzmi tak samo stanowczo jak
`code-structure.md`, a nikt jej nie sprawdza.

Zmiana tego stanu wymaga napisania bramki i przeniesienia wiersza do koszyka
`bramka` w tym samym commicie. Dopóki tego nie ma, „MUSI" w tym pliku znaczy
„MUSI, a sprawdzi to człowiek".
