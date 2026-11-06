# Wykonawczy adapter kolejki

Wymagania: Python 3.9+, Git, ps oraz system POSIX (macOS/Linux).

`agent-runtime.py` wykonuje jawny JSON work graph. Jest adapterem procesu,
nie kolejnym agentem ani sandboxem. Plan jest zaufaną konfiguracją właściciela;
nie wolno generować i uruchamiać jego komend bez sprawdzenia upoważnienia.
Nie czyta Inbox ani nie akceptuje propozycji za właściciela.

```sh
python3 templates/agent-runtime.py validate templates/agent-runtime/example.json --repo .
python3 templates/agent-runtime.py run templates/agent-runtime/example.json --repo .
python3 templates/agent-runtime.py status templates/agent-runtime/example.json --repo .
python3 templates/agent-runtime.py resume templates/agent-runtime/example.json --repo .
```

Przykład jest rzeczywistym smoke testem odczytu Git. Zastąp go grafem
zaakceptowanej pracy i sprawdzalnymi kryteriami projektu; nie świadczy o
ukończeniu funkcji aplikacji. Wyzwalacz start/resume/worker-result platformy
wywołuje `run` lub `resume`. Gdy kontroler już działa, kolejne wywołanie
odmawia duplikowania; działający kontroler sam odbiera wyniki i przydziela
kolejne gotowe nody. Bez podłączenia tego procesu do uruchamiania pracy
platforma nadal może prowadzić sesję poza kolejką.

## Powiadomienie nie jest zakończeniem batcha

Każdy wrapper po zapisaniu własnego wyniku dopisuje osobny trwały event
`result-ready` do outboxu SQLite, także gdy kontroler został przerwany.
Szybki worker nie czeka na najwolniejszy. Odbiorca rozróżnia wykonanie
(`state`) i dostarczenie wyniku (`delivery_state`): `running`, `result-ready`
oraz `received`. `received` oznacza jawne potwierdzenie odbiorcy; samo
zakończenie procesu lub zielony acceptance nie oznacza, że sesja główna
odebrała wynik. Ack nie zatwierdza jakości i nie zamyka backlogu.
Gdy worker znika bez poprawnego wyniku, kontroler lub poller publikuje
`attention-required` z diagnostyką i `result_available: false`. Takie
powiadomienie wymaga wyjaśnienia blokady; nie jest zakończeniem zadania.
Diagnostyka ma `delivery_state: attention-required` albo `received-attention`;
nie dostaje `result-ready`. Blokada przed startem publikuje osobne
`pre-dispatch-blocked` z `run_id: null`, bez fikcyjnej próby wykonania.

Preferuj osobne natywne zadanie background dla każdego workera, jeśli
platforma umie poinformować sesję główną o jego zakończeniu. Adapter zapisuje
rzeczywisty uchwyt platformy, nie wymyślone ID:

```sh
python3 templates/agent-runtime.py bind-task plan.json --repo . \
  --node X3 --run-id <UUID-próby> --native-task-id <ID-natywnego-zadania>
```

Mapowanie należy do runtime i może zostać zapisane po starcie workera.
Jeden native task odpowiada jednej próbie. Runtime nie zna API dowolnej
sesji Claude/Codex i nie potrafi sam wysłać wiadomości do jej czatu.
To zadanie rzeczywistego adaptera platformy; zapis ID nie zastępuje takiego
podłączenia. Powłokowe `&` nie rejestruje natywnego zadania. `&` z jednym
`wait` dla całej grupy również nie daje powiadomienia po każdym workerze.
Nie wykrywaj tego zakazem regex obejmującym `&&` lub `2>&1`; argv runnera
nie jest domyślnie wykonywane przez powłokę.

Gdy natywne powiadomienie nie jest dostępne, zewnętrzny subscriber albo
natywne zadanie obserwujące odpytuje outbox. Interwał i najkrótszy
oczekiwany czas workera są jawne, z interwałem nie większym od tego czasu:

```sh
python3 templates/agent-runtime.py watch plan.json --repo . --consumer main \
  --poll-seconds 1 --shortest-worker-seconds 5 --max-wait 30
```

