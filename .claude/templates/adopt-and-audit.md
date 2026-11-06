# Zlecenie dla agenta projektu: adopcja, sprawdzenie działania, audyt

Pracujesz w repozytorium aplikacji. Zaadoptuj wskazane wydanie claude-toolkit,
sprawdź jego działanie w tej platformie, a następnie wykonaj audyt aplikacji.
Źródło: `https://github.com/SzymonPaczos/claude-toolkit`, wydanie `2026.11.06`.
Przed rozpoczęciem potwierdź opublikowany commit/gałąź przekazany przez
właściciela. Brak docelowej wersji nie oznacza zgody na inną ani na pozorną
adopcję. Nie skanuj dysku w poszukiwaniu klona; użyj źródła z locka lub
przekazanego adresu i istniejących instrukcji projektu.

## Jeden plan pracy

Zapisz to zlecenie w backlogu, z jednym planem odbioru: A1 adopcja,
A2 rzeczywiste sprawdzenie integracji, A3 audyt rezultatów/jakości,
A4 audyt bezpieczeństwa i raport. Zachowaj wszystkie wcześniejsze otwarte
zadania i etapy; nowy temat ich nie anuluje. Nie twórz drugiej listy stanu
w handoffie. Nie zastępuj pracy nad produktem nieograniczonym poprawianiem
reguł. Audyt nie naprawia sam znalezisk poza przyjętym zakresem.

## A1 — Adopcja

Czytaj właściwe sekcje ADOPT i przewodnik przejścia z faktycznej wersji
projektu, zamiast całego korpusu. Sprawdź lock, lokalne rozszerzenia i
sprzeczne instrukcje. Użyj prepare-update/update oraz jawnego rekordu
adopcji; zachowaj uzasadnione różnice. Skille kopiuj całymi katalogami,
bez symlinków i instalacji globalnej. Cloudflare security-audit zachowuje
MIT LICENSE, UPSTREAM.json oraz lokalną mapę ról. Toolkit-sync obejmuje
także pliki Python/JSON/YAML oraz wszystkie companions skilla, w tym CJS.

Istniejący projekt adaptuj bez nadpisywania lokalnych plików. Generator
bootstrap-project służy jawnemu profilowi nowego projektu; nie zastępuje
kontrolowanej migracji istniejącego locka i historii adopcji. Profil CI,
produkcji i backend agenta bierz z decyzji właściciela, nie zgaduj.

## A2 — Sprawdzenie rzeczywistej integracji

Podłącz start/resume, odbiór wyników i potwierdzony merge do mechanizmów
platformy. Nie kończ na skopiowaniu skryptów. Każdy worker dostaje natywne
zadanie w tle i własny identyfikator; samo shellowe `&`, także z jednym
końcowym wait, nie jest kanałem powiadomień per worker. Trwały outbox i
potwierdzenie odbioru nie zastępują rzeczywistego wybudzenia sesji głównej.

Sprawdź na małej próbie: szybki worker jest odebrany i skierowany do review,
gdy wolny nadal pracuje; wolny slot dostaje kolejne gotowe upoważnione
zadanie. Przerwij/wznów kontroler: wyniki zostają i nie ma duplikatów.
Review ocenia dokładny SHA Buildera. Po rzeczywistym merge czyści się
wyłącznie własny czysty nieużywany worktree, zachowując gałąź/commity.
Brudny, locked, bieżący i niezintegrowany checkout zostaje z powodem.

Sprawdź też timeout z potomkiem, odrzucenie fałszywego raportu, faktyczny
zapis backlogu i uprawnienia do Git. Brak możliwości commita w sandboxie
oznacza jawnego właściciela tego kroku, bez wyłączania ochron. Nie uruchamiaj
pełnej suity ręcznie tuż przed hookiem, który wykona tę samą kontrolę.
Bez spełnienia wymaganych prób rekord adopcji nie jest complete.

## A3 — Audyt rezultatów i jakości

Porównaj uzgodnione cele i wszystkie etapy z dostawami za ostatni tydzień;
przy zastoju rozszerz historię do 21 dni. Sprawdź zamknięcia rodziców,
nieodebrane wyniki roju, opuszczone zadania, blokady i dryf procesu.
Zieleń testów części nie dowodzi wykonania całości. Nie mierz czasu ani
wartości liczbą plików testowych lub commitów.

Próbkę TDD oceń po rzeczywistym red–green–refactor, istotnych przypadkach
i wykrywalności błędów; sam procent coverage nie wystarcza. Dobierz warstwę
testu do ryzyka. Kontrole zakończone dla niezmienionego stanu nie wymagają
powtarzania bez nowej przyczyny. Raportuj koszt i czas tylko z pomiaru.

## A4 — Bezpieczeństwo i końcowy raport

Uruchom niezależnego read-only Security Reviewera i użyj security-audit
Cloudflare do wyraźnie zleconego pełnego zakresu. Orchestrator uruchamia
ograniczonych wykonawców i skanery; Reviewer nie dostaje szerokiego Bash.
Inventory/SBOM, OSV/CVE/KEV, SAST, sekrety w historii, obrazy/IaC i DAST są
osobnymi klasami. Zapisz SHA, kody wyjścia, świeżość, zakres i błędy.
Pusta lista CVE nie oznacza bezpieczeństwa aplikacji.

Kod kontrolowany przez cel, buildy, testy i PoC wykonuj tylko w rzeczywistym
sandboxie OS, bez zewnętrznej sieci, z oczyszczonym środowiskiem, limitami
i wyłącznie dozwolonym scratch. Bez tych warunków pozostaw needs_validation.
Aktywne próby na działającej aplikacji dotyczą tylko wcześniej uzgodnionego
środowiska/zakresu. Nie pobieraj i nie uruchamiaj wszystkich exploitów CVE.
Znaleziska weryfikuje świeży agent; naprawia osobny Builder.

Raport rozlicza A1–A4: dowód albo jawny brak, potwierdzone ustalenia,
needs_validation, pokrycie i zaległe zadania. Zachowaj wyniki poza korpusem,
bez sekretów, danych klientów i surowych transcriptów. Jeśli adopcja jest
zablokowana, prowadź niezależne części audytu według przyjętej wersji,
oznaczając luki; sam upgrade instrukcji nie zastępuje audytu produktu.
