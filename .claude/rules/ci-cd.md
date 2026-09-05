# Konwencja: bezpieczny baseline CI/CD

Stack-agnostic. Domyślny punkt startu dla nowych projektów na GitHubie.
Powstał z audytu praktyk dwóch projektów produkcyjnych oraz aktualnych
zaleceń GitHub, npm, PyPI i uv (2026-07-11).

> **D-007 — profil CI wybiera się per projekt, pytaniem.** Nie zakładaj ani
> dostępności płatnego hosted CI, ani jej braku — agent przy adopcji/
> bootstrapie PYTA właściciela: hosted CI (Actions — darmowe dla repo
> publicznych, minuty limitowane/płatne dla prywatnych) czy **local-first**
> (pre-push lustrzy pipeline, wzorzec `scripts/local-ci.sh` z projektu
> prowadzonego local-first;
> audyt pilnowany lokalnym preflightem). Odpowiedź → `decisions.md`
> projektu. Hosted → pełny hardening z sekcji 2; local-first → zapisz,
> które zabezpieczenia tracisz (gate'y na zmianach botów, czyste
> środowisko, required checks).

## 1. Dwa niezależne poziomy kontroli

- Hooki lokalne dają szybki feedback, ale **nie zastępują CI**: można je
  ominąć, nie uruchamiają się na zmianach botów i zależą od lokalnego
  środowiska.
- CI na PR/push do głównej gałęzi odtwarza wymagane gate'y w czystym
  środowisku. Jeśli hosted CI zostaje wyłączone z powodu kosztów, zapisz tę
  decyzję i jawnie wskaż, które zabezpieczenia tracisz.
- Gate wymagający narzędzia lub usługi działa fail-closed: brak DB, skanera
  albo runtime'u blokuje z instrukcją instalacji. Ciche `skip` jest awarią
  gate'a.

Minimalny szybki pipeline: format/lint, typecheck, testy jednostkowe i build,
z celem użytecznego feedbacku poniżej 10 minut. SAST i wieloplatformowość
dodawaj proporcjonalnie do ryzyka. Test acceptance/integration jest jednak
obowiązkowy przed wydaniem, gdy zmiana dotyka krytycznej ścieżki użytkownika,
trwałych danych albo realnej integracji, której nie potwierdza unit test.

## 1.1 Małe partie i jeden kanoniczny artefakt

- Mutujące zadanie pracuje na małej, krótko żyjącej gałęzi: cel <1 dzień,
  sygnał ostrzegawczy po 3 dniach. Read-only rozmowa/rola nie tworzy brancha.
- Integruj co najmniej raz dziennie. Zepsuty required check napraw albo revertuj
  przed dokładaniem kolejnych zmian.
- CI buduje release candidate **raz** z zatwierdzonego SHA i zamrożonego
  lockfile. Test, pre-production i produkcja promują dokładnie ten sam digest.
- Poprzedni znany dobry artefakt pozostaje dostępny do rollbacku. Skrypty
  deploymentu i konfiguracja są wersjonowane.
- Profile i rollout opisuje [`progressive-delivery.md`](progressive-delivery.md).

## 2. Supply chain GitHub Actions

1. Każde zewnętrzne `uses:` przypnij do pełnego 40-znakowego commit SHA,
   również akcje GitHub. Tag dopisz jako komentarz dla czytelności:
   `uses: actions/checkout@<FULL_COMMIT_SHA> # vX.Y.Z`.
2. Każdy workflow ma jawne top-level `permissions: {}` albo
   `permissions: contents: read`. Podnoś uprawnienia tylko w konkretnym jobie.
3. Nie uruchamiaj uprzywilejowanego `pull_request_target` na niezaufanym
   kodzie. Dane z tytułu/body PR lub issue przekazuj jako quoted zmienną
   środowiskową, nigdy jako część generowanego skryptu.
4. Job z sekretami, publikacją lub deployem nie przetwarza niezaufanego kodu,
   cache ani artefaktów bez weryfikacji.
