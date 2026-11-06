# Migawka: toolchainy językowe, sierpień 2026

| | |
|---|---|
| **Data zebrania** | 2026-08-18 |
| **Data przeglądu** | 2027-02-18 (6 miesięcy) |
| **Zebrał** | właściciel repozytorium, na podstawie stron dokumentacji i rejestrów pobranych 2026-08-18 |
| **Weryfikacja niezależna** | **nie przeprowadzono** — wersje i statusy nie były sprawdzane ponownie przy wnoszeniu do toolkitu |
| **Zasada grounding** | każda wartość pochodzi ze źródła pobranego w dniu zebrania; brak potwierdzenia zapisano jako `n.a.` |

Statusy (*production default*, *dobra alternatywa*, *emerging*, *legacy*) są
**rekomendacją autorską** opartą na cytowanych faktach, nie etykietami
producentów — z wyjątkiem miejsc, gdzie wprost zaznaczono cytat.

Zasady, według których te statusy się przyznaje i zmienia, opisuje
`conventions/tool-adoption-and-measurement.md`. **Ta migawka nie zastępuje
konwencji** — gdy się rozjeżdżają, obowiązuje konwencja.

Deklarowane przyspieszenia („X razy szybciej") są cytatami z materiałów
producentów i nie zostały niezależnie zweryfikowane.

---

## JavaScript / TypeScript

**Golden path:** menedżer wersji narzędzi (Node LTS + pnpm) → pnpm →
TypeScript 7 z `tsc --noEmit` w CI → oxlint z lintem świadomym typów, formatter
produkcyjny Biome (oxfmt równolegle w trybie cienia do wyjścia z bety) → Zod na
granicach → Hono z generowaniem OpenAPI → Vitest (unit, integracja) +
Playwright (E2E) + fast-check (property) → Turborepo dla cache zadań → audyt
zależności i skan sekretów w CI.

| Narzędzie | Rola | Status | Uzasadnienie z migawki |
|---|---|---|---|
| Vite 8 + Rolldown | build | production default | wydanie stabilne 12.03.2026, Rolldown jako jedyny bundler |
| Vitest 4 | testy | production default | Browser Mode oznaczony jako stabilny |
| oxlint z lintem typów | lint | production default | 59 z 61 reguł świadomych typów; wersjonowanie sprzężone z TS 7 |
| oxfmt | format | emerging | producent oznacza „Formatter (Beta)" |
| Biome | format + lint | dobra alternatywa | 97% zgodności z Prettier, 524 reguły, jedna komenda |
| ESLint + typescript-eslint | lint | dobra alternatywa | kompatybilność wtyczek |
| oxc-minify | minifikacja | emerging | producent oznacza „Minifier (Alpha)" |
| pakiet `rolldown-vite` | migracja | legacy | „experimental", zmiany łamiące możliwe w patchu; jest stabilna ścieżka przez Vite 8 |
| Deno | runtime + toolchain | dobra alternatywa | wbudowane format, lint, testy, audyt |
| Bun | runtime + PM + testy | dobra alternatywa, selektywnie | „stable and ready for production", ale część podsystemów eksperymentalna |
| wbudowany runner testów Node | testy | dobra alternatywa | stabilny, ale pokrycie kodu wciąż eksperymentalne |
| TypeScript 7 | typy | production default | „Battle-Tested and Ready for Production"; **API kompilatora dopiero w 7.1** |

**Antywzorce:** równoległe utrzymywanie Prettier + ESLint + Biome + oxlint
(nakładanie ról — patrz konwencja §6); uruchamianie testów runnerem innym niż
skonfigurowany w projekcie; produkcja na wersji runtime poza LTS; traktowanie
modelu uprawnień runtime jako sandboxa bezpieczeństwa („malicious code can
bypass the permission model"); migracja na pakiet przejściowy zamiast na
wersję stabilną.

## Python

**Golden path:** menedżer wersji + uv (wersja Pythona i lock) →
`uv sync --locked` w CI → Ruff (format i lint, z regułami bezpieczeństwa) →
sprawdzanie typów w CI → Pydantic na granicach → FastAPI (OpenAPI i
dokumentacja automatycznie) → pytest + Hypothesis → audyt zależności i skan
sekretów → obraz distroless.

| Narzędzie | Rola | Status | Uzasadnienie z migawki |
|---|---|---|---|
| uv | pakiety, lock, wersje Pythona | production default | jeden CLI zastępuje pip, pip-tools, pipx, poetry, pyenv, twine, virtualenv |
| Ruff | lint + format | production default | ponad 900 reguł, parytet z Flake8, isort i Black |
| Pyright | typy | production default | zgodny ze standardami, CLI i serwer języka |
| mypy | typy | dobra alternatywa | „production ready", typowanie stopniowe |
| ty | typy | emerging | „currently in beta", wersjonowanie `0.0.x`, brak stabilnego API |
| venv + pip | pakiety | dobra alternatywa | minimalizm, `venv` w bibliotece standardowej |
| Bandit samodzielnie | SAST | dobra alternatywa | pokrycie regułami `S` w Ruff zmniejsza potrzebę |
| Python ≤ 3.9 | runtime | legacy | koniec wsparcia |

**Antywzorce:** brak lockfile'a albo uruchamianie w CI bez trybu blokującego,
co pozwala cicho zaktualizować lock; utrzymywanie Flake8 + Black + isort obok
Ruff; włączanie reguł oznaczonych jako preview jako obowiązkowych bramek;
poleganie na narzędziu w becie jako jedynym sprawdzaczu typów.

## Go

**Golden path:** `go.mod` z liniami `go`/`toolchain` (plus zmienna toolchainu w
CI) → `gofmt` → `go vet` i analiza statyczna, ewentualnie przez runner lintów →
router zgodny z `net/http` + walidacja struktur → kontrakt OpenAPI z
generowaniem kodu, dla RPC schemat z kontrolą zgodności → `go test` z
fuzzingiem dla parserów → skan podatności świadomy wywołań → benchmarki z
analizą statystyczną i profiler.

| Narzędzie | Rola | Status | Uzasadnienie z migawki |
|---|---|---|---|
| gofmt | format | production default | narzędzie oficjalne |
| gofumpt | format ścisły | dobra alternatywa | nadzbiór gofmt |
| golangci-lint | runner lintów | production default | równoległość, ponowne użycie cache, ponad 100 lintów |
| Staticcheck | analiza | production default | „focuses on checks that produce few to no false positives" |
| connect-go | RPC | production default | „stable and used by several companies in production", trzy protokoły |
| oapi-codegen | generowanie z OpenAPI | dobra alternatywa | „OpenAPI 3.1 support is awaiting upstream support" |
| wbudowany fuzzing | fuzzing | production default z zastrzeżeniem | instrumentacja pokrycia tylko na AMD64 i ARM64 |

**Antywzorce:** trzymanie modułu na wersji języka bez wsparcia (reguła „dwa
nowsze wydania"); ręczne pinowanie commitów zamiast modelu niezmiennych
migawek modułów; wnioskowanie o regresji z jednego przebiegu benchmarku bez
powtórzeń i analizy statystycznej; publikowanie schematu RPC bez kontroli
zgodności w CI.

## Rust

**Golden path:** rustup na kanale stabilnym z plikiem toolchainu w repo →
cargo z commitowanym `Cargo.lock` → `cargo fmt` → Clippy z kategorią
correctness jako błędem → serde na granicach → axum z warstwami tower-http →
runner testów + property testy + fuzzing parserów → audyt podatności i
polityka licencji → benchmarki statystyczne, flamegraph, wykrywanie UB dla
`unsafe`.

| Narzędzie | Rola | Status | Uzasadnienie z migawki |
|---|---|---|---|
| rustup, kanał stable | toolchain | production default | oficjalne kanały wydań |
| kanał nightly | toolchain | emerging | wymagany tylko dla najnowszych funkcji formattera |
| axum | REST | production default | cienka warstwa nad hyper, ekosystem tower |
| utoipa | OpenAPI code-first | dobra alternatywa | „treats code-first approach as a first class citizen" |
| nextest | runner testów | dobra alternatywa | doctesty uruchamiane osobno |
| proptest | property testy | dobra alternatywa z zastrzeżeniem | „mainly sees passive maintenance" |
| cargo-fuzz | fuzzing | production default dla parserów | „the recommended tool for fuzz testing Rust code" |
| Miri | wykrywanie UB | dobra alternatywa | reguły aliasingu oznaczone jako eksperymentalne |
| `clippy::restriction` w całości | lint | legacy | „should, emphatically, not be enabled as a whole" |

**Antywzorce:** ręczne pinowanie rewizji zamiast polegania na lockfile;
globalne włączanie kategorii restriction i nursery; wymaganie nightly w CI bez
potrzeby; `unsafe` bez narzędzia wykrywającego UB w pipelinie; audyt podatności
bez polityki licencji i źródeł.

## C i C++

**Golden path:** presety systemu budowania + szybki backend → clang-format z
błędem przy niezgodności → clang-tidy i drugi analizator statyczny (dla kodu
wbudowanego także profil branżowy) → menedżer pakietów C/C++ → testy w
uznanym frameworku + fuzzing parserów → w CI osobne zadania: build z
sanitizerem adresów i UB, osobno sanitizer wątków → narzędzie do analizy
pamięci ad hoc → benchmarki mikro i pomiar end-to-end.

| Element | Status | Uzasadnienie z migawki |
|---|---|---|
| presety + szybki backend budowania | production default | presety od wersji 3.19 systemu budowania |
| alternatywny system budowania z prostym DSL | dobra alternatywa | „non-Turing complete DSL" |
| menedżer pakietów z weryfikacją ABI | production default (ekosystem CMake) | ponad 2300 bibliotek budowanych rutynowo |
| menedżer pakietów wieloplatformowy | production default (wiele systemów budowania) | polityka braku zmian łamiących |
| sanitizer adresów + UB w CI | production default | spowolnienie rzędu 2x, koszt UB niski |
| sanitizer wątków | dobra alternatywa, osobne zadanie | spowolnienie 5x–15x, pamięć 5x–10x |
| wykrywanie wycieków w sanitizerze adresów | emerging | producent oznacza „Memory leaks (experimental)" |
| libFuzzer | dobra alternatywa, utrzymanie ograniczone | „authors have stopped active work on it"; poprawki bezpieczeństwa tak, nowe funkcje nie |
| stare narzędzie opakowujące analizator | legacy | strona oznaczona jako deprecated |
| C++20 jako baza „modern C++" | production default | definicja z Core Guidelines |
| C++26 i nowsze | emerging | osobne tabele wsparcia, wiele pozycji „partial" |
| starsze gałęzie frameworków testowych | legacy dla nowego kodu | wymagają starych standardów języka |

**Antywzorce:** brak bazy poleceń kompilacji dla analizatora; commitowanie
lokalnych presetów użytkownika; linkowanie binarek z sanitizerem
niewłaściwym linkerem; łączenie sanitizera adresów i wątków w jednym zadaniu
CI; traktowanie analizy statycznej jako zamiennika testów; poleganie na
funkcjach języka bez sprawdzenia tabel wsparcia kompilatorów.

## Bash / Shell

**Golden path:** `#!/usr/bin/env bash` + `set -euo pipefail` → formatter
shella → analizator statyczny z kodem wyjścia jako bramką → framework testowy
dla shella z asercjami → **limit około 100 linii i prosty przepływ sterowania,
potem przepisanie do języka strukturalnego** → skan sekretów.

| Element | Status | Uzasadnienie z migawki |
|---|---|---|
| ShellCheck | production default | jedyny szeroko przyjęty analizator shella, kody wyjścia nadają się na bramkę |
| shfmt | production default | formatter POSIX sh, Bash i mksh |
| Bats-core + asercje | production default | framework dla Bash 3.2 i nowszych |
| interpreter z pakietu formattera | emerging | „proof of concept shell" |
| skrypty powyżej ~100 linii | legacy | wprost odradzane w cytowanym przewodniku stylu |
| dążenie do zgodności z POSIX sh „na wszelki wypadek" | legacy poza wymuszonymi środowiskami | „generally no need to strive for POSIX-compatibility" |

**Antywzorce:** brak `set -e`, `-u` i `-o pipefail` w skryptach CI; rozrastanie
skryptu ponad prosty wrapper; testowanie „na oko" zamiast frameworka;
pomijanie analizatora, mimo że integruje się z hookami i CI.

---

## Profile wdrożenia

**Minimalny (solo, prototyp):** deklaratywne wersje narzędzi + lockfile; jeden
przebieg formatera i lintera; wbudowany runner testów; jeden skan zależności;
krótkie gałęzie.

**Standardowy (zespół):** dodatkowo szybkie hooki na plikach w indeksie; cache
w CI; bramki kontraktu API; skanery bezpieczeństwa w warstwach; automatyzacja
aktualizacji zależności z cooldownem; właściciele kodu, reguły ochrony gałęzi i
podpisywanie commitów; konwencja commitów z automatycznym changelogiem;
telemetria z celami niezawodności.

**High-assurance (regulowane, krytyczne):** dodatkowo SBOM i skan artefaktów;
podpisy i provenance z weryfikacją fail-closed; głęboka analiza kodu; praca nad
reprodukowalnością buildów; dla języków niebezpiecznych pamięciowo obowiązkowe
zadania z sanitizerami i ciągły fuzzing; policy-as-code dla infrastruktury.

Szczegóły bramek bezpieczeństwa: `conventions/security-verification-gates.md`.
Szczegóły dostawy i provenance: `conventions/ci-cd.md`.

---

## Świadome luki (`n.a.`)

Nie wolno uzupełniać ich z pamięci przy cytowaniu tej migawki:

- pełna lista nazw dwunastu czynników metodyki 12-factor (potwierdzono
  definicję metodyki i czynnik III);
- definicja GitFlow z pierwotnego źródła — użyto wyłącznie definicji
  trunk-based jako kontrastu;
- data publikacji jednej z wersji specyfikacji OpenAPI;
- bieżące numery wersji kilkunastu narzędzi, których strony ich nie podają;
- reguły backoff i jitter — źródło nie zostało pobrane, więc rekomendacja
  ponowień opiera się wyłącznie na semantyce HTTP i drafcie nagłówka
  idempotencji;
- dokładne daty wydań poszczególnych wersji dwóch alternatywnych runtime'ów JS;
- status i rola jednego z narzędzi do analizy infrastruktury jako kodu.

---

## Jak odświeżyć tę migawkę

1. Nowy plik `references/language-toolchains-RRRR-MM.md`, nie edycja tego.
2. Przy każdej wartości zachowaj odsyłacz do źródła i datę pobrania.
3. Zachowaj sekcję świadomych luk — pusta sekcja luk oznacza zwykle, że ktoś
   uzupełnił je z pamięci.
4. W tym pliku dopisz nagłówek „zastąpione przez …" i zostaw go jako materiał
   historyczny.
