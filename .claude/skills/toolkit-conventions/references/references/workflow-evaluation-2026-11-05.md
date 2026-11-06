# Ciągłość zadań, rój i testowanie — pomiar 2026-11-05

Zebrano: 2026-11-05. Przegląd: 2026-12-05.
Zebrał: autor zmiany; pomiar i interpretacja nie mają niezależnego sign-offu.
Grounding: lokalny eksperyment opisany poniżej, pliki metryk oraz wskazane
źródła pierwotne. To materiał pomocniczy czytany na żądanie, nie nowa procedura.

## Najważniejsze ustalenia

Testy checkera miały rzeczywistą lukę: wykrywały 2 z 4 wybranych regresji,
po poprawieniu testów wykrywają 4 z 4. Pilot zachowania nie odtworzył
porzucenia X3/X4 ani braku dispatchu w krótkich scenariuszach. Nie dowodzi
więc usunięcia zgłoszonego problemu długich sesji. Poprawiono zasady zapisu
pracy, audytu i odpowiedzialności; automatycznego adaptera kolejki i cleanupu
nie wdrożono. Pozostaje w MIG-2026-11-05-24.

Ocena jakości konkretnej aplikacji i jej rzeczywistego TDD pozostaje otwarta
w EVAL-2026-11-05-01, etap E5, do wskazania repozytorium. Z samego toolkitu
nie wynika, czy wszystkie aplikacje są dobrze napisane.

## Pilot rzeczywistego CLI

Porównanie: opublikowane `2026.11.05`, commit
`f8cd5ef6dcd3bbb563ac14aeb18dbbcdf9754b40`, oraz zamrożone instrukcje
przygotowywanej wersji. CLI `2.1.318`, model główny `claude-fable-5-1`,
effort `low`. To porównanie instrukcji przy jednym modelu głównym, nie modeli.
Źródła polityk: project-state-layout, backlog-contract, Coordinator,
fragment multi-agent-delivery; dla audytów weekly-audit. Hash każdej
wstrzykniętej polityki jest w [metrykach](measurements/workflow-pilot-2026-11-05.json).
Nie mierzono całego finalnego korpusu ani automatycznego wyboru skilla.

22 próby, po 11 na wariant. Kolejność losowana z seedem 20261105,
równolegle najwyżej dwa procesy. Osobny neutralnie nazwany katalog na próbę,
identyczne zadania i narzędzia. Modele nie widziały etykiet wariantu, graderów
ani surowych logów; logi były poza ich katalogami. Włączone safe-mode,
restricted i strict MCP; brak powłoki, sieci i dostępu do rzeczywistych repo.
Main miał narzędzia zapisu tylko w scenariuszach plikowych; próby audytu
i delegacji używały narzędzi odczytu, w delegacji także Agent.