5. Zmiany `.github/workflows/**` przechodzą taki sam review jak kod
   bezpieczeństwa. Okresowy audyt uruchamia `zizmor` lub równoważny linter,
   jeśli projekt ma workflowy.
6. `.github/workflows/**` oraz release/deploy należą do CODEOWNERS i wymagają
   niezależnego review. Repo/org policy wymusza pełne SHA również dla reusable
   workflows (`jobs.<id>.uses`) i ogranicza dozwolone akcje.
7. Uprzywilejowany `workflow_run` nie checkoutuje ani nie wykonuje kodu,
   artefaktów lub cache z niezaufanego runu. GitHub-hosted ephemeral runner
   jest baseline'em; self-hosted nie obsługuje publicznych PR-ów. Wyjątek
   wymaga izolowanego/JIT runnera bez sekretów i sieci produkcyjnej.

Dependabot potrafi aktualizować akcje przypięte do SHA, jeśli komentarz wersji
jest w tej samej linii. Włącz `github-actions` version updates; same alerty
bezpieczeństwa nie raportują akcji przypiętych do SHA, więc aktualizacje oraz
okresowy audyt dependency graph są obowiązkowym uzupełnieniem.

**Pinowanie do SHA przenosi na ciebie odpowiedzialność za aktualizacje
bezpieczeństwa.** Gdy dostawca akcji zaostrza domyślne zachowanie — na
przykład blokuje checkout kodu forka w uprzywilejowanym kontekście — repo
przypięte do starego SHA **nie dostaje tej ochrony automatycznie**. To nie
jest argument przeciw pinowaniu; to powód, dla którego bot aktualizacji
przestaje być „uzupełnieniem", a staje się warunkiem koniecznym. Pinowanie
bez automatycznych aktualizacji jest zamrożeniem znanych podatności.

Pinowanie do SHA nie obejmuje też **zależności tranzytywnych** composite
actions — akcja przypięta do SHA może wewnątrz wołać kolejne po tagu. Do czasu
pojawienia się natywnego lockfile'a dla akcji jest to świadomie akceptowana
dziura; zapisz ją w `decisions.md` zamiast udawać, że pin daje pełne pokrycie.

## 3. Zależności i lockfile

- Commituj lockfile aplikacji (`package-lock.json`, `pnpm-lock.yaml`,
  `uv.lock`, `Cargo.lock` itd.). Nie edytuj go ręcznie.
- CI instaluje bez zmiany rozwiązania: `npm ci`,
  `pnpm install --frozen-lockfile`, `uv sync --locked`, `cargo --locked`.
  `--locked` jest preferowane dla uv w CI, bo wykrywa niespójność
  `pyproject.toml`↔`uv.lock`; `--frozen` tylko świadomie pomija ten check.
- Produkcja dostaje artefakt lub obraz, który przeszedł CI. Serwer nie
  rozwiązuje ponownie zależności podczas deployu.
- Bot aktualizacji zależności ma cooldown 3–7 dni dla zwykłych wydań.
  Aktualizacje security nie podlegają cooldownowi. Grupuj małe aktualizacje,
  majory osobno; każde trwałe ignorowanie ma uzasadnienie w decyzjach.
- Skrypty instalacyjne zależności są powierzchnią ataku. Wyłączaj je w jobach,
  które ich nie potrzebują; wymagane skrypty dopuszczaj świadomie. Nowsze npm
  wyłącza je domyślnie — do czasu migracji ustaw jawnie `ignore-scripts=true`
  w `.npmrc` i trzymaj listę świadomie zatwierdzonych skryptów pod review.
  `preinstall` wykonywany przed kodem projektu to klasyczny wektor wejścia
  robaka; nie polegaj na tym, że „przecież tylko instalujemy zależności".

## 4. Ochrona głównej gałęzi

Dla każdego repo skonfiguruj minimalny ruleset:

