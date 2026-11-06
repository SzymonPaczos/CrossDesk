# Kontrola głęboka — punkty oceny (Krok 2 skilla `weekly-audit`)

Wczytywane na żądanie, przy Kroku 2 audytu. Punkty mają określony zakres;
postmortem najpierw ocenia istniejącą ochronę, a nowy punkt wymaga wykazanej
luki. Data przy części punktów wskazuje pochodzenie, nie obowiązek ich mnożenia.

Odsyłacze `konwencja:<plik>.md` rozwiązuje Krok 00 skilla: osobno dla
pliku, według locka i mapy AGENTS.md. Audyt odczytuje przyjętą kopię;
brak lub sprzeczne lokalizacje zgłasza bez zmiany układu projektu.

Skrypt liczy, Ty oceniasz. Przejrzyj i oceń:

1. **Bezpieczeństwo** — nowe endpointy bez rate-limit/walidacji, XSS (HTML
   z bazy renderowany bez sanityzacji), sekrety w repo, raw SQL z interpolacją
   user-inputu.
2. **Slop** — hardcoded dane w UI udające prawdziwe, mocki podane jako dane,
   funkcje oznaczone "gotowe" gdy są zaślepkami. Dla każdego trwałego
   `EmptyState` prześledź producer chain: UI → query → DB → loader; brak
   producenta danych jest tym samym kłamstwem piętro niżej. Odróżniaj
   fallback tymczasowy (producent istnieje, dane w drodze) od stanu
   permanentnego (producenta NIE MA — wydmuszka udająca gotową funkcję).
   **Producent ≠ jednorazowy backfill:** ustal, kto pisze do tego miejsca
   przy KAŻDYM przebiegu, nie czy cokolwiek kiedyś je zapełniło — pole
   z backfillem, którego nikt nie odświeża, po cichu starzeje się względem
   nowych danych. Obietnicę producenta z komentarza migracji albo docstringu
   („loader robi X przy syncu") weryfikuj greppem; komentarz to nie kod.
   Sprawdź też realny stan (`count`, świeżość `max(updated_at)`), nie samo
   istnienie łańcucha. (Wkład z JawnePanstwo, 2026-07-12.)
3. **Jakość testów** — nie *ile*, ale czy testują **właściwe** rzeczy:
   krytyczne ścieżki bez pokrycia, testy które nic nie weryfikują, skipped
   bez uzasadnienia.
4. **Architektura** — drift dokumentacja↔kod, duplikaty, martwe pola schematu,
   nieużywane eksporty, niespójne wzorce. Osobno **dryf twierdzeń
   liczbowych**: liczby i nazwy w prozie reguł i map („N migracji",
   „M warstw gate'a", nazwa biblioteki sanityzacji) starzeją się przy każdej
   zmianie i nikt ich nie pilnuje. Wyrywkowo **przelicz je komendą**, nie
   przepisuj z dokumentu do raportu; przy okazji dopisz tę komendę obok
   liczby, żeby następny audyt miał czym zmierzyć. Automat sprawdza zwykle
   obecność nazwy, nie prawdziwość opisu.
5. **Dead code** — zweryfikuj heurystykę skryptu greppem (sub-agenty mylą
   base-classy z dead code — zawsze potwierdź).
6. **Zgodność z rejestrem decyzji** (pełny rejestr `decisions-register.md`
   i skróty `rules/decisions*.md`; w projekcie bez podziału — `decisions.md`)
   — złamana decyzja ma wpływ `critical` albo `high`, zależnie od skutku.
7. **Skille, MCP i koszt kontekstu** — czy pojawiło się coś, co przyspieszy
   pracę, i czy kontekst agentów nie rośnie (`konwencja:context-budget.md`).
   a. **Budżet bajtów** komendą z §2 konwencji: pliki ładowane zawsze do
      15 KB; `handoff.md` do 8 KB i jedna sekcja (`grep -c '^## '`);
      preambuła buildera nieinteraktywnego ok. 4 KB; suma opisów skilli
      widocznych w sesji (`description:` w `SKILL.md` i lista z promptu
      systemowego). Przekroczenie → pozycja w backlogu.
   b. **Koszt sesji z 7 dni.** Codex (`~/.codex/sessions/<rok>/<mies>/<dzień>/`):
      mediana wejścia na żądanie z unikalnych zdarzeń `token_count` —
      liczniki się powtarzają, więc deduplikacja po sumie:

      ```sh
      set -o pipefail
      rg '"type"\s*:\s*"token_count"' "$f" | jq -s '[.[]|.payload.info|select(.!=null)]
        |unique_by(.total_token_usage.total_tokens)|map(.last_token_usage.input_tokens)|sort
        |{n:length,median:((.[((length-1)/2|floor)]+.[(length/2|floor)])/2)}'
      ```

      oraz sesje powyżej 60 żądań, liczba wznowień i udział wysokiego
      rozumowania (pole `effort`: `grep -hoE '"effort":"[a-z]+"' | sort | uniq -c`).
      Claude (`~/.claude/projects/<projekt>/*.jsonl`): mediana wejścia
      razem z tokenami cache, deduplikacja po identyfikatorze wiadomości:

      ```sh
      set -o pipefail
      jq -r 'select(.message.usage != null) | [.message.id,
        ((.message.usage.input_tokens//0) + (.message.usage.cache_read_input_tokens//0)
         + (.message.usage.cache_creation_input_tokens//0))] | @tsv' "$f" \
        | sort -u -k1,1 | cut -f2 | sort -n \
        | awk '{a[NR]=$1} END{if(NR) print NR, (a[int((NR+1)/2)]+a[int(NR/2)+1])/2}'
      ```

      Koszt licz na całe zadanie razem z recenzjami, nie na sesję; przy
      porównaniu dwóch trybów napisz, czy zadania były porównywalne.
   c. **MCP i skille** — użycie w tygodniu (`grep -l 'mcp__<serwer>'` po
      dziennikach sesji), dublowanie narzędzi wbudowanych; nieużywane od
      2 tygodni → propozycja wyłączenia.
   d. **Czy każda reguła wciąż zarabia na swoje miejsce** — dla reguł
      z plików ładowanych zawsze i skrótu decyzji: czy egzekwuje ją bramka
      (tak → proza do jednej linii z nazwą bramki); czy była przywołana
      w ostatnich 30 dniach (`git log --since='<data> 00:00' --grep`,
      recenzje, historia); czy duplikuje inną; czy to wiedza ogólna modelu
      (opinia recenzenta, oznaczona jako opinia). Wynik: lista do skrócenia
      z rekomendacją; zmiana decyzji należy do właściciela.
   e. Wynik idzie do pola `CONTEXT:` raportu.
   f. **Efekt procesu** — powiąż zmiany instrukcji, audyty i powtórki testów
      z rezultatami z Kroku 0a. Mniejszy kontekst i więcej zielonych testów
      mogą współistnieć z porzuconym X3/X4. Liczba plików lub commitów nie
      mierzy czasu pracy; brak telemetrii nazwij `n/a`. Nowy obowiązek wymaga
      uzasadnienia skutkiem i oceny kosztu, a duplikat propozycji usunięcia.
8. **Gate'y** — czy `SKIP_*` jest per-warstwa; czy `exit 0` nie omija dalszych
   checków; czy gate sprawdza zmianę, a nie dowolny istniejący test; czy brak
   narzędzia/DB nie daje fałszywego sukcesu. Porównaj z
   `konwencja:rules-as-gates.md`. **Gate mierz, nie czytaj**: lektura
   hooka wykrywa to, czego się spodziewasz, więc warunki wczesnego `exit 0`
   wyciągaj z ŻYWEGO pliku i sprawdzaj testem, że wymieniają każdą flagę,
   na którą reaguje którakolwiek warstwa niżej (tak w JawnePanstwo zginęła
   cała warstwa dla pushy dotykających jednego katalogu). Wykluczenia
   ścieżek w skanie sekretów muszą być **zakotwiczone** — substring `test`
   łapał `latest`, więc plik `…_latest_….sql` był bezkarny. Skan sekretów
   testuj po jednej klasie credentiala na commit.
9. **Supply chain** — lockfile, dependency bot/cooldown, secret protection,
   OIDC/trusted publishing i release/deploy według `konwencja:ci-cd.md`.
10. **Delivery** — wiek aktywnych branchy/WIP, szybki lane CI (<10 min jako
    cel), build-once/same digest, poprzedni artifact, health gate, bake,
    rollback drill, feature-flag expiry, SLO/error budget i release evidence.
    Porównaj z `konwencja:progressive-delivery.md`.
11. **Provenance zmiany** — próbka nietrywialnych commitów zawiera `Intent`,
    `Task-Ref`, `Gates`; task brief zgadza się z diffem, a review
    record/check jest związany z niezmienionym SHA. Atrybucja AI jest
    opcjonalna zgodnie z D-019; jeśli projekt wymaga jej we własnym
    rejestrze decyzji, sprawdź spełnienie tego wymogu.
12. **Vulnerability response** — kanał disclosure, wspierane wersje, owner
    triage, otwarte advisories i root-cause→test/gate po incydencie. Dla
    prywatnego repo dopuszczalny jest prywatny runbook zamiast `SECURITY.md`.
13. **Jedna derywacja + uczciwe procenty** — byt renderowany w ≥2 widokach
    czerpie stan z JEDNEJ kanonicznej funkcji derywacji, nie liczy go osobno
    per widok (osobne wyliczenia = widoki, które się rozjadą). Każdy procent
    bez mianownika renderuje „Brak danych" — nigdy `x/0` ani `NULL→0`
    udające zero. Odróżnij test prawdziwy od **samopotwierdzającego**: test
    karmiący kontrakt inny niż produkcja (surowy enum zamiast etykiety,
    UPPERCASE zamiast lowercase z bazy) jest zielony na syntetyce i
    przepuszcza dokładnie ten bug, którego pilnuje — porównaj kształt
    fixture'a z realnym outputem producenta. (Wkład z audytu JawnePanstwo,
    2026-07-11 i 2026-07-08.)
14. **Higiena repo i ekspozycja na utratę danych** (wkład z audytu floty
    2026-08-01; 4/6 agentów niezależnie wskazało punkt a). Sprawdź:
    a. **Ekspozycja na utratę** — `git branch -vv` (gałęzie ahead/bez
       upstreamu), `git stash list`, `git worktree list --porcelain | grep
       prunable`, wiek najstarszego niepushowanego commita — oceniane łącznie
       z posturą backupu maszyny (D-005). W profilu local-first bez backupu to
       de facto check ryzyka utraty danych, nie kosmetyka.
    b. **Dane osobowe jako osobna klasa** (obok sekretów): `git ls-files |
       grep -iE 'legitymacja|dowod|pesel|zaswiadczenie|_b64'` + skany/PDF
       z PII poza katalogami dozwolonymi lokalną decyzją projektu.
    c. **Dysk vs git** — zawsze zestawiaj `du -sh` z `git count-objects -vH`
       i listą największych blobów historii (`git rev-list --objects --all |
       git cat-file --batch-check`); inaczej fałszywy alarm krytyczny albo
       przeoczony realny (baza commitowana N razy).
    d. **Integralność referencyjna** — każda ścieżka w trackowanych
       `.claude/*.md` (backlog, status) istnieje i jest trackowana albo
       świadomie ignorowana; martwy link do „jedynej kopii" ma wpływ `critical`.
    e. **Świeżość audytu** — porównaj `AUDITED_REVISION` z bieżącym HEAD
       i liczbą merge'y pomiędzy (cały silnik potrafi prześlizgnąć się między
       audytami bez wpisu).
    f. **Gotowość publikacyjna** dla „docelowo publiczne": LICENSE,
       SECURITY.md, czystość historii.
    g. **Odtwarzalność środowiska/gate'ów** — `requirements.txt`/lockfile dla
       venv/node_modules; każdy scheme z `local-ci.sh` obecny w
       `xcshareddata/xcschemes/` (świeży klon nie ma `xcuserdata`).
    h. **Wygasłe credentiale** — grep `Expires|EXPIRES_ON` w plikach env
       vs bieżąca data.
    i. **Wiek najstarszej pozycji w `Do wykonania`** — sam werdykt FAIL nie
       wymusza ruchu; starzenie kolejki trzeba mierzyć niezależnie od wpływu.
    j. **Kandydaci na mechaniczne gate'y** (`rules-as-gates.md`, tryb
       raportowy): pliki `.bak`/`BACKUP`/`*_b64` tracked; zmergowane gałęzie
       do skasowania + duplikat `master`/`main`; egzekwowanie lokalnych
       decyzji projektu (np. „skany tylko w sources/").

15. **Aktualność zależności i runtime'ów** — uruchom bramkę aktualności
    (`templates/dependency-currency.sh` albo projektową kopię) i zestaw wynik
    z poprzednim audytem. Runtime po EOL ma wpływ **critical** — po tej dacie nie ma
    poprawek bezpieczeństwa. Runtime z EOL bliżej niż 180 dni bez zaczętej
    migracji ma wpływ `high`. Wzrost liczby przeterminowanych zależności bezpośrednich
    względem poprzedniego audytu ma wpływ `low` z zapadką. Wynik `n/a` (brak
    narzędzia, brak sieci) raportuj jako `n/a`, **nigdy jako zero ustaleń** —
    reguły w `konwencja:dependency-currency.md`.

16. **Delivery/deploy honesty** (wkład z JawnePanstwo, 2026-07-12 — cała
    warstwa delivery nie miała właściciela w planie audytu i dała cztery
    znaleziska o wpływie `high`
    naraz). Przeczytaj KRYTYCZNIE skrypt deployu, compose produkcyjny i
    konfigurację reverse-proxy:
    a. **Smoke musi móc zafailować.** Sprawdź, w co realnie trafia — żądanie
       bez ciasteczka podglądu dostaje 200 od warstwy ochronnej albo statyki
       nawet przy martwej aplikacji. Smoke, który nie potrafi zafailować,
       nie jest smokiem, tylko rytuałem; asercja ma dotyczyć markera
       generowanego przez aplikację.
    b. **Build once** — artefakt testowany = artefakt wdrażany. Budowanie
       obrazu NA serwerze łamie to nawet przy identycznym Dockerfile.
    c. **Obrazy zewnętrzne przypięte** do wersji/digestu, nie do pływających
       tagów typu `*-latest`.
    d. **Nowa usługa w compose** — czy nie wnosi literalnych credentiali do
       repo.
17. **Czy mamy artefakt KANONICZNY, nie tylko jakiś** (wkład z JawnePanstwo,
    2026-07-27 — audyty przez trzy miesiące chwaliły 92,86 % „pokrycia
    tekstem", podczas gdy w bazie nie było ANI JEDNEGO egzemplarza
    dokumentu, który jest w tej dziedzinie wiążący; użytkownik przy każdej
    pozycji dostawał wersję roboczą). Wszystkie warstwy wyżej pytają „czy to,
    co pokazujemy, ma producenta / czy liczba jest liczona" — żadna nie pyta
    **„czy pokazujemy właściwy dokument"**. Pokrycie liczone po zbiorze,
    który zbieramy, jest z definicji ślepe na typ, którego nie zbieramy
    wcale. Dlatego dla każdego bytu z dokumentami: (a) nazwij **źródło
    autorytatywne** dziedziny i sprawdź `GROUP BY` po typie, czy w ogóle
    istnieje w bazie — **zero wierszy danego typu to znalezisko krytyczne,
    nawet przy 99 % „pokrycia"**; (b) sprawdź kolumny-wskaźniki do źródeł
    zewnętrznych (`*_url`, `*_id`) — czy konsument wykorzystuje je w pełni,
    czy marginalnie (tam autorytatywny tekst wisiał jeden endpoint obok
    i nikt go nie pobierał przez trzy miesiące).
18. **Czy artefakt DR daje się ODTWORZYĆ tym, czym byśmy go odtwarzali**
    (wkład z JawnePanstwo, 2026-07-30 — nocny backup produkcji był przez
    wiele tygodni nieodtwarzalny, a nikt tego nie wiedział, bo nikt nigdy
    z niego nie przywrócił bazy). Poprzednie warstwy pytają „czy producent
    istnieje" i „czy liczba jest uczciwa"; ta pyta, czy **kopia zapasowa
    jest kopią**. Mechanizm tamtej awarii: nieprzypięty meta-pakiet
    (`postgresql-contrib` bez wersji) dociągnął do obrazu klienty nowszej
    wersji głównej obok starszego serwera, `pg_dump` zaczął wskazywać na
    nowszy, a jego archiwum starszy `pg_restore` odrzuca wprost. Sprawdź:
    (a) **odtwórz** najnowszy backup do bazy jednorazowej i porównaj
    liczności z produkcją — nie poprzestawaj na tym, że plik istnieje i ma
    sensowny rozmiar; (b) czy klient robiący dump ma tę samą wersję główną
    co serwer (`pg_dump --version` wobec `SHOW server_version`, albo
    odpowiedniki twojego silnika); (c) grep po `Dockerfile`ach za pakietami
    klienta bazy **bez przypiętej wersji** (`postgresql-*`, `mysql-client`
    i podobne meta-pakiety) — meta-pakiet cicho zmienia, który plik binarny
    uruchamia backup; (d) czy backup leży gdziekolwiek poza maszyną, na
    której stoi baza. Ta warstwa jest komplementarna do rollback drillu
    z `progressive-delivery.md`: tamten ćwiczy powrót do poprzedniej WERSJI,
    ta — odzyskanie DANYCH.
19. **Czy mamy DRUGĄ OPINIĘ spoza pipeline'u** (wkład z JawnePanstwo,
    2026-08-14 — katalog pokazywał 499 osób w izbie mającej 460 miejsc,
    w tym troje zmarłych, przy WSZYSTKICH poprzednich warstwach na zielono).
    Powód jest strukturalny: warstwy 1–18 porównują **kod z kodem albo dane
    z tymi samymi danymi**. Żadna nie wykryje rozjazdu, co do którego nie ma
    drugiego zdania — nikt w repo nie wiedział, ile tych miejsc ma być.
    Dlatego: (a) dla każdego bytu o **publicznie znanej liczności albo
    znanym zakresie** (liczba miejsc, liczba jednostek administracyjnych,
    jedna osoba na stanowisku, daty kadencji, sumy kontrolne z oficjalnego
    źródła) ma istnieć asercja porównująca nasz stan z tą liczbą, trzymana
    w osobnym pliku testów-wyroczni; dopisywanie do niego jest celem, nie
    wyjątkiem; (b) **nadmiar ponad znaną liczbę to znalezisko krytyczne**,
    niedomiar bywa legalny (wakat) — asercja jest jednostronna; (c) znany,
    jeszcze nienaprawiony rozjazd zapisuj jako oczekiwaną porażkę w trybie
    ścisłym (`xfail(strict=True)` i odpowiedniki), z powodem — proza
    w backlogu zrobi się zielona sama, a marker ścisły wywali test, gdy
    rozjazd zniknie, i wymusi jego zdjęcie. Test-wyrocznia, który nigdy nie
    może zafailować, nie jest testem — ta sama zasada co smoke trafiający
    w warstwę ochronną (pkt 16a).
