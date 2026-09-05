# Konwencja: dowód z testu

Stack-agnostic. Wyekstrahowana z rundy review vocalinux 2026-08-17, gdzie
cztery z pięciu PR-ów dostały `CHANGES_REQUESTED` z tym samym zarzutem w
różnych przebraniach: test przechodziłby również bez naprawy.

## Problem

Test dołączony do poprawki buga jest **dowodem**, nie ozdobą. Test, który
przechodzi zarówno z naprawą, jak i bez niej, nie dowodzi niczego — a wygląda
identycznie jak dowód i przechodzi review u autora. Reviewer sprawdza to jako
pierwszą rzecz, więc koszt jest cały: runda review plus utrata zaufania do
pozostałych testów w PR.

Źródłem jest pisanie testów pod **diff** („czy mój nowy kod jest wołany")
zamiast pod **bug** („czy objaw z issue nadal się odtwarza").

## Procedura — weryfikacja negatywna

Dla każdego nowego testu towarzyszącego poprawce buga, nie raz na PR:

1. Cofnij naprawę w źródle — wystarczy jedna linia (`sed`, ręczna edycja).
2. Uruchom nowy test. Musi być **czerwony**.
3. Przywróć naprawę. Test musi być zielony.

Jeśli krok 2 dał zielone — test nie testuje naprawy. Przepisz go, zanim
otworzysz PR.

Ta sama procedura obowiązuje gate'y ([`rules-as-gates.md`](rules-as-gates.md)
§9): „przechodzi, gdy wszystko działa" nie jest dowodem na nic.

## Antywzorce z reprodukcją

Każdy odtworzony na działającym repozytorium.

### A1. Mock położony na granicy naprawy

**Objaw:** naprawa brzmi „wołaj resolver `X` zamiast czytać klucz `Y`", a test
mockuje `X` i sprawdza, że został wywołany.

**Reprodukcja:** usuń całe ciało `X` (niech zwraca stałą). Test dalej zielony,
bo prawdziwe `X` nigdy się nie wykonało.

**Reguła:** mockuj **na zewnątrz** granicy zmiany — sieć, dysk, zegar, toolkit
UI — nigdy naprawianej funkcji. Tam, gdzie kod dotyka configu, plików czy
serializacji, użyj prawdziwego obiektu na katalogu tymczasowym.

### A2. Stan ustawiony po operacji, która ukrywa buga

**Objaw:** bug brzmi „dwa obiekty utworzone zanim którykolwiek zapisze cofają
sobie zapisy", a test pobiera drugi uchwyt **po** pierwszym zapisie.

**Reprodukcja:** wycofaj współdzielenie instancji. Test dalej zielony, bo świeży
obiekt wczytał już zapisany plik.

**Reguła:** odtwórz kolejność użytkownika, nie kolejność wygodną dla asercji.

### A3. Test sprawdza kształt wywołania zamiast efektu

**Objaw:** asercja typu `assert kwargs["force_reinit"] is True`.

**Ryzyko:** przechodzi, gdy flaga jest przekazywana, ale nic nie robi po drugiej
stronie. Dowodzi wywołania, nie skutku.

**Reguła:** asercja na obserwowalnym efekcie (stan po operacji, zawartość pliku,
liczba re-inicjalizacji). Jeśli prawdziwa zależność jest za ciężka, użyj
stand-ina, który **odtwarza jej bramkowanie**, i osobno zapnij kontrakt
prawdziwej funkcji w obie strony (robi X, gdy flaga; nie robi X, gdy brak).

## Efekty uboczne przy imporcie plików testowych

Kod na poziomie modułu w pliku testowym wykonuje się przy **kolekcji** — w
każdej sesji i w kolejności zależnej od środowiska i wersji interpretera. Tak
nowy plik testowy psuje inny, nietknięty test na części jobów CI i na żadnym
lokalnie.

**Reprodukcja (Python, potwierdzona):** plik testowy popuje moduł z
`sys.modules`, importuje go ponownie z podmienioną zależnością i przywraca
wyłącznie wpis w `sys.modules`. `importlib.import_module` ustawia moduł **także**
jako atrybut na pakiecie rodzicu, więc zostają dwa żywe obiekty modułu. Od tej
chwili `patch("pkg.mod.func")` i `from pkg.mod import func` trafiają w różne
obiekty — inny plik testowy wywala się z niezrozumiałą asercją tylko na tych
wersjach Pythona, gdzie kolejność kolekcji ustawiła go po sprawcy.

Reguły:

1. Nie mutuj globalnego stanu interpretera przy kolekcji — `sys.modules`,
   `sys.path`, zmienne środowiskowe, podmienione builtiny. Fixture z `yield`
   i przywrócenie stanu.
2. Przy reimporcie przywróć **oba** miejsca rejestracji: wpis w `sys.modules`
   i atrybut na pakiecie rodzicu.
3. Helper oddający **żywe** patche (otwarty `ExitStack`, wystartowany patcher)
   musi je zamknąć, jeśli rzuci przed `return` — wołający zamyka tylko to, co
   dostał. Jeden wyciekły patch zatruwa wszystkie kolejne testy w sesji; w
   źródłowym incydencie odpowiadał za 160 z 192 lokalnych błędów.
4. Zanim sięgniesz po reimport, sprawdź tańsze drogi: wyciągnięcie logiki do
   funkcji modułowej (importuje się normalnie) albo asercja na źródle metody,
   jeśli chodzi wyłącznie o okablowanie.

## Wiarygodność przebiegu testów

Zanim wyciągniesz jakikolwiek wniosek z lokalnego uruchomienia:

1. **Sprawdź, który plik faktycznie się importuje.** Zainstalowana kopia w
   `site-packages` przesłaniająca drzewo źródłowe, nieaktualny katalog `build`
   albo zły `PYTHONPATH` oznaczają, że testujesz kod, którego nie edytujesz.
   W Pythonie: `python -c "import <pkg>.<mod> as m; print(m.__file__)"`.
2. **Odetnij stan maszyny.** Pliki lock, katalogi XDG/config/cache, działająca
   instancja testowanego programu, zajęte porty. Uruchomiona w tle kopia
   aplikacji wywala testy w sposób nieodróżnialny od defektu kodu.
3. **Uruchom całą suite w jednym procesie**, tak jak CI, nie tylko dotknięty
   plik. Błędy zależne od kolejności są niewidoczne per plik.
4. **Oceniaj po różnicy, nigdy po liczbie.** Zbierz listę `FAILED` na czystej
   gałęzi bazowej (osobny worktree jest tani), zbierz na swojej i porównaj
   zbiory. Błędy pre-existing to szum; liczą się wyłącznie nowe nazwy.

W źródłowym incydencie punkty 1 i 2 razem dawały 192 błędy zamiast 16 — przy
takim szumie regresja jest niewykrywalna, a „u mnie działa" nic nie znaczy.

## Sygnały maszynowe (tryb raportowy)

Kandydaci do preflightu wg procedury z [`rules-as-gates.md`](rules-as-gates.md):

1. Plik testowy z wywołaniem mutującym `sys.modules` / `sys.path` /
   `os.environ` poza ciałem funkcji i fixture'a.
2. Import produkcyjnego modułu rozwiązujący się poza drzewem roboczym
   (porównanie `__file__` z katalogiem repo) — blokuj z instrukcją.
3. Zbiór nowych nazw `FAILED` względem baseline'u gałęzi bazowej — niepusty
   blokuje.

Powiązane: [`pull-request-review.md`](pull-request-review.md),
[`issue-reporting.md`](issue-reporting.md),
[`rules-as-gates.md`](rules-as-gates.md).
