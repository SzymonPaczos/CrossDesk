# Konwencja: ścieżki importu

Stack-agnostic w warstwie zasad. Zakres: **jak moduł adresuje inny moduł
w tym samym projekcie** — kiedy wolno użyć ścieżki względnej, kiedy obowiązuje
alias, i co musi być spełnione, żeby alias nie okazał się iluzją działającą
tylko w edytorze.

Rozdział ról:

- [`code-structure.md`](code-structure.md) — **co** jest modułem i gdzie
  przebiega granica; tu chodzi wyłącznie o **zapis odwołania**.
- [`naming-conventions.md`](naming-conventions.md) — jak nazywa się plik
  i katalog, do którego alias prowadzi.
- [`runtime-boundaries.md`](runtime-boundaries.md) — co wolno zaimportować
  przez granicę serwer/klient. Alias nie znosi żadnej granicy; sprawia tylko,
  że jej przekroczenie jest **widoczne w jednej linii importu**.

## 1. Reguła

> Odwołanie do modułu spoza własnego katalogu zapisuje się **aliasem
> zakotwiczonym w korzeniu projektu**, nie wspinaczką po `../`.

```js
import { app } from '@/app.js'          // tak
import { app } from '../../app.js'      // nie
```

Powód nie jest estetyczny. `../../` koduje w treści pliku **jego własne
położenie w drzewie**, czyli fakt, którego plik nie powinien znać. Skutki są
mierzalne:

- przeniesienie katalogu o poziom wyżej psuje każdy import w środku, mimo że
  żadna zależność się nie zmieniła;
- przy trzech i więcej `../` nikt nie czyta ścieżki, tylko jej ufa — a to
  zamienia przegląd kodu w zgadywanie;
- dwa pliki importujące ten sam moduł mają **różne** ciągi znaków, więc
  wyszukiwanie „kto tego używa" po tekście przestaje działać;
- narzędzia do przenoszenia plików przepisują `../` mechanicznie i cicho
  tworzą ścieżki wychodzące poza korzeń pakietu.

## 2. Próg — kiedy względna jest w porządku

Alias nie jest dogmatem. Ścieżka względna zostaje, gdy odwołanie **nie
przekracza katalogu**:

| Zapis | Werdykt |
|---|---|
| `./helpers.js` | w porządku — rodzeństwo, przeniesienie ich rozdzieli i tak |
| `./util/format.js` | w porządku — schodzenie w dół, w obrębie własnego poddrzewa |
| `../siostra/x.js` | **granica** — jedno `..` bywa uzasadnione w ciasno powiązanej parze; dwa i więcej: nigdy |
| `../../x.js` | alias |

Reguła w jednym zdaniu: **w dół i w bok wolno, w górę nie**.

## 3. Alias musi rozwiązywać KAŻDE narzędzie, które dotyka kodu

To jest sedno tej konwencji i najczęstsza awaria przy jej wprowadzaniu.

Alias jest wpisem w konfiguracji, a konfiguracji jest w projekcie kilka:
kompilator, bundler, runner testów, runtime, czasem jeszcze linter i narzędzie
do pokrycia. **Alias skonfigurowany w jednym miejscu, a pominięty w drugim,
daje kod, który przechodzi kontrolę typów i wywala się przy uruchomieniu.**

Przykład ostrzegawczy, potwierdzony w dokumentacji TypeScriptu: `paths`
i `baseUrl` są **wyłącznie mechanizmem etapu projektowania**. Kompilator
świadomie **nie przepisuje specyfikatorów importu** w emitowanym kodzie —
w wyjściu zostaje dokładnie ten ciąg, który napisałeś. Sam `tsconfig.json`
z `paths` nie tworzy więc działającego aliasu; tworzy tylko zielone `tsc
--noEmit` i czerwony start aplikacji. Ścieżkę musi rozwiązać ktoś dalej:
bundler, loader albo pole `imports` w `package.json`.

**Zanim wpiszesz alias, wypisz listę narzędzi, które czytają importy w tym
projekcie, i skonfiguruj alias w każdym.** Lista, nie pamięć — pominięte
narzędzie zwykle jest tym, które odpala się najrzadziej, czyli na produkcji.

## 4. Który alias w którym stosie

**JavaScript i TypeScript.** Dwie możliwości, różniące się tym, **kto
rozwiązuje ścieżkę**:

| Zapis | Kto rozwiązuje | Kiedy |
|---|---|---|
| `#internal/x.js` | **Node natywnie**, przez pole `imports` w `package.json` | kod uruchamiany przez Node bez bundlera; jedyny wariant zgodny ze standardem pakietów |
| `@/x.js` | bundler albo kompilator z pluginem | aplikacje budowane (Vite, Astro, Next, webpack) |

Pole `imports` wymaga, żeby każdy klucz zaczynał się od `#` — właśnie po to,
by odróżnić alias wewnętrzny od nazwy pakietu z rejestru. Obsługuje wzorce:

```json
{ "imports": { "#internal/*.js": "./src/internal/*.js" } }
```