20. **Bramki jakości i definicja ukończenia** — katalog bramek istnieje, każda
    ma tryb (twarda/miękka) i właściciela, a odstępstwa są zapisane z terminem,
    nie milczące. Funkcjonalność „gotowa" bez spełnionej definicji ukończenia
    to znalezisko, nie kwestia gustu. Reguły:
    `konwencja:quality-gates-and-dod.md`.
21. **Bramki weryfikacji bezpieczeństwa** — które z SAST / SCA / skanu
    sekretów / IaC / DAST są skonfigurowane, która blokuje scalenie, a która
    tylko raportuje. Brak narzędzia raportuj jako `n/a`; narzędzie obecne, ale
    niepodpięte do bramki, jest gorsze niż jego brak, bo daje złudzenie
    pokrycia. Sprawdź inventory i wersje, świeżość źródeł OSV/CVE/KEV, SHA
    oraz rzeczywisty wynik skanera. Dopasowanie CVE nie jest dowodem exploitu,
    a brak trafień nie zamyka niesprawdzonych klas. Security Reviewer ocenia,
    host wykonuje skany; aktywna próba ma uzgodniony cel i zakres.
    Reguły: `konwencja:security-verification-gates.md`.
22. **Dowód z testu** — dla próbki napraw sprawdź dowód porażki badanego
    przypadku bez poprawki i zaliczenia po niej, z właściwej przyczyny.
    Audyt read-only korzysta z artefaktów; brak dowodu zapisuje jako brak.
    Nowy eksperyment należy do osobnego zadania z możliwością zmian.
    Reguły: `konwencja:test-evidence.md`.
