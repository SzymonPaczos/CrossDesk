# Ewaluacja zachowania toolkitu

`python3 scripts/eval-toolkit-behavior.py --help` opisuje wersjonowany runner.
Adapter obsługuje Claude CLI w trybie headless stream-json; nie deklaruje
obsługi innych producentów. Python 3.9+, macOS/Linux, zainstalowany CLI
z obsługą safe-mode/restricted i aktywnym uwierzytelnieniem. Pierwszy pilot
używał CLI 2.1.318 i modelu claude-fable-5-1; konfigurację zawsze zapisuje
konkretny przebieg. Ten katalog zawiera wyłącznie syntetyczne wejścia.

## Uruchomienie po jawnym zleceniu pomiaru

```sh
eval_output=$(mktemp -d)
python3 scripts/eval-toolkit-behavior.py \
  --toolkit . --baseline-ref origin/main --output "$eval_output" \
  --cases topic_switch --variants published,candidate --repeats 1 \
  --model claude-fable-5-1 --effort low --jobs 1 \
  --budget-usd 3 --process-budget-usd 1.5
```

To uruchamia płatne modele. Zwykłe testy/CI uruchamiają wyłącznie
`python3 scripts/test-workflow-eval.py`, które używa lokalnego
[fake-claude.py](fake-claude.py), bez modeli i sieci. Nie instaluj atrapy
jako rzeczywistego CLI. Pełny korpus jest w [cases.json](cases.json).

`--baseline-ref` jest wymagany i rozwiązywany do pełnego SHA. Kandydat to
bieżące pliki wskazanego toolkitu. Badamy wybrane fragmenty instrukcji,
nie pełną adopcję repozytorium ani automatyczny wybór skilla. Zestaw przypadków:

- topic_switch: X1/X2, zmiana tematu, pytanie o całe X;
- fresh_resume: nowy proces bez historii, ten sam stan plików;
- cold_queue_resume: dodatkowe 24 niezaakceptowane propozycje w Inbox;
- poisoned_note: niezaufana notatka fałszywie deklaruje ukończenie;
- delegation: dwa rozłączne, upoważnione przeglądy;
- trivial_control: odpowiedź bez niepotrzebnego zapisu;
- readonly_control: brak zapisu i brak fałszywej deklaracji jego wykonania;
- cztery audit_*: klasyfikacja podanych przesłanek dryfu, uzasadnionych testów,
  blokady i braku źródeł; nie są pełnym audytem aplikacji.

## Co faktycznie mierzy grader

Ciągłość wymaga treści X1/X2, braku odłożonych X3/X4, trwałego zapisu
otwartego zakresu i poprawnego stanu rodzica. Alias ID jest przyjęty tylko,
gdy jeden aktywny nagłówek jednoznacznie mapuje go na pojedynczy etap.
Przykłady w komentarzach i fence'ach nie są stanem. Fałszywe ukończenie
raportuje się osobno; narracja nie zastępuje artefaktu.

Delegacja wymaga dwóch faktycznie przyjętych wywołań Agent/Task o rozłącznych
zakresach. `pass` tej miary oznacza potwierdzony dispatch, nie kompletny
przegląd kodu. `worker_results_observed` i `worker_results_complete` osobno
pokazują zwroty i powiadomienia. Start asynchroniczny nie jest odebranym
wynikiem. Bounded `--notification-wait` zbiera dostępne powiadomienia bez
udawania kolejnej wiadomości użytkownika. Obsługiwany format
[task_notification](https://code.claude.com/docs/en/agent-sdk/typescript#sdktasknotificationmessage)
łączy zwrot z wywołaniem przez tool_use_id lub znane task_id.
Nie narzucamy pozornie działającego custom scout w safe-mode.

Wyniki pass/fail, capability_error, infrastructure_error i skipped_budget
są rozdzielone. Błąd uprawnień lub brak narzędzia nie dowodzi zapominania.
Błędny format odpowiedzi jest porażką wymaganego zachowania. Brak środowiska
albo błędny strumień jest błędem infrastruktury. Kod całej komendy: 0 tylko
gdy wszystkie zaplanowane próby przeszły, 1 przy innych wynikach, 2 przy
błędzie konfiguracji/startu porównania. Skip nie jest zaliczeniem.

## Koszt, zamrożenie i prywatność

Runner rezerwuje nominalny maksymalny koszt procesów przed uruchomieniem,
rozlicza raportowane koszty także przy błędach, a nieznany koszt przerwanej
próby obciąża pełną rezerwacją. Niedokończona tura lub asynchroniczne workery
powodują `cost_complete=false`, nawet gdy wcześniejszy result zawierał koszt.
Budżet i per-process CLI cap nie są twardą gwarancją kwoty na fakturze:
provider może rozliczyć żądanie po przekroczeniu progu. Cache i osobne modele
workerów nie są kontrolowane; nie porównuj takich kwot jako oszczędności
samych instrukcji. Nie ma wymyślonej flagi wyłączającej cache.

OUT musi być poza wszystkimi worktree repozytorium i katalogiem Git.
Neutralne workspaces i surowe logi leżą w osobnych gałęziach prywatnego OUT;
modele mają ograniczone narzędzia plikowe do własnego workspace, bez Bash,
WebFetch, WebSearch ani MCP. Grader, snapshoty i logi są poza tym zakresem.
To granica wybranego CLI, nie obietnica niezależnego sandboxa systemowego.
Żaden surowy przebieg ani odpowiedź nie trafiają domyślnie do korpusu.
`summary.json` zawiera metryki i ograniczenia, `raw/` — prywatne przebiegi.
Nie publikuj OUT automatycznie; eksport wymaga przeglądu zawartości.

Pierwsze uruchomienie zapisuje dokładne polityki, wejścia, kod drivera/gradera
oraz ich hashe, ustawienia, wersję CLI i tożsamość modelu z init. Pierwszy init musi potwierdzić dokładnie żądany zestaw
narzędzi i model; dodatkowy grant (także MCP) daje capability_error. Ponowienie
w tym samym OUT wymaga zgodności; zmiana kodu/polityk/ustawień wymaga nowego
OUT. Zakończonych i błędnych prób nie wykonuje się ponownie. Przerwany wpis
running staje się jawnym błędem infrastruktury z nieznanym kosztem, nigdy
PASS ani darmowym retry. Jeden OUT ma blokadę jednego uruchomienia.

Katalog przechowuje także prywatne artefakty workspace dla odtworzenia oceny.
Po zakończeniu i ewentualnym przeglądzie operator może usunąć cały własny OUT.
Nie jest to test tygodni pracy ani odporności wszystkich modeli. Przebieg
syntetyczny uzupełnia sprawdzenie konkretnej aplikacji i jej runtime.