`watch` kończy się po pierwszym niepustym batchu zdarzeń, nie po zakończeniu
wszystkich workerów. W pustej kolejce kończy się po max-wait (do 60 sekund);
brak zdarzenia nie jest sukcesem pracy. Subscriber musi faktycznie przekazać
zdarzenie do głównego harnessu, a potem ponowić obserwację. Sam `watch &`
bez takiego odbiorcy nie tworzy powiadomień w sesji. Zwykłe `events` pobiera
bieżący batch bez czekania. Opóźnienie odpytania przy sprawnym lokalnym I/O
jest ograniczone skonfigurowanym interwałem; błąd SQLite/I/O wymaga
zgłoszenia niedostępności obserwatora.

Odbiorca przetwarza zdarzenia w kolejności, utrwala wynik i pozostałe etapy,
a dopiero potem potwierdza `next_cursor` z odpowiedzi:

```sh
python3 templates/agent-runtime.py events plan.json --repo . --consumer main
python3 templates/agent-runtime.py ack plan.json --repo . --consumer main --through <next_cursor>
python3 templates/agent-runtime.py status plan.json --repo . --consumer main --stale-after-seconds 30
```

Cursor jest monotoniczny, a ack nie może wyprzedzić zdarzeń pobranych przez
danego odbiorcę. Starsze ack są idempotentne. Awaria przed ack powoduje
ponowne dostarczenie tego samego eventu/run-id, bez ponownego wykonania
zadania. Każdy consumer ma osobny cursor. Zdarzenia pozostają w bazie;
przerwę między zapisaniem result.json a eventu uzupełnia się z trwałych
receipts. `status` może zgłosić starego odbiorcę albo zbyt długo
niepotwierdzone wyniki. Nie zakładaj aktywnego powiadamiania, gdy odbiorcy
nie zarejestrowano lub native adapter jest niedostępny.
Polling może rozliczać receipts zakończonych procesów, ale nie uruchamia
ani nie ponawia żadnego workera.

## Plan i uprawnienia

- `id` nazywa plan; `schema_version: 1`, jawny `integration_branch`, `capacity`
  1–32. Stan żyje w git common dir, w `agent-coordination/runtime/<id>/`.
- Node ma `id`, `authorized`, `role`, `argv`, `cwd`, `scope`, `depends_on`,
  niepustą listę komend `acceptance`, `timeout_seconds` i `max_attempts` 1–3.
  `argv` i acceptance są tablicami argumentów; nie są ciągami dla powłoki.
- `role`: builder, scout, reviewer, security-reviewer albo red-team.
  Builder potrzebuje osobnego checkoutu i gałęzi feature, ze wspólnym git
  common dir; nie może użyć checkoutu integratora ani gałęzi integracyjnej.
  Zakresy Builderów są rozłączne. Scope jest kontraktem, nie kontrolą zapisu.
- `cwd` jest względne wobec `--repo` albo absolutne w zaufanym planie.
  Checkout musi należeć do tego samego repozytorium. Przed tworzeniem
  Builderowego drzewa cwd może jeszcze nie istnieć.
- Nazwa roli **nie ogranicza** procesu. Dostępne narzędzia, sieć, sekrety,
  ścieżki i zapis muszą być ograniczone przez rzeczywisty adapter/SDK/sandbox.
  Nie dawaj szerokiego Bash roli read-only. W argv adaptera jawnie wybierz
  model i uprawnienia; runtime nie zgaduje flag poszczególnych producentów.
- Reviewer, Security Reviewer i Red Team potrzebują czystego checkoutu
  ocenianego commita; zmiana HEAD lub źródeł w trakcie blokuje odbiór.
  Adapter zdalnego workera czeka na rzeczywisty wynik i wykonuje acceptance;
  samo uzyskanie job-id/start w tle nie może kończyć się sukcesem adaptera.
- Każda rola review ma dokładnie jedno z pól: `review_of` wskazujące
  bezpośrednią zależność typu Builder, albo pełny `review_sha` dla jawnie
  wybranego artefaktu. Sam czysty checkout nie wystarcza. SHA musi obejmować
  wyniki wszystkich bezpośrednich zależności Buildera; stary clean main
  nie przejdzie jako przegląd nowej gałęzi. Runtime nie robi checkoutu za
  recenzenta — właściciel przygotowuje poprawny, niezmienny artefakt.
- Pomocnicze komendy Git wyłączają fsmonitor oraz hooki repozytorium i nie
  cytują nazw ścieżek. Jawne komendy wykonawcy i acceptance zachowują swój
  kontrakt; wymagane kontrole projektu nadal muszą zostać uruchomione.
- Nie umieszczaj sekretów w argv ani planie. Surowe stdout/stderr i config
  prób pozostają wyłącznie w runtime, nie w korpusie. Raport produktu jest
  oddzielnym artefaktem; jego deklaracja PASS nie zastępuje acceptance.