23. **Gotowość PR i odpowiedź na review** — czy PR-y niosą preflight
    i odpowiedź na uwagi, czy scalanie odbywa się bez śladu review. Reguły:
    `konwencja:pull-request-review.md`.
24. **Topologia bramek pipeline'u** — przejdź procedurę audytu CI/CD:
    co jest naprawdę wymagane, kto może ominąć, czy któryś wymagany check może
    nigdy nie wystartować, czy bramki są fail-closed. W profilu local-first
    czytaj tę konwencję przez §11a (warstwy hooka zamiast jobów) — inaczej
    zaraportujesz „brak bramek" o repo, które ma ich kilkanaście. Reguły:
    `konwencja:ci-pipeline-architecture.md`.
25. **Zgłoszenia defektów** — czy defekty mają reprodukcję i dowód przed/po,
    czy giną w prozie. Zgłoszenie bez kroków reprodukcji wraca do zgłaszającego,
    nie do backlogu. Reguły: `konwencja:issue-reporting.md`.


26. **Zdrowie backlogu** — uruchom `templates/backlog-lint.sh`. Interesują cię
    trzy liczby, nie tylko kod wyjścia: `BACKLOG_OLDEST_P1_DAYS` rosnący
    monotonicznie między audytami znaczy, że kolejka jest fikcją;
    `BACKLOG_NO_GATE` większy niż jedna trzecia pozycji znaczy, że backlog
    zbiera życzenia zamiast usterek; `BACKLOG_OVERDUE_REVIEWS` niezerowy to
    odstępstwa, które wygasły i wróciły jako otwarte, choć nikt tego nie
    zauważył. Sam werdykt FAIL nie wymusza ruchu — te trzy trendy tak.

