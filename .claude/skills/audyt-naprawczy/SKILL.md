---
name: audyt-naprawczy
description: Audyt jakości projektu zakończony NAPRAWĄ — zakłada gałąź roboczą, przeprowadza protokół audytu, a znaleziska z klas dowodliwych naprawia sam, osobnym commitem na klasę, z bramką po każdym. Wszystko, czego nie da się udowodnić bramką, zostaje w raporcie i czeka na decyzję. Użyj gdy właściciel prosi o „audyt z naprawą", „posprzątaj projekt", „napraw co się da", albo wpisuje tę komendę wprost. Do samego rozpoznania stanu bez zmian służy weekly-audit. EN — quality audit that ends in repairs — opens a working branch, runs the audit protocol, and auto-applies only fixes a gate can prove, one commit per class; anything unprovable stays a report entry. Use when the owner asks to audit and fix, or clean up a project.
compatibility: Wymaga bash i git; repozytorium musi mieć czyste drzewo robocze. Naprawy automatyczne wymagają narzędzi projektu (formatter, linter, testy) — bez nich skill degraduje się do raportu. Zaprojektowane dla agentów czytających SKILL.md (Claude Code i pokrewne).
metadata:
  author: claude-toolkit
  version: "2026.09.04"
---

# Audyt naprawczy

Ten skill robi to, czego `weekly-audit` **nie robi z założenia**: wprowadza
zmiany. Tamten kończy się raportem i listą priorytetów, bo decyzja „co
naprawiamy" należy do właściciela. Ten bierze z tej listy wyłącznie pozycje,
przy których decyzja jest zbędna — bo poprawność zmiany da się **udowodnić
bramką**, a nie osądem — i wykonuje je od razu.

Reszta wraca do raportu. Skill, który naprawia wszystko, co znajdzie, produkuje
gałąź, której nikt nie umie przejrzeć.

## Rozdział ról

| Kto | Za co odpowiada |
|---|---|
| skill | gałąź, audyt, klasyfikacja, naprawy dowodliwe, dowód z bramki |
| właściciel | decyzja o naprawach niedowodliwych, decyzja o wypchnięciu gałęzi |

Skill **nie wypycha gałęzi, nie otwiera PR-ów i nie komentuje nigdzie**.
Kończy się gałęzią lokalną i podsumowaniem. Wypchnięcie jest osobnym poleceniem
właściciela, bo to pierwszy moment, w którym praca staje się widoczna na
zewnątrz.

## Krok 1 — Gałąź i punkt odniesienia

Zanim cokolwiek dotkniesz.

1. **Drzewo robocze musi być czyste.** `git status --porcelain` niepuste →
   przerwij i powiedz właścicielowi, co jest niescommitowane. Naprawa
   wmieszana w cudze niezapisane zmiany jest nie do rozdzielenia.
2. **Nigdy na gałęzi domyślnej.** Utwórz `audyt/RRRR-MM-DD` od bieżącego HEAD
   **i przełącz się na nią** — `git switch -c audyt/RRRR-MM-DD`. Samo
   utworzenie gałęzi nie wystarcza: `git branch` zostawia HEAD tam, gdzie był,
   więc pierwszy commit trafiłby na gałąź bazową, czyli dokładnie tam, gdzie
   ta reguła zabrania pisać. Po przełączeniu potwierdź `git branch --show-current`.
   Jeśli taka gałąź już istnieje, dopisz `-2`, `-3`. Zapamiętaj nazwę gałęzi
   bazowej i jej SHA — oba idą do raportu.
3. **Zdejmij baseline bramek**, zanim zmienisz choć znak. Nowa gałąź stoi na
   tym samym commicie co baza, więc mierzysz **na niej** — nie przełączaj się
   z powrotem, bo to tylko okazja, żeby wrócić nie na tę gałąź. Uruchom testy,
   linter i typy i **zapisz listę nazw**, które są czerwone. Bez tego nie
   odróżnisz „naprawiłem" od „zepsułem coś innego", a liczba testów nic nie
   mówi — liczy się **różnica zbiorów nazw**.

Baseline zapisz w raporcie. Jeśli któregoś narzędzia projekt nie ma, zanotuj
`n/a` — brak narzędzia to znalezisko, nie cisza.

## Krok 2 — Audyt

Przeprowadź protokół z `weekly-audit`, Krok 00 do Krok 3, bez zmian. Ten skill
go **nie powtarza i nie streszcza** — dwa opisy tej samej procedury rozjadą się
przy pierwszej poprawce. Wczytaj tamten skill i wykonaj.

Z Kroku 00 obowiązuje jedno odstępstwo: gdy `toolkit-sync check` pokaże
**ZMIENIONY LOKALNIE**, nie naprawiasz tego automatycznie. Kopia reguły
rozjechana z masterem jest decyzją (promocja albo cofnięcie), nie usterką.

Wynikiem jest lista P0/P1/P2 — wejście do następnego kroku.

## Krok 3 — Klasyfikacja: co wolno naprawić bez pytania

Kryterium jest jedno i nie ma od niego wyjątków:

> Naprawa jest automatyczna wtedy i tylko wtedy, gdy istnieje bramka, która
> **przed** zmianą jest czerwona albo milcząca, a **po** zmianie zielona —
> i gdy zmiana nie zmienia zachowania obserwowalnego dla użytkownika.

**Wolno automatycznie:**