Plan ma niezmienny hash obejmujący także upoważnienia i etapy. Zmiana
zatwierdzonego zakresu wymaga jawnego uzgodnienia i nowego ID planu, a nie
usunięcia noda z bieżącej kolejki. Ukończone nody pozostają w stanie.
Kompletność dotyczy nodów z `authorized: true`; nierozpatrzony Inbox nie jest
przyjętym zakresem. Zależność od nieupoważnionego noda pozostaje otwarta.

Przykład powiązania review z wynikiem zależności (pozostałe wymagane pola
noda pozostają jak w zwykłym grafie):

```json
{"role":"security-reviewer","review_of":"BUILD-X3","depends_on":["BUILD-X3"],"cwd":".worktrees/build-x3"}
```

Host zapisuje `expected_review_sha` w konfiguracji próby oraz SQLite i
przekazuje adapterowi `TOOLKIT_REVIEW_SHA` oraz przy review_of także
`TOOLKIT_REVIEW_OF`. Nie bierze tej wartości z deklaracji modelu.
Przed i po wykonaniu sprawdza rzeczywisty HEAD oraz czystość źródeł.
Receipt zawiera hostowe `reviewed_sha`; rozbieżność blokuje odbiór.

## Wyniki i wznowienie

SQLite zapisuje zarezerwowaną próbę przed uruchomieniem. Wrapper zapisuje
własny identyfikator, PID i czas startu procesu, a potem rzeczywiste kody
wyjścia i hashe wykonanych komend. Node jest complete tylko po sukcesie
komendy wykonawcy oraz wszystkich komend acceptance. Zapisano też oceniany
HEAD. Builder startuje z czystego checkoutu i musi oddać czysty wynik
z nowym commitem na niezmienionej gałęzi. Początkowy HEAD musi być przodkiem
wyniku; przepisanie historii albo commit poza zadeklarowanym scope blokuje odbiór.
Ten pomiar po wykonaniu nie zastępuje sandboxa podczas wykonania.
Skuteczność i kompletność samych kryteriów pozostają przedmiotem review.

Jeden kontroler zarządza repozytorium, równolegląc do `capacity` rozłączne
nody zaakceptowanego planu. Drugi plan czeka na rozliczenie żywych lub niepewnych uruchomień poprzedniego;
znana blokada przy zakończonym procesie nie zatrzymuje niezależnej pracy.
Nie ma niejawnej współbieżności między niezależnymi kontrolerami.
Po awarii kontrolera wrappery żyją dalej; `resume` odbiera ich trwałe wyniki
lub czeka na nie, bez ponownego uruchamiania pracy. Okno awarii bez pewnego
śladu startu/wyniku daje blocked. Brak dowodu żywotności przez ps blokuje;
PID bez czasu startu nie jest dowodem tożsamości.
Uszkodzony JSON, zły typ checks lub rozbieżne dane startu/wyniku zostawiają
widoczny blocked z powodem; nie powodują domyślnego complete. Niepewny worker
zajmuje slot do rozliczenia. Status zależności nieupoważnionej mówi o braku
upoważnienia zamiast sugerować gotowość do uruchomienia.

Timeout obejmuje komendę i acceptance; potomkowie w grupie procesu są
zatrzymywani. Pozostawienie działających potomków po pozornym sukcesie nie
zalicza komendy. Nie jest to izolacja wobec celowo daemonizującego się
wrogiego procesu; do tego potrzebny jest kontener lub sandbox systemowy.
Domyślne kody 2 i 78 oznaczają blokadę bez automatycznego retry; pole
`blocked_exit_codes` pozwala dopasować kontrakt prawdziwego adaptera.
Zwykła porażka ma co najwyżej `max_attempts` prób. Niepewnego wykonania
nie odtwarza się automatycznie.

Po sprawdzeniu skutków operator może wybrać retry lub failed:

```sh
python3 templates/agent-runtime.py resolve plan.json --repo . --node X3 \
  --decision retry --reason 'sprawdzono brak skutków i usunięto blokadę' \
  --acknowledge-side-effects
python3 templates/agent-runtime.py resume plan.json --repo .
```