27. **Teksty interfejsu i dane, które w nim udają prawdziwe** — uruchom
    `templates/ui-copy-lint.sh` i wczytaj skill `teksty-ui`. Sprawdzasz trzy
    rzeczy, nie jedną: nowomowę z wagą 3, liczby i cytaty bez źródła
    w repozytorium, oraz **napisy o postępie bez ścieżki wyjścia** („Zapisuję…"
    które nie gaśnie przy błędzie kłamie tak samo jak wymyślona statystyka).
    Rosnący `UI_COPY_EXEMPT` znaczy, że katalog nie pasuje do dziedziny
    projektu — popraw katalog, nie dosypuj wyjątków.

28. **Stos agentowy: znane pułapki przed własną hipotezą** — jeśli projekt ma
    agenta, przejdź `references/agentic-znane-pulapki-2026-08.md` **w całości,
    zanim postawisz własną diagnozę**. Osiem pozycji, każda z objawem i dowodem;
    najtańsze pierwsze. Cztery wymagają wyłącznie grepa: ile miejsc kompiluje
    graf albo tworzy checkpointer (więcej niż jedno = dwa magazyny stanu), czy
    istnieje własna klasa dziedzicząca po klasie bazowej frameworka, czy magazyn
    w pamięci procesu wyszedł poza testy, czy pamięć długoterminowa jest osobna
    od magazynu wątku. Objaw „agent nie widzi kontekstu" ma co najmniej pięć
    różnych przyczyn — rozstrzyga asercja na stanie wątku (twardo) osobno od
    asercji na interfejsie (miękko).

