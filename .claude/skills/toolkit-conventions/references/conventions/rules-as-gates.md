# Konwencja: reguły jako gate'y

Zakres: projektowanie, zmiana i audyt bramek. Celem jest wiarygodne wykrycie
określonego naruszenia. Dobór implementacji należy do autora; poniższy
kontrakt nie jest listą czynności do powtarzania przy każdej zmianie kodu.

## Kontrakt bramki

Numery identyfikują wymagania przywoływane przez szablony i audyt.

1. Bramka odpowiada na opisany incydent lub ryzyko oraz konkretną regułę.
2. Sygnał rozstrzyga wskazaną klasę błędu. Szeroka heurystyka pozostaje
   oceną pomocniczą.
3. Przed włączeniem blokowania istnieje przebieg raportowy z oceną
   fałszywych alarmów.
4. Awans do blokowania obejmuje podłączenie do CI w tej samej zmianie.
   W projekcie local-first stosuje się zapisany profil z [`ci-cd.md`](ci-cd.md).
5. Szybkie kontrole biegną zawsze; zakres ciężkich zależy od zmienionych
   ścieżek i ryzyka. Wymagane kontrole projektu zachowują swój zakres.
6. Brak środowiska wymaganego przez blokującą bramkę kończy się porażką
   i informacją o brakującym warunku. Nieobowiązujący pomiar to `n/a`
   z powodem, a nie zaliczona kontrola.
7. Awaryjne pominięcie jest jawne i ograniczone do nazwanej warstwy.
   Nie wyłącza pozostałych bramek i nie jest dowodem ich zaliczenia.
8. Audyt sprawdza rzeczywisty trigger i zakres: właściwą zmianę, wykonane
   warstwy oraz zgodność opisu z działaniem. Wczesne wyjście nie może
   pomijać wymaganych kontroli.
9. Raport podaje ustalony stan, jego skutek i dowód: komendę lub źródło.
   Identyfikator służy odwołaniom; sam nie wyjaśnia naruszenia. Te informacje
   mogą być zdaniem, tabelą lub polami formatu maszynowego.
   Przykład po potwierdzeniu odczytu bez logowania: „Panel ujawnia dane bez
   uwierzytelnienia; anonimowy GET zwrócił pełną treść (AUD-03)”. Sam kod
   `AUD-03` nie dostarcza tych faktów; raport nie dopowiada brakującego dowodu.
10. Bramka ma sprawdzian na znanym poprawnym i błędnym materiale. Wyniki
    potwierdzają zarówno akceptację, jak i odrzucenie właściwego przypadku.
    Wzorzec: `templates/test-gates.sh`.
11. Pomiar dotyczy wskazanego repozytorium. Tożsamość wejścia i oczekiwane
    wyniki potwierdzają odczyt; dwie różne próbki mogą mieć tę samą liczność.
    Niedostępny pomiar ma status `n/a` z powodem, nigdy zero ustaleń.
    Brak narzędzia wymaganego przez bramkę blokującą nadal oznacza porażkę z punktu 6.
12. Raport rozróżnia wynik, metodę sprawdzenia oraz brak wykonania:
    `passed`, `failed`, `not-run`, `n/a`, z metodą `gate` lub `review`.
    Ocena ręczna nie jest wykonaniem skryptu. Używany format projektu
    zachowuje te rozróżnienia, nawet jeśli ma inne etykiety.
13. Weryfikacja negatywna spełnia [`test-evidence.md`](test-evidence.md).
    Wynik ujawnia użyte źródło i konfigurację, wersję narzędzia oraz zakres
    zebranych plików lub testów; sam kod wyjścia nie potwierdza wykonania.
14. Zmiana kontraktu między warstwami ma test ich połączenia, używający
    rzeczywistych kształtów producenta i odbiorcy.
15. Bramka podaje maszynowy mianownik, np. `NAZWA_TOTAL: <n>`, oraz
    wykluczenia. Wymagany pomiar z zerowym zakresem nie jest sukcesem.
    Zakres ma niezależne źródło kontrolne; rozbieżność unieważnia wynik.
    Raport identyfikuje oba źródła albo jawnie ujawnia brak niezależnej
    kontroli. Rejestr: `fixtures/rejestr-bramek.tsv`.
16. Materiał known-good i known-bad pozostaje w repo i jest sprawdzany
    przy pushu przez `templates/gate-selfcheck.sh`. Spadek zakresu względem
    `fixtures/mianowniki.baseline` wymaga jawnego zatwierdzenia w repo.