Prefiks `@` jest wygodniejszy w czytaniu i przyjęty w większości szablonów,
ale **nie jest rozumiany przez Node**. Ma jeszcze jedną pułapkę: `@` bez
ukośnika po nim to przestrzeń nazw w npm (`@scope/pakiet`), więc alias musi
mieć postać `@/` albo `@app/`, inaczej rozwiązanie zależy od kolejności reguł
i potrafi trafić w cudzy pakiet.

Wybierz jeden i trzymaj się go w całym repozytorium. Dwa style aliasu obok
siebie znaczą, że połowa plików rozwiązuje się inaczej niż druga.

**Python.** Importy bezwzględne od korzenia pakietu (`from app.core import x`).
Względne (`from ..core import x`) są w języku dozwolone i właśnie dlatego
wymagają jawnego zakazu — pakiet przeniesiony w drzewie ciągnie za sobą
niewidoczny łańcuch zależności. Bramka: reguła zakazująca importów względnych
w linterze (rodzina „relative imports" w `ruff`/`flake8-tidy-imports`).

**Go.** Import względny w module jest **niedozwolony przez język** — ścieżka
zawsze idzie od ścieżki modułu. Nic do konfigurowania, nic do pilnowania.

**Rust.** `crate::` dla korzenia skrzyni, `super::` wyłącznie do rodzica
w ciasno powiązanej parze modułów.

**Java, C#.** Pakiet lub przestrzeń nazw; ścieżki względne nie istnieją.

**CSS, SCSS, zasoby.** Ten sam alias co w kodzie, skonfigurowany w bundlerze.
Rozjazd między aliasem w JS a aliasem w stylach to najczęstszy powód, dla
którego obraz ładuje się lokalnie i znika po zbudowaniu.

## 5. Wprowadzenie do zastanego kodu

Jak przy każdej konwencji obejmującej cały korpus (patrz
[`naming-conventions.md`](naming-conventions.md) §5): **baseline z zapadką**,
nie jednorazowe przepisanie wszystkiego.

1. Skonfiguruj alias **we wszystkich** narzędziach z §3 i udowodnij go jednym
   plikiem: import przez alias, bramki zielone, aplikacja wstaje.
2. Policz istniejące naruszenia i zapisz liczbę jako próg. Nowy kod: alias
   bezwarunkowo. Stary: przy dotknięciu pliku.
3. Masową zamianę rób **osobnym commitem bez zmian zachowania**, najlepiej
   codemodem, i dopisz rewizję do pliku ignorowanych rewizji narzędzia
   przypisującego autorstwo — inaczej jedno sprzątanie kasuje historię
   autorstwa połowy repozytorium.
4. Po zejściu do zera zamroź próg w bramce.

Nie zamieniaj `../` na alias „przy okazji" innej zmiany. Diff, w którym
poprawka logiki tonie w dwustu przepisanych importach, nie da się przejrzeć,
a to on ma być dowodem.

## 6. Czego alias nie załatwia

- **Nie znosi cykli.** Moduł A importujący B importujący A jest cyklem tak
  samo przez alias, jak przez `../`. Alias tylko sprawia, że cykl trudniej
  zauważyć gołym okiem, więc wykrywanie cykli musi być bramką, nie nawykiem.
- **Nie zastępuje granicy pakietu.** Jeśli dwa katalogi nie powinny się
  widzieć, alias tego nie pilnuje — pilnuje to reguła zależności między
  warstwami.
- **Nie czyni importu poprawnym.** Alias do modułu serwerowego użyty
  w komponencie klienckim jest tym samym błędem co ścieżka względna; różnica
  jest taka, że teraz widać go w jednej linii.

## 7. Egzekwowanie

**Blokują:**

- import zawierający dwa lub więcej `..`;
- alias użyty w kodzie, a nieobecny w konfiguracji **któregokolwiek**
  z narzędzi z §3 — sprawdzane budowaniem i uruchomieniem, nie samą kontrolą
  typów;
- dwa różne prefiksy aliasu w jednym repozytorium.

**Raportują:**

- pojedyncze `..` przekraczające katalog — do przeglądu, nie do odrzucenia;
- liczba pozostałych naruszeń wobec progu baseline;
- alias zdefiniowany w konfiguracji, ale nieużywany przez żaden plik.

Bramka blokująca musi udowodnić alias **na artefakcie wyjściowym**. Zielone
`tsc --noEmit` nie jest dowodem — patrz §3.

## 8. Sygnały maszynowe

| Sygnał | Znaczenie |
|---|---|
| `IMPORT_DEPTH_MAX` | najgłębsza wspinaczka w repo; docelowo 1 |
| `IMPORT_VIOLATIONS` | liczba importów z dwoma i więcej `..`, wobec progu |
| `ALIAS_TOOLS` | narzędzia, w których alias jest skonfigurowany — liczba musi się zgadzać z listą z §3 |
| `ALIAS_PREFIXES` | rozpoznane prefiksy; więcej niż jeden = rozjazd |

Powiązane: [`code-structure.md`](code-structure.md),
[`naming-conventions.md`](naming-conventions.md),
[`runtime-boundaries.md`](runtime-boundaries.md),
[`rules-as-gates.md`](rules-as-gates.md),
[`quality-gates-and-dod.md`](quality-gates-and-dod.md).