29. **Czy stos jest pisany, czy wzięty** — wczytaj skill `agentic-apps`, sekcja
    „Kontrola przed napisaniem infrastruktury", i porównaj z katalogiem warstw
    w `references/agentic-harness-2026-08.md`. Dla każdej warstwy (trwałość
    stanu, pamięć długoterminowa, wzorce wieloagentowe, narzędzia, most do
    interfejsu, obserwowalność) odpowiedz: **wzięte z biblioteki czy napisane
    u nas?** Napisane u nas bez zapisanej decyzji w rejestrze to znalezisko,
    a nie styl. Wynik zapisz **zdaniem w formie zalecenia** — „używaj X zamiast
    Y, bo Z" — biorąc brzmienie z tabeli „Zalecenia wprost" w tej referencji.
    Odchylenie z zapisaną decyzją przechodzi bez uwagi; bez decyzji trafia do
    raportu jako `AGENTIC_STACK`. Osobno sprawdź, czy warstwa interfejsu stoi na dojrzałej
    bibliotece komponentów, czy na czymś zbudowanym doraźnie.

30. **Model domeny: czy agent widzi byt, czy tylko jego kontekst** — weź jeden
    byt domeny i policz, **ile miejsc opisuje, czym on jest**. Jedno źródło,
    z którego generują się typy interfejsu i walidacja serwera, znaczy kontrakt.
    Dwa i więcej znaczy konteksty zamiast kontraktu — i wtedy „raz odpowiada
    z danych, raz zgaduje" jest skutkiem, nie przyczyną.

    Do tego klasyczne objawy modelu anemicznego, które w systemie agentowym bolą
    podwójnie, bo agent nie ma jak odkryć reguły, której nie ma w bycie: encje
    będące workiem getterów i setterów; reguły biznesowe rozlane po kontrolerach
    i warstwie usług; warstwa usług puchnąca, bo model deleguje do niej pracę na
    własnych polach. Sprawdź też **sterowalność**: czy do każdej operacji na
    bycie istnieje narzędzie z własnym schematem. Operacja bez narzędzia dla
    agenta nie istnieje i lepiej, żeby to było widać.

