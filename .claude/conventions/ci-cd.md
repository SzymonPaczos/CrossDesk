# Konwencja: bezpieczny baseline CI/CD

Zakres: konfiguracja, zmiana i audyt CI/CD. Zwykła zmiana kodu używa
istniejących komend i profilu projektu; nie konfiguruje pipeline'u od nowa.

Przy adopcji lub bootstrapie D-007 wymaga ustalenia z właścicielem profilu
hosted albo local-first i zapisania go w `decisions.md`. Stosuj już podjętą
decyzję; wraca do wyboru, gdy zmienią się warunki projektu. Profil local-first
ujawnia utracone zabezpieczenia: kontrole zmian botów, czyste środowisko,
required checks. Profil hosted stosuje sekcję 2.

## 1. Dwa niezależne poziomy kontroli

Hook daje lokalny feedback. CI odtwarza wymagane bramki na PR i push
do głównej gałęzi w czystym środowisku. Wyłączenie hosted CI jest zapisaną
decyzją ze wskazaniem utraconych zabezpieczeń. Brak warunku wymaganej bramki
obsługuje [`rules-as-gates.md`](rules-as-gates.md) punkt 6.

Szybki pipeline obejmuje format/lint, typecheck, testy jednostkowe i build,
z celem feedbacku poniżej 10 minut. Zakres SAST i platform wynika z ryzyka.
Przed wydaniem zmiana krytycznej ścieżki, trwałych danych lub rzeczywistej
integracji ma test acceptance/integration, jeśli unit test jej nie potwierdza.

## 1.1 Małe partie i jeden artefakt wydania

Mutujące zadanie pracuje na własnej, krótkiej gałęzi: cel poniżej dnia,
sygnał ostrzegawczy po trzech dniach. Rytm integracji to co najmniej raz
dziennie; nie nadaje agentowi uprawnienia do merge. Zepsuty required check
wymaga naprawy lub revertu przed dokładaniem zmian.

Release candidate powstaje raz z zatwierdzonego SHA i zamrożonego lockfile.
Test, pre-production i produkcja używają tego samego digestu. Poprzedni
dobry artefakt pozostaje do rollbacku; deploy i konfiguracja są wersjonowane.
Profile rolloutów: [`progressive-delivery.md`](progressive-delivery.md).

## 2. Supply chain GitHub Actions

1. Zewnętrzne `uses:`, także reusable workflows, są przypięte do pełnego
   40-znakowego SHA z komentarzem wersji. Automatyczne aktualizacje
   `github-actions` i okresowy audyt uzupełniają pinowanie.
2. Workflow ma top-level `permissions: {}` lub `contents: read`.
   Dodatkowe uprawnienia dotyczą tylko wymagającego ich joba.
3. Uprzywilejowany `pull_request_target` nie wykonuje niezaufanego kodu.
   Tytuł i treść PR/issue są danymi, np. cytowaną zmienną środowiskową,
   nigdy interpolowanym fragmentem skryptu.
4. Job z sekretami, publikacją lub deployem nie przetwarza niezaufanego
   kodu, cache ani artefaktów bez weryfikacji.
5. Workflowy podlegają review bezpieczeństwa i okresowej kontroli przez
   `zizmor` lub równoważny linter.
6. Workflowy, release i deploy należą do CODEOWNERS i wymagają niezależnego
   review. Polityka repo/org ogranicza akcje i wymusza pełne SHA.
7. Uprzywilejowany `workflow_run` nie checkoutuje ani nie wykonuje
   niezaufanego kodu, cache ani artefaktów z wcześniejszego runu.
   Baseline to ephemeral runner; self-hosted nie obsługuje publicznych PR-ów,
   chyba że jest izolowany/JIT, bez sekretów i sieci produkcyjnej.

Pin zewnętrznej akcji nie gwarantuje pinów jej zależności tranzytywnych.
Niepokryty zakres jest zapisany w decyzjach; sam pin nie dowodzi pełnej ochrony.

Pin SHA zamraża konkretny kod; nowe zabezpieczenie dostawcy nie trafi do
workflowu bez aktualizacji pinu. Dependabot version updates z ekosystemem
`github-actions` może aktualizować SHA. Komentarz wersji w tej samej linii
pozwala botowi aktualizować również tę etykietę; nie jest warunkiem
aktualizacji samego SHA. Przykładowo `uses: actions/checkout@<SHA> # vX.Y.Z`
ma w PR aktualizacyjnym nowy SHA i odpowiadającą mu wersję. SHA bez
powiązanego taga może zostać zaktualizowany do najnowszego commita zamiast
wydania, więc review sprawdza docelowy commit, tag i źródłowe repozytorium.
Projekt ma automatyczne version updates lub jawny proces aktualizacji;
same alerty bezpieczeństwa nie pokrywają akcji przypiętych do SHA.

## 3. Zależności i lockfile

- Lockfile aplikacji jest wersjonowany i aktualizowany menedżerem zależności.
  CI instaluje bez zmiany rozwiązania, np. `npm ci`, `pnpm install --frozen-lockfile`,
  `uv sync --locked`, `cargo --locked`. `uv --frozen` pomija kontrolę
  zgodności manifestu i wymaga świadomego wyboru.
- Produkcja dostaje sprawdzony artefakt; deploy nie rozwiązuje zależności
  ponownie.
- Zwykłe aktualizacje mają cooldown 3–7 dni, security bez zwłoki. Małe
  aktualizacje mogą być grupowane, majory są osobno; trwałe ignorowanie
  wymaga uzasadnienia.
- Niepotrzebne skrypty instalacyjne są wyłączone, np. `ignore-scripts=true`
  w npm. Wymagane skrypty są jawnie dopuszczone i objęte review.

## 4. Ochrona głównej gałęzi

