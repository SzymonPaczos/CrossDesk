# Konwencja: wersjonowanie i synchronizacja toolkitu

Stack-agnostic. Powstała 2026-08-06 po wykryciu, że model „master → kopia"
działa wyłącznie na dobrą wolę i cicho się rozjeżdża.

## Problem

Reguły i skille żyją w masterze, a projekty dostają **kopie**. Kopia nie
zawiera żadnej informacji o tym, z czego pochodzi. Skutki zaobserwowane
w jednej flocie sześciu projektów:

- ten sam skill audytu w **trzech różnych wersjach naraz** (187 / 154 / 54 linii);
- dwa projekty założone **po** wprowadzeniu nowej reguły dostały wersję
  sprzed tej reguły, bo bootstrap ciągnął z mastera, a master stał od miesiąca;
- reguła wypracowana downstream nigdy nie wróciła do mastera, więc każdy
  kolejny projekt startował bez niej;
- audyt miał w checkliście zdanie „porównaj kopie z masterem" — i to zdanie
  przegrało trzy razy z rzędu, bo nikt nie miał czym porównać.

Proza nie utrzyma synchronizacji między repozytoriami. Potrzebny jest numer
wersji, manifest i komenda.

## Mechanizm

| Element | Gdzie | Po co |
|---|---|---|
| `VERSION` | korzeń mastera | jedna liczba, którą da się porównać |
| `adoptions/<stara>-to-<nowa>.md` | master | co nowa wersja zastępuje i czego szukać w projekcie |
| `.claude/toolkit.lock` | każdy projekt | wersja + sha256 każdej przyjętej kopii |
| `.claude/toolkit-adoptions/` | każdy projekt | rozstrzygnięte sprzeczności, adaptacje i dowody |
| `scripts/toolkit-sync.sh` | master | `check` / `update` / `promote` / `contrib` |

Skrypt musi działać na BSD (macOS) tak samo jak na GNU — `find -printf` jest
rozszerzeniem GNU i wywracał warstwę kompletności skilli tak, że `check`
kończył **zielono** mimo niewykonanego sprawdzenia. Przenośność jest tu
częścią poprawności, nie wygodą.

Gdy kopie instaluje menedżer skilli (`npx skills add` i pokrewne), **tryb
kopiowania jest częścią mechanizmu, nie preferencją**. Instalacja dowiązaniem
sprawia, że projekt czyta bieżący stan mastera: nie ma czego stemplować, nie
ma czego porównać i nie ma momentu, w którym ktokolwiek zgodził się na nową
regułę. Kopia z sumą kontrolną jest jedyną formą, w której poniższe dwa
zdarzenia dają się rozróżnić.

`toolkit.lock` jest generowany, nie pisany ręcznie. Trzyma **dwie** sumy
kontrolne na wpis: kopii w projekcie i mastera, z którego ją stemplowano.

Druga kolumna nie jest ozdobą — bez niej mechanizm kasował pracę. Sama suma
kopii odpowiada tylko na pytanie „czy plik zmienił się od przyjęcia", a to za
mało: kopia przyjęta **już po ręcznym scaleniu** zgadza się ze swoim lockiem,
więc wygląda jak nietknięty master i `update` nadpisywał ją bez pytania —
dokładnie tę klasę plików, dla której napisano `purely_outdated` (role, które
master KAŻE skonkretyzować, jak `security-reviewer`). Awaria była cicha:
zwykła linia `⬇️`, nieodróżnialna od rutynowej aktualizacji. Zestawienie obu
sum rozstrzyga to wprost — kopia równa masterowi ze stemplowania jest dosłowna
i wolno ją nadpisać; różna była scaleniem i wraca do człowieka. Lock bez
czwartej kolumny (sprzed tej zmiany) nie jest zgadywany: wraca heurystyka
„zero dopisanych linii", więc stare projekty są bezpieczne bez migracji.
Pilnuje tego test negatywny w `scripts/validate-toolkit.sh`.

Dzięki temu lock odróżnia dwa różne zdarzenia:

- **MASTER NOWSZY** — kopia zgadza się z lockiem, ale master poszedł do przodu.
  Normalna sytuacja. Rozwiązanie: `update`.
- **ZMIENIONY LOKALNIE** — kopia nie zgadza się z własnym lockiem. Ktoś
  poprawił regułę w projekcie. To sygnał do promocji albo do cofnięcia,
  nigdy do cichego nadpisania.

## Protokół przy audycie