31. **Język identyfikatorów** — uruchom `templates/identifier-language.sh`.
    Reguła z `naming-conventions.md` §2 mówi: identyfikatory po angielsku,
    **nawet gdy projekt ustalił inaczej**. Interesuje cię `IDENT_NON_ENGLISH`
    wobec progu, nie liczba bezwzględna: zapadka ma nie rosnąć. Wzrost przy
    istniejącym progu znaczy, że nowy kod dokłada polskie nazwy — to znalezisko,
    nie styl. Brak pliku leksykonu zgłoś osobno: bez niego termin dziedzinowy
    nie ma jak zostać zwolniony i spór skończy się wyłączeniem bramki.

32. **Inwentarz stosu** — uruchom `templates/stan-stosu.sh`. To jedyny punkt,
    który odpowiada na pytanie „czym ten projekt w ogóle jest napisany", i on
    ma trafić do raportu **w całości, z wierszami BRAK włącznie**. Wynik czyta
    się w dwóch kolumnach naraz: co stoi i co ma stać. Dwa frameworki widoku
    w jednym repozytorium to znalezisko, nawet gdy oba działają — bo znaczy, że
    migracja się zaczęła i nie skończyła, a każdy widok trzeba odtąd robić
    dwa razy. Tak samo dwa magazyny stanu: Postgres w compose i SQLite
    w migracjach to nie „mamy oba", tylko pytanie, który jest prawdą.
    Odstępstwo od zasady stosu nie jest błędem do naprawienia na miejscu —
    jest decyzją do zapisania z właścicielem i datą przeglądu.

