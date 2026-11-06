# Cloudflare Security Audit w claude-toolkit

Źródło: [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill/tree/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8),
commit `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`, import 2026-11-05.
Licencja: [MIT](LICENSE), z zachowanym copyright Cloudflare, Inc.
[UPSTREAM.json](UPSTREAM.json) zapisuje SHA-256 oryginałów i lokalnych kopii.

Import wykonano helperem skill-installer z jawnym `--dest <checkout>/skills`
i przypiętym `--ref`. Zachowano cały katalog skilla, schemat, oba walidatory
oraz ich oryginalne testy. Dodano licencję z korzenia tego samego commita.
Nie instalowano ani nie aktywowano skilla globalnie w profilu użytkownika.

## Rola i uprawnienia

To procedura pełnego audytu koordynowanego przez sesję główną, a nie nowa
definicja uprawnień Security Reviewera. Domyślny guidance mode dobiera
istotne fragmenty; samo wczytanie skilla nie zleca pełnych sześciu faz,
uruchamiania roju ani tworzenia raportów. Pełny tryb wymaga zlecenia
odpowiadającego zakresowi opisanemu w SKILL.md.

| Termin upstream | Odpowiednik w toolkicie | Uprawnienia |
|---|---|---|
| Parent | główny orchestrator | zapis backlogu i współdzielonych artefaktów audytu w dozwolonym runtime |
| research | Scout | odczyt wskazanych źródeł; bez Bash/Edit/Write |
| general — source hunting | odseparowany hunter/Scout | odczyt źródeł; wyniki do parenta |
| general — bounded execution | ograniczony wykonawca bezpieczeństwa | wyłącznie zadany test w rzeczywiście izolowanym runtime |
| fresh verifier | niezależny Reviewer/Security Reviewer | odczyt źródeł i dowodów; bez naprawiania własnego findingu |

Nie mapuj nazwy `general` automatycznie na agenta o szerokim zestawie
narzędzi. Jeśli platforma nie wymusza zapisu wyłącznie do przypisanego
scratch, rola odczytu zwraca wynik parentowi, który zapisuje artefakt.
Nie dawaj jej szerokiego Write/Bash pod warunkiem opisowym. Read-only
reviewer może korzystać z przeglądu odizolowanego pakietu plików; dostępność
takiego adaptera i faktycznie udostępnione narzędzia sprawdza host.

Kod celu uruchamia się tylko przy wszystkich kontrolach upstream:
OS-enforced sandbox, brak zewnętrznej sieci, oczyszczone środowisko,
kontrolowane zapisy i niskie limity zasobów oraz czasu. Worktree, watchdog,
lista narzędzi lub deklaracja modelu samodzielnie nie tworzą tego sandboxa.
Bez którejkolwiek kontroli pozostaje odczyt źródeł oraz `needs_validation`
z konkretnym blockerem, bez udawania wykonania reprodukcji.

Nie zmieniaj środowiska ani katalogu domowego procesu hosta na potrzeby
testu. Izolowany proces dostaje własne bezpieczne ustawienia dopiero od
zaufanego launchera sandboxa; hostowe profile, sekrety, sockety i usługi
nie są mu montowane. Pobieranie zależności, żywe serwery i płatne API nie
są częścią tej metody. DAST z osobnym zakresem środowiska jest odrębnym
zadaniem; w tym imporcie nie ustalono żadnego celu serwerowego.

## Stan pracy i znaczenie wyniku

Jeden wpis backlogu wskazuje zadanie audytu. Runtime coverage-ledger
rozlicza jego jednostki pokrycia, nie jest drugim backlogiem produktu.
Parent przenosi findingi i follow-upy do backlogu z dowodem i ID audytu;
otwarte jednostki, `needs_validation` i przerwany budżet pozostają jawne.
Zmiana tematu nie zamyka brakujących etapów. Nie uruchamiaj równoległych
zapisów do wspólnych findings/report/ledger.

Źródło dowodu obejmuje oceniony commit i stan dirty. Przy lokalnym skanie
powiąż raport z treścią źródeł, np. fingerprintem z receipt kolektora,
a nie samym SHA przy zmienionych plikach. Zachowaj istniejący schemat
findings i coverage-ledger; dodatkową tożsamość snapshotu można utrwalić
w metadanych runu i odsyłaczach do dowodów.

PASS walidatora oznacza poprawną strukturę i lokalne inwarianty danych,
nie prawdziwość wszystkich findingów ani bezpieczeństwo aplikacji.
Pusty findings.json, szybki/scoped profil i zielone testy nie potwierdzają
pełnego pokrycia. Potwierdzone luki wymagają świeżej niezależnej weryfikacji;
Builder naprawia, a Reviewer ponownie sprawdza nową rewizję.

Wszystkie surowe raporty, prompty, logi i reprodukcje z danymi celu zostają
poza korpusem toolkitu. Budżet i kontrola zaległych etapów w SKILL.md
obowiązują; nie podnoś liczby agentów, poziomu modelu ani liczby powtórek
tylko dlatego, że ta procedura jest dostępna.

## Lokalne adaptacje i sprawdzenie

Zmiany względem przypiętego upstream:

- SKILL.md — dwujęzyczny opis, compatibility, license, metadata.version i odsyłacz
  do tej integracji; metoda sześciu faz i wszystkie companion files zachowane.
- LICENSE — kopia niezmienionej licencji MIT z korzenia repozytorium.
- UPSTREAM.json, LOCAL-REVIEW.md i ten plik — pochodzenie, hashe, mapa ról,
  granice wykonania i ocena kontekstu sygnałów analizatora.

Po przeglądzie źródeł można uruchomić oryginalne testy walidatorów:

```sh
node --test skills/security-audit/validate-findings.test.cjs skills/security-audit/validate-coverage-ledger.test.cjs
```

Testy używają Node built-ins, własnych plików tymczasowych i lokalnych
procesów walidatorów. Nie wykonują badanego kodu ani prób serwerowych.
Przy aktualizacji najpierw przejrzyj zmianę upstream i licencji, potem
zaktualizuj pin/manifest oraz sprawdź walidatory i adaptacje. Lokalny skan
analizatorami deterministycznymi jest dowodem pomocniczym; wzmianki o
atakach w tej defensywnej dokumentacji wymagają oceny kontekstu.
