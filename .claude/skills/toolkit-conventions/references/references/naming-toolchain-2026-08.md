# Migawka: narzędzia pilnujące nazewnictwa, sierpień 2026

| | |
|---|---|
| **Data zebrania** | 2026-08-20 |
| **Data przeglądu** | 2027-02-20 (6 miesięcy) |
| **Zebrał** | właściciel repozytorium; korekty wersji i nazw reguł zweryfikowane w dokumentacji narzędzi w dniu zebrania |
| **Weryfikacja niezależna** | częściowa — zweryfikowano usunięcie reguł stylistycznych w Stylelint 16 oraz istnienie reguły nazewniczej w Biome; pozostałe pozycje pochodzą z praktyki i nie były sprawdzane ponownie |
| **Zasada grounding** | wersje i nazwy reguł pochodzą z dokumentacji z dnia zebrania; czego nie potwierdzono, oznaczono jako `n.a.` |

Reguły, które te narzędzia egzekwują, opisuje
`conventions/naming-conventions.md`. **Migawka nie zastępuje konwencji**: gdy
narzędzie zmieni nazwę reguły albo zniknie, zmienia się ta migawka, nie reguła.

---

## Mapa: rodzaj bytu → narzędzie

| Rodzaj bytu | Narzędzie | Uwaga |
|---|---|---|
| nazwy plików i katalogów | `ls-lint` | wzorce per katalog i rozszerzenie, języko-neutralne, jeden plik konfiguracji |
| znaki i kolizje wielkości liter | własny krok CI nad `git ls-files` | patrz „Bramka minimalna" niżej |
| granice między katalogami funkcjonalnymi | `dependency-cruiser` (JS/TS) | repozytorium: `sverweij/dependency-cruiser` |
| symbole Python | `ruff` (reguły `N…`, pep8-naming) | zastąpił flake8 + pylint w tej roli |
| symbole JS/TS | `eslint` z regułą nazewniczą **albo** `biome` (`useNamingConvention`) | Biome to jedno narzędzie zamiast pary linter + formatter |
| symbole Go | `golangci-lint` (`revive`, `stylecheck`) | `gofmt` nie sprawdza nazw |
| klasy CSS | `stylelint` (`selector-class-pattern`) | patrz korekty |
| SQL | `sqlfluff` | nazewnictwo identyfikatorów pokryte słabo — patrz korekty |
| REST / OpenAPI | `spectral` | wzorce ścieżek i parametrów jako reguły własne |
| zmienne środowiskowe | walidacja schematem przy starcie + krok CI na `.env.example` | fail-fast w runtime jest ważniejszy niż format |
| commity | `commitlint` albo `conventional-pre-commit` | format commita opisuje `conventions/change-provenance.md` |
| gałęzie | skrypt w `pre-push` **plus** job CI | patrz korekty |
| Markdown | `markdownlint` | |
| literówki w identyfikatorach | `typos` | tania część tego, co zwykle spisuje się na przegląd kodu |
| warstwa edytora | EditorConfig | jedyna warstwa działająca, zanim powstanie różnica |

## Korekty wobec konfiguracji krążących w sieci

Pięć rzeczy, które w kopiowanych konfiguracjach są nieaktualne albo po prostu
nie działają. Każda sprawdzona w dniu zebrania:

1. **ESLint: `.eslintrc.json` to format zaszły.** Od linii 9.x obowiązuje
   konfiguracja płaska (`eslint.config.js`). Konfiguracja w starym formacie bywa
   po cichu ignorowana — linter „przechodzi", bo nic nie sprawdza.
2. **Stylelint: reguły stylistyczne usunięte w 16.0.0** (zdeprecjonowane
   w 15.0.0). `indentation` już nie istnieje; wcięciami zajmuje się formatter.
   Konfiguracja z tą regułą kończy się błędem nieznanej reguły.
3. **Stylelint: `no-id-selector` i `no-important` nie są nazwami reguł.**
   Działające odpowiedniki to `selector-max-id` (z wartością `0`)
   i `declaration-no-important`.
4. **Akcje CI przypięte do znacznika (`@v4`) to nie jest przypięcie.**
   Wymagane pełne SHA z komentarzem wersji — `conventions/ci-cd.md` §2.
5. **Sprawdzanie nazwy gałęzi w `pre-commit` jest w złym miejscu.** Hook
   commitowy odpala się przy każdym commicie, także na gałęzi, której nikt nie
   zamierza wypchnąć, i nie widzi gałęzi docelowej. Właściwe miejsca to
   `pre-push` (szybka informacja) i job CI na pull requeście (bramka).

## Bramka minimalna — cztery kroki dające najwięcej

Kolejność wdrożenia od najwyższego stosunku wartości do szumu:

1. **Znaki i kolizje w nazwach plików** — krok CI nad `git ls-files`: brak
   spacji, brak znaków spoza ASCII, brak nazw różniących się wyłącznie
   wielkością liter, brak końcowych kropek. Zero fałszywych alarmów, natychmiast
   jako bramka blokująca.
2. **Linter języka z regułami nazewniczymi** w trybie zapadki na plikach
   nowych i zmienionych.
3. **`commitlint` albo odpowiednik** na komunikacie commita.
4. **`ls-lint`** dla wzorców plików i katalogów, gdy poprzednie trzy są zielone.

Reszta (`dependency-cruiser`, `spectral`, `sqlfluff`, `typos`) wchodzi wtedy,
gdy w danym obszarze pojawi się realny problem — kolejność wynika z
`conventions/tool-adoption-and-measurement.md`, nie z listy dostępnych narzędzi.

## Świadome luki

- **`sqlfluff` pokrywa formatowanie i wielkość liter słów kluczowych, nie
  nazewnictwo identyfikatorów.** Reguły dla nazw tabel i kolumn są ubogie
  i zmienne między wersjami; kontrola nazw schematu to własny skrypt na
  migracjach albo przegląd.
- **Czasownik w nazwie funkcji i przedrostek `is`/`has`/`can` dla wartości
  logicznych** nie mają gotowej reguły w głównych linterach. Własna reguła jest
  możliwa, ale zwykle nie zwraca kosztu utrzymania — zostaje przegląd.
- **Wzorzec blokowy CSS** (element i modyfikator względem bloku) jest
  sprawdzalny tylko wzorcem, nie semantycznie: linter nie powie, że modyfikator
  wystąpił bez klasy bazowej.
- **Wersje narzędzi nie są tu podane celowo.** Przypina się je w plikach
  blokad i konfiguracji hooków, gdzie podlegają aktualizacji przez bota —
  `conventions/dependency-currency.md`.