33. **Rejestr reguł** — uruchom `templates/rejestr-regul.sh`. Wypisuje każdą
    konwencję toolkitu z jednym z czterech stanów. Sprawdź trzy rzeczy.
    **Po pierwsze**, ile reguł ma bramkę, a ile rozstrzyga czytanie: to mówi,
    jaka część raportu stoi na czyimś słowie, i jest liczbą do podania wprost.
    **Po drugie**, czy „nie dotyczy" jest prawdziwe — reguła zwolniona sondą,
    która szukała nie tam, gdzie trzeba, cicho znika z audytu.
    **Po trzecie**, czy któraś bramka zwraca tę samą liczbę w każdym projekcie.
    Tak wygląda bramka pytająca środowisko audytora zamiast repozytorium;
    liczba, która nie zmienia się między projektami, jest gorsza od `n/a`,
    bo wygląda jak pomiar. Zdarzyło się to naprawdę — `pip list --outdated`
    bez środowiska projektu meldował 98 przeterminowanych pakietów w repo,
    które miało jeden plik i zero zależności.

34. **Zastąpienia w rejestrze decyzji** — przejrzyj decyzje podjęte od ostatniego
    audytu i sprawdź, **co każda z nich unieważniła**. Nowsza decyzja nadpisuje
    wcześniejsze rozstrzygnięcia o tej samej rzeczy i zabiera ze sobą pozycje,
    które istniały tylko dlatego, że zastąpiona rzecz stała
    (`architecture-change.md` §5). Trzy rzeczy do wypisania przy każdej:
    co przestaje obowiązywać, które pozycje znikają razem z tym, i czego
    decyzja **nie** obejmuje.

    Szukaj obu kierunków. **Pozycja, która powinna zniknąć, a nie zniknęła** —
    audyt zgłosi ją znowu, a rejestr znowu ją rozstrzygnie, i tak co tydzień.
    **Odrzucenie, które przestało być aktualne** — rzecz odrzucona jako
    „nie warto" bywa częścią nowej decyzji i musi wrócić jako jej element,
    nie jako świeże znalezisko.

    Sprzeczność jest znaleziskiem samym w sobie: dopóki nikt nie napisał,
    co zastępuje co, obie decyzje są w mocy naraz.

