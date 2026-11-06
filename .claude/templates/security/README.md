# Wykonawcze dowody bezpieczeństwa

Security Reviewer i Red Team pozostają rolami odczytu. Ten adapter uruchamia
host z upoważnieniem do wskazanego repozytorium. To kolektor dowodów,
nie sandbox, kompletny audyt ani automat uruchamiający exploity.
Wymagania: Python 3.9+, security-check.py i sąsiedni codex-builder/watchdog.py;
wybrany zewnętrzny skaner musi być wcześniej zainstalowany i zaufany.

## Inventory i źródła podatności

```sh
python3 templates/security-check.py inventory --repo <repo> --output <runtime>/inventory.json
python3 templates/security-check.py sync-kev --output <runtime>/kev.json
python3 templates/security-check.py advisories --inventory <runtime>/inventory.json --kev <runtime>/kev.json --online --output <runtime>/advisories.json
```

Inventory rozpoznaje npm lock v2/v3 albo CycloneDX JSON (`--sbom <plik>`).
Purl wspieranych ekosystemów językowych daje dokładną nazwę i wersję do OSV.
Linki workspace, nieznane wersje i komponenty OS są jawnie niesprawdzone.
Dla OS/obrazów użyj skanera znającego dystrybucję i backporty, np. Trivy;
nie dopasowuj podatności po samym fragmencie nazwy.

`--online` oznacza wysłanie tożsamości pakietów do publicznego API OSV,
bez kodu. Maksymalnie 500 pakietów, budżet 180 s plus trwające żądanie do
30 s. Przekroczenie lub błąd to UNVERIFIED. KEV jest pobierany z oficjalnego
repozytorium CISA; źródło starsze niż 7 dni jest odrzucane. KEV nie jest
bazą wszystkich CVE. Brak KEV daje unknown, nie „niewykorzystywana”.

Wynik rozróżnia dopasowanie wersji i nieprzetestowaną wykorzystywalność.
Kandydackie wersje naprawione trzeba dobrać do właściwej linii i wymagań
projektu, następnie ponownie przeskanować nowy lock/obraz. Nie traktuj
listy wszystkich fixów różnych zakresów jako nakazu instalacji najstarszego.

## Uruchomione skanery

```sh
python3 templates/security-check.py scan --scanner trivy --target <repo> --output <runtime>/trivy.json
python3 templates/security-check.py scan --scanner semgrep --target <repo> --rules <lokalne-przejrzane-reguly> --output <runtime>/sast.json
python3 templates/security-check.py scan --scanner skill-scanner --target <katalog-skilla> --output <runtime>/skill.json
```

Wyjście musi leżeć poza skanowanym katalogiem. Skanery dostają stałe profile
argv, timeout grupy procesów i osobny host receipt z SHA, kodem zakończenia,
hashem raportu, profilu, pliku lokalnych reguł oraz launchera skanera.
Hash launchera nie jest hashem wszystkich jego bibliotek i bazy podatności.
Surowe raporty i znalezione sekrety nie trafiają do
korpusu. Kody: 0 = brak ustaleń w sprawdzonym zakresie, 1 = ustalenia,
2 = blokada/błąd/niesprawdzony zakres. INFO skanera skilli również pozostaje
w raporcie; samo wyjście 1 nie ustala polityki blokowania merge.

Trivy pokrywa SCA i IaC, Semgrep wyłącznie wskazane reguły SAST. Profil
skill-scanner używa analizatorów lokalnych, bez LLM/AI Defense/VirusTotal;
sprawdza również skład uruchomionych analizatorów. Nie zastępuje skanu
sekretów w historii, uprawnień, logiki biznesowej ani aktywnego DAST.
Brak wymaganego narzędzia i błędny/niepełny raport nigdy nie są PASS.

