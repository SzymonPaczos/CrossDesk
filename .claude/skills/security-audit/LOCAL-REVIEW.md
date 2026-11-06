# Przegląd importu i kontekstu sygnałów skanera

Data: 2026-11-05. Zakres: import przypiętego commita wskazanego w
[UPSTREAM.json](UPSTREAM.json), lokalna adaptacja wejścia oraz oryginalne
walidatory i testy. Ocenił wykonawca importu; nie jest to niezależny
Security Review całej zintegrowanej gałęzi ani audyt aplikacji właściciela.

## Sprawdzenia

- Zachowano 20 oryginalnych plików skilla i niezmieniony MIT LICENSE
  z tego samego commita. Każdy ma hash oryginału i lokalnej kopii.
- Walidatory używają Node built-ins, parsują JSON z ograniczeniem rozmiaru,
  głębokości, liczby elementów i liczby błędów. CLI otwiera wejście
  no-follow/nonblocking i sprawdza typ zwykłego pliku.
- Testy uruchamiają lokalne walidatory przez argument vector, bez powłoki,
  i tworzą własne dane w katalogach tymczasowych. Nie ma pobierania kodu,
  wywołań sieci ani wykonania aplikacji celu.
- Oryginalne testy obu walidatorów: 65 PASS, 0 FAIL, 0 SKIP.
  Kontrola Agent Skills: valid. To weryfikacja narzędzi i formatu,
  nie dowód bezpieczeństwa wszystkich możliwych wejść lub aplikacji.

## Sygnały Cisco 2.2.0

Pierwszy lokalny przebieg czterech deterministycznych analizatorów dał
18 sygnałów: 12 CRITICAL, 5 LOW i 1 INFO. Receipt potwierdził niezmienny
snapshot; nie używano LLM ani analizatorów chmurowych. Surowy raport
i receipt pozostały poza korpusem.

| Reguła | Plik i wystąpienia | Ocena kontekstu |
|---|---|---|
| COMMAND_INJECTION_JS_CHILD_PROCESS | validate-coverage-ledger.test.cjs — import i pięć spawnSync | Stałe lokalne Node/mkfifo z argv; brak shell:true i konkatenacji polecenia powłoki |
| COMMAND_INJECTION_JS_CHILD_PROCESS | validate-findings.test.cjs — import i pięć spawnSync | Stałe lokalne Node/mkfifo z argv; testowane dane pozostają JSON-em |
| DATA_EXFIL_JS_FS_ACCESS | oba pliki testów — po dwa writeFileSync | Zapis własnych tymczasowych fixtures, bez sieciowego sinka |
| DATA_EXFIL_JS_FS_ACCESS | validate-findings.cjs — readFileSync | Odczyt zaufanego sąsiedniego report-schema.json, nie ambient secrets |
| MANIFEST_MISSING_LICENSE | SKILL.md | Licencja MIT była dołączona; dodano również standardowe pole license |

W tych konkretnych przypiętych plikach obecność child_process/fs nie
ustanawia ścieżki command injection ani eksfiltracji. Nie potwierdzono
12 krytycznych exploitów; są to sygnały wzorców wymagające oceny kontekstu.
Nie usunięto testów i nie wyciszono reguły globalnie. Ocena dotyczy wyłącznie
tej wersji, wskazanych plików i ich hashy; zmiana upstream wymaga ponownego
przeglądu. Pozostałe ograniczenia skanera nadal obowiązują.

Import nie daje agentom szerszych narzędzi. Source hunting jest odczytem,
a wykonanie kodu celu wymaga wszystkich kontroli opisanych w SKILL.md
i TOOLKIT-INTEGRATION.md. Brak środowiska izolowanego oznacza
needs_validation, nigdy symulowane potwierdzenie ataku. Nie wskazano celu
serwerowego i nie wykonano testów penetracyjnych.