35. **Dane, które cicho kłamią** (wkład z CrossDesk, 2026-08-21 — trzy sygnały
    żyły w checkliście projektowej, której mechanizm synchronizacji nie widział,
    bo nie była kopią; do mastera trafiły dopiero przy przepisaniu jej na
    nakładkę). Wspólny mianownik: kod przechodzi wszystkie bramki i produkuje
    wartość, która wygląda poprawnie i jest nieprawdziwa. Sprawdź:
    a. **Połknięte błędy** — `except: pass`, `except: return []`, `catch {}`
       i odpowiedniki. Pusty wynik z połkniętego wyjątku jest nieodróżnialny od
       pustego wyniku prawdziwego, a wyżej wygląda jak „brak danych", nie jak
       awaria. To ta sama klasa co skan, który padł i podał zero (Krok 0).
    b. **Czas wykonania podany jako czas zdarzenia** — `datetime.now()`/`NOW()`
       wpisane jako data dokumentu, zdarzenia albo rekordu historycznego.
       Backfill i ponowne przetworzenie przesuwają wtedy całą historię na dziś,
       bez żadnego sygnału. Data pochodząca ze źródła i data zapisu to dwa
       różne pola; jeśli jest jedno, ustal które.
    c. **Identyfikator jako licznik zamiast skrótu** — ID nadawane sekwencyjnie
       tam, gdzie ma być stabilne i deterministyczne. Ujawnia liczność zbioru,
       rozjeżdża się przy dwóch producentach i zmienia po ponownym imporcie,
       więc odsyłacze zewnętrzne wskazują po czasie na inny byt.

27. **Przesłanki pozycji backlogu** (wkład z projektu civic-tech, 2026-09-07 —
    dwa fałszywe zdania wykryte tego samego dnia, w dwie przeciwne strony).
    Pozostałe punkty sprawdzają kod i dane. Backlog jest trzecim artefaktem,
    który kłamie, i kłamie najdrożej, bo jego zdania **zamrażają pracę**:
    z nich biorą się decyzje o tym, czego nie robić i o co poprosić człowieka.
    Pełna konwencja: `konwencja:backlog-premise-audit.md`, rozwiązywana
    według locka i mapy projektu.
    Zmierzone: wpis niosący „0 czytelników" o siedmiu kolumnach był fałszywy
    dla czterech z nich i o mało nie skasował działającej funkcji; wpis niosący
    „nie da się bez właściciela" rozstrzygnęło jedno zapytanie do kopii
    produkcji, którą repo pobiera co rano. Sprawdź:
    a. **Zdanie, na którym stoi STATUS pozycji**, nie całą pozycję. Wpis ma
       kilkanaście zdań; tylko jedno decyduje, że jest zablokowany, krytyczny
       albo gotowy usunąć coś. Przelicz to jedno w HEAD.
    b. **Kolejność: najpierw pozycje blokujące człowieka**, potem najwyższa
       ważność, potem nietykane najdłużej. Ich przesłanki starzeją się bez
       świadka, bo z definicji nikt ich nie rusza.
    c. **„Nie da się bez X" sprawdzaj tym, co już masz** — kopia produkcji,
       fixture'y, cache, ledger, logi. Ta postać przesłanki upada najczęściej.
    d. **„Nikt tego nie czyta" wymaga kontroli dodatniej.** Grep po symbolu,
       którym kod naprawdę się posługuje; ORM zwraca typ wiersza, nie tabelę,
       więc grep po nazwie tabeli „udowodni" brak czytelników dla wszystkiego.
    e. **Obalona przesłanka to poprawka wpisu w tym samym commicie co audyt**,
       a gdy zdejmuje blokadę — przeniesienie pozycji do kolejki roboczej.
       Inaczej audyt zauważył, że człowiek jest wolny, i nie powiedział mu tego.
