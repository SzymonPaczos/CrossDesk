# Konwencja: układ plików stanu projektu (wg cyklu życia)

Stack-agnostic. Dotyczy każdego projektu prowadzonego z Claude Code. Powstała
2026-05-22 z sesji nad projektem webowym (konsolidacja rozproszonego śledzenia
postępu).

## Problem

Pliki śledzące postęp (backlog, TODO, status, "co zrobione", raporty sesji)
mnożą się i mieszają. Typowe objawy:

- "Co jest do zrobienia" rozsiane po 5-8 plikach (ROADMAP, status, osobne TODO,
  backlog z datą w nazwie, log audytu, sekcje "otwarte ryzyka").
- Pliki z datą w nazwie (`backlog-2026-05-19.md`) — nazwa rotuje, plik się
  starzeje, następna sesja tworzy kolejny.
- Stan przejściowy wrzucony do `rules/` (auto-wstrzykiwane do kontekstu każdej
  sesji) — agent ładuje dziesiątki kB nieaktualnego backlogu jako "reguły".
- Zrobione pozycje leżą obok otwartych — nie wiadomo co jeszcze aktualne.

## Zasada: dziel wg cyklu życia, nie wg tematu

Każdy plik stanu odpowiada na jedno pytanie: **kiedy linia stąd znika?**

| Cykl życia | Kiedy linia znika | Plik |
|------------|-------------------|------|
| Trwałe | prawie nigdy | `rules/*.md` (ze skrótem decyzji), `decisions-register.md`, README/VISION |
| Mapa | przy zmianie architektury | `architecture.md` |
| Otwarta praca | gdy zrobione | **`backlog.md` — JEDEN plik** |
| Specyfikacja otwartej pracy | gdy zadanie zamknięte | `task-briefs/<task-id>.md` — zawsze link z backlogu |
| Stan bieżący | gdy stan się zmienia | `status.md`, `ignorefiles.md` |
| Koordynacja | koniec sesji | shared runtime ledger, `handoff.md` (jedna sekcja, nadpisywana) |
| Historia | nigdy (append), poza kontekstem | `audit-log.md`, `history/` |

## Reguły

1. **Jeden backlog.** Cała otwarta praca w `.claude/backlog.md`. Sekcje:
   `Do wykonania` (kolejność jest kolejnością realizacji, ustaloną przez
   właściciela i zależności), `Inbox`, `Poza kolejką` (świadomie odłożone,
   z datą przeglądu), "Czeka na decyzję", "Zablokowane". Pozycja znika, gdy
   jest zrobiona; dowodem jest commit, nie wpis. Dawne trzystopniowe etykiety
   nie sterują backlogiem: mieszały wpływ znaleziska z kolejnością pracy i
   zostawiały trzy wiecznie rosnące kosze.

   Wpływ mówi, jak bardzo boli; kolejka mówi, co robimy najpierw. To dwie
   różne rzeczy. Dwie drobne pozycje po dziesięć minut bywają właściwszym
   początkiem niż jedna duża na trzy dni. Backlog porządkowany wyłącznie
   dotkliwością nigdy się nie kurczy.

   Kształt pojedynczej pozycji (pola obowiązkowe, identyfikator, warunek
   domknięcia) opisuje [`backlog-contract.md`](backlog-contract.md). Ta reguła
   mówi tylko, gdzie backlog leży i z czego się składa.
2. **`rules/` = tylko trwałe instrukcje.** Reguły, decyzje, wzorce. Nigdy
   backlog, status ani historia — `rules/` bywa auto-wstrzykiwane do kontekstu
   każdej sesji; stan przejściowy marnuje budżet kontekstu i myli się z regułą.
   Pliki `rules/` bez `paths:` razem z `CLAUDE.md` i `AGENTS.md` mieszczą się
   w budżecie z [`context-budget.md`](context-budget.md) §2.
3. **Stan przejściowy w `.claude/`, nie w `rules/`.** `backlog.md`, `status.md`
   czytane na żądanie (CLAUDE.md kieruje), nie ładowane wszędzie. Backlog
   czyta się przez spis treści i `grep -n '^### <ID>'`, handoff to jedna
   sekcja — [`context-budget.md`](context-budget.md) §1.
4. **Zero plików z datą w nazwie dla żywych plików.** Data w nazwie =
   antywzorzec. Albo plik jest żywy (bez daty — `backlog.md`), albo to zamknięty
   raport (→ `history/YYYY-MM-DD-temat.md` — data tam jest OK, plik już martwy).
