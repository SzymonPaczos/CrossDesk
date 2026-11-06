---
name: plan-naprawy
description: Czyta raport audytu i backlog, po czym buduje kolejkę naprawy — uzupełnia brakujące pola pozycji danymi z raportu, scala duplikaty, odkłada świadomie to, co odkładamy, i pyta właściciela wyłącznie tam, gdzie odpowiedź zmienia kolejność. Plan zapisuje w samym backlogu, nie w osobnym pliku. Użyj gdy audyt się skończył i trzeba zdecydować, co robimy najpierw, albo gdy właściciel prosi o plan naprawy, priorytety, „co robimy dalej". EN — reads the audit report and the backlog, then builds a repair queue; fills missing item fields from the report, merges duplicates, defers deliberately, and asks the owner only where the answer changes the order. The plan lives in the backlog itself, never in a second file.
compatibility: Wymaga bash i git oraz skryptów backlog-lint.sh i backlog-migrate.sh z toolkitu. Skill jest z natury interaktywny — zadaje pytania i czeka na odpowiedź, więc NIE nadaje się do przebiegu bezobsługowego (claude -p, cron, CI). Zaprojektowane dla agentów czytających SKILL.md.
metadata:
  author: claude-toolkit
  version: "2026.11.07"
---

# Plan naprawy

Audyt kończy się listą znalezisk i zdaniem „czekaj na decyzję właściciela".
Ten skill jest tą decyzją — pierwszym w toolkicie, który bierze backlog na
**wejściu**, a nie tylko do niego dopisuje.

Wynikiem nie jest nowy plik. Plan to **kolejność pozycji w samym backlogu**:
sekcja `## Do wykonania` mówi, po co sięgamy najpierw, `## Poza kolejką` mówi, co
świadomie odkładamy i do kiedy. Osobny `plan.md` byłby drugim źródłem prawdy,
które starzeje się niezależnie od backlogu — a dwa nieaktualne pliki są gorsze
niż jeden.

## Rozdział ról

| Kto | Za co odpowiada |
|---|---|
| skill | migracja formatu, uzupełnienie pól z raportu, triaż, propozycja kolejności |
| właściciel | rozstrzygnięcia, których nie da się wyprowadzić z artefaktów |

Skill **nie zmienia kodu, nie zakłada gałęzi, nie commituje i niczego nie
wypycha**. Jedyny plik, który zapisuje, to `.claude/backlog.md` — te same
granice, które `multi-agent-delivery.md` nakłada na Coordinatora.

## Krok 1 — Preflight

```sh
bash <toolkit>/templates/backlog-lint.sh .
```

| Wynik | Co robisz |
|---|---|
| zielony | przejdź do Kroku 3 |
| czerwony, backlog sprzed kontraktu | Krok 2 — migracja |
| czerwony, pojedyncze naruszenia | napraw je w Kroku 2 punktowo, bez migracji całości |
| brak pliku backlogu | załóż z `templates/backlog.md` i powiedz właścicielowi, że projekt nie miał backlogu |

Brak `backlog-lint.sh` w toolkicie przerywa z instrukcją, gdzie go wziąć — nie
udawaj, że backlog jest w porządku, bo nie masz czym sprawdzić
(`rules-as-gates.md` pkt 6).

## Krok 2 — Migracja i uzupełnienie pól

Najpierw mechanicznie:

```sh
bash <toolkit>/templates/backlog-migrate.sh .          # podgląd, pisze obok
bash <toolkit>/templates/backlog-migrate.sh --apply .  # po przejrzeniu diffa
```

Migrator zostawia markery `TODO:` wszędzie tam, gdzie nie potrafił wyprowadzić
pola ze źródła. **To jest Twoja robota w tym kroku** i nie jest zgadywaniem:
brakujące `DOWOD` i `BRAMKA_ZAMYKAJACA` prawie zawsze leżą w raporcie audytu
obok, w `.claude/audit-log.md`. Raporty niosą je wprost — kolumny „Dowód / gdzie"
i „Propozycja / bramka zamykająca", albo zdanie „Propozycja:" w treści pozycji.

Kolejność szukania dla każdego markera:

1. raport audytu z tą samą datą co `ZRODLO` pozycji;
2. wcześniejsze wpisy w `audit-log.md`, jeśli pozycja jest starsza;
3. treść samej pozycji — proza często zawiera komendę reprodukcji.

Czego **nie wolno**: wymyślić komendy, która wygląda wiarygodnie. Pole, którego
nie ma w żadnym z trzech źródeł, dostaje:

```text
BRAMKA_ZAMYKAJACA: odstepstwo: brak bramki — do ustalenia
PRZEGLAD: <dzisiaj + 14 dni>
```

Pozycja bez bramki nie znika po cichu; wraca za dwa tygodnie jako otwarta.

Po uzupełnieniu `backlog-lint.sh` musi być zielony. Dopiero wtedy dalej.

## Krok 3 — Triaż bez pytań

Rozstrzygnij regułami wszystko, co się da. Każde pytanie zadane niepotrzebnie
zużywa uwagę właściciela, której zabraknie przy pytaniu istotnym.

