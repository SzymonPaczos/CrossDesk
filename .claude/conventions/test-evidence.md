# Konwencja: dowód z testu

Zakres: testy zmian zachowania, regresji i samych bramek. Test potwierdza
opisany efekt na właściwym kodzie; raport nie przypisuje mu szerszego dowodu.

## Weryfikacja negatywna

Nowy test regresji towarzyszący naprawie wykazuje obie strony:

- bez naprawy odtwarza wskazany błąd i zawodzi na właściwej asercji;
- z naprawą ten sam przypadek przechodzi.

Autor dobiera sposób odtworzenia błędu: poprzednią wersję, skuteczną mutację
lub kontrolowane wejście. Dotyczy to również zmian metadanych, uprawnień
i konfiguracji. Awaria budowania, importu lub środowiska nie zastępuje
porażki badanego zachowania. Jeśli oba przebiegi przechodzą, dowód pozostaje
niepotwierdzony; trzeba ustalić przyczynę przed uznaniem naprawy za sprawdzoną.

Przebiegi dotyczą tego samego przypadku i różnią się badaną przyczyną.
Kod oraz artefakty pośrednie odpowiadają każdej stronie próby. Sposób
zapewnienia świeżości zależy od runnera; nie ma obowiązku kasowania każdego
cache przy każdej próbie. Sama liczba testów, które zawiodły po mutacji,
nie rozstrzyga, czy mutacja trafiła w przyczynę.

Zapis wyników: [`negative-verification.md`](negative-verification.md).
Weryfikacja bramki używa znanego poprawnego i błędnego materiału według
[`rules-as-gates.md`](rules-as-gates.md).

## Granica dowodu

- Test odtwarza warunki i kolejność prowadzące do objawu. Asercja dotyczy
  obserwowalnego efektu, nie wyłącznie kształtu wywołania.
- Mock nie zastępuje naprawianego zachowania. Dla configu, plików
  i serializacji sprawdzian używa rzeczywistego formatu i odczytu.
- Twierdzenie o zapisie wymaga odczytania wyniku pisarza. Ręcznie zbudowana
  fikstura może potwierdzać czytelnika, lecz nie dowodzi działania pisarza.
- Twierdzenie o renderowaniu dotyczy wyrenderowanego komponentu; parsowanie
  wejścia tego nie zastępuje. Asercja wskazuje konkretny byt, jeśli ekran
  zawiera powtarzalne wartości.
- Sonda obserwuje instancję lub klasę używaną przez kod pod testem i ma
  kontrolę, że rzeczywiście zarejestrowała badane zdarzenia.
- Test granicy wydajności odzwierciedla wymaganie: dla skalowania porównuje
  rozmiary wejścia, a dla jawnego limitu sprawdza ten limit.

## Wiarygodność przebiegu testów

Przykłady diagnostyczne — objaw wskazuje hipotezę do sprawdzenia:

| Objaw | Co sprawdzić |
|---|---|
| Test przechodzi po obu stronach mutacji | Czy import trafia w zmienione źródło i czy build/bytecode odpowiada próbie; zob. `rules-as-gates.md` punkt 20. |
| Mock zwraca stałą mimo zmiany resolvera | Czy test wykonuje naprawianą funkcję, czy zastąpił ją mockiem. |
| Drugi uchwyt powstaje dopiero po zapisie | Czy odtworzono nieświeży stan istniejący przed zmianą. |
| `assert_called_with` przechodzi mimo nieskutecznej flagi | Czy asercja sprawdza efekt flagi. |
| Parser propsów przechodzi, a widok pozostaje pusty | Czy próba renderuje właściwy komponent. |
| Test ręcznie buduje poprawny rekord | Czy testowano wynik rzeczywistego pisarza. |
| Oczekiwany tekst jest w sąsiedniej komórce | Czy asercja wskazuje badany wiersz i pole. |
| Licznik SQL zawsze wynosi zero | Czy sonda obserwuje używany silnik i wykrywa kontrolne zapytanie. |
| Test deklaruje stałą liczbę zapytań | Czy porównano różne rozmiary danych. |
| Wartość oczekiwana jest liczona kodem pod testem | Czy druga strona porównania jest wyprowadzona ręcznie (literał, fixture); obie strony z jednego źródła są równe niezależnie od błędu. |
| Test pada tylko przy świadomej zmianie stałej lub brzmienia | Czy istnieje mutacja logiki, którą test wykryje; test czuły wyłącznie na decyzje sprawdza kształt, nie zachowanie. |

Przebieg używa właściwego źródła, konfiguracji i środowiska. Każdy test
odtwarza własne warunki wejściowe oraz zwalnia zmieniony stan, również
po błędzie. Test nie może znikać wskutek działania sąsiedniego przypadku.

Zakres weryfikacji wynika ze zmiany, ryzyka i wymaganych komend projektu.
Pełny zestaw jest potrzebny, gdy wymaga go CI lub pozostaje ryzyko interakcji
między testami. Nie narzuca się jednego procesu runnerom działającym inaczej.
Kolejne przebiegi służą nowej zmianie, wykrytej awarii lub nierozstrzygniętemu
ryzyku, zamiast powtarzać już uzyskany dowód.

Przy błędach istniejących na bazie porównuje się przypadki i przyczyny
porażek. Ta sama nazwa `FAILED` może kryć nową regresję. Raport podaje zakres,
liczbę wykonanych i pominiętych przypadków oraz niezweryfikowane zachowania.
`skipped`, pusty zbiór i awaria narzędzia nie są zaliczeniem testu.

## Kontrakt dublera i prawdziwego dostawcy

Dowód oparty na dublerze wymaga zgodności istotnego zachowania z produkcją.
Te same scenariusze kontraktowe sprawdzają dublera i adapter produkcyjny;
transport może być podmieniony, badana logika adaptera pozostaje rzeczywista.
Organizacja suity należy do autora.

Dubler uwzględnia istotne odpowiedzi i błędy dostawcy, bez wymyślania
deduplikacji, rozliczania lub walidacji nieobecnych w produkcji. Rozjazd
dublera z tym kontraktem powoduje porażkę kontroli. Twierdzenie o zapisie,
który schemat bazy może odrzucić, ma test przez prawdziwy silnik.

## Kontrole pomocnicze

Czytnik używany przez test ma potwierdzony zakres; jego pusty wynik nie
potwierdza kompletności porównania. Sprawdzian odrzuca znany błędny materiał
i akceptuje poprawny. Dla wersji schematu projekt określa obsługiwany zakres:
test odróżnia nieobsługiwaną wersję od starszej, którą system nadal wspiera.

Przy izolowaniu importów Pythona stan obejmuje zarówno `sys.modules`, jak
i atrybut modułu na pakiecie rodzicu. Zmiany globalnego stanu podczas
kolekcji testów mogą naruszyć tę izolację; należą do zakresu testu lub fixture.

Powiązane: [`pull-request-review.md`](pull-request-review.md),
[`issue-reporting.md`](issue-reporting.md).

Egzekwuje: review dowodu; `templates/test-evidence.sh` wykrywa tylko opisane w nim sygnały statyczne.