- blokada usuwania i force-push na `main`/`master`;
- merge przez PR oraz wymagany status minimalnego CI;
- opcjonalny bypass wyłącznie dla właściciela i sytuacji awaryjnej;
- osobny tag ruleset dla tagów wydań, jeśli projekt je publikuje;
- allowlista wyzwalaczy workflowów, jeśli platforma ją oferuje: kto może
  uruchomić przebieg i które zdarzenia go uruchamiają. Tryb ewaluacyjny
  (raport bez blokady) mapuje się wprost na krok 3
  [`rules-as-gates.md`](rules-as-gates.md) — włącz go najpierw, policz
  fałszywe alarmy, dopiero potem egzekwuj.

Merge queue ma sens dopiero przy realnej kolejce wielu PR-ów. Nie jest
domyślnym wymaganiem dla projektu solo.

## 5. Sekrety, publikacja i deploy

- Włącz secret scanning/push protection tam, gdzie plan repo na to pozwala.
  Lokalny `gitleaks` uzupełnia ochronę, szczególnie w prywatnych repozytoriach.
- Do chmur i rejestrów używaj OIDC zamiast długowiecznych kluczy. Przyznawaj
  `id-token: write` wyłącznie jobowi, który wymienia token. Cloud trust policy
  ogranicza `aud` i `sub` do konkretnego repo oraz chronionego environment,
  taga lub refu — samo OIDC bez tych warunków nie daje least privilege.
  **Sprawdź format `sub` przy zakładaniu repo, zanim napiszesz trust policy** —
  format bywa różny dla starszych i nowszych repozytoriów (niezmienne
  identyfikatory właściciela/repo), a zmiana nazwy repo potrafi unieważnić
  politykę napisaną pod stary wzorzec.
- Publikacja npm/PyPI używa Trusted Publishing. Po migracji usuń/revokuj
  klasyczne tokeny publikacyjne.
- **Trusted Publishing i provenance dowodzą pochodzenia, nie nieszkodliwości.**
  Chronią przed kradzieżą *tokena*; nie chronią przed kompromitacją *workflow*.
  Attestation mówi „to zbudował ten workflow z tego SHA" — nie „ten build jest
  bezpieczny". Pakiet opublikowany przez przejęty pipeline niesie **ważne**
  provenance. Zielona weryfikacja nie kończy analizy, jeśli podmieniono sam build.
- **Rotacja poświadczeń zakłada wrogiego obserwatora.** Złośliwa persistence
  (LaunchAgent, systemd user unit, cron) potrafi pollować API i traktować
  odpowiedź 40x — czyli moment odwołania tokenu — jako sygnał wyzwalający.
  Kolejność: najpierw odetnij maszynę od sieci i przejrzyj jednostki
  autostartu, dopiero potem revoke. Odwrotna kolejność sama uzbraja handler.
- Job mający sekrety nie uploaduje artefaktów bez przeglądu ich zawartości i
  nie serializuje całego kontekstu sekretów (`toJSON(secrets)`). Oba wzorce
  są tanim kandydatem na grep w trybie raportowym.
- Deploy na zwykły VPS, gdy OIDC nie jest dostępne, używa osobnego klucza
  per projekt i użytkownika bez uprawnień administracyjnych. Ogranicz klucz
  w `authorized_keys` (`command=`, `no-pty`, bez forwardingów) albo wybierz
  model pull-based.
- Sekrety deployu żyją w chronionym GitHub Environment ograniczonym do tagów
  wydań. Produkcję obowiązuje [`production-operations.md`](production-operations.md).

## 6. Release i pochodzenie artefaktów

- Release powstaje z zatwierdzonego taga; najpierw draft, potem komplet
  artefaktów, na końcu publikacja.
- Dla repozytoriów wydających binaria włącz immutable releases.
- Release workflow buduje kanoniczny artefakt od zera z zamrożonego lockfile i
  bez cache z niezaufanych PR-ów. Dalsze etapy już go **nie przebudowują**.
- Dla publicznych binariów i obrazów generuj build provenance attestation.
  Baseline to SLSA Build L1; hosted builder generujący podpisane provenance
  może dawać L2, ale deklaruj poziom dopiero po sprawdzeniu wymagań.