| Sytuacja | Rozstrzygnięcie |
|---|---|
| `critical` z działającą bramką | na górę kolejki, bez pytania |
| dwie pozycje o tym samym `DOWOD` | scal; zachowaj oba identyfikatory w prozie scalonej |
| pozycja `Inbox` z jasnym wpływem z raportu | przenieś do `## Do wykonania` z wypełnionym `WPLYW` |
| pozycja bez ruchu od trzech audytów | `## Poza kolejką` z `PRZEGLAD` za 30 dni |
| odstępstwo po terminie | z powrotem do `## Do wykonania`, `STATUS: otwarte` |
| pozycja, której bramka jest już zielona | kandydat do domknięcia — zgłoś, nie zamykaj sam |

Ostatni wiersz jest ważny: bramka zielona **przed** naprawą zwykle znaczy, że
pozycja opisuje problem, którego już nie ma albo którego bramka nie mierzy.
Jedno i drugie jest ustaleniem dla właściciela, nie powodem do cichego
skreślenia.

## Krok 4 — Pytania, których nie da się uniknąć

**Najwyżej siedem pytań w jednej turze.** Po dziesiątym właściciel odpowiada
„tak, tak, dalej" i to już nie jest decyzja, tylko jej pozór.

Pytaj wyłącznie wtedy, gdy **odpowiedź zmienia kolejność albo los pozycji**.
Nie pytaj o rzeczy, które da się odczytać z repozytorium, ani o zgodę na to,
co i tak wynika z reguł Kroku 3.

Każde pytanie ma:

- **rekomendację** — co proponujesz i dlaczego, jednym zdaniem;
- **domyślną odpowiedź** — co się stanie, jeśli właściciel powie „rób jak
  uważasz";
- **konsekwencję** — co się zmienia w kolejce przy każdej z opcji.

Typowe pytania, które zwykle są istotne: czy środowisko jest wystawione na
zewnątrz (zmienia dotkliwość luki); czy funkcja jest jeszcze używana (zmienia
sens naprawy); czy zbliża się termin, który wywraca kolejność; czy pozycja
kosztowna ma sens przed decyzją architektoniczną, która może ją unieważnić.

Gdy właściciel nie odpowiada na część pytań, te pozycje idą do
`## Czeka na decyzję właściciela` — nie do kolejki i nie do kosza.

## Krok 5 — Zapis

1. `## Do wykonania` — pozycje w kolejności wykonania. Kolejność ustalasz,
   przestawiając całe pozycje; nie prowadź osobnej listy identyfikatorów.
2. `## Poza kolejką` — pozycje odłożone, każda z `PRZEGLAD`. **Powód wpisz do
   prozy pozycji.** To on sprawia, że następny audyt nie zgłosi jej ponownie
   jako nowej.
3. Pozycje odrzucone **nie znikają** — dostają `STATUS: zaparkowane`, powód
   i `PRZEGLAD`. Skreślenie bez śladu jest nieodróżnialne od przeoczenia.
4. Uruchom `backlog-lint.sh` ostatni raz. Czerwony = nie skończyłeś.

## Krok 6 — Podsumowanie

```text
PLAN_DATE: <data>
MIGRATED: <n pozycji> | n/a (backlog był zgodny)
FILLED_FROM_REPORT: <n pól uzupełnionych z audit-log>
QUEUED: <n> (<identyfikatory w kolejności>)
DEFERRED: <n> (<identyfikator → data przeglądu>)
MERGED: <n> (<identyfikatory scalone>)
QUESTIONS_ASKED: <n>
BLOCKED_ON_OWNER: <identyfikatory | brak>
CLOSURE_CANDIDATES: <identyfikatory z zieloną bramką | brak>
```

Na koniec pokaż właścicielowi trzy pierwsze pozycje kolejki i jedno zdanie:
od czego zacząć i dlaczego akurat od tego.

## Egzekwowanie

**Blokują:**

- praca na backlogu, który nie przechodzi `backlog-lint.sh` po Kroku 2;
- wymyślona wartość w `BRAMKA_ZAMYKAJACA` albo `DOWOD` — brak pola w źródłach
  daje odstępstwo z datą, nie prawdopodobnie wyglądającą komendę;
- zamknięcie pozycji przez ten skill; domknięcie wymaga commita i zielonej
  bramki, a skill nie commituje;
- więcej niż siedem pytań w jednej turze.

**Raportują:**

- pozycje bez bramki zamykającej;
- pozycje, których bramka jest zielona przed naprawą;
- wiek najstarszej pozycji o wpływie `high`;
- liczba pozycji odłożonych wobec poprzedniego przebiegu.

## Sygnały maszynowe

| Sygnał | Znaczenie |
|---|---|
| `QUEUED` | pusta kolejka po przebiegu = triaż nic nie rozstrzygnął |
| `QUESTIONS_ASKED` | powyżej siedmiu = złamany limit, decyzja jest pozorna |
| `BLOCKED_ON_OWNER` | rośnie między przebiegami = pytania nie docierają |
| `CLOSURE_CANDIDATES` | pozycje do sprawdzenia, czy problem jeszcze istnieje |
| `FILLED_FROM_REPORT` | zero przy niezerowym `MIGRATED` = raport nie został przeczytany |

Powiązane: `backlog-contract.md` (kształt pozycji i warunek domknięcia),
`weekly-audit` (skąd bierze się raport), `audyt-naprawczy` (co naprawia się
bez pytania), `project-state-layout.md`, `rules-as-gates.md`.
