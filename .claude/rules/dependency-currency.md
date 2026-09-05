# Konwencja: aktualność zależności, runtime'ów i dokumentacji

Stack-agnostic. Zakres: **jak mierzyć i raportować dystans do bieżących wersji,
kiedy przeterminowanie blokuje scalenie, oraz skąd pochodzi dokumentacja, na
której opiera się decyzja o wersji.**

Trzy pytania, które bywają mylone, bo odpowiada na nie ten sam ekran z listą
paczek:

| Pytanie | Klasa weryfikacji | Tryb |
| --- | --- | --- |
| Czy zależność ma znaną **podatność**? | SCA — [`security-verification-gates.md`](security-verification-gates.md) | blokujący |
| Czy runtime jest jeszcze **wspierany**? | ta konwencja, §2 | blokujący po dacie EOL |
| Jak daleko **odstajemy** od bieżących wersji? | ta konwencja, §3 | raportowy |

Rozdział ról: mechanikę aktualizacji (lockfile, bot, cooldown) opisuje
[`ci-cd.md`](ci-cd.md) §3; status dojrzałości narzędzia —
[`tool-adoption-and-measurement.md`](tool-adoption-and-measurement.md). Ta
konwencja mówi wyłącznie o **dystansie i wsparciu**.

---

## 1. Aktualność jest stanem mierzonym, nie wrażeniem

Zdanie „jesteśmy na bieżąco" bez liczby jest niesprawdzalne. Stan aktualności
MUSI dać się wyrazić trzema liczbami, zbieranymi automatycznie:

- ile zależności bezpośrednich jest za bieżącym wydaniem i o ile **majorów**,
- ile dni ma najstarsze przeterminowanie w zestawie,
- ile dni zostało do EOL najkrótszego runtime'u w projekcie.

Bez tych liczb nie da się odróżnić projektu, który świadomie zostaje na starszej
wersji, od projektu, który przestał patrzeć.

## 2. Runtime po EOL blokuje

- Uruchamianie kodu na runtime po dacie **końca wsparcia** (interpreter, VM,
  obraz bazowy, dystrybucja systemu) MUSI blokować wydanie. Po tej dacie nie ma
  poprawek bezpieczeństwa — to nie jest dług techniczny, to niezałatana
  powierzchnia ataku.
- Data EOL jest **znana z wyprzedzeniem**, więc bramka MUSI ostrzegać zawczasu:
  tryb raportowy od 180 dni przed, blokujący po dacie. Migracja runtime'u
  zaczęta w dniu EOL jest zawsze awaryjna.
- Wersja runtime'u MUSI być **zadeklarowana w repozytorium** (plik wersji,
  `engines`, `requires-python`, dyrektywa w module, obraz bazowy), a nie brana
  z tego, co akurat stoi na maszynie budującej. Bramka sprawdza deklarację;
  gdy jej nie ma, raportuje brak deklaracji jako ustalenie.
- Deklaracja MUSI być **jedna na repozytorium** — rozbieżność między obrazem
  CI, obrazem produkcyjnym i plikiem wersji jest osobnym ustaleniem, nawet gdy
  żadna z wersji nie jest jeszcze po EOL.

## 3. Dystans raportuje, nie blokuje

Bramka blokująca na „jest nowsza wersja" wymusza aktualizacje w dniu wydania —
czyli dokładnie to, przed czym chroni cooldown w [`ci-cd.md`](ci-cd.md) §3.
Dlatego:

- Dystans do bieżących wersji jest **raportowany**, z baseline'em i zapadką:
  liczba przeterminowanych zależności bezpośrednich NIE MOŻE rosnąć względem
  gałęzi bazowej. Ratchet wymusza kierunek bez wymuszania tempa.
- Zależność **bezpośrednia** liczy się inaczej niż tranzytywna: pierwszą
  wybraliście, drugą odziedziczyliście. Raport rozdziela te dwie liczby.
- Przeterminowanie o **major** jest osobną pozycją, nie sumuje się z patchami.
  Trzydzieści zaległych patchy to higiena; jeden zaległy major to projekt.