Warstwa danych stanu w obu wariantach była jednakowo mapowana z `.claude/`
na syntetyczne `state/`. Próba wykonalności wykazała, że CLI restricted
z dontAsk odmawia zapisu chronionego `.claude/` mimo udostępnionego Write.
Nie zmieniano ochron CLI. W produkcyjnej adopcji trzeba sprawdzić faktyczny
zapis backlogu; deklaracja narzędzia nie potwierdza uprawnienia.
To udokumentowane zachowanie [chronionych ścieżek Claude Code](https://code.claude.com/docs/en/permission-modes#protected-paths).

| Obserwacja | Opublikowana | Przygotowana |
|---|---:|---:|
| X3/X4 zachowane po zmianie tematu | 2/2 | 2/2 |
| X3/X4 odzyskane przez nowy proces bez historii rozmowy | 2/2 | 2/2 |
| Trwały zapis pozostałego zakresu w tych próbach | 4/4 | 4/4 |
| Fałszywe ukończenia przy brakujących X3/X4 | 0/4 | 0/4 |
| Dwa rzeczywiste przydziały w próbie roju | 2/2 | 2/2 |
| Prosta odpowiedź bez niepotrzebnego zapisu | 1/1 | 1/1 |
| Syntetyczna klasyfikacja audytowa zgodna z pełną rubryką | 3/4 | 4/4 |

W próbach X sprawdzono powstanie X1/X2 i ich treść, brak X3/X4 oraz odpowiedź
o stanie całego zadania. Nowy proces miał tylko pliki. Jedna odpowiedź
opublikowanej wersji podała stabilne ID dwóch rekordów backlogu zamiast
literalnych X3/X4. Nagłówki tych rekordów jednoznacznie wskazywały X3 i X4,
więc uznano odzyskanie zakresu. Wynik pierwotnego, zbyt ścisłego gradera
zachowano osobno w JSON, razem z jawną normalizacją aliasów.

Dispatch sprawdzono po rzeczywistych wywołaniach Agent i potwierdzeniach
ich przyjęcia, dla obu przypisanych plików. Łącznie osiem uruchomień:
sześć synchronicznych zwrotów i dwa potwierdzenia startu w tle. Odbioru tych
dwóch wyników asynchronicznych nie zmierzono; zaliczenie dotyczy dispatchu,
nie ukończenia całego przeglądu. CLI wybierał wbudowane Explore lub
general-purpose; jawna definicja scout nie zapewniła stałej roli w safe-mode.
Nie ustalano osobnego modelu każdego workera, więc koszt nie jest
porównaniem identycznych konfiguracji wszystkich wykonawców.

Cztery syntetyczne audyty dostawały przesłanki w evidence.json: 21 dni dryfu
od eksportu do reguł/testów, uzgodniona naprawa z testem regresji, potwierdzona
blokada oraz brak źródła zakresu. Obie wersje rozpoznały dryf, blokadę i brak
źródeł. Przy uzgodnionej naprawie opublikowana zwróciła unverified/null,
przygotowana complete/false. To różnica ostrożności wobec dostarczonych
przesłanek, a nie wykazany fałszywy alarm ani dowód lepszego audytu realnego
repozytorium. Nie wykonywano pełnego weekly-audit ani Security Review.

Koszt raportowany przez CLI: opublikowana 2,323263 USD, przygotowana
2,548190 USD; razem 4,871453 USD. Próby wykonalności i błędy reportera przed
ustalonym porównaniem: dalsze 3,065771 USD raportowanego kosztu. Wcześniejsza
kalibracja transportu i dwa próbne scenariusze są poza tymi kwotami.
To telemetria CLI, nie odczyt faktury. Czas pojedynczych prób jest w JSON.
Cache serwera, modele workerów i mała próba nie pozwalają wnioskować
o oszczędności, produktywności ani stabilnej różnicy kosztu instrukcji.

Nie jest to test trzytygodniowej pracy, wymuszonego compactu, dużej kolejki,
wznowienia po awarii workerów ani realnego merge/cleanup. Nie obejmuje
wszystkich producentów. Skrypt pilota był narzędziem jednorazowym poza
korpusem, nie dystrybuowanym harnessem; JSON zachowuje warunki i hashe,
ale sam nie zapewnia pełnej odtwarzalności. Przed bramką release potrzebny
jest wersjonowany runner, więcej powtórzeń i test tych trudniejszych sytuacji.
To ogranicza zakres wniosków, nie usprawiedliwia zamknięcia pozostałych etapów.

## Czy testy wykrywają błąd

W prywatnych kopiach task-completion.py celowo usunięto kolejno ochronę:
otwartych etapów, brakujących dowodów, braku bazy i zmiany zakresu.
Każda próba miała poprawny składniowo mutant i zielony test kontrolny.
Sprawdzano istniejący test przypisany do danej regresji, nie pełny wynik
wszystkich możliwych mutacji. [Przed](measurements/continuity-mutations-before-2026-11-05.json)
wykrywane były tylko brak bazy i zmiana zakresu: 2/4.

Dwa testy bez bazy kończyły się odmową także wtedy, gdy badana ochrona
przestała działać — druga blokada maskowała defekt. Dodano zaakceptowaną
bazę do tych przypadków, izolując powód odmowy. [Po zmianie](measurements/continuity-mutations-after-2026-11-05.json)
testy wykrywają 4/4 wybrane regresje. Checker pozostał bez zmian.
To lokalny wynik czterech dobranych regresji, nie globalny mutation score
ani dowód poprawności wszystkich bramek toolkitu.

## TDD i jakość budowania aplikacji

Dotychczasowa praca nad checkerem nie ma wystarczającego dowodu ścisłego
red–green–refactor: testy i implementacja powstawały także po review.
Zieleń 18 testów nie potwierdza TDD. W aktualnym pomiarze wykazano lukę
testów, poprawiono je i sprawdzono ponownie te same mutanty.

W planie funkcji wymagano pełnego kodu testu przed wykonaniem, pomijając
jawny krok refaktoryzacji. Usunięto obowiązek powielania kodu w planie.
Plan określa wejście, obserwowalny wynik, kontrakt i ryzyko. Przy znanym
zachowaniu preferowane są małe cykle test–minimalna zmiana–uproszczenie.
Przy nieznanym kontrakcie lub projekcie wizualnym dopuszczono ograniczony
prototyp, potem adekwatne zabezpieczenia. Zachowano obowiązkowe testy domeny,
uprawnień, transakcji, idempotencji, migracji i kontraktów.

Wniosek autora: nie ma tu podstaw do zastąpienia wszystkiego jednym nowym
procesem. Ważniejsze są małe dostawy, testy publicznego zachowania i istotnego
ryzyka, właściwa integracja oraz niezależny odbiór. Google opisuje dobór
testów według przypadków i ryzyka, a nie celu w postaci liczby testów:
[web.dev, What to test](https://web.dev/learn/testing/get-started/what-to-test).

Badanie 39 profesjonalistów wiązało jakość i produktywność bardziej
z małymi, równymi krokami niż z samą kolejnością test-first/test-last;
wynik dotyczy tego badania, nie dowodzi równoważności w każdym projekcie:
[Fucci i in.](https://arxiv.org/abs/1611.05994).
Analiza sześciu modeli i interwencja promptowa dla czterech na SWE-bench
Verified nie wykazały istotnej poprawy napraw przez samo zwiększenie
liczby testów pisanych przez agenta. Nie dowodzi to bezużyteczności testów
ani nie rozstrzyga całego TDD: [Chen i in.](https://arxiv.org/abs/2602.07900).

## Priorytety po researchu GitHuba i producentów

| Kierunek | Co wykorzystać | Otwarte zadanie |
|---|---|---|
| Ewaluacje zachowania | rzeczywisty wynik i wywołania narzędzi, kontrole negatywne, powtórzenia; ten pilot to początek | MIG-2026-11-05-01 |
| Obsługa kolejki | adapter start/resume/worker-result, trwały stan, rozliczenie wyników i cleanup po merge | MIG-2026-11-05-24 |
| Bezpieczny launcher | watchdog procesów, schemat wyniku i próba faktycznych uprawnień do stanu/gita | MIG-2026-11-05-02 |
| Mniej rozbieżnych kopii | generator bootstrapu, profile i adaptery zamiast ręcznego rozrostu NEW-PROJECT | MIG-2026-11-05-40 |
| Importowane skille | mały pomiar skanera, trafień i fałszywych alarmów, najpierw analiza deterministyczna | MIG-2026-11-05-03 |
| Architektura agentowa | ponownie ocenić uniwersalne nakazy grafu/LangGraph wobec potrzeb konkretnego projektu | MIG-2026-11-05-39 |

Metoda oceny wyników zamiast samej narracji jest zgodna z materiałami
[OpenAI o evalach skilli](https://developers.openai.com/blog/eval-skills)
i [Anthropic o evalach agentów](https://www.anthropic.com/research/demystifying-evals-for-ai-agents).
To uzasadnienie sposobu pomiaru, nie zewnętrzne potwierdzenie naszych wyników.

Przejrzane oficjalne punkty odniesienia to
[OpenAI Agents SDK](https://github.com/openai/openai-agents-python),
[Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python)
oraz [Google ADK](https://github.com/google/adk-python).
Są kandydatami do adapterów i porównań dla konkretnego projektu; sama
instalacja żadnego z nich nie dowodzi rozwiązania problemu zadań.
Google ADK pokazuje wbudowany adk eval, a Claude Agent SDK interaktywne sesje
oraz hooki, które mogą być punktem podłączenia odpowiednich adapterów.

[Spec Kit](https://github.com/github/spec-kit) jest wzorcem oddzielenia
szablonów, presetów i integracji, bez przyjmowania całego procesu w toolkicie.
[Cisco skill-scanner](https://github.com/cisco-ai-defense/skill-scanner)
ma analizatory statyczne oraz opcjonalne silniki LLM/chmurowe; propozycja
dotyczy początkowo tych deterministycznych, bez wysyłania korpusu.
Nie zainstalowano tych narzędzi ani nie wdrożono nowego frameworka.

## Co wykonano i co pozostaje

Pozostawiono jeden plan etapów przy rekordzie backlogu; rodzic nie jest
gotowy przy brakujących etapach, dowodach lub niesprawdzonym zakresie.
Audyt porównuje cele z dostawami, przy zastoju do 21 dni; nie utożsamia
dużej liczby testów z dryfem, gdy testy były uzgodnionym celem. Upgrade
instrukcji nie zastępuje audytu produktu. Nowy stały punkt wymaga uzasadnienia,
zamiast automatycznego rozrostu checklisty po każdym incydencie.

Integrator odpowiada za czyste, nieużywane worktree po potwierdzonym merge.
Sprzątnięto trzy stare czyste checkouty i trzy martwe rejestracje; pozostał
bieżący checkout. Zachowano gałęzie, w tym dwa niescalone commity starej
migracji. Nie wykonano merge ani push obecnych zmian.

Claude CLI jest dostępny. Fable recenzował plan i dwie wersje kodu checkera
oraz lintera; potwierdzone uwagi naprawiono. To nie jest niezależny audyt
aplikacji, sign-off końcowego korpusu ani walidacja wyników tego pilota.
Historia zgłoszonego trzytygodniowego incydentu nie została udostępniona,
więc nie ustalono jego konkretnej przyczyny.

## Aktualizacja po implementacji

Powyższy pilot zachowuje historyczny zakres i wyniki. Kolejny etap dostarczył
wersjonowany runtime kolejki, watchdog buildera, generator bootstrapu i runner
ewaluacji. Osobny [smoke runnera](measurements/versioned-runner-smoke-2026-11-05.json)
zachowuje pierwotne wyniki oraz jawną korektę błędu parsera oceny; nie jest
benchmarkiem modeli. [Pomiar bezpieczeństwa](measurements/security-pilot-2026-11-05.json)
obejmuje rzeczywiste kontrole i naprawę zależności, ze wskazaniem ograniczeń.

Dołączono też przypięty skill Cloudflare. Aktualny zakres adopcji i audytu
produktu określa [brief przekazania](../templates/adopt-and-audit.md).
Agent projektu ma podłączyć natywne powiadomienia i potwierdzić ich działanie
na szybkim i wolnym workerze; sama obecność plików tego nie dowodzi.
Audyt aplikacji pozostaje odrębnym etapem wykonywanym po adopcji w projekcie.
