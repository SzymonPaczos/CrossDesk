# Konwencja: gotowość PR i odpowiedź na review

Stack-agnostic. Wyekstrahowana z rundy review vocalinux 2026-08-17: siedem PR-ów
jednego autora, pięć odbitych. W żadnym z pięciu maintainer nie zakwestionował
pomysłu — wszystkie blokady dotyczyły **dowodu**, nie rozwiązania.

## Problem

PR jest oceniany jako twierdzenie plus dowód. Autor optymalizuje twierdzenie
(kod), reviewer weryfikuje dowód (testy, CI, zgodność opisu z kodem). Rundy
review przepalają się na dowodzie.

Trzy przyczyny źródłowe, każda potwierdzona w źródłowym incydencie:

- testy pisane pod diff, nie pod bug — osobna konwencja:
  [`test-evidence.md`](test-evidence.md);
- lokalne „zielono" nieodzwierciedlające CI;
- analiza funkcji w izolacji od jej wywołującego.

## Preflight — przed otwarciem i ponownie przed prośbą o re-review

1. **Rebase na aktualną gałąź bazową.** Reviewer czytający kod, który merge już
   zmienił, zgłosi zarzuty nieaktualne w chwili pisania; runda przepada. Dotyczy
   każdej otwartej gałęzi, nie tylko tej właśnie zmienianej.
2. **Uruchom checki tak, jak robi to CI — z flagami z pliku workflow.** Czytaj
   workflow, nie zgaduj. Czerwony linter często **skipuje** job testowy, więc PR
   dociera wyglądając na nieprzetestowany; reviewerzy rutynowo pomijają PR-y z
   czerwonym pipeline'em bez czytania kodu.
3. **Zweryfikuj negatywnie każdy nowy test** — [`test-evidence.md`](test-evidence.md).
4. **Porównaj listę błędów całej suite z gałęzią bazową**; zbiór nowych nazw
   musi być pusty.

## Opis PR jest częścią diffa

Każde twierdzenie o zachowaniu ma mieć pokrycie w teście w tym samym PR.
Twierdzenia bez pokrycia usuń — łapane są przede wszystkim te: „stare configi
zachowują się bez zmian", „to no-op dla X", „brak zmian widocznych dla
użytkownika".

Sprawdzaj takie zdania po stronie **wywołującego**, nie samej funkcji. Większość
fałszywych twierdzeń bierze się z czytania funkcji w izolacji, podczas gdy
wywołujący zdążył już scalić domyślne wartości, znormalizować wejście albo
skrócić ścieżkę. Prześledź jedno realne wywołanie end-to-end, zanim napiszesz
zdanie.

**Reprodukcja:** funkcja ma fallback „gdy klucza brak, użyj generycznego". Autor
opisuje to jako zachowanie wsteczne. W rzeczywistości wołający scala słownik
domyślnych wartości, w którym ten klucz **już jest**, więc fallback nie odpala
nigdy, a stare pliki startują na wartości domyślnej.

## Naprawa musi leżeć na ścieżce, która się wykonuje

Zanim wstawisz obsługę błędu w `except`, sprawdź **kontrakt wywoływanej
funkcji**: rzuca wyjątek czy zwraca sentinel (`False`, `None`, kod błędu)? Jeśli
łapie wewnętrznie i zwraca wartość, twój handler jest martwym kodem, a issue
zostaje otwarte mimo zmergowanego PR. Gdy możliwe są oba warianty — obsłuż oba.

Nigdy nie opieraj poprawności swojego PR na innym, **nieprzemergowanym** PR.
Zakładaj, że Twój wejdzie pierwszy.

Dla stanu, który może rozjechać się ze źródłem prawdy — UI pokazujące coś, czego
config nigdy nie przyjął — dodaj **backstop** porównujący oba na naturalnej
granicy (zamknięcie modala, zamknięcie okna), zamiast wyliczać wszystkie ścieżki
błędu. Łapie przypadki, których nie przewidziałeś.

Zamknięcie issue potwierdzaj, przechodząc kroki reprodukcji zgłaszającego, a nie
sprawdzając, że nowy kod się wykonuje.

## Odpowiedź na review

- `CHANGES_REQUESTED` to prośba o dowód, nie odrzucenie. Zwykle reviewer już
  zaakceptował podejście — zanim zaczniesz przerabiać projekt rozwiązania,
  przeczytaj, czy blokada nie dotyczy wyłącznie testów i CI.
- Odnieś się do **każdego** punktu, również oznaczonego jako nieblokujący.
  Napisz wprost, który odkładasz i dlaczego.
- Gdy zarzut zdezaktualizował się (baza się przesunęła, inny PR wszedł), napisz
  to wprost ze wskazaniem commita — i mimo to dołóż część defensywną, jeśli
  kosztuje niewiele.
- Gdy reviewer oferuje, że zrobi follow-up później: zrób go teraz, jeśli bez
  niego PR wprowadza znaną regresję, i **napisz w odpowiedzi**, że wziąłeś to
  na siebie — żeby mógł poprosić o wydzielenie.
- Nie edytuj pierwszego posta w odpowiedzi na review, jeśli właściciel tego nie
  polecił; dopisz komentarz. Historia zarzutu ma zostać czytelna.

## Higiena wielu równoległych PR-ów

- Gałęzie dotykające tego samego pliku wprowadzaj **pojedynczo**, rebase'ując
  resztę po każdym mergu.
- Nigdy nie commituj przez `git add -A`. Stage'uj jawne ścieżki: repozytoria
  gromadzą nietrackowane pliki robocze, logi sesji i lokalne notatki, które
  zbiorczy add wciąga do commita.

Powiązane: [`test-evidence.md`](test-evidence.md),
[`issue-reporting.md`](issue-reporting.md),
[`change-provenance.md`](change-provenance.md).