- Zależność **bez wydania od 24 miesięcy** albo z archiwalnym repozytorium
  źródłowym jest ustaleniem nawet wtedy, gdy „nie ma nowszej wersji". Brak
  aktualizacji nie jest dowodem dojrzałości; częściej jest dowodem porzucenia.
- Wpis oznaczony przez autora jako **przestarzały** (deprecated) MUSI mieć
  zapisany plan wyjścia z terminem, a nie wyciszenie.

## 4. Aktualizacja idzie klasami, nie hurtem

- Osobno: aktualizacje bezpieczeństwa (bez cooldownu), patch/minor (grupowane),
  major (**zawsze osobny PR**, z własnym testem ścieżki, której dotyczy zmiana).
- Aktualizacja hurtowa „wszystko naraz" nie da się zrewidować i nie da się
  wycofać pojedynczo. Gdy coś się psuje, bisekcja wraca do jednego commita,
  który zmienił czterdzieści zależności.
- Aktualizacja MUSI przechodzić ten sam zestaw bramek co zmiana kodu.
  Zielony bot nie jest przeglądem.
- Świadome pozostanie na starszej wersji MUSI być **decyzją z datą przeglądu**
  ([`change-provenance.md`](change-provenance.md), rejestr decyzji), nie
  milczeniem. Milczenie po pół roku wygląda identycznie jak przeoczenie.

## 5. Dokumentacja, na której opiera się decyzja, pochodzi ze źródła

Ta sekcja dotyczy zarówno człowieka, jak i agenta — ale dla agenta jest
wiążąca, bo agent nie ma jak zauważyć, że jego wiedza się zestarzała.

- Twierdzenie o **API, konfiguracji, domyślnych wartościach albo bieżącej
  wersji** biblioteki MUSI pochodzić z aktualnej dokumentacji tej biblioteki,
  nie z pamięci modelu. Model ma datę odcięcia; biblioteka nie ma obowiązku
  się do niej stosować.
- Jeżeli środowisko udostępnia **serwer dokumentacji** (MCP typu Context7 lub
  równoważny), agent MUSI go użyć przed napisaniem takiego twierdzenia —
  również wtedy, gdy „zna odpowiedź". Znajomość odpowiedzi jest właśnie tym
  stanem, w którym nieaktualność jest niewykrywalna od środka.
- Jeżeli serwera **nie ma**, agent MUSI to napisać wprost, oznaczyć odpowiedź
  jako opartą na pamięci modelu z podaniem daty odcięcia i **poprosić
  właściciela o udostępnienie źródła dokumentacji**. Cicha odpowiedź z pamięci
  jest gorsza od odmowy, bo nie da się jej odróżnić od sprawdzonej.
- Numer wersji, data wydania i status wsparcia NIE MOGĄ być podawane z pamięci
  **nigdy** — to fakty datowane, a nie wiedza o bibliotece. Ich miejsce
  opisuje [`references/README.md`](../references/README.md): reguła żyje latami,
  migawka wersji miesiącami.
- Dotyczy to tak samo języka i runtime'u, jak bibliotek: „ta składnia wymaga
  wersji X" jest twierdzeniem sprawdzalnym i podlega tej samej regule.

Zastosowanie w praktyce: audyt okresowy sprawdza dostępność źródła
dokumentacji **na starcie** i zapisuje wynik w raporcie jako `DOCS_SOURCE`.
Brak źródła nie unieważnia audytu — unieważnia prawo do podawania wersji jako
faktu.

## 6. Bramka w CI

- Kontrola aktualności NIE POWINNA wisieć na każdym pull requeście: wynik
  zmienia się od cudzych wydań, nie od Twojego diffa, więc jako bramka PR
  produkuje czerwone przebiegi bez związku ze zmianą. Uruchamiaj ją
  **cyklicznie** (raz w tygodniu) oraz **przy zmianie manifestu lub lockfile'a**.
- Wynik cykliczny MUSI mieć adresata: zgłoszenie aktualizowane w miejscu albo
  wpis do backlogu. Raport, który ląduje wyłącznie w logu przebiegu, nie
  istnieje.
