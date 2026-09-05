# Konwencja: ekonomia uruchamiania testów przez agenta

Stack-agnostic; dotyczy KAŻDEGO agenta uruchamiającego testy, buildy i bramki.
Uzupełnia [`test-quality-baseline.md`](test-quality-baseline.md) (własności
suity) i [`test-evidence.md`](test-evidence.md) (dowód z pojedynczego testu) —
ta konwencja mówi o tym, ile KOSZTUJE bieganie testów w kontekście modelu
i jak ten koszt ściąć bez utraty dowodu.

Źródło: sesja JawnePaństwo 2026-09-04 (decyzja właściciela + pomiary).
Zmierzone sterowniki kosztu, w kolejności od największego:

1. **Snapshot DOM / screenshot w kontekście drogiego modelu** — jeden krok
   interaktywnej przeglądarki (MCP) zwraca cały snapshot strony; kilka kroków
   debugowania kosztuje więcej niż cała reszta iteracji.
2. **Czytanie logów zielonych biegów** — informacja zerowa, koszt niezerowy.
3. **Powtórki biegów** — odczuwane „testy są wolne" pochodziło z zimnych
   cache'ów, awarii zewnętrznego registry i powtarzanych pushów, nie z testów
   (pomiar warstwa po warstwie: pełny zestaw bramek ≈ 6 min, w tym pełne e2e
   194 testy = 154 s).

## Zasady

1. **Bieg testu/builda = proces w tle + plik wyjścia.** W trakcie biegu agent
   nie wykonuje akcji testowych i nie odpytuje statusu — notyfikacja
   zakończenia niesie kod wyjścia.
2. **Zielony bieg (exit 0): logu się NIE czyta.** Warunek uczciwości: kod
   wyjścia musi być wiarygodny — potok z `set -o pipefail`, bo `… | tail`
   zamienia czerwony bieg w exit 0 (zmierzone tego samego dnia, w którym
   spisano tę regułę).
3. **Czerwony bieg: wycinek, nie plik.** `grep -m5 -B2 -A8 'FAIL|Error'`
   + ostatnie linie. Pełny log czyta się dopiero, gdy wycinek nie wystarcza.
4. **Oglądanie nie należy do drogiego modelu.** Hierarchia od najtańszego:
   - **zero modelu** — geometrię/stan DOM mierzy jednorazowy skrypt
     (node+playwright itp.), który drukuje LICZBY-wnioski; żadnych
     screenshotów „do analizy";
   - **tani model** — screenshot, ocena wizualna, przekopanie długiego loga
     idzie do subagenta na tanim modelu (np. Haiku); wraca kilkuzdaniowy
     wniosek, koszt obrazów zostaje w tanim kontekście;
   - **model główny** decyduje na wnioskach, nie na surowych artefaktach.
   Model lokalny (LM Studio itp.) to świadoma inwestycja następnego kroku —
   wymaga modelu wizyjnego i kalibracji zaufania, nie wchodzi „przy okazji".
5. **Bramki jedną paczką na koniec iteracji**, nie warstwami w środku pracy;
   biegi cząstkowe tylko dla czerwono-zielonej pary dowodowej naprawianego
   testu.
6. **Zanim przyspieszysz — zmierz warstwa po warstwie** (`date +%s` wokół
   wywołań; liczba bez komendy nie istnieje). Potem, w kolejności zysku:
   najpierw wyeliminuj powtórki (batching pushy, ciepłe cache), potem
   zrównoleglaj — i tylko to, co nie dzieli zasobu. **Izoluj, zanim
   zrównoleglisz**: lane split writerów dał 212→31 s; równoległość bez
   izolacji produkowała nieistniejące regresje, z których każda kosztowała
   osobne śledztwo.

## Egzekwowanie

Report-only — to praktyka agenta, nie bramka repo. Przegląd (audyt albo
właściciel) wyrywkowo sprawdza sesje: czytanie logu zielonego biegu, snapshot
DOM w kontekście modelu głównego i optymalizacja bez pomiaru to naruszenia.
Projekt może zapisać kontrakt w pamięci trwałej agenta, żeby przeżył sesję.

## Sygnały maszynowe

- potok testowy bez `set -o pipefail` w hookach/skryptach wołających runnery,
- wywołania interaktywnej przeglądarki (narzędzia `browser_*`) w transkrypcie
  modelu głównego tam, gdzie wystarczał skrypt albo tani subagent.
