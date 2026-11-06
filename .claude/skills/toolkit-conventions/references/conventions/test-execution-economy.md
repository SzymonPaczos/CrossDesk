# Konwencja: ekonomia uruchamiania testów przez agenta

Cel: uzyskać wymagany dowód bez zbędnych powtórek i kosztu kontekstu.
Zakres: dobór uruchomień testów, buildów i bramek. Kryteria dowodu określa
[`test-evidence.md`](test-evidence.md), a własności suity
[`test-quality-baseline.md`](test-quality-baseline.md).

## Dobór pracy

Agent dobiera zakres dodatkowych prób, kolejność, pracę w tle i delegację
do zadania, dostępnego runtime'u oraz budżetu użytkownika. Wymagane checki
projektu pozostają wymagane. Równoległe przebiegi nie współdzielą zasobów,
których stan może zmienić wynik.

Po uzyskaniu dowodu kolejny przebieg uzasadnia zmiana kodu, wykryta awaria
lub nierozstrzygnięte ryzyko. Kontrola cząstkowa może pomóc w diagnozie przed
pełnym zestawem; nie ma obowiązku odkładania wszystkich bramek na koniec.
Audyt porównuje próbkę przebiegów i ich przyczyny z uzgodnionymi rezultatami
z 7 i 21 dni (`weekly-audit`, Krok 0a). Liczba testów, zmienionych plików
lub commitów nie mierzy czasu ani wartości. Utrzymanie i testowanie mogą
być celem zadania; raport rozróżnia je od nieuzgodnionego dryfu procesu.

Na współdzielonej maszynie kolejność zamków i limit ciężkich biegów określa
[`local-gate-orchestration.md`](local-gate-orchestration.md). Slot ogranicza
liczbę równoległych przebiegów; nie zastępuje budżetu workerów.

## Wynik i koszt kontekstu

Z udanego przebiegu zwykle wystarcza podsumowanie zakresu, wyników i pominięć.
Kod 0 bez tych informacji może wymagać odczytu logu. Przy porażce zacznij
od informacji pozwalających ustalić przyczynę i rozszerz odczyt, jeśli potrzeba.
Potok zachowuje wynik właściwego narzędzia; ucięcie wyjścia go nie zmienia.

Pomiar DOM, screenshot i ocena wizualna służą różnym twierdzeniom.
Model główny może użyć każdego z nich, jeśli jest potrzebny do oceny wyniku.
Delegacja lub tańszy model są opcją, nie warunkiem oglądania artefaktów.

Pomiar właściciela w JawnePaństwo z 2026-09-04 wskazał obrazy/snapshoty
w drogim kontekście, zielone logi i powtórki jako główne źródła kosztu;
pełny zestaw bramek trwał około 6 minut, w tym 194 E2E około 154 sekund.
Zachowana preferencja: przy porównywalnej wiarygodności wybierz pomiar
bez modelu, następnie tańszy model, następnie model główny. Dobór zależy
od twierdzenia i dostępnych narzędzi; delegacja nie zwalnia z oceny dowodu.

Optymalizacja opiera się na zmierzonym koszcie, czasie i przyczynie powtórek.
Wynik porównania określa, co mierzono; oszczędność tokenów nie zastępuje
potwierdzenia zachowania.

## Egzekwowanie

Pełna kontrola wykonana przez pre-commit jest kontrolą przed commitem,
nie dodatkowym punktem ponad identyczne ręczne uruchomienie. Nie powtarzaj
jej bez zmiany, nowego ryzyka lub obowiązku konkretnego pipeline'u. Wynik
musi dotyczyć rzeczywiście ocenianego stanu; optymalizacja nie wyłącza hooka.

Konwencję ocenia review. Nie ma skryptu rozstrzygającego, ile kontekstu
potrzebował model; sam odczyt logu lub obrazu nie jest naruszeniem.

Egzekwuje: review wyników i kosztów w kontekście budżetu projektu.
