# Konwencja: styl instrukcji dla agentów

Dotyczy instrukcji projektu, konwencji, skilli, ról i plików stanu.
Cel: agent zna oczekiwany wynik i granice pracy, a sposób wykonania dobiera
do zadania i dostępnych narzędzi.

## Reguły

1. Instrukcja określa rezultat, ograniczenie lub kryterium odbioru.
   Procedurę narzuca tylko wtedy, gdy jej kolejność lub narzędzie stanowi
   wymaganie projektu; wyjaśnia wtedy powód.
2. Stały kontekst zawiera decyzje projektu, komendy i informacje potrzebne
   do pracy, których nie dostarcza samo zadanie. Ogólne rady o programowaniu
   i powtórzenia innych instrukcji można usunąć.
3. Szczegóły CI, publikacji, audytu i konkretnego runtime'u mają wskazany
   zakres zastosowania. Dostępność pliku nie oznacza obowiązku czytania go
   w każdej sesji.
4. Wymóg, zalecenie i opcja są rozróżnione słowami „wymaga”, „zwykle”
   i „może” lub równie jednoznacznym zdaniem. Opis incydentu nie ustanawia
   dodatkowej reguły.
5. Proza jest zwięzła i opisuje czynności lub fakty. Podział zdań,
   pogrubienia i zapis sekwencji służą czytelności; nie mają sztywnych limitów.
   Hasło lub nacisk typograficzny nie zastępuje wyjaśnienia wymagania.
6. Uzasadnienie zostaje przy regule, gdy pomaga ją zastosować. Dłuższa
   historia należy do decyzji lub materiału czytanego przy danym problemie.
   Nieoczywiste kryterium może mieć krótki przykład „objaw — co sprawdzić”.
7. Wpis stanu podaje wynik, dowód i otwartą blokadę, jeśli istnieje.
   Długość wynika z informacji potrzebnej do wznowienia pracy, nie z limitu
   jednej linii. Zachowuje format maszynowy wymagany przez projekt.
   Tekst stanu wraca jako kontekst kolejnej sesji; kopiowanie haseł i nacisku
   może utrwalać ten ton, więc zapis wyniku powinien opierać się na faktach.
8. Przy skracaniu instrukcji sprawdza się, czy zostały granice upoważnienia,
   decyzje projektu i kryteria odbioru. Liczba słów mierzy rozmiar;
   wpływ na skuteczność wymaga porównania wykonanych zadań.
9. Opis skilla we frontmatterze podaje warunki użycia: sytuację, objawy,
   rodzaj zadania. Streszczenie przebiegu w opisie bywa wykonywane zamiast
   treści pliku; zewnętrzna biblioteka skilli zaobserwowała jeden przegląd
   zamiast dwóch opisanych w treści, gdy opis wymieniał „przegląd między
   zadaniami". Opis zwykle nie zawiera kroków procedury.

## Ocena

Konwencję ocenia review. `scripts/register-lint.sh` daje pomocnicze metryki
języka, nie rozstrzyga zgodności z powyższymi regułami. Jego progi nie są
limitami dla autora; ostrzeżenie samo w sobie nie wymaga odstępstwa ani
blokady commita. Tryb raportowy pozostaje domyślny.

Powiązane: [`rules-as-gates.md`](rules-as-gates.md),
[`issue-reporting.md`](issue-reporting.md).

Źródła i granice wnioskowania: [referencja o instrukcjach](../references/instruction-evidence.md), czytana przy projektowaniu lub ocenie instrukcji.

Egzekwuje: review; linter dostarcza pomocniczych metryk.