- Bramka MUSI odróżniać **„nic nie znaleziono"** od **„nie sprawdzono"**. Brak
  narzędzia, brak sieci i przekroczony limit zapytań są wynikiem `n/a` i
  degradują przebieg — nigdy nie są zerem ustaleń. To najczęstszy sposób, w jaki
  taka bramka cicho przestaje działać.
- Job MUSI mieć minimalne uprawnienia i nie potrzebuje sekretów; jeżeli
  odpytuje zewnętrzne źródło danych o wsparciu, to źródło jest **zależnością
  zewnętrzną** — przypnij wersję API, buforuj odpowiedź i traktuj jej
  niedostępność jak `n/a`, nie jak sukces.
- Ekosystemy bez własnego polecenia „przeterminowane" (albo takie, gdzie kod
  wyjścia polecenia oznacza „znaleziono", a nie „błąd") MUSZĄ być obsłużone
  **po treści wyniku, nie po kodzie wyjścia**. Kod wyjścia narzędzia, którego
  kontraktu nie sprawdziłeś, jest zgadywaniem.

Szkielet skryptu:
[`../templates/dependency-currency.sh`](../templates/dependency-currency.sh) —
wykrywa manifesty, odpytuje o wsparcie runtime'ów, liczy dystans i kończy
statusem `OK` / `REPORT` / `EOL` / `DEGRADED`.

Przykładowy job (GitHub Actions; przenieś 1:1 na inny system CI):

```yaml
name: dependency-currency
on:
  schedule:
    - cron: "17 6 * * 1"          # poniedziałek rano, przed przeglądem
  pull_request:
    paths:
      - "**/package.json"
      - "**/package-lock.json"
      - "**/pyproject.toml"
      - "**/requirements*.txt"
      - "**/go.mod"
      - "**/Dockerfile"
  workflow_dispatch:

permissions:
  contents: read

jobs:
  currency:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<pełny SHA>   # patrz ci-cd.md §2
      - run: bash .ci/dependency-currency.sh | tee currency-report.txt
        env:
          STRICT_EOL: "1"        # runtime po EOL kończy przebieg błędem
      - uses: actions/upload-artifact@<pełny SHA>
        if: always()
        with:
          name: dependency-currency
          path: currency-report.txt
```

## 7. Egzekwowanie

**Blokują:**

- runtime po dacie EOL użyty w obrazie budowania, testów albo produkcji;
- wzrost liczby przeterminowanych zależności bezpośrednich względem gałęzi
  bazowej (zapadka);
- aktualizacja major scalona bez osobnego PR-a i bez testu dotkniętej ścieżki;
- wynik `n/a` bramki potraktowany jako sukces.

**Raportują:**

- runtime z EOL bliżej niż 180 dni;
- zależność bezpośrednia przeterminowana o major;
- zależność bez wydania od 24 miesięcy lub z archiwalnym źródłem;
- wpis oznaczony jako przestarzały bez planu wyjścia;
- rozbieżność deklaracji wersji runtime'u między plikami projektu;
- twierdzenie o wersji podane bez wskazania źródła dokumentacji.

## 8. Sygnały maszynowe (tryb raportowy)

1. Brak zadeklarowanej wersji runtime'u w repozytorium.
2. Wersja runtime'u w obrazie kontenera inna niż w pliku wersji projektu.
3. Krok kontroli aktualności z wymuszonym sukcesem albo z wyciszonym błędem.
4. Manifest zmieniony bez odpowiadającej zmiany lockfile'a.
5. Zależność wskazana na gałąź, tag ruchomy albo zakres bez górnego ograniczenia.
6. Wpis w konfiguracji wyciszający ostrzeżenie o przestarzałości bez daty.
7. Raport aktualności starszy niż 30 dni w projekcie z aktywnymi zmianami.

Powiązane: [`ci-cd.md`](ci-cd.md), [`rules-as-gates.md`](rules-as-gates.md),
[`change-provenance.md`](change-provenance.md),
[`security-verification-gates.md`](security-verification-gates.md),
[`tool-adoption-and-measurement.md`](tool-adoption-and-measurement.md),
[`references/README.md`](../references/README.md).