Sprawdzenie wersji jest **pierwszym krokiem audytu**, przed czytaniem kodu.
Audyt prowadzony na nieaktualnej checkliście sprawdza wczorajsze ryzyka.

1. `toolkit-sync.sh check .` — porównaj wersję projektu z masterem.
2. **Master nowszy** → przeczytaj `adoptions/<stara>-to-<nowa>.md`, potem
   zgłoś upgrade jako osobne zadanie. Audyt rezultatu i niezależnych ryzyk
   trwa według przyjętej wersji; nowe lub niespójne zakresy są niesprawdzone.
   Audyt nie zmienia własnych instrukcji, a jego wyniki nie ogłaszają adopcji.
3. Po zleceniu upgrade'u Builder uruchamia `prepare-update`, zapisuje skan
   sprzeczności i `update` jako osobny, reviewowany commit, wykonuje adaptacje w żywych
   plikach projektu i testy. `check` pozostaje czerwony przy rekordzie
   `Status: in-progress`; dopiero zapisane rozstrzygnięcia i dowody pozwalają
   ustawić `Status: complete`.
4. **Kopia najnowsza i adopcja zamknięta** → prowadź audyt normalnie.
   Wymagane Security Review, bramki i granice upoważnienia pozostają w mocy;
   luka w zakresie audytu nie jest ich zaliczeniem ani zgodą na merge.
5. **Znalazłeś błąd w regule** → nie łataj kopii w projekcie. Poprawka idzie
   do mastera, potem wraca przez `update`. Załatana kopia to początek
   następnego dryfu — dokładnie tak powstały trzy wersje jednego skilla.
6. **Powstała nowa reguła albo skill** → `promote` do mastera **od razu**,
   w tej samej sesji. Odłożona promocja nie następuje; sprawdzone empirycznie.
   Podbij `VERSION` i zrób commit w masterze.

Zapis reguły w masterze nie jest zgodą na jej wdrożenie we wszystkich
projektach. Każdy projekt przyjmuje upgrade świadomie, przez rekord adopcji,
`update`, adaptację własnych plików i dowód. Skopiowanie mastera bez
rozstrzygnięcia sprzecznych lokalnych instrukcji nie jest przyjęciem wersji.

## Co widzi `check`, a czego nie

`check` porównuje **kopie** — pliki wymienione w locku. Reguła wypracowana
w pliku, który kopią NIE jest (własny `rules/audit.md` obok masterowego
skilla, projektowy skrypt, sekcja dopisana do `general.md`), jest dla niego
niewidzialna. To nie jest teoria: checklista audytu w jednym projekcie urosła
z 14 do 17 pozycji przez pięć tygodni przy `check` świecącym na zielono, bo
rosła w pliku spoza manifestu.

Stąd `contrib` — wyciąga tytuły pozycji z pliku projektu i z jego
odpowiednika w masterze i pokazuje, co jest tylko po jednej stronie:

```sh
toolkit-sync.sh contrib <projekt> <plik-w-projekcie> [plik-w-masterze]
```

Dopasowanie idzie po tytule, więc przeredagowany nagłówek wygląda jak nowa
pozycja. To **sygnał do przeczytania, nie werdykt** — scalasz treścią, nie
kopiowaniem. Miejsce w procesie: krok 00 audytu, obok `check`.

## Czego `promote` nie zrobi za ciebie

`promote` nadpisuje master treścią projektu, więc jest jedyną komendą, która
potrafi skasować pracę pozostałych projektów. Dlatego:

- **Nie utworzy nowego mastera przez pomyłkę.** Plik, który nie jest kopią
  i którego cel w masterze nie istnieje, zatrzymuje komendę — razem z listą
  masterów mówiących prawdopodobnie o tym samym. `promote <…> rules/audit.md`
  wyprodukowałby `conventions/audit.md` obok istniejącego
  `skills/weekly-audit/SKILL.md`, czyli **drugi master jednego dokumentu** —
  tę awarię ten mechanizm miał kończyć, nie zaczynać. Świadomie nowy artefakt:
  `--new`. Cel pod inną nazwą: `--into <ścieżka>`.
- **Pokaże diff i zapyta.** Bilans „master zyska N / straci M" jest pierwszą
  linią, bo promocja kopii okrojonej pod jeden projekt zabiera te linie
  wszystkim pozostałym. Tryb nieinteraktywny wymaga `--yes`; bez terminala
  i bez flagi komenda odmawia zamiast zgadywać.