5. **Historia poza kontekstem.** Zrealizowane inicjatywy →
   `history/completed-work.md` (append-only). Raporty sesji →
   `history/YYYY-MM-DD-temat.md`. Nie ładuj `history/` bez wyraźnej potrzeby.
6. **Done ≠ open.** Gdy pozycja zrobiona — usuń z `backlog.md`, dopisz do
   `history/`. Nie zostawiaj "✅ zrobione" obok otwartych pozycji. „Zrobiona"
   znaczy: commit z `Task-Ref:`, zielona bramka zamykająca i wpis w historii —
   patrz [`backlog-contract.md`](backlog-contract.md) §6. Odhaczone pole nie
   jest dowodem.
7. **Strategia ≠ backlog — ale osobny plik strategii bywa czwartą kopią.**
   Rozdzielenie kierunku od pracy jest słuszne; **osobny plik** na kierunek już
   niekoniecznie. Zweryfikowane 2026-09-04 na projekcie prowadzonym tą
   konwencją od maja: `ROADMAP.md` okazał się czwartą kopią treści żyjących
   w rejestrze decyzji (wizja), historii (pozycje ✅) i backlogu (odłożone
   funkcje), a kopia bez konsumenta się starzeje — **trzy fałszywe twierdzenia
   naraz** (data startu przesunięta pięć tygodni wcześniej, zniesiony freeze
   opisany jako obowiązujący, zbudowana funkcja opisana jako odłożona).
   Pięć pozycji istniejących wyłącznie tam trzeba było przenieść, żeby
   skasowanie pliku ich nie zgubiło.

   Wniosek nie brzmi „nigdy nie miej ROADMAP-u", tylko: **kierunek to decyzja,
   nie dokument**. Jeśli wizja da się zapisać jako wpisy w rejestrze decyzji
   („desktop-only", „AI wyłącznie po stronie backendu", „strona główna = stream
   zdarzeń"), to tam należy — bo rejestr decyzji ma regułę „decyzji się nie
   usuwa, zmienia się status", więc nie kłamie po zmianie kursu. Osobny plik
   strategii uzasadnia dopiero **czytelnik spoza zespołu** (inwestor, sponsor
   grantu), a wtedy jest materiałem komunikacyjnym, nie źródłem prawdy.
   Granularne TODO nie należy do żadnego z tych miejsc.
8. **Pozycja niesie ROZUMOWANIE, nie sam wniosek.** Wpis „89 % numerów bez
   przekierowania" jest wnioskiem: nie mówi, co z tego wynika ani jakie są
   wyjścia, więc przy każdym powrocie trzeba odtwarzać kontekst od zera.
   Zmierzone: właściciel projektu zadał **te same pytania trzy razy w jednej
   sesji**. Kształt, który to zamyka — pięć pól:
   **Kontekst** (po co to istnieje) · **Problem** (co jest nie tak, z pomiarem) ·
   **Opcje** (A/B/C z konsekwencją każdej) · **Rekomendacja** (jedno zdanie;
   gdy brak podstaw — dosłownie „brak w źródle — do ustalenia", nigdy zmyślona) ·
   **Stan** (otwarte / czeka na decyzję / w toku).
   Dyscyplina objętości jest częścią reguły: nowa lub zmieniana pozycja ma
   do 1 500 B, notka stanu do 4 linii, narracja wykonania idzie do `history/`,
   dłuższe analizy do osobnego briefu ([`context-budget.md`](context-budget.md)
   §6). Bez niej plik puchnie i znowu staje się nieczytelny.

9. **Domknięcie pozycji egzekwuj maszynowo.** Reguła prozą „zrobione → historia"
   przegrywa: zmierzone na projekcie stosującym ją od maja — commit dopisał wpis
   do historii i **nie tknął backlogu**, a ręczny przegląd usunął potem
   **91** nieaktualnych pozycji. Mechanizm: każda pozycja ma **stabilne ID**,
   commit kończący ją nosi trailer `Closes: <ID>`, a bramka pre-push sprawdza,
   że ID **zniknęło** z backlogu i **pojawiło się** w historii. Bramka jest
   opt-in z konstrukcji (commit bez trailera jej nie obchodzi) — niemożliwa
   staje się jedna konkretna nieuczciwość: zadeklarować zamknięcie i zostawić
   pozycję otwartą. ID **nie przenumerowuj** przy przenoszeniu pozycji.

10. **Spis treści to nie ozdoba, to warunek używalności.** Powyżej ~50 pozycji
   plik bez nawigacji przestaje być czytany w całości. Kotwice zapisuj **jawnie**
   (`<a id="...">`), nie licz na slug z nagłówka — slugi różnią się między
   rendererami, gdy w tytule są emoji i interpunkcja, a spis, którego linki po
   cichu nie trafiają, jest gorszy niż jego brak. Oznacz w spisie pozycje
   czekające na decyzję właściciela: to jedyna lista, która mówi mu, co blokuje
   jego, a nie zespół. Spis jest też drogą odczytu: sesja nie czyta backlogu
   w całości, tylko spis i wskazaną pozycję.

11. **Audyt zasila backlog.** Cotygodniowy audyt może zapisać wpływ znaleziska
   jako `critical/high/medium/low`, ale zadania trafiają do jednej uporządkowanej
   kolejki `Do wykonania`. `audit-log.md` trzyma migawkę + trend, nie osobną
   listę zadań. Wpływ nie jest drugim mechanizmem planowania.
12. **Linki przenośne.** Trwałe dokumenty używają ścieżek względnych. Absolutne
   `file:///Users/...` i lokalne ścieżki rotują po zmianie nazwy/katalogu i nie
   działają na drugiej maszynie.
13. **Najpierw zapisz, potem kontynuuj.** Agent główny zapisuje każde przyjęte
    nietrywialne zadanie do `backlog.md` przed wykonaniem, także w bieżącym
    scope. Deduplikuje odkrycia; nieustalony zakres trafia do `Inbox`, sam zapis
    nie upoważnia do implementacji. Zwykła odpowiedź lub drobna oczywista
    poprawka nie wymaga osobnego rekordu.
    Zadanie wieloetapowe ma jeden plan etapów odbioru: w pozycji albo w briefie
    wskazanym przez `BRIEF`, według `backlog-contract.md` §6a. Przy zmianie
    tematu agent utrwala pozostałe etapy i następny krok. Nowa wiadomość sama
    nie anuluje zakresu; ukończenie X2 nie zamyka X przy otwartych X3–X4.
    Decyzja zmienia wymagania, backlog stan pracy; handoff i ledger odsyłają
    po ID, bez drugiej ręcznie utrzymywanej listy etapów.
14. **Task brief nie jest drugim backlogiem.** Dłuższy kontekst może żyć w
    `.claude/task-briefs/<task-id>.md`, ale plik musi mieć dokładnie jeden link
    z backlogu. Bez wpisu w backlogu brief jest osierocony i niewidoczny.
15. **Po zamknięciu brief idzie do historii.** Usuń link z backlogu, a brief
    przenieś do `.claude/history/task-briefs/` razem z referencją do commit/PR.
16. **Live claims nie żyją na feature branchu.** Dla równoległych worktree
    wspólny ledger (lock) znajduje się w git common dir
    (`agent-coordination/`); dla różnych klonów użyj draft PR/issue. Tracked
    `active-work.md` trzyma mirror claimów commitowany
    `chore(coord): claim/release <branch>` — review trail i ślad po crashu,
    świadomie NIE blokada współbieżności.

## Docelowy układ `.claude/`

```
.claude/
├── backlog.md          ← JEDYNA otwarta praca (kolejka, Inbox, decyzje, blockery)
├── status.md           ← known issues: co dziś nie działa
├── active-work.md      ← mirror claimów (review trail); lock poza branchami
├── handoff.md          ← stan dla następnej sesji: jedna sekcja, do 8 KB (gitignored)
├── task-briefs/        ← specyfikacje otwartych zadań; indeks = backlog.md
├── architecture.md     ← mapa projektu
├── ignorefiles.md      ← dead code manifest
├── audit-log.md        ← historia audytów (migawka + trend)
├── decisions-register.md ← pełne wpisy decyzji (nieładowane, odczyt grepem)
├── history/
│   ├── completed-work.md       ← zrealizowane inicjatywy (append-only)
│   └── YYYY-MM-DD-*.md         ← zamknięte raporty sesji
└── rules/              ← TYLKO trwałe instrukcje
    ├── general.md, frontend.md, backend.md, security.md
    └── decisions.md    ← skrót zakazów z rejestru (ładowany zawsze)
```

## Test poprawności

Dla każdego pliku stanu zadaj pytanie: **"kiedy linia stąd znika?"** Jeśli nie
ma jednej jasnej odpowiedzi — plik miesza cykle życia i trzeba go rozbić.