Nie ma komendy dopisującej dowolne complete ani pomijającej acceptance.
Resolve sprawdza tożsamość procesu przez launch albo zapasowy spawn receipt;
przy utracie obu nie odtwarza pracy na podstawie samej deklaracji operatora.
Trzeba zweryfikować procesy i naprawić dowód tożsamości. Decyzja failed
wyłącza dalsze retry tej próby także wtedy, gdy pozostał budżet.
`status` podczas pracy zwraca snapshot SQLite; gdy nie ma kontrolera,
rozlicza nowe receipts. Niewykonane lub zablokowane nody dają niezerowy kod.

## Integracja i sprzątanie

Worktree przeznaczone do automatycznego sprzątania tworzy sam adapter:

```sh
python3 templates/agent-runtime.py worktree-add plan.json --repo . \
  --node X3 --branch feat/x3 --start-point HEAD
```

Docelową ścieżkę wyznacza cwd noda. Adapter nie przejmuje dowolnego starego
checkoutu na podstawie deklaracji modelu. Gałąź musi być nowa. Builder
wykonuje i odbiera własny commit; integrator scala według zasad projektu.
**Push i utworzenie PR nie są zdarzeniem integracji.**

Po potwierdzonym scaleniu obsługa zdarzenia merge uruchamia:

```sh
python3 templates/agent-runtime.py integrated plan.json --repo . \
  --node X3 --commit <pełny-SHA-bieżącego-celu-integracji>
```

Polecenie sprawdza zakończenie noda, zgodność HEAD z odebranym wynikiem,
pełny SHA tipa zadeklarowanej gałęzi integracyjnej i osiągalność commita
noda z tej gałęzi. **Następnie samo wykonuje cleanup**, bez osobnego kroku
do zapamiętania. Git nie rozstrzyga czy istniał PR; dowodem integracji jest
osiągalność dokładnie odebranego nowego commita z uzgodnionej gałęzi.
Builder bez nowego commita nie przechodzi odbioru; sama obecność gałęzi
ani istniejąca wspólna baza nie wyzwala sprzątania.

Usuwane są tylko checkouty utworzone i zarejestrowane przez ten plan.
Bieżące, zmienione, niezintegrowane, zablokowane, prunable lub o zmienionym
HEAD/branch pozostają z powodem. Czystość obejmuje pliki ignorowane.
Sprzątanie nie stosuje force, nie usuwa gałęzi ani commitów. Wszystkie
wykonania runtime muszą korzystać z kontrolera; zewnętrzny operator, który
zajmuje checkout po odbiorze, blokuje go przez `git worktree lock`, zamiast
używać go po cichu poza protokołem. Program nie wykrywa dowolnego edytora
lub procesu uruchomionego poza tym protokołem.

Po usunięciu przyczyny zachowania można ponowić samo `cleanup`. Właściciel
starych checkoutów wybiera je osobno; ten adapter ich nie przejmuje.

## Ograniczony adapter review

`readonly-review.py` uruchamia Claude CLI z samymi Read/Glob/Grep,
safe-mode/restricted i bez MCP/customizacji. Wymaga jawnego modelu, zaufanej
polityki i briefu oraz wymaganych ścieżek. `--expected-sha` może pochodzić
z hostowego `TOOLKIT_REVIEW_SHA`; czysty target musi odpowiadać temu SHA.
Model czyta migawkę zwykłych plików commita, bez `.git`, ignorowanych danych,
symlinków i typowych nazw sekretów. Kontekst ma limity i jawne pominięcia;
wymagana ścieżka nie może być pominięta. Pliki źródła i środowisko nie są
uruchamiane przez model.

Raport i surowe przebiegi leżą poza wszystkimi checkoutami. Adapter sprawdza
rzeczywiste Read, model, SHA i verdict; sukces procesu CLI nie jest PASS.
Każde żądanie Read/Glob/Grep poza migawkę unieważnia odbiór, także gdy
narzędzie odmówiło wykonania. W czasie pracy granicę odczytu egzekwuje
`--restricted` w CLI; hostowa analiza śladu jest dodatkową kontrolą po fakcie,
nie sandboxem OS. Konkretną wersję CLI należy sprawdzić syntetycznym odczytem
spoza cwd, zamiast przyjmować skuteczność samych nazw flag.
Nierozwiązane HIGH/CRITICAL nie przechodzą jako PASS, INFO może być uwagą
nieblokującą. To pomocnicza recenzja modelu, nie dowód bezpieczeństwa ani
zastępstwo CI, sandboxa dla wykonywanego kodu i owner gates. Inny dostawca
wymaga własnego adaptera z taką kontrolą, nie zmiany etykiety roli.