17. Lokalne i CI wywołują to samo wejście, np. `scripts/gates.sh`.
    Wersja narzędzia i suma konfiguracji pozwalają porównać przebiegi.
    Komendy i nazwy zmiennych w dokumentacji odpowiadają temu wejściu;
    kontrola porównująca dokumentację ze skryptem wykrywa ich rozjazd.
18. Rejestr przypisuje każdej konwencji sposób egzekwowania: `bramka`,
    `do-zrobienia` z powodem lub `czytanie`. Pokrycie obejmuje wszystkie
    konwencje, bez braków i podwójnych przypisań; sama zgodność sum nie
    dowodzi pokrycia. Reguła oceniana ręcznie nie obiecuje egzekwowania
    przez skrypt. Wzorzec: `templates/rejestr-regul.sh`.
19. Mutacja zmienia zachowanie istotne dla scenariusza. Porażka wynika
    z badanej przyczyny; liczba czerwonych testów tego nie rozstrzyga.
    Niepotwierdzony wpis dowodu jest usuwany lub korygowany.
20. Każda strona próby korzysta z odpowiadającego jej kodu i artefaktów.
    Czyszczenie lub odizolowanie cache jest jednym ze sposobów zapewnienia
    świeżości. Wzorzec: `templates/negative-verification.sh`.
21. Znany błędny materiał powstaje wraz z bramką. Bramka nie uznaje liczby
    własnych uruchomień ani wytworzonych raportów za pomiar poprawności repo.
22. Job raportuje wykonaną pracę. Brak wymaganego sekretu na własnej gałęzi
    blokuje; niedostępność sekretu w PR z forka ma jawny status pominięcia.
    Zero wykonanych kroków nie dowodzi zaliczenia wymaganej kontroli.
    Wzorzec: `templates/ci-effective-work.sh`.
23. Inwentarz testu lub bramki pochodzi z aplikacji albo źródła, dzięki
    czemu obejmuje nowe byty. Wyjątki są jawne i nazwane. Niezależna kontrola
    mianownika z punktu 15 wykrywa niepełne odkrywanie.
24. Czerwona i zielona strona dowodu mają tę samą etykietę i szczegółowość.
    Rejestr ujawnia brakujące pary i rozjazdy granulacji; wzrost braków
    wymaga jawnego wpisu w repo. Wynik całego pliku nie domyka pominiętego testu.
25. Pominięty przypadek pozostaje `skipped`, również w zielonym jobie.
    Wynik podaje liczbę wykonanych i pominiętych przypadków.
26. Test argumentu ścieżki używa znanego materiału także poza katalogiem
    wywołania. Weryfikuje odczyt tego materiału i oczekiwany wynik,
    zamiast wnioskować o błędzie z samej równości liczników.
27. Nadzór długiej pracy korzysta z sygnałów runtime'u, jeśli są dostępne.
    Własny monitor odróżnia żywotność, postęp i brak danych. Zatrzymanie
    procesu dotyczy zidentyfikowanego PID i uwzględnia stan ukończonej pracy;
    szeroki wzorzec nazwy nie identyfikuje bezpiecznie celu.
    Przed uznaniem ciszy za zawis sprawdź ostatni komunikat i stan procesu:
    wyczerpany limit dostawcy może wyglądać jak brak postępu. Te dane oraz
    zachowane wyniki pracy pozwalają rozstrzygnąć, czy proces zatrzymać.

## Dwa przypadki implementacyjne

### A1. Hook pre-push sprawdza wysyłany commit

Zakres wynika z refów i SHA przekazanych na stdin, nie z bieżącego `HEAD`.
Sprawdzany jest wysyłany commit, nawet gdy working tree ma już poprawkę.
Odtworzenie commita w tymczasowym worktree jest jednym z rozwiązań.
Wzorzec: `NEW-PROJECT.md` §4.2.

### A2. Warstwy skryptu zachowują wynik i zakres

Nieblokujący pipeline nie przerywa kolejnych kontroli przez `set -e` lub
`pipefail`. Oczekiwany brak dopasowania jest obsłużony oddzielnie od awarii
narzędzia. Końcowy status uwzględnia wszystkie wymagane warstwy.

## Ratchet

Ustalony poziom jakości nie pogarsza się bez jawnej decyzji. Po usunięciu
istniejących naruszeń bramka chroni osiągnięty poziom. Nowy incydent
aktualizuje właściwy test lub kryterium audytu; nie musi dodawać kolejnego
ogólnego nakazu do instrukcji każdej sesji.

Egzekwuje: review kontraktu; `templates/gate-selfcheck.sh` i rejestr sprawdzają zadeklarowane przypadki oraz pokrycie, nie sens każdej reguły.
