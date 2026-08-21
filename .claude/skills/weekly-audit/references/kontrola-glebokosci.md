# Kontrola głęboka — punkty oceny (Krok 2 skilla `weekly-audit`)

Wczytywane na żądanie, przy Kroku 2 audytu. Lista rośnie z postmortemów: każdy
potwierdzony incydent dopisuje stały punkt, dlatego przy części z nich stoi
data i projekt, z którego wkład pochodzi.

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
6. **Zgodność z rejestrem decyzji** (`decisions.md`) — złamana decyzja = P0/P1.
7. **Skille / MCP** — czy pojawiło się coś nowego co przyspieszy pracę.
8. **Gate'y** — czy `SKIP_*` jest per-warstwa; czy `exit 0` nie omija dalszych
   checków; czy gate sprawdza zmianę, a nie dowolny istniejący test; czy brak
   narzędzia/DB nie daje fałszywego sukcesu. Porównaj z
   `.claude/rules/rules-as-gates.md`. **Gate mierz, nie czytaj**: lektura
   hooka wykrywa to, czego się spodziewasz, więc warunki wczesnego `exit 0`
   wyciągaj z ŻYWEGO pliku i sprawdzaj testem, że wymieniają każdą flagę,
   na którą reaguje którakolwiek warstwa niżej (tak w JawnePanstwo zginęła
   cała warstwa dla pushy dotykających jednego katalogu). Wykluczenia
   ścieżek w skanie sekretów muszą być **zakotwiczone** — substring `test`
   łapał `latest`, więc plik `…_latest_….sql` był bezkarny. Skan sekretów
   testuj po jednej klasie credentiala na commit.
9. **Supply chain** — lockfile, dependency bot/cooldown, secret protection,
   OIDC/trusted publishing i release/deploy według `.claude/rules/ci-cd.md`.
10. **Delivery** — wiek aktywnych branchy/WIP, szybki lane CI (<10 min jako
    cel), build-once/same digest, poprzedni artifact, health gate, bake,
    rollback drill, feature-flag expiry, SLO/error budget i release evidence.
    Porównaj z `.claude/rules/progressive-delivery.md`.
11. **Provenance zmiany** — próbka nietrywialnych commitów zawiera `Intent`,
    `Task-Ref`, `Gates`; task brief zgadza się z diffem, a review
    record/check jest związany z niezmienionym SHA. Sprawdź też, czy do
    commitów nie wróciła atrybucja AI (`AI-Contribution`, `Co-Authored-By`)
    wbrew D-006 — chyba że projekt ma zapisany wyjątek we własnym
    `decisions.md` (np. projekt, który jawnie deklaruje użycie AI); wtedy
    pilnuj odwrotnie: atrybucja MA być. **Raz w miesiącu** zadaj
    właścicielowi pytanie, czy chce zmienić politykę oznaczania udziału AI;
    odpowiedź (także „nie") zapisz w `decisions.md` z datą.
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
       git cat-file --batch-check`); inaczej fałszywy „bloat P0" albo
       przeoczony realny (baza commitowana N razy).
    d. **Integralność referencyjna** — każda ścieżka w trackowanych
       `.claude/*.md` (backlog, status) istnieje i jest trackowana albo
       świadomie ignorowana; martwy link do „jedynej kopii" to P0.
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
    i. **Wiek najstarszej pozycji P1 w backlogu** — sam werdykt FAIL nie
       wymusza ruchu (P1 potrafią przetrwać kilka audytów).
    j. **Kandydaci na mechaniczne gate'y** (`rules-as-gates.md`, tryb
       raportowy): pliki `.bak`/`BACKUP`/`*_b64` tracked; zmergowane gałęzie
       do skasowania + duplikat `master`/`main`; egzekwowanie lokalnych
       decyzji projektu (np. „skany tylko w sources/").

15. **Aktualność zależności i runtime'ów** — uruchom bramkę aktualności
    (`templates/dependency-currency.sh` albo projektową kopię) i zestaw wynik
    z poprzednim audytem. Runtime po EOL to **P0** — po tej dacie nie ma
    poprawek bezpieczeństwa. Runtime z EOL bliżej niż 180 dni bez zaczętej
    migracji to P1. Wzrost liczby przeterminowanych zależności bezpośrednich
    względem poprzedniego audytu to P2 z zapadką. Wynik `n/a` (brak
    narzędzia, brak sieci) raportuj jako `n/a`, **nigdy jako zero ustaleń** —
    reguły w `.claude/rules/dependency-currency.md`.
16. **Delivery/deploy honesty** (wkład z JawnePanstwo, 2026-07-12 — cała
    warstwa delivery nie miała właściciela w planie audytu i dała cztery P1
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
    `.claude/rules/quality-gates-and-dod.md`.
21. **Bramki weryfikacji bezpieczeństwa** — które z SAST / SCA / skanu
    sekretów / IaC / DAST są skonfigurowane, która blokuje scalenie, a która
    tylko raportuje. Brak narzędzia raportuj jako `n/a`; narzędzie obecne, ale
    niepodpięte do bramki, jest gorsze niż jego brak, bo daje złudzenie
    pokrycia. Reguły: `.claude/rules/security-verification-gates.md`.
22. **Dowód z testu** — dla próbki napraw z ostatniego okresu sprawdź
    weryfikację negatywną: cofnij naprawę, test MUSI zrobić się czerwony,
    przywróć. Test, który przechodzi także bez naprawy, nie jest dowodem.
    Reguły: `.claude/rules/test-evidence.md`.
23. **Gotowość PR i odpowiedź na review** — czy PR-y niosą preflight
    i odpowiedź na uwagi, czy scalanie odbywa się bez śladu review. Reguły:
    `.claude/rules/pull-request-review.md`.
24. **Topologia bramek pipeline'u** — przejdź procedurę audytu CI/CD:
    co jest naprawdę wymagane, kto może ominąć, czy któryś wymagany check może
    nigdy nie wystartować, czy bramki są fail-closed. W profilu local-first
    czytaj tę konwencję przez §11a (warstwy hooka zamiast jobów) — inaczej
    zaraportujesz „brak bramek" o repo, które ma ich kilkanaście. Reguły:
    `.claude/rules/ci-pipeline-architecture.md`.
25. **Zgłoszenia defektów** — czy defekty mają reprodukcję i dowód przed/po,
    czy giną w prozie. Zgłoszenie bez kroków reprodukcji wraca do zgłaszającego,
    nie do backlogu. Reguły: `.claude/rules/issue-reporting.md`.
