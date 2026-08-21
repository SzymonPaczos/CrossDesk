# Konwencja: mechaniczne gate'y higieny repozytorium

Stack-agnostic. Wyekstrahowana z audytu floty 2026-08-01, gdzie te same klasy
problemów powtórzyły się niezależnie w wielu projektach. Zgodnie z
[`rules-as-gates.md`](rules-as-gates.md): najpierw tryb raportowy, potem — po
policzeniu false positives — ewentualnie gate blokujący. Gate jest podłogą, nie
sufitem.

## Powód

Audyt sześciu projektów jednego właściciela ujawnił powtarzalne, wykrywalne
mechanicznie naruszenia, których proza „pilnuj czystości" nie łapała:

- praca istniejąca wyłącznie lokalnie na maszynie bez backupu (5/6 projektów);
- dane osobowe/skany w gicie, część już na remote (3/6);
- duplikaty `.bak`/`BACKUP`/`*_b64` i binaria puchnące historię;
- martwe linki z `.claude/*.md` do plików untracked („jedyna kopia");
- zmergowane gałęzie i duplikat `master`/`main` nigdy nieusuwane;
- wygasłe tokeny leżące w `.env`.

## Sygnały maszynowe (tryb raportowy)

Każdy z tych checków jest tani i deterministyczny — kandydat do preflightu
audytu albo pre-push w trybie `WARN`:

1. **Ekspozycja na utratę:** `git branch -vv` (ahead/bez upstreamu) +
   `git stash list` + `git worktree list --porcelain | grep prunable` +
   wiek najstarszego niepushowanego commita. Raportuj łącznie z posturą
   backupu (czy repo ma remote / świeży `git bundle`).
2. **Dane osobowe:** `git ls-files | grep -iE
   'legitymacja|dowod|pesel|zaswiadczenie|_b64'` oraz skany/PDF poza
   katalogami dozwolonymi lokalną decyzją projektu.
3. **Dysk vs git:** `du -sh` zestawione z `git count-objects -vH` i listą
   największych blobów historii.
4. **Integralność referencyjna:** każda ścieżka pliku wymieniona w
   trackowanych `.claude/*.md` istnieje i jest trackowana albo świadomie
   ignorowana.
5. **Duplikaty/śmieci tracked:** `git ls-files | grep -iE
   '\.bak$|BACKUP|_b64'`.
6. **Gałęzie do sprzątania:** `git branch --merged main` (poza chronionymi
   i żywymi worktree) + wykrycie duplikatu `master`/`main`.
7. **Wygasłe credentiale:** `grep -riE 'Expires|EXPIRES_ON' .env*` vs
   bieżąca data.
8. **Wroga konfiguracja w klonowanym repo** — uruchamiany **przed** otwarciem
   cudzego repozytorium w agencie lub edytorze, nie po:

   ```sh
   git ls-files | grep -E '^\.claude/(settings|settings\.local)\.json|^\.claude/hooks/|^\.vscode/tasks\.json|^\.claude/.*\.(mjs|js|sh|py)$'
   git ls-files | grep -iE '(^|/)(git|npm|node|python|sh|bash)(\.exe|\.cmd|\.bat)?$'
   ```

   Pierwszy grep łapie pliki, które wykonują kod **przy samym otwarciu
   checkoutu** — hooki `SessionStart` w `.claude/settings.json` i zadania
   z `.vscode/tasks.json` nie wymagają `npm install` ani zgody na komendę.
   Drugi łapie binarki podszywające się pod narzędzia systemowe: edytor
   szukający `git` w katalogu workspace uruchomi podłożone `git.exe`
   bez pytania.

   Klasa potwierdzona z dwóch stron: publiczne CVE w narzędziach agentowych
   dotyczące obejścia dialogu zaufania przez plik ustawień kontrolowany przez
   repo, oraz kampanie supply-chain commitujące takie pliki do repozytoriów.
   Traktuj otwarcie projektu jak przyjęcie żądania z internetu.

   Konsekwencja proceduralna: cudze repo (`vendor/`, klon z issue, fork do
   review) otwiera się **najpierw bez agenta**, a `.claude/` i `.vscode/`
   czyta człowiek. Dopiero potem sesja z narzędziami.

## Zła kandydatura

Nie blokuj na osądzie „czy ten plik jest potrzebny" — to check głębokiego
audytu, nie mechaniczny gate. Lista chronionych gałęzi i katalogów
dozwolonych na dane osobowe jest lokalną decyzją projektu (`decisions.md`),
nie globalną stałą.

## Ratchet

Gdy projekt osiąga zero findings w danej klasie, zamroź: zamień `WARN` na
gate blokujący dla tej klasy. Każdy nowy incydent dopisuje stały punkt.

## Źródła referencyjne

- [`rules-as-gates.md`](rules-as-gates.md)
- Postmortem źródłowy: audyt floty sześciu projektów (2026-08-01), trzymany
  w repozytorium właściciela floty, nie w toolkicie.
