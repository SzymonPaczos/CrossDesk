# Konwencja: orkiestracja lokalnych bramek

Cel: ograniczyć koszt współbieżnych bramek na współdzielonej maszynie bez osłabiania
testów.
Zakres: zamki klas, sloty ciężkich biegów, nadzór procesów i lokalna weryfikacja.

Uzupełnia [`ci-pipeline-architecture.md` §11a](ci-pipeline-architecture.md#11a-profil-local-first--jak-czytać-tę-konwencję-bez-hosted-ci)
i [`test-execution-economy.md`](test-execution-economy.md).
Graf bramek i detekcję zmian opisuje [`ci-pipeline-architecture.md`](ci-pipeline-architecture.md), bezpieczeństwo dostawy [`ci-cd.md`](ci-cd.md), kryteria testów
[`test-quality-baseline.md`](test-quality-baseline.md), role
[`multi-agent-delivery.md`](multi-agent-delivery.md), a warunki zakończenia
[`quality-gates-and-dod.md`](quality-gates-and-dod.md).

## 1. Serializacja pushu

Push uruchamiaj z katalogu głównego drzewa przez
[`templates/local-gates/push-lock.sh`](../templates/local-gates/push-lock.sh).
Wrapper trzyma zamek klasy frontendu przez cały push i jego hooki. Usuwa to
nakładanie się kosztownego pushu na build lub test przeglądarkowy weryfikatora.
Hook sprawdza `GATE_FRONT_LOCK` poleceniem `heavy-slot.py front-check --token
"$GATE_FRONT_LOCK"`; sam napis w środowisku nie wystarcza. Bez poprawnego tokenu
hook musi sam wejść w ten sam protokół zamka i slotu albo odmówić uruchomienia.
Weryfikacja: worktree z plikiem `.git` jest odrzucane przed wywołaniem Git;
dwa pushe nie wykonują równocześnie kosztownej części. Używaj atrapy Git,
nie prawdziwego zdalnego repozytorium.

## 2. Klasy zamków i limit dwóch ciężkich biegów

Osobne klasy obejmują frontend, backend i testy wspólnej bazy. Klasa ogranicza
równoczesny dostęp do jednego zasobu; dwa globalne sloty ograniczają sumę
buildów i ciężkich zestawów testów na maszynie. Wszystkie checkouty i hooki
muszą wskazywać te same `GATE_LOCK_DIR` i `GATE_STATE_DIR`. Domyślne wartości
to `/tmp/local-gates-<uid>` i `${XDG_STATE_HOME:-~/.local/state}/local-gates`.
Katalogi muszą należeć do użytkownika, mieć tryb 700 i nie być dowiązaniami.

Kolejność: zamek klasy, następnie `hs_take klasa opis`, następnie praca,
`hs_release`, zwolnienie zamka klasy. Przed czekaniem na inny zamek klasy oddaj
slot; nie zagnieżdżaj dowolnie zamków klas. Dla fazy bazy stosuj jeden globalny
porządek klas, np. backend przed bazą, a slot bierz dopiero po obu zamkach.
Koszt usuwany: przeciążenie pamięci i CPU, timeouty oraz zakleszczenia kolejki.

Dowód dla tego protokołu: proces posiadający slot nie czeka na zamek klasy.
Proces czekający na zamek klasy nie posiada slotu, więc nie blokuje pojemności
procesowi, który ma wykonać pracę i zwolnić zamek. Jednolity porządek klas
wyklucza cykl między samymi zamkami klas. Zatem oczekiwanie na slot nie zamyka
cyklu zależności; dowód nie obejmuje dodatkowych zamków aplikacji lub bazy,
które trzeba osobno uwzględnić w porządku.

Weryfikacja: dwa żywe procesy otrzymują sloty, trzeci dostaje kod 1 z `try`;
po zwolnieniu jednego slotu trzeci wchodzi. Slot identyfikuje PID i czas startu:
martwy PID lub ponowne użycie PID zwalnia slot przy następnym odczycie do przejęcia.
Błąd `ps` oznacza odmowę przejęcia, a nie martwy proces. Token potomka jest
sprawdzany względem pliku slotu i żywego przodka. Limit oczekiwania daje kod
124; uszkodzony stan nie uruchamia ciężkiego biegu.

Szablon pushu używa `flock` przez Python zamiast katalogowego zamka `mkdir`.
Nie mieszaj tych protokołów dla jednego zasobu. Pliku `frontend.lock` nie
usuwaj: blokada jądra znika z zamknięciem deskryptora, także po śmierci procesu.
Stan slotów sprząta pomocnik pod własnym `flock`, z kontrolą właściciela i typu
pliku. Zmiana katalogu stanu podczas aktywnych biegów tworzy niezależną pulę
i łamie limit – zmieniaj konfigurację dopiero po zatrzymaniu wszystkich biegów.

## 3. Współdzielona baza i liczba workerów

Testy zapisujące do wspólnej bazy uruchamiaj po jednym zestawie pod wspólnym
zamkiem DB, bez równoległych workerów. Zapobiega to wyścigom migracji,
czyszczenia i danych testowych. Weryfikacja: drugi zestaw czeka, zanim rozpocznie
pierwszy zapis; testy używają wyłącznie odrębnej lokalnej bazy testowej.

Limit slotów nie zastępuje limitu workerów. Ustal budżet pozostawiający rdzenie
dla systemu, np. `max(1, liczba_rdzeni - 4)`; przy dwóch aktywnych klasach
podziel ten budżet. Nie stosuj `pytest -n auto` ani nieograniczonego Jesta.
Koszt usuwany: zwielokrotnione procesy i zamrożony interfejs maszyny.
Weryfikacja: sprawdź argumenty rzeczywiście uruchomionych runnerów i sumę
workerów obu klas, nie tylko deklarację w konfiguracji.

## 4. Weryfikator buildera

Builder robi testy celowane w swojej piaskownicy. Nadzorca z głównego drzewa
uruchamia zaufany skrypt weryfikatora nad kodem worktree w osobnym ograniczonym
środowisku dopuszczającym tylko potrzebne lokalne usługi. „Poza piaskownicą
buildera” nie oznacza pełnego dostępu do sieci lub sekretów. Nie wykonuj
zmodyfikowanego przez buildera wrappera z uprawnieniami nadzorcy.
Koszt usuwany: fałszywa czerwień ograniczeń buildera i możliwość zmiany własnej
bramki przez oceniany kod. Weryfikacja: zmiana wrappera w worktree nie zmienia
wykonywanego nadzorcy; brak dostępu do niedozwolonych usług pozostaje błędem.

W rundach poprawek zakres gałęzi skraca testy. Po zielonej rundzie zawężonej
nadzorca uruchamia jedną pełną konfirmację; dopiero jej wynik pozwala ogłosić
pełną zieleń. Nie ufaj plikowi wyniku buildera jako dowodowi pełnego zakresu.
Przykładowy interfejs to `CODEX_VERIFY=frontend` i `CODEX_E2E_SCOPE=branch`.
Weryfikacja: zawężony sukces powoduje pełny bieg, a jego porażka zachowuje czerwień.

Przy sygnale lub końcu runnera nadzorca kończy całą grupę procesów przed
oddaniem slotu i zamka. Grupa, której nie da się zakończyć, utrzymuje zamek.
Weryfikacja: przerwij test z potomkiem; drugi bieg nie wchodzi przed śmiercią
potomka. SIGKILL samego wrappera wymaga osobnego nadzorcy: slot PID może zostać
odzyskany, chociaż osierocone dzieci jeszcze działają. Same szablony nie
stanowią pełnego nadzorcy odpornego na zabicie wrappera.

Wyników nie przenoś między różnymi drzewami ani zakresami na podstawie samego
„ostatnio zielone”. Ewentualne ponowne użycie wymaga identycznego drzewa,
konfiguracji, zależności, runnera i zakresu; nie zastępuje pełnej konfirmacji.
Weryfikacja: zmiana dowolnego wejścia unieważnia wynik. Szablony nie wdrażają cache.

## 5. Zapadki audytu zależności

Nowa podatność powyżej ustalonego progu blokuje wydanie. Znany dług ma jawną
listę identyfikatorów z uzasadnieniem i właścicielem akceptacji; lista nie
rośnie automatycznie, a nieaktualne wpisy usuwa się. Niepoprawny lub brakujący
raport oznacza błąd, a nie brak podatności. Oddzielnie sprawdzaj wiek ostatniego
audytu według ustalonego budżetu dni. Koszt usuwany: stałe omijanie audytu
przez jeden znany problem oraz wydawanie na podstawie starego raportu.
Weryfikacja offline: fixture nowej podatności blokuje, jawnie przyjętej przechodzi,
uszkodzony raport blokuje, a przeterminowana data blokuje niezależnie od CVE.

## 6. Zmiana UI wymaga testu interakcji

Zmiana komponentu klienckiego lub hooka wymaga powiązanego speca: kliknięcie
lub wpisanie wartości oraz asercja skutku po tej czynności. Sam render i sama
obecność `expect` w pliku nie dowodzą zachowania. Mierz rzeczywisty zakres pushu,
uwzględnij przeniesienia plików; nie zastępuj go domyślną gałęzią zdalną.
Koszt usuwany: pozornie działające kontrolki. Weryfikacja: zmiana bez speca
blokuje, spec sprawdzający tylko render blokuje, interakcja z poprawną asercją
przechodzi; sabotaż obsługi kliknięcia daje czerwień tego speca.

## 7. Test niestabilny pod obciążeniem

Po porażce pod obciążeniem uruchom wskazany test osobno trzy razy. Trzy zielone
wyniki oznaczają wpis do backlogu z licznikiem zdarzeń i logami, następnie
ponowienie pushu z pełnymi bramkami, bez `SKIP_*`. Pojedynczy czerwony wynik
izolowany wymaga diagnozy; nie przykrywaj go automatycznym retry ani etykietą
„flaky”. Koszt usuwany: znikające regresje i marnowanie pełnych biegów.
Weryfikacja: raport zawiera pierwotny błąd, trzy wyniki izolowane i wynik
ponownego pushu, a konfiguracja runnera nie włącza retry.

## 8. Wydanie z taga jedną akcją

Jedno polecenie tworzy albo wskazuje istniejący tag, przeprowadza wymagane
bramki i przekazuje dokładnie ten tag do wdrożenia. Wdrożenie przyjmuje tylko
istniejący tag; ponowienie nie przesuwa taga. Wymagaj czystego drzewa i właściwej
gałęzi wydania. Koszt usuwany: rozjazd między przetestowanym SHA i wdrożeniem
oraz ręczne, pomijane kroki. Weryfikacja offline: atrapy Git i wdrożenia
potwierdzają identyczny tag; brak taga, brudne drzewo i błąd bramki blokują deploy.
Konwencja nie dostarcza adaptera infrastruktury wdrożeniowej.

## 9. Egzekwowanie

Szablony: [`heavy-slot.sh`](../templates/local-gates/heavy-slot.sh)
i [`heavy-slot.py`](../templates/local-gates/heavy-slot.py).
Test offline: `bash scripts/test-local-gate-templates.sh`. Raport podaje
liczbę przypadków wykonanych i pominiętych; pominięta integracja z `ps`
wymaga powtórzenia w środowisku pozwalającym obserwować procesy.
Pozostałe kontrakty wymagają adapterów projektu i review.

## 10. Pomiar w projekcie źródłowym

W jednym projekcie zaobserwowano 309 procesów jest-worker, około 100 MB
wolnej pamięci z 64 GB i load average 97. Przy 3–4 równoległych klasach
na czterech rdzeniach wydajności load average wynosiło 51–65.
Przyjęto dwa sloty oraz budżet workerów liczony jako rdzenie minus cztery.
To obserwacje źródłowe, nie nowy benchmark ani uniwersalny dobór liczb.
