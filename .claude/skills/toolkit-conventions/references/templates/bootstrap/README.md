# Generator projektu

`python3 scripts/bootstrap-project.py --project <katalog> --config <profil.json>`
kopiuje wybrane mastery i ich lokalne zależności Markdown. Nie uruchamia
poleceń profilu, nie instaluje hooków, nie zmienia konfiguracji Git i nie
wdraża aplikacji. Wymaga Python 3.9+ i blokad katalogowych macOS/Linux.
Katalog nadrzędny projektu musi istnieć. Wyjście leży poza źródłem toolkitu.

## Konfiguracja

Punkt wyjścia: [example.json](example.json). Pola obowiązkowe:

- `name`, `stack`: rzeczywista nazwa i stos, po jednej linii;
- `ci`: jawnie `local-first` albo `hosted`;
- `production`, `multi_agent`: jawne wartości logiczne;
- `security_context`: projektowe granice, wejścia, walidacja, uprawnienia
  i miejsca wymagające kontroli — nie zgadywane nazwy helperów;
- `verification_commands`: niepusta lista poleceń jako tablice argv.

`setup_commands` to opcjonalna lista jawnie zaakceptowanych poleceń
przygotowania. Polecenia pochodzą od właściciela; generator ich nie
weryfikuje jako bezpiecznych ani nie wykonuje przy generowaniu.
`hosted` wymaga `hosted_provider: "github"`; innych dostawców ten adapter
nie obsługuje. Przykład zmiany profilu: `production: true` dodaje wskazanie
procedur produkcyjnych, nie dostęp do serwera.

Profil local-first przygotowuje wykonywalny `.githooks/pre-push`, który
wywołuje `python3 .claude/run-checks.py`. Instalację `core.hooksPath`
przeprowadza właściciel po review; generator nie nadpisuje istniejącego hooka.
Profil hosted tworzy workflow GitHub Actions z checkoutem przypiętym pełnym
SHA i uruchomieniem `python3 .claude/run-checks.py --setup`. Potrzebne
zależności i kontrole projektu muszą zostać podane w konfiguracji. Błąd
polecenia lub brak programu daje niezerowy wynik; kolejne kontrole wtedy
nie są wykonywane.

Multi-agent dodaje role i kontrakt work-graph. Builderzy nadal potrzebują
osobnych worktree oraz faktycznych ograniczeń narzędzi na danej platformie;
skopiowanie pliku z nazwą roli nie tworzy sandboxa ani nie uruchamia agenta.

Pełne źródło wydania dołącza `security-check.py` z katalogiem `security/`
oraz dla roju `agent-runtime.py` z `agent-runtime/`. Cały `codex-builder/`
zawiera także watchdog. Źródła i grupy są w [profiles.json](profiles.json).
Brak całej grupy jest jawny w `unavailable_integrations`, nie stanowi
potwierdzenia dostępności mechanizmu. Częściowo obecna grupa blokuje
bootstrap jako niespójne źródło. Generator nie wymyśla brakujących adapterów.

## Ochrona istniejących plików

`--check` nie zapisuje: kod 0 oznacza brak różnic, 1 planowane zmiany,
2 błąd lub konflikt. Zwykłe generowanie ma kod 0 przy sukcesie i 2 przy odmowie.

`.claude/bootstrap-files.json` zawiera sumy kontrolne plików zarządzanych
przez generator. Nie jest backlogiem ani rejestrem statusów adopcji.
Niezarządzana kolizja, zmieniony lub usunięty plik zarządzany i symlink
w docelowej ścieżce powodują odmowę przed rozpoczęciem zapisu. Lokalne pliki
spoza manifestu pozostają. Generator nigdy nie usuwa starego pliku na podstawie
samego edytowalnego manifestu. Gdy nowy profil nie potrzebuje poprzedniego
wyjścia (np. lokalnego hooka), zachowuje je i odmawia generowania do jawnego
rozstrzygnięcia pliku oraz jego wpisu w manifeście przez operatora.

Blokada katalogu nadrzędnego serializuje współpracujące generatory.
Pojedynczy zapis pliku jest atomowy; cała generacja wielu plików nie jest
transakcją odporną na przerwanie procesu. Po przerwaniu niespójne pliki są
wykrywane i wymagają jawnego rozstrzygnięcia, nie cichego nadpisania.
Podczas generacji nie powinien działać inny edytor tych samych plików.

## Lock i odbiór

`.claude/toolkit.lock` używa formatu toolkit-sync: wersja, źródło, SHA
bez userinfo, query i fragmentu URL oraz cztery kolumny: sha kopii, ścieżka projektu, źródło mastera, sha mastera.
`toolkit_adoption initial` oznacza pierwszą kopię, a nie udany audyt aplikacji.
Projektowy kontekst Security Reviewera ma osobny wpis `toolkit.local`, aby
aktualizacja nie skasowała wymaganego uszczegółowienia.

Generator zwraca `adoption: pending_project_verification` i przygotowuje
checklistę odbioru według [protokołu adopcji](../../conventions/toolkit-sync.md). Nie oznacza jej jako
ukończonej. `toolkit-sync.sh check` sprawdza zgodność kopii, nie zastępuje
kontroli projektu i niezależnego review. Upgrade do innego VERSION lub
istniejąca historia adopcji pozostają domeną prepare-update/update;
generator odmawia restemplowania tej historii jako initial.

Regresje: `python3 scripts/test-bootstrap-project.py`.
