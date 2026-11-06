# Konwencja: bramki jakości, odstępstwa i definicja ukończenia

Zakres: wybór bramek projektu, ich tryb oraz odbiór zmiany.
Wiarygodność dowodu określa [`test-evidence.md`](test-evidence.md), a kontrakt
bramki [`rules-as-gates.md`](rules-as-gates.md). Wymaganie obowiązuje
w podanym zakresie; „zwykle” oznacza zalecenie, „może” dopuszcza wybór.

## Strategia testów

- Zmiana zachowania ma test adekwatny do ryzyka; naprawa błędu krytycznego
  zawiera test regresji. Wybór warstwy i narzędzia należy do autora.
- Reguły domenowe, autoryzacja, transakcje, idempotencja, migracje i kontrakty
  mają testy automatyczne.
- Testy jednostkowe są izolowane od kolejności, czasu rzeczywistego,
  zewnętrznej sieci i współdzielonego stanu. Zależności integracyjne i E2E
  są jawne.
- Test zwykle sprawdza zachowanie publiczne. Snapshot lub procent coverage
  nie jest samodzielnym dowodem poprawności złożonej logiki.

Przy ustalonym zachowaniu i naprawie błędu preferuj małe cykle:
test wykazuje konkretny brak → minimalna implementacja → uproszczenie kodu
i testu przy zachowaniu kontroli. Błąd infrastruktury lub importu nie jest
dowodem odtworzenia defektu. Zielona suita nie dowodzi, że zastosowano TDD;
do takiego twierdzenia potrzebny jest zapis rzeczywistego wyniku przed
zmianą i po niej, bez dodatkowego obowiązkowego dokumentu.

Nieznane API, eksperyment i projekt wizualny mogą najpierw wymagać krótkiego
prototypu z pytaniem i limitem. Po ustaleniu kontraktu dodaj zabezpieczenia
adekwatne do ryzyka przed odbiorem. Integracja, testy kontraktów i generowanie
przypadków uzupełniają testy jednostkowe; wybrane mutacje krytycznej logiki
mogą sprawdzić, czy test wykrywa błąd. Nie narzucaj proporcji testów ani
pełnego kodu testów w planie. Obowiązkowe zakresy automatyzacji powyżej
pozostają wymagane.

## Macierz bramek

Stosuj wiersze dotyczące technologii i zakresu zmiany. Konwencja nie wymaga
dodawania nieużywanego stosu tylko po to, żeby uruchomić jego bramkę.

| Bramka | Tryb |
|---|---|
| formatowanie, lint, typecheck | blokujący |
| testy jednostkowe | blokujący |
| testy integracyjne zmienianego obszaru | blokujący |
| testy i diff kontraktów | blokujący |
| kierunek importów, deep importy, cykle | blokujący |
| secret scanning | blokujący |
| krytyczne/wysokie SAST i SCA | blokujący według polityki ryzyka |
| wyciek server-only do bundle’a | blokujący |
| E2E krytycznych podróży | blokujący przed release; tryb na PR ustala projekt |
| liczba linii, propsów, flag, złożoność | raportowy |
| dyrektywa client w korzeniu | raportowy |
| spadek coverage | raportowy lub blokujący dla ustalonego obszaru krytycznego |

## Jakość bramki i wyjątki

Bramka jest deterministyczna i uruchamialna lokalnie lub w kontenerze.
Komunikat pozwala rozpoznać naruszenie i sposób jego sprawdzenia.
Nowa reguła dla legacy może działać raportowo do ustalonej daty migracji.
Ocena wymagająca osądu pozostaje w review; metryka pomocnicza nie staje się
automatycznie blokadą.

Globalnego progu nie obniża się dla pojedynczego PR. Wyjątek jest lokalny,
ma właściciela i termin według [`architecture-principles.md`](architecture-principles.md).
CI odrzuca wyjątki po terminie. Wyjątek dłuższy niż kwartał zwykle wymaga
decyzji architektonicznej albo usunięcia.

## Definition of Done dla funkcjonalności

Zmiana spełnia zaakceptowane kryteria odbioru i wymagane bramki projektu.
Przy zadaniu wieloetapowym rozlicza wszystkie etapy z przyjętego planu
(`backlog-contract.md` §6a). Zielone testy X2 nie potwierdzają wykonania X3
ani X4; ukończenie rodzica wymaga dowodów dla całego uzgodnionego zakresu.
W swoim zakresie zachowuje granice warstw, walidację wejść i uprawnienia;
obejmuje testy sukcesu, błędu oraz krytycznego ryzyka.
UI obsługuje loading/error/empty, a I/O właściwe timeouty,
retry/idempotencję. Potrzebne sygnały diagnostyczne i wyjątki są jawne.

Raport rozlicza punkty weryfikacji z zadania lub planu: wynik, brak
wykonania z powodem albo uzgodnioną zmianę zakresu. Niewykonana wymagana
kontrola pozostaje otwarta; nie jest dowodem ukończenia. Brakująca kontrola
nie wymaga ponawiania uzyskanych zgód ani wstrzymania niezależnej pracy.

Powiązane: [`ci-pipeline-architecture.md`](ci-pipeline-architecture.md).

Egzekwuje: bramki projektu dla przyjętej macierzy i review pozostałych kryteriów odbioru.
