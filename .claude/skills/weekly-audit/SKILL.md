---
name: weekly-audit
description: Przeprowadza cotygodniowy/okresowy audyt jakości kodu projektu — czystość, dead code, bezpieczeństwo, pokrycie testów, drift dokumentacji, zgodność z decyzjami. Użyj gdy właściciel prosi o audyt, przegląd jakości, sprawdzenie stanu kodu, lub gdy minęło >7 dni od ostatniego wpisu w audit-log.
---

# Cotygodniowy audyt jakości kodu

Cel: jakość rośnie monotonicznie. **Audyt wykrywa → naprawiamy → ratchet
zamraża → trend mierzy.** Audyt sam niczego nie naprawia — kończy się raportem
i listą działań, decyzję podejmuje właściciel.

## Krok 1 — Warstwa statyczna

Jeśli projekt ma `.claude/audit.sh` — uruchom `bash .claude/audit.sh`
(w głównym working tree, nie w worktree — potrzebny `node_modules`).
Jeśli nie ma — policz ręcznie: błędy lintera (eslint/ruff/...), liczba
TODO/FIXME, liczba plików testowych, moduły bez importera (`grep -rl`).

## Krok 2 — Warstwa głęboka (osąd agenta)

Skrypt liczy, Ty oceniasz. Przejrzyj i oceń:

1. **Bezpieczeństwo** — nowe endpointy bez rate-limit/walidacji, XSS (HTML
   z bazy renderowany bez sanityzacji), sekrety w repo, raw SQL z interpolacją
   user-inputu.
2. **Slop** — hardcoded dane w UI udające prawdziwe, mocki podane jako dane,
   funkcje oznaczone "gotowe" gdy są zaślepkami.
3. **Jakość testów** — nie *ile*, ale czy testują **właściwe** rzeczy:
   krytyczne ścieżki bez pokrycia, testy które nic nie weryfikują, skipped
   bez uzasadnienia.
4. **Architektura** — drift dokumentacja↔kod, duplikaty, martwe pola schematu,
   nieużywane eksporty, niespójne wzorce.
5. **Dead code** — zweryfikuj heurystykę skryptu greppem (sub-agenty mylą
   base-classy z dead code — zawsze potwierdź).
6. **Zgodność z rejestrem decyzji** (`decisions.md`) — złamana decyzja = P0/P1.
7. **Skille / MCP** — czy pojawiło się coś nowego co przyspieszy pracę.

## Krok 3 — Raport + lista P0/P1/P2

- **P0** — krytyczne: luki bezpieczeństwa, utrata integralności danych, kod
  kłamiący użytkownika.
- **P1** — ważne: dług blokujący rozwój, ciche błędy, brak testów krytycznych ścieżek.
- **P2** — porządkowe: dead code, drift, kosmetyka.

Dopisz raport do `.claude/audit-log.md` (najnowszy na górze). Przedstaw listę
właścicielowi — **czekaj na jego decyzję** co naprawiamy.

## Krok 4 — Ratchet (po naprawie)

Gdy coś naprawione, natychmiast zamroź: usuń `|| true` z gate'a w pre-push gdy
linter dochodzi do 0; podnieś próg coverage; zapisz decyzję do `decisions.md`.
Raz osiągnięty poziom = podłoga, nie sufit.

Pełna konwencja: `conventions/weekly-audit.md` w claude-toolkit.