Ruleset chroni `main`/`master` przed usuwaniem i force-push, wymaga PR oraz
minimalnego CI. Ewentualny bypass dotyczy właściciela i sytuacji awaryjnej.
Tagi wydań mają osobną ochronę. Jeśli platforma udostępnia kontrolę
wyzwalaczy workflowów, zakres zdarzeń i uprawnionych osób jest ograniczony.
Nowy check przechodzi ocenę raportową przed blokowaniem.
Merge queue jest opcją przy rzeczywistej kolejce PR-ów.

## 5. Sekrety, publikacja i deploy

- Secret scanning/push protection są włączone tam, gdzie dostępne;
  lokalny skaner uzupełnia ochronę.
- Chmury i rejestry używają OIDC zamiast stałych kluczy. `id-token: write`
  dotyczy tylko potrzebującego joba. Trust policy ogranicza `aud` i `sub`
  do repo oraz chronionego environment, taga lub refu. Konfiguracja używa
  rzeczywistego formatu `sub` danego repozytorium.
  Zmiana nazwy lub transfer repo może zmienić ten format i unieważnić trust
  policy; sprawdź dopasowanie również po takiej operacji, nie tylko przy setupie.
- npm/PyPI korzystają z Trusted Publishing; po migracji stare tokeny
  publikacji są odwołane. Provenance nie dowodzi nieszkodliwości builda.
- Przy podejrzeniu przejęcia maszyny rotacja uwzględnia jej izolację
  i persistence. Tryb reagowania określa runbook incydentu; zwykła rotacja
  nie zakłada automatycznie, że maszyna jest przejęta.
  Jeśli rozpoznana persistence reaguje na utratę tokenu, runbook izoluje
  maszynę przed revoke, aby nie wyzwolić reakcji z dostępem do sieci.
  To warunek tego scenariusza incydentu, nie kolejność każdej rotacji.
- Job z sekretami kontroluje zawartość uploadowanych artefaktów
  i nie serializuje całego kontekstu sekretów, np. `toJSON(secrets)`.
- VPS bez OIDC ma osobny klucz per projekt i użytkownika bez administracji.
  Dostęp SSH ogranicza `command=`, `no-pty` i wyłączenie forwardingów
  w `authorized_keys`; alternatywą jest model pull-based.
- Sekrety deployu są w chronionym Environment ograniczonym do tagów wydań.
  Produkcja stosuje [`production-operations.md`](production-operations.md).

## 6. Release i pochodzenie artefaktów

Release powstaje z zatwierdzonego taga: draft, komplet artefaktów, publikacja.
Binaria korzystają z immutable releases. Build używa zamrożonego lockfile
i nie korzysta z niezaufanego cache PR; kolejne środowiska nie przebudowują go.

Publiczne binaria i obrazy mają build provenance attestation, baseline
SLSA Build L1. Wyższy poziom deklaruje się po sprawdzeniu jego wymagań.
Verifier sprawdza digest, repo/owner, ref/tag, `predicateType` i oczekiwanego
buildera/workflow; brak zgodności blokuje release/deploy.
Cosign weryfikuje konkretną identity i OIDC issuer, bez wildcardów
i `--check-claims=false`. Ścieżka artefaktu ma jeden ustalony verifier.
Zachowane są artefakt, provenance i dane integralności; SBOM ma wskazanego
konsumenta w analizie zależności lub podatności.

## 7. Agenty i AI w CI

Review AI jest advisory; wymagany Reviewer z
[`multi-agent-delivery.md`](multi-agent-delivery.md) nie zastępuje bramek
ani nie nadpisuje czerwonego CI. Autor nie zatwierdza własnej zmiany:
odbiór wymaga niezależnej kontroli lub zgody właściciela.
Workflow sterowany treścią PR/issue nie łączy tego wejścia z sekretami
lub write permissions. Zakres narzędzi, sieć, koszt i czas pracy agenta
są ograniczone.

## 8. Co jest opcjonalne

Szybsze runnery, preview environments, remote cache, Testcontainers,
performance baselines i dodatkowe macierze wynikają z potrzeb projektu.
Ich dostępność nie ustanawia obowiązku wdrożenia.

## 9. Profile adopcji

- Biblioteka: szybkie CI, ruleset, lockfile i provenance odpowiednie do dystrybucji.
- VPS: dodatkowo pre-production, smoke, atomowe przełączenie, bake condition
  i rollback do poprzedniego digestu.
- Wiele instancji: canary/control, rollout falami i rollback z telemetryki.

Szczegóły: [`progressive-delivery.md`](progressive-delivery.md).

## 10. Vulnerability response

Projekt ma kanał zgłoszeń, wspierane wersje, właściciela triage i runbook
incydentu. Usunięcie przyczyny podatności ma test lub bramkę oraz ślad zadania.

## Źródła referencyjne

- [GitHub — bezpieczne Actions](https://docs.github.com/en/actions/reference/security/secure-use)
- [GitHub — aktualizacja komentarzy wersji przy SHA](https://github.blog/changelog/2022-10-31-dependabot-now-updates-comments-in-github-actions-workflows-referencing-action-versions/)
- [GitHub — OIDC](https://docs.github.com/en/actions/reference/security/oidc)
- [GitHub — attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)
- [npm — Trusted Publishing](https://docs.npmjs.com/trusted-publishers/)
- [PyPI — Trusted Publishers](https://docs.pypi.org/trusted-publishers/)
- [uv — locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [DORA — continuous delivery](https://dora.dev/capabilities/continuous-delivery/)
- [SLSA — verifying artifacts](https://slsa.dev/spec/v1.2/verifying-artifacts)

Egzekwuje: review; checki YAML i polityk repo potwierdzają tylko swój zadeklarowany zakres.