- **Sam podbije `VERSION`, ale nie ogłosi adopcji projektu źródłowego.** Lock
  zapisuje jeszcze na poprzedniej wersji, aby także projekt, z którego przyszła
  promocja, przeszedł przewodnik, skan pozostałych sprzeczności i adaptację.
  Wcześniej prosił o podbicie zdaniem na końcu outputu — a ta konwencja w innym
  miejscu sama stwierdza, że proza przegrywa z mechanizmem.

## Kiedy podbijać `VERSION`

Format: `RRRR.MM.DD` — data wydania. Wystarcza,
bo jedynym konsumentem jest porównanie „nowsze / starsze / takie samo".
Podbij przy każdej zmianie treści reguły, skilla, agenta lub szablonu.
Przed publikacją poprawki mogą pozostać w przygotowywanym wydaniu.
Po publikacji zmieniona treść otrzymuje osobny numer i przewodnik;
dotyczy to również literówek w dystrybuowanych plikach. Data kolejnego
wydania może być przygotowana na gałęzi, z jawnym opisem daty przygotowania.

`scripts/check-release-contract.sh` porównuje zawartość z opublikowanym
commitem. Wymaga nowszego numeru dla zmienionych plików wydania, zachowania
dotychczasowych przewodników oraz przejścia od wersji bazowej i changelogu.
Porównuje bajty, nie rozpoznaje zmiany semantycznej. Walidator używa
`TOOLKIT_RELEASE_BASE` lub lokalnego `origin/main`, bez automatycznego fetch.
Brak bazy jest błędem. CI przekazuje bazę PR lub poprzedni SHA pusha;
lokalne `origin/main` powinno odpowiadać publikacji sprawdzanej przez autora.
Reguła dotyczy wydania mastera, nie codziennego `update` w projektach.

Każde podbicie wymaga pliku `adoptions/<poprzednia>-to-<bieżąca>.md`. Autor
wersji najpierw przeszukuje aktywne pliki samego toolkitu pod kątem
sprzeczności, aktualizuje konsumentów, a w przewodniku zapisuje komendę i
wynik. Wymienia też reguły zastąpione i usunięte, wzorce wyszukiwania
sprzeczności w projekcie oraz warunek zamknięcia. Walidator toolkitu odrzuca
wersję bez tego pliku. Jeśli projekt pominął wersję pośrednią, aktualizuje się
kolejno przez opisane przejścia; nie wolno zgadywać skumulowanej migracji.

## Ratchet

Etap wdrożenia zgodnie z [`rules-as-gates.md`](rules-as-gates.md): `check`
działa dziś w trybie raportowym i zwraca kod 1 przy dryfie, ale nikogo nie
blokuje. Gdy liczba fałszywych alarmów spadnie do zera, projekt może podpiąć
go jako preflight audytu albo warstwę `pre-push`.

## Czego ten mechanizm nie robi

Nie rozstrzyga, czy nowa wersja reguły jest **lepsza**. Wykrywa różnicę i
wymusza zapis decyzji, ale nie ocenia jej. Decyzję o przyjęciu podejmuje
właściciel lub Reviewer; automat kopiujący reguły bez review byłby dokładnie
tym confused deputy, przed którym ostrzega
[`multi-agent-delivery.md`](multi-agent-delivery.md).

Nie synchronizuje też **lustra korpusu**. `skills/toolkit-conventions/references/`
jest generowane przez `scripts/build-skills.sh` i pilnowane osobną bramką
(`--check`). Gdyby weszło do manifestu, każda konwencja liczyłaby się dwa razy,
a deklaracja odstępstwa w `.claude/toolkit.local` wyciszałaby tylko jedną
z dwóch kopii — `check` świeciłby zielono dokładnie wtedy, gdy jedna reguła
żyje w projekcie w dwóch wersjach. Miejscem autorskim jest korzeń repo; poprawkę
wprowadza się w `conventions/<plik>`, nigdy w lustrze.

## Migracje zbiorcze

Resolver wybiera `adoptions/<stara>-to-<nowa>.md`, a przy jego braku jawny
plik w `adoptions/migrations/`. Oba formaty wskazują jeden rekord projektu.
Przewodnik zbiorczy wymaga rozliczenia wszystkich źródłowych przejść;
nie zalicza ich automatycznie. Brak, symlink lub błędne pola wersji blokują
przejście przed zapisem. Pełne warunki odbioru pozostają w rekordzie adopcji.
