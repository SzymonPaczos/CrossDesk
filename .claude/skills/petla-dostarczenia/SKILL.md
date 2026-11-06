---
name: petla-dostarczenia
description: Użyj gdy właściciel zleca nową funkcję, zmianę zachowania albo poprawkę, którą trzeba doprowadzić od zlecenia do gałęzi gotowej do integracji — w pracy solo albo jako jeden Builder. Nie dla literówek i jednoplikowych oczywistych poprawek, nie dla audytu (weekly-audit) ani kolejki naprawy z raportu (audyt-naprawczy, plan-naprawy). EN — use when the owner asks for a feature or a behaviour change that has to travel from request to an integrable branch, solo or as a single Builder; not for trivial fixes, audits or repair queues.
compatibility: Wymaga bash i git. Krok 1 i krok 6 czekają na odpowiedź właściciela (klasyfikacja architektoniczna, decyzja integracyjna), więc pełny przebieg nie nadaje się do trybu bezobsługowego; kroki 2–5 mogą iść bez pytań w zatwierdzonym zakresie. Zaprojektowane dla agentów czytających SKILL.md.
metadata:
  author: claude-toolkit
  version: "2026.11.07"
---

# Pętla dostarczenia

Konwencje toolkitu określają kryteria odbioru; żaden skill nie prowadził
dotąd zadania od zlecenia do gałęzi gotowej do integracji. Ten skill to
robi. Nie powtarza reguł — wskazuje, którą konwencję czytać na którym
kroku. Sposób wykonania w obrębie kroku dobiera agent (D-016); skill
określa, co ma powstać i kiedy potrzebna jest decyzja właściciela.

## Rozdział ról

| Kto | Za co odpowiada |
|---|---|
| skill | klasyfikacja zakresu, plan, izolacja, wykonanie, przegląd, propozycja domknięcia |
| właściciel | decyzja przed kodem w klasie architektonicznej, wybór sposobu integracji |

Skill nie merguje, nie pushuje i nie kasuje pracy. Każda z tych czynności
wymaga jawnego wyboru właściciela w kroku 6.

## Krok 1 — Klasyfikacja zakresu

Zanim padnie pierwsze pytanie o szczegóły, nazwij klasę zadania jednym
zdaniem, żeby właściciel mógł ją poprawić.

| Klasa | Kryterium | Co powstaje przed kodem |
|---|---|---|
| sonda | pytanie o wykonalność; wynikiem jest odpowiedź, nie kod do utrzymania | dwa zdania: co sprawdzisz i ile to kosztuje |
| ograniczona | zmiana w przepływie, który już istnieje w repo i da się go przeczytać | krótki opis w rozmowie: podejście, pliki, test |
| architektoniczna | nowy podsystem, zmiana interfejsu używanego przez innych, nowy projekt | decyzja właściciela zapisana przed kodem, plan z szablonu |

Kod z sondy jest oznaczony jako jednorazowy; zachowanie go to nowe zadanie
z własną klasyfikacją. Znajomość rodzaju aplikacji nie czyni zadania
ograniczonym — liczy się, czy zmieniany przepływ już istnieje w tym repo.

Zapadka działa w jedną stronę. Wątpliwość między dwiema klasami rozstrzyga
cięższa. Złożoność odkryta w trakcie podnosi klasę: zatrzymujesz się,
mówisz o tym i wracasz do tego kroku. Klasa nie spada w trakcie zadania.

Zmiana zachowania, która nie jest defektem, ma decyzję właściciela przed
kodem (`conventions/issue-reporting.md` §1). Wcześniejsze upoważnienie
obowiązuje w swoim zakresie i nie wymaga ponawiania
(`conventions/agent-communication.md` §4); klasa ograniczona
w zatwierdzonym zakresie idzie dalej bez czekania.

## Krok 2 — Plan

Klasa ograniczona: opis w rozmowie z kroku 1 jest planem; nie zakładaj
pliku.

Klasa architektoniczna: plan z `templates/plan-funkcji.md`. Kryteria planu:

