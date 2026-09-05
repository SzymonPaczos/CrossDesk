# Konwencja: baza jakości suity testowej (audytowalna)

Stack-agnostic. Wyekstrahowana z planu poprawy testów JawnePaństwo
(2026-09-02/03: trzy rundy recenzji Codex + arbiter Gemini, wykonany w całości
z pomiarami) — każda własność poniżej ma za sobą ZMIERZONĄ awarię, nie teorię.
Uzupełnia `test-evidence.md` (dowód z pojedynczego testu —
weryfikacja negatywna/sabotaż); ta konwencja mówi o własnościach CAŁEJ suity.

## Po co audytowi ta lista

Warstwa „Testy" audytu, która liczy pliki testowe, mierzy pojemniki, nie
ochronę. Suita może mieć setki plików i nie zauważyć, że strona główna
straciła pięć sekcji (zmierzone: `.catch(() => [])` zamieniał awarię zapytania
w „brak danych", smoke przechodził nad martwym producentem przez miesiące).
Audyt sprawdza więc WŁASNOŚCI. **Brak własności nie jest automatycznie P1 —
jest ostrzeżeniem z obowiązkowym wpisem planu do backlogu.** Świadoma decyzja
„nie dotyczy" (z powodem) jest OK; cisza nie jest.

## Checklist własności (audyt: przejdź co tydzień, wynik w audit-log)

| # | Własność | Jak sprawdzić | Zmierzona awaria, przed którą chroni |
|---|---|---|---|
| 1 | **Producent danych klasyfikuje własną awarię** — strona/handler rozróżnia `ready`/`empty`/`error`; żadnego `catch → pusta wartość` | grep `catch.*=>.*\[\]` / `except: return []` w warstwie danych; czy istnieje inwentarz par (trasa, producent) z ratchetem | 5 sekcji strony głównej znikło cicho; 92,86 % „pokrycia" bez ani jednego właściwego dokumentu |
| 2 | **Obie ścieżki pary** — szczęśliwa na realnych danych + wymuszona awaria (mock rzucający) per producent | inwentarz z licznikiem `settled`, kotwice liczbowe idą TYLKO w dół | producent połykający błąd u siebie oddaje pustkę i „uczciwie" melduje empty |
| 3 | **Test nie może po cichu się nie wykonać** — każdy skipif/warunek kolekcji ma nazwanego obserwatora | uruchom suitę bez środowiska (np. bez DB): ile skipów, jaki exit code? | `pytest -m db` bez `DATABASE_URL`: 205/226 skip, exit 0, samo `s` |
| 4 | **Liczby z runnera, jednostka nazwana** — „testów" = wynik runnera; plików wolno, ale nazwane; nigdy proporcja obu | porównaj liczby w dokumentach stanu z wyjściem runnera | „1814 / 42 / 158" mieszało trzy jednostki; e2e 185 wg runnera przy 159 wg grepa |
| 5 | **Progi z pomiaru albo z rachunku kosztu** — coverage/mutation/flake bez „do kalibracji później" | każda liczba progu ma obok komendę pomiaru | „80 % mutation score" wszedł do planu przed jakimkolwiek pomiarem i przeżył dwie recenzje |
| 6 | **Każda bramka ma meta-test z ŻYWEGO pliku** — warunek podnoszony ze skryptu/hooka, nie przepisany | lista bramek vs lista meta-testów | `SKIP_E2E` wyłączał cudzą warstwę; gate „ istnieje jakikolwiek test" przepuszczał wszystko |
| 7 | **Ratchet z listą wyjątków przeglądaną cyklicznie** — wyjątek, który przeżył przyczynę, wytłumaczy następny regres | audyt czyta listy wyjątków (TLS-bypass, empty-columns, unlimited-routes…) | 2 nieaktualne wpisy przy 46 w `ALLOWED_EMPTY` |
| 8 | **Writery odseparowane od wspólnej bazy** — test read-only wymuszany SERWEREM (`default_transaction_read_only`), writer na jednorazowym klonie z migracji; partycję wyznacza bieg-wyrocznia pod wymuszonym read-only, nie grep | czy test piszący bez markera w ogóle może przejść? | 3 sesje zgłosiły nieistniejące regresje z kolizji o bazę; suita 212 s → 33 s po splicie |
| 9 | **Wariant zapytania bez wykonawcy ma test integracyjny** — parametr/gałąź SQL, której żadna trasa e2e nie wykonuje, dostaje itest na realnej bazie; brak bazy = BLOKADA, nie skip | inwentarz wariantów per moduł | warianty `senat`/`sort`/`recipientIds` nigdy nie wykonane przez żadną trasę |
| 10 | **Flake zmierzony przed naprawą** — `--retries=0` + powtórzenia; czerwień przy równoległym dostępie do zasobu NIEWAŻNA | konfiguracja retries w CI vs lokalna; log pomiaru | retry=1 ukrywał 6 speców padających DETERMINISTYCZNIE (zgniły, nie flake) |
| 11 | **Waity deterministyczne, nie sieciowe** — kotwica DOM/stan zamiast `networkidle`/sleep | grep `networkidle|waitForTimeout|sleep` w e2e | prefetch trickle głodził okno ciszy; wiszące zdjęcia zewnętrzne = timeout bez winy DOM |
| 12 | **Parser testowy asertuje własny wynik** — enumeracja plików/route'ów ma kotwicę `>= N` | każdy test-enumerator ma licznik | parser wziął `[` z adnotacji typu → 0 ścieżek i zielone `it.each` na pustej tabeli |
| 13 | **PBT tam, gdzie dwie derywacje jednego bytu** — parser↔serializer, dwa czytniki jednego formatu | czy krytyczne pary mają własności? | pierwsza własność znalazła rozjazd czytników ELI↔ISAP na `…/ogl//` |
| 14 | **Mutation testing jako pilotaż bez progu** — narzędzie skonfigurowane, wynik zapisany, próg dopiero po pomiarach | czy istnieje config + zapis biegu | pilotaże: 21/21 na pokrytym (mutmut), 23/23 (Stryker) — liczby, nie obietnice |

## Wynik w audycie

Jedna linia na własność wystarczy (`test-baseline: 1✓ 2✓ 3✗(plan w backlogu)
4✓ …`). Własność ✗ bez wpisu planu w backlogu = znalezisko audytu. Projekt,
który świadomie odpuszcza własność (np. brak DB → #8 nie dotyczy), zapisuje
to RAZ z powodem — audyt przestaje pytać, dopóki stan się nie zmieni.

## Skąd wzory

Implementacje referencyjne żyją w JawnePaństwo (`producer-manifest.ts`,
`backend/conftest.py` lane split, `test_prepush_heavy_block_scope.py`,
`test_reject_trend.py`, `plan-poprawy-testow.md`) — kopiować WZORZEC, nie pliki;
szczegóły są projektowe, własności są przenośne.