- Release/deploy weryfikuje fail-closed: subject digest, repo/owner, ref/tag,
  `predicateType` i oczekiwaną tożsamość workflow/buildera. Samo udane
  `gh attestation verify` bez zapisanych expectations nie wystarcza.
- Przy bezpośrednim cosign weryfikuj digest oraz konkretne
  `--certificate-identity` i `--certificate-oidc-issuer`; bez wildcardów i
  `--check-claims=false`. W małym projekcie wybierz jeden obowiązkowy verifier
  na ścieżkę artefaktu zamiast dwóch niespójnych systemów.
- Dla dystrybuowanych obrazów/binarnych release'ów zachowaj artefakt,
  provenance i dane integralności; SBOM dodaj, gdy jest konsumowany w
  vulnerability/dependency review, a nie jako martwy plik compliance.

## 7. Agenty i AI w CI

- Review AI jest domyślnie **advisory**. W zespole opisanym w
  [`multi-agent-delivery.md`](multi-agent-delivery.md) niezależny Reviewer może
  być wymaganym proceduralnym sign-offem, ale nigdy jedynym gate'em i nigdy nie
  nadpisuje czerwonego CI.
- Workflow wyzwalany tekstem PR/issue nie może jednocześnie mieć sekretów lub
  write permissions. Treść użytkownika jest niezaufanym inputem i może
  zawierać prompt injection.
- Agent nie zatwierdza własnej zmiany. Dla zmian przez agenta zachowaj
  niezależny gate lub jawne zatwierdzenie właściciela.
- Koszt, zakres narzędzi, sieć i maksymalny czas pracy agenta są jawnie
  ograniczone. Nie uruchamiaj nieograniczonych pętli autonomicznych.

## 8. Co jest opcjonalne

Włączaj dopiero po pomiarze problemu: płatne szybkie runnery, preview
environments, Docker Buildx remote cache, Testcontainers, performance
baselines, macierz N-1, wieloarchitekturowe buildy. Każdy z tych mechanizmów
ma dobry use-case, ale nie jest kosztem bazowym każdego nowego repo.

## 9. Profile adopcji

- **Biblioteka / bez produkcji:** szybkie CI, ruleset, frozen lockfile,
  kanoniczny release artifact i provenance adekwatne do sposobu dystrybucji.
- **Pojedynczy VPS:** powyższe + pre-production na drugim porcie/kontenerze,
  smoke, atomowe przełączenie, bake condition, poprzedni digest i rollback.
- **Wiele instancji:** powyższe + canary/control, rollout falami i automatyczny
  rollback z telemetryki. Szczegóły:
  [`progressive-delivery.md`](progressive-delivery.md).

## 10. Vulnerability response

Projekt określa kanał zgłoszeń (`SECURITY.md` dla publicznego repo albo
prywatny odpowiednik), wspierane wersje, właściciela triage i runbook
incydentu. Po podatności root cause tworzy test/gate zapobiegający powtórce i
zadanie w backlogu. To domyka grupę Respond to Vulnerabilities z NIST SSDF;
sam skaner zależności nie jest procesem response.

## Źródła referencyjne

- GitHub: [Secure use
  reference](https://docs.github.com/en/actions/reference/security/secure-use)
- GitHub: [OIDC hardening](https://docs.github.com/en/actions/reference/security/oidc)
- GitHub:
  [Rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets)
- GitHub: [Artifact
  attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)
- GitHub: [Immutable
  releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases)
- GitHub: [Dependabot
  cooldown](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#cooldown)
- PyPI: [Trusted Publishers](https://docs.pypi.org/trusted-publishers/)
- npm: [Trusted publishing](https://docs.npmjs.com/trusted-publishers/)
- uv: [Locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- DORA: [Continuous delivery](https://dora.dev/capabilities/continuous-delivery/)
- NIST: [Secure Software Development Framework
  1.1](https://csrc.nist.gov/pubs/sp/800/218/final)
- SLSA: [Build track basics](https://slsa.dev/spec/v1.2/build-track-basics)
- SLSA: [Verifying artifacts](https://slsa.dev/spec/v1.2/verifying-artifacts)