Skaner dostaje prywatną kopię źródeł. Fingerprint obejmuje treść i tryby
plików, również dirty/untracked; sam SHA nie przypisuje wyniku do zmian
roboczych. Porównanie przed i po obejmuje źródło, kopię, HEAD/status Git,
reguły oraz launcher. Zmiana, brak raportu, stary plik, timeout, niezgodny
kod wyjścia lub brak analizatora daje `unverified` z receipt. Żaden skaner
nie zapisuje `--output` pod ścieżkę kontrolowaną przez badane źródło:
stdout/stderr są otwarte przez host, a promocja i cleanup kotwiczone w
deskryptorach katalogów. Podmiana rodzica wyjścia również unieważnia wynik.

Granice kopii: 10 000 wpisów plików/katalogów, głębokość 64,
64 MiB łącznie, 16 MiB na plik. Pomijane
nazwy na każdej głębokości: `.git`, `.worktrees`, `node_modules`.
Symlinki i pliki specjalne są nieobsługiwane; kolektor ich nie śledzi i
nie wydaje wtedy zielonego wyniku. Dla większego repo wybierz jawny podzakres
lub oddzielny adapter. Nie jest to kontrola historii ani runtime permissions.
Timeout dotyczy procesu skanera; limit całego kroku zapewnia nadrzędny runtime.

Kolektor uruchamiaj z przejrzanej, zaufanej instalacji toolkitu, w runnerze
bez sekretów produkcji. Profil lokalnych analizatorów i odfiltrowane zmienne
konfiguracji nie zastępują sandboxa/egress policy. Trivy może pobrać publiczną
bazę; `--offline-scan` wyłącza dodatkowe API rozpoznawania zależności.

## Powtarzalny, opcjonalny pomiar skanera skilli

Sprawdzona wersja: `cisco-ai-skill-scanner==2.2.0`, osobny Python 3.13.
Instalacja jest osobnym, świadomym krokiem operatora, bez globalnych hooków:

```sh
uv venv --python 3.13 <runtime>/scanner-venv
uv pip install --python <runtime>/scanner-venv/bin/python cisco-ai-skill-scanner==2.2.0
python3 templates/security-check.py measure-skills --binary <runtime>/scanner-venv/bin/skill-scanner --output <runtime>/skill-comparison.json
```

Komenda tworzy dwa syntetyczne przypadki: poprawny skill i skill żądający
eksfiltracji z plikiem przykładowego payloadu. Payload nigdy nie jest
wykonywany. Rozlicza TP/TN/FP/FN oraz próby nieważne przy progu HIGH;
INFO zostaje widoczne, ale nie jest fałszywym alarmem na tym progu.
Próbka dwóch przypadków nie mierzy recall ani bezpieczeństwa całego korpusu.
Wymagane są wszystkie cztery lokalne analizatory: static_analyzer, bytecode,
pipeline, correlation; nieznany/zewnętrzny lub brakujący daje UNVERIFIED.
Wywołanie jest opt-in, nie częścią każdego commita ani testów offline.
Format i konfigurację opisuje [oficjalny skill-scanner](https://github.com/cisco-ai-defense/skill-scanner).

## Testy działającej aplikacji

NVD/CVE/OSV są źródłami opisów podatności, nie uniwersalną biblioteką
bezpiecznie uruchamialnych ataków. Zasób → komponent/wersja → zgodność
konfiguracji → priorytet → dobrany test → dowód → naprawa → retest.
Skany bez logowania nie sprawdzają reguł dostępu między rolami użytkowników.

Projekt zapisuje cele stagingu/labu, właściciela upoważnienia, dozwolone
operacje, role testowe bez prawdziwych danych, limit czasu/zapytań, warunek
stop i wybrane wersje/hash testów. Dopiero wtedy host uruchamia np. ZAP
lub wybrane przejrzane szablony Nuclei. Bez wskazanego środowiska nie ma
aktywnego testu. Żaden adapter tutaj nie skanuje automatycznie serwerów
z backlogu ani nie pobiera/uruchamia PoC z internetu. Odbiór DAST jest
odrębny od poprawnego działania kolektora i od read-only review kodu.