- każde zadanie ma pliki, interfejsy (co konsumuje z wcześniejszych zadań,
  co produkuje dla późniejszych — nazwy i typy), kryteria odbioru i bramki;
- ograniczenia globalne z decyzji są przepisane dosłownie, nie streszczone;
- brak wypełniaczy: „do ustalenia", „dodaj walidację", „testy jak wyżej"
  bez konkretnego wejścia i wyniku, „jak w zadaniu N", odwołanie do funkcji, której żadne
  zadanie nie definiuje;
- plan określa zachowania i kontrakty, bez wymagania gotowego kodu testów;
  wykonanie idzie małymi fragmentami zgodnie ze strategią testów projektu;
- przegląd planu przed wykonaniem: każda sekcja decyzji ma zadanie, nazwy
  z późniejszych zadań zgadzają się z wcześniejszymi.

Wielu Builderów o rozłącznych zakresach dostaje `templates/work-graph.md`;
plan funkcji jest wariantem jednego noda i ma te same pola.

Decyzja, która zmieniła się w trakcie, wraca do właściciela i do rejestru
decyzji (`conventions/document-claim-drift.md`, „Decyzja, która przestała
obowiązywać"). Zawężenie zakresu opisane w commicie nie jest decyzją
(`conventions/multi-agent-delivery.md` §1).

## Krok 3 — Izolacja i baseline

Praca idzie na własnej gałęzi. Równoległość wymaga osobnego worktree;
lista kontrolna przed jego utworzeniem jest w
`conventions/multi-agent-delivery.md` §2.2 (wykrycie istniejącej izolacji,
narzędzie natywne przed `git worktree add`, katalog ignorowany).

Przed pierwszą zmianą uruchom wymagane kontrole projektu. Czerwony baseline
jest raportem dla właściciela, nie cichą naprawą przy okazji: bez tego
każda późniejsza porażka jest dwuznaczna.
Zapisany wynik kontroli dokładnego bazowego SHA może być źródłem baseline'u
w zakresie, który rzeczywiście obejmuje. Różne środowisko lub nowe ryzyko
wymaga odpowiedniej kontroli lokalnej. Nie powtarzaj identycznej pełnej
suity ręcznie tuż przed hookiem, który wykona ją na tym samym stanie.

## Krok 4 — Wykonanie

Agent główny utrwala przyjęte zadanie w backlogu przed wykonaniem, także gdy
mieści się w bieżącym scope. Dla wielu etapów wskazuje jeden plan odbioru
w pozycji albo jej briefie (`backlog-contract.md` §6a).

Zadanie po zadaniu, w kolejności z planu. Każde kończy się dowodem według
`conventions/test-evidence.md` i `conventions/quality-gates-and-dod.md`,
commitem według `conventions/change-provenance.md` i linią w ledgerze
postępu (`conventions/multi-agent-delivery.md` §2.3). Ledger jest mapą
wznowienia po kompaktowaniu kontekstu; po wznowieniu ufasz ledgerowi
i `git log`, nie pamięci rozmowy.
Przy nowym temacie zapisz pozostałe etapy i następny krok; zmiana tematu sama
nie anuluje zakresu. Po powrocie porównaj cały plan z dowodami. X1–X2 gotowe
przy otwartych X3–X4 oznacza częściowe wykonanie X, także gdy testy X2 są zielone.

Zatrzymujesz się i pytasz, gdy:

- brakuje zależności lub środowiska (`BLOCKED`, nie obejście);
- plan ma lukę, przy której każda droga jest zgadywaniem;
- instrukcja jest niezrozumiała;
- ta sama uwaga z przeglądu wraca po drugiej naprawie;
- trzecia naprawa tego samego objawu zawiodła — to sygnał do taksonomii
  awarii z `conventions/architecture-change.md` §1, nie do czwartej próby.

Zadanie odkryte poza zakresem trafia do backlogu po deduplikacji; zapis nie
rozpoczyna implementacji.

## Krok 5 — Przegląd

Solo: porównaj diff z kryteriami odbioru i bramkami zadania; preflight PR
według `conventions/pull-request-review.md`. Z zespołem: verdict Reviewera
według `agents/reviewer.md`, przypięty do SHA. Narracja wykonawcy nie jest
dowodem w żadnym wariancie.

## Krok 6 — Domknięcie gałęzi

Przed nazwaniem całego zadania ukończonym rozlicz wszystkie etapy odbioru.
Sprawdź plan przez `python3 <toolkit>/templates/task-completion.py <plan>`
(dla pozycji backlogu: `--task <ID>`). Przed zamknięciem porównaj zakres przez
`--baseline-ref <commit>:<plan>` lub `--baseline <wcześniej-utrwalona-baza>`.
Bez bazy wynik pozostaje `SCOPE_UNVERIFIED`.
Wynik strukturalny nie potwierdza prawdziwości dowodów; kryteria ocenia review.

1. Pełny zestaw wymaganych kontroli projektu. Czerwony wynik kończy krok
   raportem porażek; menu integracji przychodzi po zielonym.
2. Wykryj środowisko, zanim zmienisz katalog:

   ```sh
   GIT_DIR=$(cd "$(git rev-parse --git-dir)" && pwd -P)
   GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)
   WORKTREE_PATH=$(git rev-parse --show-toplevel)
   git branch --show-current   # pusty wynik = detached HEAD
   ```

   `GIT_DIR` równy `GIT_COMMON` to zwykły checkout. Różne wartości na
   nazwanej gałęzi to worktree; różne przy pustym wyniku `show-current` to
   worktree zarządzany z zewnątrz.
3. Potwierdź gałąź bazową, jeśli nie wynika z planu ani z upstreamu:
   „ta gałąź odeszła od `<baza>` — zgadza się?". Merge do złej bazy jest
   drogi w cofnięciu.
4. Przedstaw właścicielowi opcje i czekaj na wybór:

   ```text
   Implementacja gotowa. Co dalej?
   1. Scal lokalnie do <baza>
   2. Wypchnij i otwórz PR
   3. Zostaw gałąź jak jest
   ```

   Przy detached HEAD są dwie opcje: wypchnij jako nową gałąź i otwórz PR,
   albo zostaw. Porzucenie pracy pojawia się wyłącznie na jawne polecenie
   właściciela.
5. Wykonaj wybór. Po scaleniu integrator sprząta czyste, nieużywane worktree
   utworzone dla zadania i sprawdza wynik listą worktree. Push/PR nie oznacza
   merge. Zajęte lub brudne checkouty mają powód zachowania i następny krok;
   zastane pozostają, chyba że właściciel zlecił ich sprzątanie.

Scalenie z zespołem podlega kontraktowi merge
z `conventions/multi-agent-delivery.md` §7.

## Podsumowanie

```text
KLASA: sonda | ograniczona | architektoniczna
PLAN: rozmowa | <ścieżka pliku>
GALAZ: <nazwa> (<baza>)
ZADANIA: <zamknięte>/<wszystkie>
POZOSTALE_ETAPY: <ID i następny krok | brak>
BRAMKI: PASS <komendy> | FAIL <co>
LEDGER: <ścieżka> | n/a
DECYZJA_INTEGRACYJNA: scal | PR <url> | zostaw | czeka
POST_INTEGRATION: removed <n> | kept <powód, następny krok> | n/a <brak merge>
DISCOVERED_TASKS: recorded <odsyłacze> | none
```

## Egzekwowanie

Blokują:

- kod w klasie architektonicznej bez zapisanej decyzji właściciela;
- merge, push albo skasowanie gałęzi bez wyboru właściciela z kroku 6;
- „gotowe" bez zielonych wymaganych kontroli i bez commita;
- obniżenie klasy w trakcie zadania.

Raportują:

- baseline czerwony przed pierwszą zmianą;
- liczba zatrzymań i ich powody;
- zadania odkryte poza zakresem.

Powiązane: `conventions/issue-reporting.md` (decyzja przed kodem),
`conventions/multi-agent-delivery.md` (worktree, ledger, kontrakt merge),
`conventions/test-evidence.md`, `conventions/change-provenance.md`,
`conventions/pull-request-review.md`, `templates/plan-funkcji.md`,
`templates/work-graph.md`.
