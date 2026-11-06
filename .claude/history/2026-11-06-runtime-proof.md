# CrossDesk — częściowy dowód A2, 2026-11-06

Źródło: `d761d6805be6e70a9a23b0276fad16b1b6e6c969`. **A2 pozostaje OPEN.** Nie wykonano zmian w projekcie ani aktywacji domyślnego roju.

SLOW, FAST i REFILL: trzy rzeczywiste sesje Fable, trzy zaakceptowane raporty. Wszystkie sesje korzystały z oryginalnego adaptera read-only, dokładnego `claude-fable-5-1` oraz wyłącznie Read/Glob/Grep. Session ID odczytano z rzeczywistych eventów init; w publicznym dowodzie pozostają hashe uchwytów. `native_task_id=null`: to uchwyty sesji CLI, nie natywne zadania background. Nie uruchomiono supervisora Claude ani daemona.

ROOT rzeczywiście zapisał wynik FAST, gdy SLOW nie miał jeszcze wyniku końcowego. Następny rzeczywisty worker REFILL dostał wolny slot i rozpoczął pracę przed końcem SLOW. Trzy eventy odebrano i potwierdzono do kursora 3. ACK oznacza odbiór, nie zakończenie zablokowanego zadania.

Opóźnienie event → zapis ROOT wyniosło **58.425 s**; backend watch odpytywał co 1 s. Nie jest to gwarancja powiadomienia czatu w 1 s. Gdy sesja główna jest zajęta, trwałe result-ready pozostaje niepotwierdzone do rzeczywistego odbioru.

Restart: completed-state resume only; live crash window missed and no signal sent. Każdy node zachował jedną próbę; wznowienie nie utworzyło nowych sesji. Oryginalny BootControl SLOW pozostaje BLOCKED — bez ponowienia, zmiany parsera lub udawanej zieleni.

## Brakujący dowód Git lifecycle

Próby obu projektów w ścisłym Dockerze zakończyły się **BLOCKED podczas inicjalizacji tożsamości procesu, przed komendą zadania**, ponieważ zatwierdzony obraz nie zawiera programu `ps`, wymaganego przez niezmieniony runtime. Nie instalowano narzędzi, nie pobrano obrazu, nie maskowano `ps` i nie poluzowano limitów. Kontenery usunięto przed promocją dowodów. Merge, timeout i cleanup nadal wymagają rzeczywistego wykonania w odpowiednim środowisku.

Fixture jest deterministycznym testem operacyjnym, nie workerem dostawcy. CrossDesk zachował źródłowe ancestry; jedyny za duży dokumentacyjny GIF pominięto osobnym commitem wyłącznie w jednorazowej kopii. BootControl zachował faktycznie nieaktywne hooki bazowe; brak cargo nie został przedstawiony jako zaliczenie fmt/clippy.

## Kandydat integracji

Przygotowano konfigurowalny, ręczny `reference/a2-on-demand/toolkit-on-demand.py`, profil `reference/a2-on-demand/a2-readonly.json` i konwencję `reference/a2-on-demand/README.md`. Parametry obejmują zaufany toolkit root, katalog projektu/stanu, dokładny SHA/model, zgodę i task-ref. Sprawdzono składnię, przygotowanie planów obu projektów i sześć strażników metadanych. Kandydat jest zachowany jako nieaktywny materiał do przeglądu w reference/a2-on-demand; finalny refaktor nie przeszedł testu end-to-end.

Żadne autostart, hook, harmonogram, globalny skill ani stały proces nie zostały dodane. CrossDesk zachowuje inactive-by-default i wyjątek dla jawnego zadania ADP. Logi, prompty i transcripty zostają prywatne.

Szczegóły i hashe: [JSON](2026-11-06-runtime-proof.json).