| Klasa | Dowód |
|---|---|
| formatowanie | formatter kończy się bez zmian przy powtórnym uruchomieniu |
| autofix lintera | linter schodzi z N do 0 w naprawionej regule, reszta bez zmian |
| martwy kod wskazany narzędziem | narzędzie przestaje go zgłaszać, testy bez nowych czerwonych |
| literówki i zepsute odsyłacze w dokumentacji | check odsyłaczy zielony |
| brakujący `.gitignore`/`.git/info/exclude` na artefakty | `git status` czysty po przebiegu |
| aktualizacja zależności **bez zmiany major** | bramki zielone, różnica zbiorów pusta |

**Nie wolno automatycznie — to idzie do raportu:**

- cokolwiek zmienia zachowanie widoczne dla użytkownika;
- poprawki bezpieczeństwa wymagające decyzji projektowej (P0 zgłaszasz, nie
  łatasz — zła łata na lukę jest gorsza niż jawna luka w backlogu);
- zmiana kontraktu, API, schematu danych, migracja;
- zmiana konfiguracji CI, bramek, progów, `decisions.md`;
- zmiana zależności o major albo taka, która rusza lockfile poza aktualizowanym
  pakietem;
- każda zmiana, dla której projekt nie ma bramki zdolnej ją potwierdzić.

Ostatni punkt jest najważniejszy. Projekt bez testów nie dostaje „naprawy na
oko" — dostaje raport i pozycję w backlogu o brakującej bramce.

## Krok 4 — Naprawa

Dla każdej dopuszczonej klasy, po kolei:

1. Wykonaj zmianę **tylko tej klasy**. Nie łącz klas w jednym commicie —
   przegląd i cofnięcie muszą być możliwe osobno.
2. Uruchom bramki. Zbiór czerwonych nazw porównaj z baseline z Kroku 1.
3. **Zbiór nowych czerwonych niepusty → cofnij tę klasę w całości**
   (`git restore` / `git reset --hard` do poprzedniego commita) i zapisz
   pozycję do raportu jako niedowodliwą. Nie debuguj, nie łataj łaty.
4. Zbiór pusty → commit. Wiadomość zgodna z `change-provenance.md`:
   `Intent:`, `Task-Ref:`, `Gates:` z faktycznie uruchomionymi komendami.

Po każdej klasie drzewo robocze jest czyste. Jeśli nie jest — coś zostawiło
artefakt i to też jest znalezisko.

**Nie podbijaj VERSION, nie ruszaj CHANGELOG-a** — audyt naprawczy nie jest
wydaniem.

## Krok 5 — Ratchet

Klasa naprawiona do zera zostaje zamrożona w tym samym przebiegu, zgodnie
z Krokiem 4 `weekly-audit`: usuń `|| true` z bramki, podnieś próg, zapisz
decyzję. Poziom osiągnięty i niezamrożony wraca w następnym audycie — tyle że
wtedy jako regresja, czyli drożej.

Ratchet jest zmianą konfiguracji bramki, więc z Kroku 3 **nie wolno go
automatycznie**. Przygotuj go jako propozycję w raporcie, z dokładną linią do
zmiany.

## Krok 6 — Podsumowanie

Dopisz do `.claude/audit-log.md` raport w formacie z `weekly-audit`,
rozszerzony o:

```text
BRANCH: audyt/RRRR-MM-DD (baza: <gałąź>, <SHA>)
BASELINE_FAILURES: <lista nazw | brak | n/a (brak narzędzia)>
NAPRAWIONE: <klasa: n commitów> …
COFNIĘTE: <klasa: powód> …
DO DECYZJI: <pozycje niedowodliwe, z propozycją>
NOWE_CZERWONE: <lista | pusta>
```

`NOWE_CZERWONE` niepuste przy zakończeniu = błąd przebiegu, nie wynik. Zgłoś
to jako pierwszą rzecz w podsumowaniu.

Na koniec pokaż właścicielowi: nazwę gałęzi, listę commitów jednolinijkowo
i jedno zdanie — co dalej. Zapytaj o wypchnięcie, nie wypychaj.

**HEAD zostaje na gałęzi audytu.** Nie wracaj na bazę bez polecenia: powrót
sprawia, że praca znika z oczu właściciela, który widzi wtedy czyste repo
i wnioskuje, że audyt nic nie znalazł.

## Egzekwowanie

**Blokują:**

- brudne drzewo robocze na starcie;
- praca na gałęzi domyślnej;
- commit klasy, po której zbiór nowych czerwonych jest niepusty;
- naprawa klasy spoza tabeli dozwolonych.

**Raportują:**

- brak narzędzia zdolnego udowodnić klasę (formatter, linter, testy);
- pozycje P0/P1/P2 niedowodliwe;
- propozycje ratchetu;
- dryf kopii reguł z Kroku 00.

## Sygnały maszynowe

| Sygnał | Znaczenie |
|---|---|
| `BRANCH:` | gdzie leży praca; brak = przebieg nie zaczął się poprawnie |
| `BASELINE_FAILURES:` | punkt odniesienia; bez niego wynik jest nieinterpretowalny |
| `NOWE_CZERWONE:` | niepuste = regresja wprowadzona przez ten przebieg |
| `COFNIĘTE:` | klasy odrzucone przez bramkę — materiał na następny audyt |

Powiązane: `weekly-audit` (protokół audytu), `audyt-floty` (ten sam audyt na
wszystkich projektach), `change-provenance.md`, `quality-gates-and-dod.md`,
`rules-as-gates.md`, `toolkit-sync.md`.
