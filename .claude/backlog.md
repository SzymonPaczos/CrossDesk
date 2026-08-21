# Backlog — post-MVP / kiedyś (parking)

> **To NIE jest board „co dalej".** Droga do v0.1.0 → [`PLAN.md`](../PLAN.md)
> (jedyny board MVP). Ten plik = długi ogon pozycji **poza** v0.1.0 + kontekst
> techniczny. Jak szukasz co robić teraz — nie tu. Stan / partiale —
> [`status.md`](status.md). Archiwum — [`history/completed-work.md`](history/completed-work.md).

Pozycje realnie należące do v0.1.0 (P0 hard_destroy, FS Stage B, doctor/uninstall
live, pomiary N1, M5, packaging test) żyją w `PLAN.md`; tu zostają jako kontekst.

> Sfoldowany z FOLLOWUPS.md (1260 linii) 2026-05-23 — archiwum:
> [`history/2026-05-23-followups-archive.md`](history/2026-05-23-followups-archive.md).
> Inline `FOLLOWUPS:NNN` adnotacje w źródłach rozwiązują się przeciwko
> archiwum (decyzja [DEC-META-004](rules/decisions.md)).

**Konwencja:** jedna pozycja = jedna linia opisu + (opcjonalnie) jedna
linia kontekstu. **Priorytety** tu są *względne w obrębie post-MVP*.
**Marker `[HW]`** (box jest żywy od 2026-07) = **genuine hardware, którego ten
box NIE ma**: GPU passthrough, Looking Glass, multi-monitor (2+ ekrany),
self-hosted CI runner. Rzeczy „tylko odpalić na tym boxie" (real libvirt,
VirtioFS, perf, suspend/resume) **nie są już `[HW]`** — są w `PLAN.md` NEXT.
`[~PARTIAL]` = częściowo shipped (reszta w [`status.md`](status.md)).

---

## 🔴 TOP — dokończenie adopcji claude-toolkit 2026.08.21

**Warstwa audytu ZROBIONA 2026-08-21** (`chore/audit-toolkit-2026-08-20`,
DEC-META-009). Zostaje **P0 bramki `pre-push`** i promocje do mastera — poniżej.
Master ruszył w trakcie pracy (2026.08.20 → 2026.08.21); adopcja powtórzona na
wersji końcowej, lock stoi na `2026.08.21`.

### ✅ ZROBIONE 2026-08-21 — sposób audytu przebudowany na master 2026.08.20

- **7 kopii zsynchronizowanych** (`toolkit-sync.sh update`), lock `2026.08.06`
  → `2026.08.20`, `check` **zielony**.
- **`references/kontrola-glebokosci.md`** przyjęte — checklista głęboka
  **14 → 25 punktów**; wyszła z ciała skilla, więc trzeba ją wczytać osobno.
- **`rules/audit.md` przepisany na nakładkę.** `contrib` pokazał **16 pozycji
  projektu wobec 8 w masterze** przy zielonym `check` — plik nie jest kopią,
  więc manifest go nie widział. Nie trzyma już własnej numeracji.
- **8 konwencji zaadoptowanych** (decyzja właściciela): dependency-currency,
  quality-gates-and-dod, security-verification-gates, test-evidence,
  ci-pipeline-architecture, repo-hygiene-gates, pull-request-review,
  issue-reporting. Dwie pierwsze z listy „każde zadanie" w load-liście
  `CLAUDE.md`, reszta audytowo.
- **`audit.sh`:** trzy stany zamiast jednego (liczba · `n/a` · **`BLOCKED`**),
  nagłówek maszynowy, Krok 00, higiena repo (14), aktualność runtime'ów (15),
  przeliczanie liczb z prozy (4), `CROSSDESK_AUDIT_DRYRUN=1`.
- **Drugi skill audytowy `audyt-naprawczy`** przyjęty w całości (D-015) —
  audyt kończący się naprawą klas dowodliwych bramką. Trzy odstępstwa
  CrossDeska w `rules/audit.md` (boundary files poza automatem, prefiks
  `audyt/`, zawis pytest = `n/a`).
- **`.claude/toolkit.local`** — zadeklarowane odstępstwo dla
  `agents/security-reviewer.md`. Powód namacalny: `update` **skasował** sekcję
  projektową (lock zgadzał się z plikiem → „kopia nietknięta"); odtworzona
  z `git show` i zaktualizowana do DEC-0019.

### 1. P0 — bramka `pre-push` skanuje dysk, nie pushowany commit

**Potwierdzone 2026-08-21 lekturą kodu, nie założeniem.** Lista plików jest
poprawna — pochodzi z commita (`pre-push:52`,
`git diff -z --name-only origin/main...HEAD`). **Treść już nie:**
`pre-push:222-228` robi `grep -E -l "$SECRET_PATTERNS" "$f"` **z dysku**,
z gardą `[ -f "$f" ] || continue`. Sekret zacommitowany i posprzątany **tylko
w working tree** przechodzi na `origin`. Hook nie czyta refów ze stdin ani nie
odtwarza commita w `git worktree`.

Reprodukcja: zacommituj plik z sekretem, popraw go tylko w working tree, pushnij.
Potwierdzone w **7 z 7** repozytoriów floty — wszystkie skopiowały ten sam
wadliwy szablon, więc to nie jest błąd autora tego repo.
Wzorzec naprawy: `claude-toolkit/NEW-PROJECT.md` §4.2 — refy ze stdin, zakres
`remote_sha..local_sha` (nowa gałąź: `local_sha --not --remotes`), odtworzenie
commita przez `git worktree add --detach`, advisory pipeline w `{ …; } || true`,
jeden `exit "$STATUS"` na końcu.

**Dowód wymagany do zamknięcia:** `test-gates.sh` → **6/6 z niesprzecznych
powodów** (patrz pozycja niżej — dziś harness nie jest w stanie tego zmierzyć).

### 1a. [P1, nowe 2026-08-21] Warstwa 5 `pre-push` myli awarię narzędzia ze znaleziskiem

`pre-push:323`:

```sh
(cd "$REPO_ROOT/guest" && cargo audit --quiet --deny warnings 2>&1) || {
    echo "❌ cargo audit found vulnerabilities in guest workspace."; exit 1; }
```

Gdy `cd` się nie powiedzie (brak katalogu), hook melduje **„found
vulnerabilities"** i kończy 1. Fail-closed — ale z fałszywym powodem, a to
psuje dwie rzeczy naraz: diagnostykę i **mierzalność bramki**.

Zmierzone: `test-gates.sh .githooks/pre-push` → `4 zdanych, 2 niezdanych`,
przy czym wynik jest **skażony**. Testy 2 (zdrowy commit) i 3 (usunięcie
gałęzi) padają, bo fixture nie ma katalogu `guest/`; test 1 „przechodzi"
**z tego samego powodu** — hook zwrócił 1, tylko nie za sekret. To jest
dokładnie klasa z Kroku 0 mastera: *skan, który padł, nie ma prawa podać
wyniku*. Fix: rozdzielić „nie mogę wejść / nie mam narzędzia" (`BLOCKED`
z instrukcją) od „znalazłem podatność"; dopiero potem `test-gates.sh` mierzy
cokolwiek. To jest **warunek konieczny** zamknięcia P0 wyżej.

### 2. ✅ Kopie do ręcznego scalenia — ZROBIONE

`security-reviewer.md` scalony (baza mastera + sekcja CrossDesk, accepted-risk
zaktualizowany DEC-0018 → DEC-0019) i zadeklarowany w `toolkit.local`.
`ci-cd.md` (+2/−41) i `red-team.md` (+1/−9) przejęte z mastera w całości —
nie miały treści projektowej, tylko były stare.

### 3. ✅ Krok 00 audytu — ZROBIONE

`toolkit-sync.sh check` jest pierwszą sekcją `audit.sh`; brak mastera obok repo
raportuje **`DEGRADED`**, nie „pominięto" (ścieżka konfigurowalna przez
`CROSSDESK_TOOLKIT_DIR`). Reguła przy błędzie w regule: **nie łataj kopii
w projekcie** — poprawka idzie do mastera i wraca przez `update`.

### 4. ✅ Odesłane do mastera — ZROBIONE 2026-08-21

Stary `rules/audit.md` miał sygnały **ogólne**, których master nie ma. Przy
przepisywaniu na nakładkę wypadły z tego pliku (są w `git show HEAD~:`), więc
albo wracają do mastera, albo znikają. Kandydaci (§3 „Backend" starej wersji):

- `except: pass` / `except: return []` jako klasa „swallowed errors";
- `datetime.now()` użyte jako **data dokumentu historycznego**;
- **ID jako licznik zamiast hasha**.

Wylądowały w masterze jako **punkt 26 „Dane, które cicho kłamią"**
(`kontrola-glebokosci.md`), po decyzji właściciela 2026-08-21. Wróciły tu przez
`update`, więc obowiązują całą flotę, a nie tylko ten projekt. Gałąź w toolkicie:
`fix/sync-nie-kasuje-scalonej-kopii` — **niezmergowana**, czeka na przegląd.

### 5. ✅ [P2] `toolkit-sync.sh` na macOS — NAPRAWIONE U ŹRÓDŁA 2026-08-21

`scripts/toolkit-sync.sh:240` (master) używa GNU-owego
`find skills -mindepth 1 -maxdepth 1 -type d -printf '%f\n'`. BSD find na macOS
nie zna `-printf` → `find: -printf: unknown primary or operator`, więc **check
kompletności skilli (D-015) nie wykonuje się na maszynie właściciela** — a
`check` i tak kończy zielono. Awaria wygląda dokładnie jak brak znalezisk, czyli
klasa z Kroku 0 mastera.

Naprawione w masterze (`-exec basename {} \;`) na gałęzi
`fix/sync-nie-kasuje-scalonej-kopii`, wraz z **poważniejszą** usterką wykrytą
przy okazji: `update` kasował ręcznie scaloną kopię, bo lock trzymał tylko sumę
kopii, więc plik stemplowany PO scaleniu wyglądał na nietknięty master. Lock ma
teraz drugą sumę — mastera z chwili stemplowania — a `validate-toolkit.sh` ma
test negatywny (sentinel: bez naprawy pada na drugim przebiegu). Gałąź
**niezmergowana**, czeka na przegląd właściciela.

### 6. [P2, nowe 2026-08-21] Dwie konwencje z fali 2026.08.21 bez decyzji

`conventions/naming-conventions.md` (233 l.) + `conventions/module-paths.md`
(184 l.) wraz z `templates/{lexicon.md,import-depth.sh}`. **Nie zaadoptowane** —
checklista audytu ich nie dereferencjonuje (punkty 1–25 bez zmian w tej fali),
a zadanie dotyczyło sposobu audytu. Realne dla kodu (nazewnictwo, głębokość
importów). Do decyzji właściciela: przyjąć czy jawnie odrzucić.

### Kryteria akceptacji

- ✅ `toolkit-sync.sh check .` → zielono (jedno odstępstwo zadeklarowane);
- ✅ Krok 00 wpięty w audyt;
- ✅ zachowana treść lokalna ma wpis w `decisions.md` (DEC-META-009) i
  w `toolkit.local` z uzasadnieniem;
- ✅ zmiany w osobnym commicie, oddzielone od pracy merytorycznej;
- ⬜ `test-gates.sh .githooks/pre-push` → **6/6** (blokowane przez 1 i 1a);
- ✅ promocje z §4 wykonane (punkt 26 w masterze);
- ⬜ przegląd i merge gałęzi `fix/sync-nie-kasuje-scalonej-kopii` w toolkicie.
## 🔴 P0 — z audytu 2026-08-22 (Red Team, zweryfikowane niezależnie)

### JIT-lite omija opt-in ORAZ scope DEC-0019 — whole-`$HOME` R/W bez ostrzeżenia

**Zweryfikowane empirycznie 2026-08-22**, nie tylko przeczytane.
`_jitlite_flags` ([management.py:563](../host/src/crossdesk_host/ipc/management.py#L563))
jest wołane **bezwarunkowo** z `_launch` (`:452`) i **nigdy nie sprawdza
`shared_folder_enabled`** — config ładuje wyłącznie po nazwę share'u i literę
dysku. Skutek: przy share'owaniu **wyłączonym** (default) otwarcie pliku
aplikacją Windows i tak tworzy `/drive:`.

Drugi błąd w tym samym miejscu: walidowany jest **plik**, a udostępniany
**katalog nadrzędny**, który nie przechodzi ponownej walidacji — mimo że
`parent_share_path` sam tego wymaga w kontrakcie („*Caller still must run
`validate_mount_path` on the result*",
[path_validation.py:104](../host/src/crossdesk_host/jit_mount/path_validation.py#L104)).

Repro (uruchomione, `$HOME` podstawione na tmp):

| argument | udostępniony katalog |
|---|---|
| `$HOME/notatki.txt` | **całe `$HOME`** |
| `$HOME` (katalog) | **rodzic `$HOME`** — poza allowed root |

**Skutek:** dokładnie ta eskalacja, którą DEC-0019 nazwał po imieniu — gość
czyta `~/.ssh` i `~/.config/crossdesk/vm.toml`, zapisuje `~/.bashrc`,
`~/.config/autostart/` i `~/.local/state/crossdesk/`. Kryt. #3 nie może zostać
uczciwie zamknięte, dopóki to żyje: kod przeczy `docs/DECISIONS.md:43-48`.

**Bramka utrwala błąd, zamiast go łapać.**
`test_jitlite_flags_shares_parent_of_opened_file`
([test_management_launch.py:456](../host/tests/test_management_launch.py#L456))
asertuje „*Only the parent dir is shared — not the whole `$HOME`*", ale fixture
kładzie plik w **podkatalogu** — własność pochodzi z fixture'a, nie z kodu.
Ten sam test ustawia `PeripheralsConfig()  # persistent share OFF` i oczekuje
`/drive:` mimo to, czyli **utrwala obejście opt-inu jako poprawne**.

**Fix + testy (muszą czerwienić na dzisiejszym kodzie):** `_jitlite_flags`
zwraca `None` gdy `not cfg.shared_folder_enabled`; `validate_mount_path` na
rodzicu z `allowed_roots` = katalog skonfigurowanego scope'u; odrzucić
`parent == Path.home()`. Testy: `test_jitlite_refuses_when_parent_is_home`,
`test_jitlite_refuses_directory_argument_above_home`,
`test_jitlite_noop_when_sharing_disabled`.
**Boundary:** po naprawie `docs/THREAT_MODEL.md` §C5 wiersz I wymaga przeglądu
(właściciel).

### Ostrzeżenie DEC-0019 o whole-`$HOME` jest wycinane przez własną redakcję

**Zweryfikowane empirycznie 2026-08-22.** `docs/THREAT_MODEL.md:120` mówi, że
scope `home` podnosi residual do **High** i jest *„mitigated **only** by the loud
warning"*. To ostrzeżenie nie dociera do użytkownika **żadnym** kanałem:

1. **Log** — `management.py:540` loguje `logger.warning("shared_folder_home_scope",
   warning=home_warning)`. Pole `warning` nie jest w `ALLOWED_FIELDS`
   (`observability/redaction.py`), a jego treść zawiera frazę `password`, którą
   łapie `_FORBIDDEN_PATTERNS` (`:97`) — dwa niezależne powody redakcji.
   Realny output: `{"event":"shared_folder_home_scope","warning":"<redacted>",
   "redaction_drop_count":1}`.
2. **CLI** — `launch_cmd.py` drukuje tylko „Launching {name}…"; `home_warning`
   nie jest przenoszone do `LaunchResponse`. Docstring `peripherals.py:377`
   twierdzi „Callers (launcher, CLI, GUI) surface it" — produkcyjny call-site
   jest **jeden** (`management.py:538`).

**Skutek:** warunek, pod którym właściciel przyjął ryzyko whole-`$HOME`
(needs-owner §9, DEC-0019), nie jest spełniony. To nie jest accepted risk,
tylko finding — mitygacja istnieje w dokumencie, nie w działaniu.

**Fix:** ostrzeżenie musi iść kanałem **omijającym redakcję świadomie** (osobny
kanał UI / stderr / pole w `LaunchResponse`), nie przez dopisanie `warning` do
`ALLOWED_FIELDS` — wzorzec `password` i tak zetnie treść. Test:
`test_home_scope_warning_survives_redaction_and_reaches_the_user`.

### `steady-state.xml` + `install.state.json` bez kontroli integralności

Gość, który raz zapisze w `~/.local/state/crossdesk/` (dostarcza to P0 wyżej),
dyktuje hostowi trwały XML domeny. `finalize_steady_state`
([steady_state.py:104](../host/src/crossdesk_host/installer/steady_state.py#L104))
czyta plik i podaje go do `redefine_steady_state` **bez żadnej walidacji**;
`install.state.json` nie ma sumy ani podpisu (grep `sha256|hmac|signature` w
`installer/state.py` = 0), więc `"steady_state": "done"` → `"pending"` odblokowuje
ponowny przebieg, a `on_session_ready` odpala na **każdym** Hello.

Prymitywy dostępne z samego XML-a: `<disk><source file='~/.ssh/id_ed25519'/>`,
`<filesystem><source dir='/'/>` (z pominięciem całej warstwy
`validate_mount_path`), `<emulator>` wskazujący binarkę wybraną przez gościa.
Auto-recovery po `destroy` wprowadza nową definicję w życie bez udziału człowieka.

**Trigger:** przed jakimkolwiek przejazdem `backend=real` z włączonym share'em.
**Fix:** sha256 XML-a w state przy instalacji i weryfikacja przed `defineXML`,
albo odbudowa XML z `DomainSpec` w procesie zamiast czytania pliku. Niezależnie:
share nigdy nie może obejmować `~/.config/crossdesk` ani `~/.local/state/crossdesk`.
Test: `test_finalize_rejects_tampered_steady_state_xml`.

### Kolejność naprawy tych trzech + flaga boundary (dopisane 2026-08-22)

Nie są równoległe: **JIT-lite jest bramą** do `steady-state.xml` (dostarcza
zapis do `~/.local/state/crossdesk`).

1. **JIT-lite** — jedyny z trzech, który wywala się przy **zwykłym użyciu**,
   bez złośliwego gościa (plik wprost w `$HOME` → rodzicem jest `$HOME`).
   Naprawa lokalna i mechanicznie gotowa: `validate_mount_path` przyjmuje
   `allowed_roots`, a `shared_folder_resolved_path()`
   ([peripherals.py:391](../host/src/crossdesk_host/config/peripherals.py#L391))
   zwraca korzeń skonfigurowanego scope'u — czyli walidacja **rodzica** ma
   gotowy argument:

   ```python
   if not cfg.shared_folder_enabled:        # (1) honoruj opt-in
       return None
   parent = parent_share_path(validated.canonical)
   if parent == Path.home():                # (2) nigdy całe $HOME
       return None
   validate_mount_path(                     # (3) rodzic wobec scope'u
       str(parent),
       allowed_roots=[Path(cfg.shared_folder_resolved_path())],
   )
   ```

   Zasada, której dziś brak: JIT-lite ma **zawężać** skonfigurowany scope,
   nigdy go poszerzać.

2. **Denylist `~/.config/crossdesk` + `~/.local/state/crossdesk`** w
   `jit_mount/path_validation.py`. Dwie linijki, a odcinają łańcuch do
   `steady-state.xml` **także** przy świadomie włączonym scope `home` — więc
   warte zrobienia niezależnie od kolejności reszty.

3. **`steady-state.xml`** — trigger to dopiero pierwszy przejazd
   `backend=real` z włączonym share'em. *Rek.: wariant (b)* — odbuduj XML
   z `DomainSpec` w procesie zamiast czytać plik. Nie ma pliku → nie ma czego
   podmienić; wariant (a) (sha256 w state) zostawia podatny `install.state.json`
   obok i wymaga osobno jego podpisania.

4. **Ostrzeżenie o scope `home`** — osobno, bo **dotyka boundary**. Najczystszy
   kanał (pole `warning` w `LaunchResponse` → `stderr` w `launch_cmd.py`)
   wymaga edycji `proto/**`, czyli decyzji właściciela. Wariant bez proto:
   stderr daemona — ale wtedy ostrzeżenie widzi operator daemona, niekoniecznie
   ten, kto klika. **Rozstrzygnąć przed naprawą, nie w trakcie.**

## Inbox — zapisane automatycznie, do sklasyfikowania

### [P1, audyt 2026-08-22] `AuthValidator`: nonce bez limitu, mapa bez sufitu, brak sprzątania

`_active_streams[nonce] = seq + 1` ([auth.py:90](../host/src/crossdesk_host/ipc/auth.py#L90))
bez limitu długości nonce'a, bez TTL, bez sufitu liczby wpisów. `remove_stream`
ma **jeden** call-site (`control.py:291`) — heartbeat i filesystem nie sprzątają
nigdy. Nonce rotowany co ramkę = trwały wpis na ramkę, a gałąź `seq != expected`
nigdy się nie wykonuje, więc **anty-replay milczy**.

Asymetria we własnym repo: `filesystem.py:19` ma `MOUNT_TOKEN_LEN = 32`
egzekwowane w `:130` z uzasadnieniem „*would let a malicious peer balloon host
memory*". Ten sam wektor dla `stream_nonce` — który jest **kluczem trwałej
mapy** — nie jest obsłużony. `proto/crossdesk/v1/common.proto:35-37` wymaga
16 bajtów i stałości w obrębie strumienia; host nie sprawdza ani jednego, ani
drugiego.

**Fix:** wymusić `len(nonce) == 16`; przypiąć nonce do strumienia i odrzucać
zmianę; `remove_stream` w `finally` na wszystkich trzech płaszczyznach; sufit
liczby strumieni. W tym samym zadaniu wyrównać `docs/THREAT_MODEL.md:96,99`
(boundary — właściciel).

### [P1, audyt 2026-08-22] SAST działa doradczo — 51 znalezisk bez triażu

`semgrep ci … || true` (`security.yml:145`) i bandit `… || true` (`:87`) nigdy
nie failują joba. SCA blokuje (`pip-audit`, `cargo audit --deny warnings`,
`cargo deny`), ale **SAST nie**. Lokalny przebieg: **51 znalezisk (4 ERROR,
2 WARNING, 45 INFO) + 2 błędy parsowania**. Zatriażowane w tym audycie: żadne
nie jest eksploatowalne (`saxutils.escape` to escaper nie parser;
`subprocess.run` dostaje listę; XML pochodzi od libvirt i z naszego szablonu),
ale **nie ma baseline'u ani allowlisty**, więc realne znalezisko wygląda dziś
identycznie jak dzisiejszy szum. Punkt 21: narzędzie obecne, ale niepodpięte
do bramki, daje złudzenie pokrycia.

### [P1, audyt 2026-08-22] `RailManager._windows` rośnie z danych gościa

`rail_manager.py:96-113` wstawia wpis per `window_id` (gość wybiera klucz) i
zapisuje `title` oraz `icon_png` **bez limitu rozmiaru**; usuwa tylko na
`KIND_DESTROYED`, czyli na zdarzenie, którego złośliwy gość nigdy nie wyśle.
Limit 1 MiB + magic PNG istnieje w `window_icon.py:110-116` — czyli **po** tym,
jak `rail_manager.py:112` już skopiował bajty; `_handle_icon_change` (`:230`)
omija walidator zupełnie. `THREAT_MODEL.md:88,132` deklaruje rate-limit na
Launch/Discover; `grep -rE 'rate_limit|maximum_concurrent_rpcs'` = **0 trafień**.

### [P1, audyt 2026-08-22] Hasło VM w argv `xfreerdp` → `/proc/<pid>/cmdline`

`rail_command.py:139` buduje `f"/p:{conn.password}"`, `freerdp/real.py:160`
odpala to `Popen`-em. Na Linuksie `/proc/<pid>/cmdline` jest domyślnie czytelne
dla wszystkich → drugie konto lokalne odczytuje hasło konta Windows.

**To nie jest out-of-scope §C7** (tamto wyłącza *tego samego* użytkownika):
projekt świadomie broni się przed **innymi** kontami lokalnymi w trzech
miejscach — `vm.toml` 0600, socket mgmt 0600, log capture 0600. Argv obchodzi
wszystkie trzy naraz. **To także nie jest** powtórka P1-1 z 2026-07-07: tamta
naprawa dotyczyła wyłącznie logu i explicite zostawiła realne argv.
Precedens we własnym repo: `keyring/kwallet.py:63` podaje sekret przez `input=`
(stdin). Ta sama właściwość dotyczy `crossdesk vm credentials set --password`
(plus historia powłoki). Test: `test_password_never_appears_in_spawned_argv`.

### [P2, audyt 2026-08-22] Trzy deklaracje THREAT_MODEL bez pokrycia w kodzie

Wszystkie wymagają edycji boundary (właściciel) **albo** naprawy kodu:
- `THREAT_MODEL.md:76` obiecuje TTY-gated `credentials show`;
  `cli/credentials_cmd.py:55-62` drukuje bezwarunkowo, `grep isatty host/src` = 0.
- `THREAT_MODEL.md:117` obiecuje weryfikację `mount_token` „on every subsequent
  op"; `ipc/filesystem.py:128-139` sprawdza **tylko długość** i nigdy nie
  porównuje z wydanym tokenem. Uśpione — `trigger_mount` bez produkcyjnych
  callerów; domknąć razem z Phase 5.
- `THREAT_MODEL.md:99` obiecuje „per-stream bounded buffers"; nie istnieją
  (pokryte pozycją o `AuthValidator` wyżej).

### [P2, audyt 2026-08-22] Okno TOCTOU na sockecie zarządzania

`daemon.py:277-284`: `add_insecure_port` → `start()` → **dopiero potem**
`chmod 0600`. Na Linuksie chroni `$XDG_RUNTIME_DIR` (0700), ale fallback
`~/.local/run` (`ipc/management.py:86-88`) powstaje `mkdir(parents=True)`
z domyślnym umaskiem. Okno milisekundowe, wymaga innego konta lokalnego.

### [P1, audyt 2026-08-22] Dziesiątki pól logów spoza allow-listy → `<redacted>` w produkcji

Ta sama przyczyna co P0 z ostrzeżeniem, szerszy zasięg: `error`, `detail`,
`reason`, `app_id`, `file_path`, `host_dir`, `phase`, `fsms` i inne nie są
w `ALLOWED_FIELDS`, więc w trybie lenient produkcyjny log gubi treść
(`daemon.py:294,317`, `management.py:477,582,597`, `lifecycle/dbus_listener.py:65`).
Dług obserwowalności bez ścieżki exploitu — ale to znaczy, że diagnostyka
produkcyjna jest dziś istotnie słabsza, niż wygląda w kodzie.

### [P2, audyt 2026-08-22] `import libvirt` poza `libvirt_ctl/real.py` — bez gate'a

`lifecycle/domain_events.py` importuje `libvirt` w trzech miejscach (`:198`,
`:243`, `:260`). Abstrakcja jest zachowana (`DomainEventSource` Protocol +
Mock + Libvirt), więc to drugi **legalny** real-impl, ale reguła w
`rules/audit.md` §6 i `backend.md` mówi „poza `real.py`" i jest dziś
nieprawdziwa. **Gate'a nie ma** (grep w `.githooks/`, `.github/`, `audit.sh` = 0)
— audyt sprawdza to ręcznie co tydzień. Ratchet: albo dopisać drugi dozwolony
call-site do reguły, albo przenieść klasę; w obu wypadkach dołożyć grep-gate.

**Gorszy skutek uboczny:** autouse-guard z incydentu 2026-07-05
(`host/tests/conftest.py:40`) łata wyłącznie `RealLibvirtController._connect`,
a `LibvirtDomainEventSource.start()` woła `libvirt.open()` wprost
(`domain_events.py:209`) — czyli **omija guard**. Ta ścieżka jest
nie-mutująca (subskrypcja zdarzeń), więc nie powtórzy incydentu z `undefine`,
ale docstring guardu obiecuje „slam the real-libvirt connection choke point
shut for the whole suite" i to jest dziś nieprawda.

### [P2, audyt 2026-08-22] Rozjazd deklaracji runtime'u Pythona

`requires-python = ">=3.9"` (`host/pyproject.toml:8`) wobec **wyłącznie 3.12**
w matrycy CI. Albo deklarowana podłoga jest nietestowana (czyli nieprawdziwa),
albo 3.9 jest wspierany i wtedy jego status EOL przesądza o P0 wg punktu 15.
**Nie rozstrzygam** — audyt nie miał `DOCS_SOURCE`, więc nie ma prawa podać
daty EOL jako faktu. Do sprawdzenia przy pierwszym audycie ze źródłem
dokumentacji.

### [P2, audyt 2026-08-22] Dwa uśpione, z jawnym triggerem

- `attach_virtiofs` buduje XML f-stringiem bez escapingu
  (`libvirt_ctl/real.py:251-261`); `trigger_mount` nie ma produkcyjnego callera.
  Trigger: Stage C. Nazwa katalogu z apostrofem jest osiągalna dla gościa
  w share'owanym `~/Documents`.
- `display_name` niesanityzowany w `name:` klauzuli `/app:` i w `Name=` pliku
  `.desktop` (`management.py:128` sanityzuje tylko `app_id`). Źródłem jest
  lokalny socket mgmt (0600), czyli użytkownik — higiena, nie ścieżka ataku.

### [NOTE, audyt 2026-08-22] Nowy punkt do checklisty: fixture zamiast kodu

Trzy znaleziska tego audytu mają **zielony test asertujący własność silniejszą,
niż kod egzekwuje** (`test_management_launch.py:466,471`,
`test_security_edges.py:29-43`). To rozszerzenie punktu 13 („test
samopotwierdzający") o wariant, w którym własność pochodzi z **fixture'a**,
nie z produkcyjnego kontraktu. Kandydat do `promote` przy najbliższej sesji
w toolkicie.



<!-- Nietrywialne zadanie odkryte poza bieżącym scope trafia tu OD RAZU,
gdy priorytet jest niejasny (reguła „zapisz najpierw" w rules/general.md,
adopcja 2026-07-12). Praca v0.1.0 → PLAN.md, nie tu. Najpierw deduplikuj.
Zapis ≠ zgoda na implementację. Pusto = nic nieoczekującego. -->

_(pusto)_

---

## P0

### ✅ BRAK DETEKTORA ŚMIERCI VM — ZROBIONE `414c879` (2026-07-14, live-verified)
Zamknięte tego samego dnia, w którym odkryte. **Zmierzone na żywo:** `virsh destroy` →
wykryte w **1 s** → auto-recovery → domena w 6 s → **agent w 25 s** (budżet 90 s),
bootując dysk bez nośników. Wymagało **trzech** brakujących elementów, nie jednego:
realne `LibvirtDomainEventSource` (nie istniało), recovery w `DomainEventReactor`
(tylko logował), oraz `LibvirtController.start()` (nie było czym wystartować martwej
domeny — `hard_destroy()` robi `destroy()+create()`, a `destroy()` na martwej rzuca).
Czyste wyłączenie gościa świadomie **nie** jest wskrzeszane. Oryginalny opis:

<details><summary>diagnoza z live-verify</summary>

**Zabity VM nie jest w ogóle zauważany przez daemona.** Odkryte przy przejeździe
Fazy B na żywej domenie: `virsh destroy windows-guest` → 60 s obserwacji → **zero**
linii w logu daemona, zero eskalacji FSM, domena leży wyłączona. Root cause
zweryfikowany (nie zgadnięty):

- **FSM heartbeatu tyka z `request_iterator`** strumienia gRPC
  (`ipc/heartbeat.py`). Śmierć VM zamyka strumień → **FSM przestaje tykać i nigdy
  nie dojdzie do HARD_DESTROY**. FSM eskaluje tylko gdy gość *żyje, ale jest
  niezdrowy* — nie gdy zniknie.
- **`daemon.py` nie wpina żadnego źródła zdarzeń domeny** (grep po
  `DomainEventReactor|LibvirtDomainEventSource|domain_events|event_source`: 0 trafień).
- **`LibvirtDomainEventSource` NIE ISTNIEJE** — `lifecycle/domain_events.py` ma tylko
  `DomainEventReactor` + `MockDomainEventSource`. Realnego źródła nigdy nie napisano.

**Co trzeba zrobić:** realne `LibvirtDomainEventSource` (libvirt event loop →
`VIR_DOMAIN_EVENT_STOPPED`) wpięte przez `DomainEventReactor` do daemona, z akcją
recovery.

**Pułapka projektowa (ważna):** `hard_destroy()` robi `destroy()` **+** `create()`,
a `destroy()` na **martwej** domenie rzuca `RuntimeError` (`real.py`). Recovery po
zabiciu VM musi wołać **samo `create()`** — naiwne wpięcie `hard_destroy` do
detektora **wywali się**.

**Budżet:** zmierzony reconnect po `create()` = **105 s** przy budżecie #6 = 90 s.
Nawet z działającym wyzwalaczem kryterium nie przechodzi. Kandydat na przyczynę:
dysk SATA + NIC e1000e zamiast virtio (jest osobna pozycja „virtio perf").
Alternatywa: właściciel re-definiuje budżet.

**Kontekst:** naprawa P0 `hard_destroy` steady-state (data-loss) jest **ZAMKNIĘTA
i live-verified** — recovery bootuje dysk, nośniki wyjęte, zero reinstalacji. Była
**konieczna, ale niewystarczająca** dla #6.


### A7-live install-path findings (żywa reinstalacja + adversarial audyt 11-agent, 2026-07-01)
Czysta reinstalacja na żywym KVM boxie **potwierdziła A7-live core**: świeży
`crossdesk install` → Windows unattended → agent NT-service **auto-łączy się w
~12 min, zero ręcznych kroków** (Hello+READY+heartbeat). Naprawione+zmergowane:
drive-find (`0dc3424`) + FreeRDP TOFU pin-clear (`2ab10d1`). Adversarial Workflow
(6 potwierdzonych defektów) + live-diagnoza odsłoniły resztę:

- **[P0-latentny, BLOKUJE A3] `hard_destroy` → REINSTALACJA Windows = utrata danych.**
  Domena ma install-ISO na `<boot order='1'>` przez CAŁE życie VM; nie ma
  steady-state XML. `hard_destroy()` ([`libvirt_ctl/real.py`](../host/src/crossdesk_host/libvirt_ctl/real.py) 94-107)
  robi `destroy()`+`create()` z persistent config → post-install auto-recovery
  heartbeat-FSM ([`ipc/heartbeat.py`](../host/src/crossdesk_host/ipc/heartbeat.py) 272-274 →
  `watchdog/fsm.py` HARD_DESTROY) bootuje install-ISO → **autounattend reinstaluje
  Windows na istniejącym dysku, bez człowieka** (albo wedge na firmware). Dziś
  latentny (daemon używa mock-libvirt); **A3 NIE MOŻE wpiąć realnego
  `LibvirtController` do lifecycle dopóki to nie naprawione.** Fix: po pierwszym
  Hello redefiniuj domenę do steady-state (eject oba CD, disk `boot order=1`,
  `defineXML` z zachowaniem UUID by przeżyło destroy+create) + persist flag
  „installed" w `install.state.json`.
  **[MECHANIZM shipped 2026-07-05]** `build_steady_state_domain_xml` +
  `redefine_steady_state` (Protocol/real/mock) + testy gotowe; ZOSTAJE tylko
  wpięcie finalize po Hello + live-verify (box-gated). Front w
  [`PLAN.md`](../PLAN.md) TERAZ; stan w [`status.md`](status.md) Partial.
- **[P1] Brak post-install wait — `_step_run_autounattend` deklaruje sukces gdy
  domena tylko `is_running()`.** ([`cli/install_cmd.py`](../host/src/crossdesk_host/cli/install_cmd.py)
  398-411; `install_agent_service`/`post_install_tweaks` = no-op printy). Host
  nigdy nie obserwuje przejścia installing→installed → **żaden finalize (eject /
  redefine / logoff konsoli / healthcheck) nie może być zsekwencjonowany**, a
  padnięty in-guest FirstLogonCommand jest niewidoczny. Enabler dla powyższego +
  console-session fix. Fix: bounded poll na pierwszy Hello/heartbeat (timeout →
  czytelny błąd wskazujący VNC + FirstLogonCommands log) gate'ujący finalize.
- **✅ [P1 ZROBIONE `0bccb73`] Console-session blokowała PIERWSZY managed RAIL
  launch.** AutoLogon(LogonCount=1) zostawiała aktywną sesję konsoli `crossdesk`;
  Win10 single-session → RDP RemoteApp jako ten sam user padał `LOGON_FAILED_OTHER`.
  Fix: order-21 `shutdown /r` (OS-initiated, czysty) na końcu FirstLogonCommands →
  czysty logon screen, agent (session 0) reconnectuje. **LIVE-VERIFIED na drugiej
  pristine reinstalacji:** Hello#1 → auto-reboot → Hello#2 → `crossdesk launch
  notepad` renderuje Notepada (1426×782 natywne okno). Follow-up (P1): pierwszy
  launch tuż po reconnectcie ściga się z verify-creds → bounded post-install-wait
  (niżej) by wygładził.
- **[P1] Eject install media po instalacji.** Install-ISO zostaje podłączone →
  każdy reboot re-trafia „press any key to boot from CD"; **live: ACPI reboot
  świeżego gościa ZAWIESIŁ go na firmware**, recovery = eject ISO + destroy+start.
  Współdzieli fix ze steady-state XML (P0 wyżej). Host-side, gated na post-install-wait.
- **✅ [P1 ZROBIONE `29ccea5`+`bac8dfd`] Hardcoded ścieżki OVMF łamały non-Debian.**
  Fix: `resolve_ovmf()` w `domain_xml.py` (env override `CROSSDESK_OVMF_CODE/VARS`
  → Debian/Fedora/Arch candidate-list → `FileNotFoundError` z listą ścieżek);
  `create_libvirt_domain` woła to (I/O) i przekazuje do `DomainSpec`, `build_domain_xml`
  zostaje pure. + `check_ovmf_firmware` doctor pre-flight. 9 nowych testów.
  **Pozostaje (P2):** Win11 (secure=yes+smm) wymaga osobnego deskryptora.
- **[P2] mTLS guest identity nie rotuje przy reinstalacji.** `_resolve_mtls_pki`
  ([`cli/install_cmd.py`](../host/src/crossdesk_host/cli/install_cmd.py) 185-210)
  reużywa `infra/certs/pki` (default) → każda instalacja na klonie dzieli tę samą
  guest identity + CA (contra per-install-uniqueness obietnica `pki.py`). RDP TOFU
  rotuje, mTLS nie — niespójność. Hardening (same-user host compromise = out of
  scope per THREAT_MODEL). Fix: mint fresh leaf przy wykrytej reinstalacji, albo
  głośny warn + gate in-repo dev-dir za env/flag.
- **[P2] Single-VM hardcoded assumptions.** `_DISK_GB=64` (brak `--disk-size`),
  `vsock_cid=3` + `_DOMAIN_NAME="windows-guest"` (2 instalacje kolidują;
  `define_and_start` cicho niszczy istniejącą domenę), hostfwd `3389` + endpoint
  `10.0.2.2:50051` (SLIRP-only, brak port-conflict detekcji). Większość świadoma
  per DEC-0017 single-VM; warte: `--force`/confirm guard przed clobber + port-conflict
  doctor check.
- **[C-2, audyt 2026-07-07 P2-8] Marker-gated `RealLibvirtController`
  destructive-path integration test.** Trigger: owner greenlight P0 live-verify
  (needs-owner ▶). Wtedy: pytest marker `live_libvirt` (deselected by default)
  pokrywający `define_and_start` → `redefine_steady_state` → `hard_destroy` →
  `undefine` na jednorazowej throwaway domenie (NIGDY `windows-guest`), odpalany
  w cyklu live-verify → kryt. #6 staje się regression-guarded. Dziś
  `test_libvirt_real.py` pokrywa tylko czysty `_with_domain_uuid`.

</details>

### Filesystem bridge — kierunek A→B (DECYZJA właściciela 2026-06-12; beta-blocker #1)
- **Etap A: litera dysku `Z:` + redirect Dokumenty.** `[~PARTIAL 2026-06-12]`
  Host-side + generator skryptu **ZROBIONE** na `feat/fs-drive-letter`
  (5 commitów; bramki zielone): config (`shared_folder_drive_letter` D-Z +
  `redirect_documents`/`redirect_desktop` + `shared_folder_drive_path()`),
  workdir UNC→`Z:\` w `_peripheral_flags`, `installer/drive_map.py` generator
  skryptu logon + 9 testów. **Live-findings (na żywej VM) zmieniły mechanizm:**
  Run key NIE odpala się przy logonie RAIL (rdpinit shell) → ścieżka (i)
  MARTWA; **trwałe mapowanie `/persistent:yes` JEST auto-odtwarzane przez MPR**
  → to jest mechanizm drive'a. `workdir:Z:\` jest racy → robust lever to
  redirect shell-foldera (leniwy). **POZOSTAJE:** GUI-verify Save dialogu
  (brak xdotool/scrot w sesji — doinstaluj lub user patrzy) + wybór triggera
  one-time (A: deklaratywny `HKCU\Network` przez autounattend / B: agent-svc
  `CreateProcessAsUser`) + wiring provisioning. Pełny stan:
  [`history/2026-06-12-fs-stage-ab-plan.md`](history/2026-06-12-fs-stage-ab-plan.md)
  §2.7 „AKTUALIZACJA MECHANIZMU" + `status.md` A1. **Bez boundary files.**
- **Etap B: VirtioFS jednego folderu jako trwały dysk `Z:`** (po becie).
  Plan: [`history/2026-06-12-fs-stage-ab-plan.md`](history/2026-06-12-fs-stage-ab-plan.md)
  §2.8. Gated: smoke-test sterownika virtio-win VirtioFS
  `[HW]` + weryfikacja vhost-user/memfd na `qemu:///session` + **ADR
  właściciela + THREAT_MODEL row** **`[user-approval]`**. Provider-swap pod
  tym samym `Z:` (redirect z Etapu A bez zmian); rdpdr zostaje fallbackiem.

### Display / Phase 4 baseline
- **X11 RAIL pipeline.** Implement
  [`host/src/crossdesk_host/display/rail_manager.py`](../host/src/crossdesk_host/display/rail_manager.py)
  RAIL launch z `GDK_BACKEND=x11`; translate `RailWindowEvent` →
  compositor ops (CREATED → spawn + WM_CLASS; DESTROYED → close; FOCUS/
  TITLE/ICON/MOVED/RESIZED → WM hints). Idempotent + out-of-order
  tolerant. `[HW]`

### GPU passthrough (Phase 4.5 / post-MVP)
ADR: [`docs/DECISIONS.md`](../docs/DECISIONS.md) DEC-0009. Strategia:
[`docs/GPU_PASSTHROUGH.md`](../docs/GPU_PASSTHROUGH.md).
- **`crossdesk gpu setup` helper.** Per-distro kernel cmdline (GRUB /
  systemd-boot / NixOS), initramfs binding (mkinitcpio / dracut /
  initramfs-tools), GPU + audio function PCI ID detection, `--commit`
  vs `--dry-run` default. Plus `crossdesk gpu verify` post-reboot.
- **Tier 1 vendor smoke tests.** Manual QA matrix per release: ≥1 NVIDIA
  Tier 1 + ≥1 AMD Tier 1 host. CI bez dedicated runner. `[HW]`

### Looking Glass (post-Phase 4.5)
Strategia: `docs/GPU_PASSTHROUGH.md` §"GPU passthrough interakcja z RAIL".
- **Bundle LG client w distro packages.** ~5 MB binary do deb/rpm/AUR/
  NixOS/PyPI. GPL-2.0+ kompatybilne. Update
  [`docs/PACKAGING.md`](../docs/PACKAGING.md).
- **LG host installer w Windows install pipeline.** Optional component
  (`crossdesk install --gpu --with-lg`) → secondary OEM disk + Windows-
  side autostart. `[HW]`
- **IVSHMEM device w `infra/launch-vm.py`.** 8 MB shared memory region
  do libvirt domain XML gdy LG enabled.
- **Scream audio bundling.** LG nie ma audio; Scream = standard companion.
  Bundle Scream client + server z LG package set.
- **`crossdesk launch --mode=desktop` CLI.** Per-app config knob
  `mode = "rail" | "desktop"` w `~/.config/crossdesk/peripherals.toml`.
  `desktop` mode → spawn LG client zamiast FreeRDP RAIL.

### Post-MVP / winapps parity
- **App discovery service.** Źródło: `third_party/winapps/install/
  ExtractPrograms.ps1` (336 lines PowerShell). Reimplement jako Rust
  binary w `guest/` (mamy windows-rs), gRPC RPC nad VSOCK. Sources:
  `HKLM\...\App Paths` + `HKLM\...\Uninstall` + `HKCU\...\Uninstall` +
  `WOW6432Node` 32-bit + UWP via `Get-AppxPackage` + Chocolatey + Scoop.
  Beat winapps gap (oni robią tylko App Paths).

---

## P1

### Metryka launcha nie mierzy kryterium #2 (end-to-end) — follow-up (2026-07-14)
`launch_duration_seconds` (`472b0e8`) mierzy **host-side**: resolve + verify-creds +
spawn FreeRDP = **7,5 ms p50**. Użytkownik czeka **2,75 s**. Czyli daemon to ~0,3%
opóźnienia; resztę zjada FreeRDP negocjujący RDP+RAIL **po** powrocie RPC.
**Żeby zmierzyć kryterium w produkcie**, trzeba skorelować launch z `RailWindowEvent`
CREATED od agenta (host już go dostaje — `RailManager`). Bez tego `crossdesk metrics`
pokazuje liczbę, która wygląda świetnie i **nie jest tym, co obiecuje kryterium**.

### Ogon launcha (max 5,3 s) + brak okna przy pierwszym launchu po boocie
Zmierzone przy #2: p50 2,748 s (PASS), ale **max 5,311 s wychodzi poza budżet 3 s**,
a **pierwszy launch po boocie gościa nie wyprodukował okna w ogóle** (rc=0, „Launching
Notepad…", brak okna) — to znany wyścig z verify-credentials. Kandydat: bounded
post-boot wait zanim launch przejdzie przez bramkę.


### Agent nie łączy się ponownie po restarcie daemona hosta (live-verified 2026-07-14)
**Restart daemona osierocia gościa aż do reboota VM.** Zaobserwowane przy pomiarze #4:
daemon zrestartowany → VM **działa**, Windows **wstał** (RDP 3389 nasłuchuje), proces
agenta **żyje** — ale kanały control/heartbeat **nigdy nie wracają**. 160 s obserwacji,
`ss -tn | grep :50051` = **0**. Dopiero restart VM (przez auto-recovery) przywrócił
agenta w 19 s.

**Wniosek:** agent dzwoni do hosta **tylko przy własnym starcie**; nie ma pętli
re-dial przy zerwaniu połączenia z hostem.

**Skutek dla bety:** każda aktualizacja CrossDeska, crash daemona albo zmiana configu
zostawia gościa bez kontroli, dopóki user nie zrestartuje VM. Dla bety to szorstkie.

**Fix (guest-side, Rust):** pętla reconnect z backoffem w `agent-svc` — dial → on
disconnect → retry (np. 1s → 30s cap). Host-side nic nie trzeba.


### [P1, Security Review 2026-07-22, SEC-01] Bramka sekretów po majorze — niepotwierdzona jako fail-closed
`gitleaks-action` 2.3.9 → **3.0.0** (`security.yml:48`). Ta akcja ma historię trybu,
w którym kończy się kodem 0 mimo trafień (brak licencji dla organizacji = cichy
no-op). Repo jest **publiczne**, a lokalny mirror w `pre-push` jest warunkowy
(`command -v gitleaks`) — więc jeśli v3 jest fail-open, sekret w historii nie
zostanie zatrzymany przez nic. **Zamknięcie:** kanarek — gałąź z syntetycznym
kluczem w formacie łapanym przez gitleaks, push, oczekiwany job **czerwony**.
Zielony = cofnąć bump albo skonfigurować licencję. Do czasu przejazdu kanarka
NIE twierdzimy, że skanowanie sekretów jest egzekwowane.

### CI / supply chain — fala z audytu 2026-07-12 (✅ ZROBIONA `05653c7`, 2026-07-14)
Sign-off właściciela 2026-07-14 („wykonaj falę + merge"); `.github/**` przestało
być boundary dla pętli (`loop-spec.md` toggles). **zizmor: 86 findings (42 High)
→ 16 (0 High / 0 Medium / 0 Low, 3 informational).**
- **✅ [P1] `security.yml` manual-only vs dokumentacja — ZROBIONE.** Przywrócone
  triggery `push` + `pull_request` + `schedule` (pn 06:17 UTC) → `AGENTS.md:64-69`
  („runs on every push, every PR, and weekly on Mondays") stało się **prawdziwe
  bez edycji boundary** (opcja (a) z needs-owner §8). Repo publiczne = Actions
  darmowe, więc powód billing-freeze'u 2026-05-20 odpadł.
- **✅ [P1, Red Team HIGH] SHA-pinning third-party — ZROBIONE.** Wszystkie 4
  third-party przypięte do 40-hex SHA: `dtolnay/rust-toolchain` ×5 →
  `4be7066…c30` (branch `stable`), `bufbuild/buf-setup-action` → `a47c93e…a99`
  (v1.50.0), `gitleaks/gitleaks-action` → `ff98106…0c7` (v2.3.9),
  `softprops/action-gh-release` był już przypięty. `image: semgrep/semgrep` →
  digest `sha256:59fbed…66e`. Naprawiony też **dryf komentarz↔YAML**:
  `release.yml` twierdził, że jest przypięty, gdy nie był. Konwencja
  („third-party = hash, first-party = tag") jest teraz **maszynowo sprawdzalna**
  w `.github/zizmor.yml` — bez niej `--no-config` pokazuje **33 High**.
  ⏸ **Zostaje decyzja właściciela:** czy zratchetować także first-party
  (`actions/*`, `github/*`) do hash-pinu, czego chce `ci-cd.md` §2 — to te 33
  findings. Zaparkowane w `needs-owner.md`.
  Nie zrobione (świadomie, poza zakresem fali): `actions/attest-build-provenance`
  + `cargo build --locked` w release — trigger: przed pierwszym tagowanym release.
- **✅ [P1, Red Team LOW 2026-07-12] pre-push secret-gate bypass — ZROBIONE
  `1b9c6f1` (2026-07-14).** `.githooks/pre-push` iterował `for f in $CHANGED_FILES`
  (niecytowane) → nazwa ze spacją rozpadała się na tokeny, `[ -f "$f" ]` je odrzucał,
  plik z realnym sekretem **nigdy nie był skanowany** (gdy gitleaks nieobecny = jedyna
  bramka). Potwierdzone empirycznie: `git diff --name-only` wypisuje ścieżkę ze spacją
  BEZ cudzysłowów. **Fix:** diff czytany NUL-delimited do tablicy + helper
  `changed_match`; ten sam split dotykał pętli console.log/print/qmllint oraz
  akumulatorów `SECRET_HITS`/`QML_HITS` → też tablice. 3 testy regresyjne
  (`host/tests/test_pre_push_hook.py`), **sentinel-verified**: spaced-filename test
  pada na starym hooku (skaner przechodzi obok pliku), przechodzi na nowym.
- **✅ [P1] Brak dependency bota — ZROBIONE.** `.github/dependabot.yml`: 4
  ekosystemy (github-actions, cargo ×2 guest+gui, pip host), tygodniowo (pn),
  cooldown 5 dni, minor/patch grupowane, majory osobno; security-updates omijają
  cooldown z definicji. **Uwaga:** `dtolnay/rust-toolchain` NIE będzie bumpowany
  automatycznie — repo publikuje branche (`stable`), nie tagi semver, a dependabot
  potrzebuje wersji w komentarzu przy `uses:`. Pin bumpować ręcznie (udokumentowane
  w nagłówku `dependabot.yml`; warto sprawdzać przy cotygodniowym audycie).
- **✅ [P2, ta sama fala] Top-level `permissions:` + `persist-credentials` —
  ZROBIONE.** `contents: read` na górze `ci.yml`, `compat-matrix.yml`,
  `security.yml`, `release.yml`; `persist-credentials: false` na **wszystkich 13**
  checkoutach (artipacked → 0). Przy okazji odwrócono dwa złamane least-privilege:
  `security.yml` dawał `security-events: write` **wszystkim** 5 jobom (teraz tylko
  dwa uploadujące SARIF), a `release.yml` dawał `contents: write` jobowi
  trzymającemu sekret podpisujący (teraz tylko `publish-release`).

### Display & forwarding
- **RAIL window icons — native high-res Windows icons on Linux windows.**
  (user request 2026-06-02; supersedes the P2 "Auto-extract icons" item.)
  Today FreeRDP sets only a 32×32 `_NET_WM_ICON` from the RDP RAIL ICON
  orders — blurry in docks/hi-DPI. The proto already carries the payload
  (`RailWindowEvent.icon_png`, populated for CREATED/ICON_CHANGED), so **no
  proto change**. Design:
  1. **Agent (rail-bridge)** — on CREATED, resolve the window's process
     image (`GetWindowThreadProcessId` → `OpenProcess` →
     `QueryFullProcessImageNameW`), extract the largest icon
     (`PrivateExtractIconsW(path, 0, 256, 256, …)`), convert HICON→RGBA
     (`GetIconInfo` → `GetDIBits` 32bpp top-down BGRA; alpha-from-mask
     fallback), PNG-encode (`png` crate), set `icon_png`. The exact seam is
     `events.rs::build_rail_event` (`icon_png: vec![]` TODO). Adds windows-rs
     `Win32_UI_Shell` + `Win32_Graphics_Gdi` features.
  2. **Host consume** — two paths (do both):
     a. *Titlebar / window icon*: set a rich multi-size `_NET_WM_ICON`
        (16/32/48/64/128/256) on the RAIL X window, found by **WM_CLASS
        instance == app_id** (we already pass `/wm-class:<app_id>`; per-app
        is the right granularity for icons). Needs PNG decode + X11 prop
        set — Pillow + python-xlib (new host deps) OR a small ctypes/xcb
        helper. Source = the agent's `icon_png` (RailManager already stores
        it in `_windows[hwnd]["icon_png"]`).
     b. *Dock / launcher / alt-tab*: write per-app
        `~/.local/share/applications/crossdesk-<app>.desktop` with
        `StartupWMClass=<app_id>` + `Icon=crossdesk-<app_id>`, and install
        the extracted icon into `~/.local/share/icons/hicolor/<size>/apps/`.
        Idiomatic, **no runtime X11/deps** — the desktop matches WM_CLASS to
        the .desktop and uses its icon. Highest-visibility, lowest-risk.
  Correlation note: control-plane `icon_png` is keyed by HWND; the X window
  is keyed by WM_CLASS=app_id. They don't share a key per-window, but
  per-app is sufficient for icons (cache the latest non-empty icon per
  process_id→app, or extract once at discovery). `[HW]`
- **Wayland-native RAIL.** FreeRDP 3.x Wayland support audit; missing
  `xdg-shell` / `xdg-decoration-unstable-v1` / `xdg-foreign-unstable-v2`
  / `wlr-foreign-toplevel-management` handlers (upstream FreeRDP PR
  preferred). Migrate `rail_manager.py` do Wayland-native default na
  Wayland sessions; fall back na X11 dla unknown compositors. `[HW]`
- **Multi-monitor RAIL — wiring deferred parts.** `enumerate_monitors()`
  shipped; podłączyć do `rail_manager._handle_create` + WM-hint
  forwarding via `_NET_WM_DESKTOP` / xdg_output_manager + per-monitor
  scale re-eval on drag-between. `[~PARTIAL]` `[HW]`
- **HiDPI per-monitor scale + monitor-change re-eval.** `hidpi.py`
  shipped system-level; per-monitor wymaga RANDR/wl_output per-output
  enumeration; re-evaluation on monitor change events. `[~PARTIAL]`

### Peripherals & host integration
Strategia: [`docs/PERIPHERALS.md`](../docs/PERIPHERALS.md). Typed config
([`host/src/crossdesk_host/config/peripherals.py`](../host/src/crossdesk_host/config/peripherals.py))
shipped — implementacje brakują.
- **Audio z PipeWire per-app tagging.** FreeRDP `/sound:sys:pipewire`
  (pulse fallback). Tag każdy RAIL stream `PA_PROP_APPLICATION_NAME`
  → separate streams w `pavucontrol` / `wpctl`.
- **Clipboard rich-content + file-list translation.** FreeRDP
  `+clipboard` + extended formats. Rich mode: intercept FORMAT_FILELIST
  guest→host, translate UNC → local paths. Text-only mode: drop FILELIST.
  Off default = isolation.
- **Drag-and-drop host-to-guest.** Host compositor initiates; FreeRDP
  RAIL receives drop + FORMAT_FILELIST; Windows app opens via translated
  path. Direction limited host→guest; reverse OOS.
- **Microphone.** FreeRDP `/microphone:sys:pulse` lub pipewire. Default
  off; opt-in per VM przez typed config.
- **Printer redirection via CUPS.** FreeRDP `/printer:CUPS`. Modes:
  `auto` (all) lub `named:<printer-name>`. Document Easy Print quality
  caveats (duplex, color).

### Versioning & compatibility
Strategia: [`docs/VERSIONING.md`](../docs/VERSIONING.md). ADR DEC-0007.
- **`crossdesk upgrade` agent hot-swap z handshake-aware sequencing.**
  FSM enters `UPGRADING` state during agent swap (suppresses
  HARD_DESTROY ≤60s); exits po pierwszym Hello z nowego agenta. Patrz
  P2 Operations `crossdesk upgrade` (ten sam ficzer, dwa side).
- **N-1 agent CI matrix.** GitHub Actions job: build previous minor
  agent, run handshake tests vs current host. Catches accidentally-
  breaking proto changes. Compat-matrix wf już istnieje; brakuje
  trigger na faktyczny pre-built agent.
- **CLI semver commitment v1.x — snapshot test.** Snapshot `--help`
  output, fail on unexpected change. Strategia w `VERSIONING.md`;
  brakuje test'u. `[~PARTIAL]`
- **`crossdesk config migrate` CLI subcommand.** Shipped 2026-05-23:
  argparse plumbing + migration logic in `cli/config_cmd.py`; 6 tests.
  Remaining: migration registry for v2+ schema (host daemon config +
  app catalog). `[~PARTIAL]`

### Distribution & packaging
Strategia: [`docs/PACKAGING.md`](../docs/PACKAGING.md). ADR DEC-0008.
- **`deb` package + apt repo.** `dh-virtualenv` lub `fpm`. Repo
  `https://repo.crossdesk.dev/deb/` (domain pending — patrz reminders
  w `AGENTS.md`). GPG-signed.
- **`rpm` package + Copr/OBS repos.** Fedora Copr (free, automated);
  openSUSE OBS. RPM signing via OBS lub self-hosted key.
- **Sigstore signing dla `agent.exe`.** Wired do release CI. Public
  verification key on download page. Documented w install docs.
- **[C-1, audyt 2026-07-07 P2-4] PKGBUILD `sha256sums=('SKIP')` → pin.**
  Trigger: PIERWSZY tagowany release tarball (kryt. #12 packaging test). Wtedy:
  `updpkgsums` przeciw opublikowanemu tarballowi + regen `.SRCINFO`; dodać pin
  do release checklist. Dopóki tarball nie istnieje — nie ma czego hashować.

### Lifecycle: power, suspend/resume, autostart
- **VM autostart on login (opt-in).** `crossdesk install --autostart`
  + `crossdesk vm autostart enable|disable`. Default off.
- **Shutdown handler — install-state persistence + D-Bus inhibitor
  release.** CLI `crossdesk vm shutdown` shipped; brakuje
  `lifecycle/coordinator.py` daemon-shutdown path. `[~PARTIAL]`
- **Hibernation-aware AuthValidator / nonce / sequence resync.**
  `LifecycleCoordinator` stamps shipped; faktyczny `AuthValidator`
  wiring czeka na hardware (touch security model = ADR required per
  AGENTS.md). `[~PARTIAL]` `[HW]`
- **Autopause × balloon — Phase 7 driver implementation.**
  `BalloonHook` Protocol seam shipped; real virtio-balloon driver
  brakuje. Plus single `lifecycle/` supervisor owning state machine
  across all three mechanisms (autopause + LifecycleCoordinator dziś
  duplikują order — merge when third caller arrives). `[~PARTIAL]`

### Performance budgets
Strategia: [`docs/PERFORMANCE.md`](../docs/PERFORMANCE.md). ADR DEC-0004.
Budgets w [`docs/REQUIREMENTS.md`](../docs/REQUIREMENTS.md) §N1.
- **Integration benchmarks.** `host/tests/benchmarks/`:
  `bench_install_pipeline.py`, `bench_cold_launch_lightweight.py` (N1.1a),
  `bench_recovery_destroy_start.py` (N1.6a). Slower; gated by PR label
  `perf-full`. Run on main-branch nightly. `[HW]` dla cold-launch.
- **`tools/bench_report.py`.** Agreguje wyniki across runs → markdown
  table for release notes.
- **PR comment automation.** GitHub Action posting perf table. Już
  częściowo wired w `bench_report.py` (ale jako step, nie automation).

### GPU passthrough Tier 2 docs
- **AMD reset-bug Tier 2 docs.** Detection (`lsmod | grep vendor_reset`);
  doctor warning surface; link do upstream instalacji; sami nie shippujemy
  modułu.
- **NVIDIA pre-2021 Tier 2 hide-the-VM docs.** Explain Code 43 history;
  document `<hidden>` flag opt-in; warn drivers 465+ obsolete; for users
  stuck on old explain workaround.
- **TA7 row w `docs/THREAT_MODEL.md`.** Malicious GPU firmware threat +
  mitigations (signed firmware verification, no ACS override, IOMMU
  enforcement). Adds when implementation lands per DEC-0009. **`[user-approval]`**

### Looking Glass P1
- **Single-GPU hot-switch path.** Detection (doctor) + orchestration:
  compositor stop → GPU rebind to vfio-pci → VM start z LG host → LG
  client spawn on iGPU/vesa fallback → reverse on exit. `[HW]`
- **C8 IVSHMEM channel w `docs/THREAT_MODEL.md`.** New component row:
  IVSHMEM jako non-VSOCK trust surface; brak per-frame AuthContext;
  threat reduced (unidirectional pixel firehose). **`[user-approval]`**

### Software rendering fallback
- **Document supported app classes per render path.** Word/Outlook/
  Excel/VS: software OK. Photoshop/Premiere/AutoCAD/Blender: software
  unusable. Concrete table w `docs/USER_GUIDE_HARDWARE_COMPAT.md` (new).
- **`crossdesk doctor` rekomenduje app categories per hardware tier.**
  "Hardware Tier 3 → productivity apps OK via software rendering";
  redirect Photoshop/Premiere → Wine/CrossOver/cloud GPU.

### Phase 1 follow-ups (przed Phase 4)
- **Live-install follow-ups (2026-06-01).** Pierwszy realny boot ujawnił
  (`status.md` "Live install"): (a) **autounattend windowsPE UI nie tłumi
  ekranu wyboru edycji** mimo `/IMAGE/INDEX=6` — audyt kompletności
  answer-file; (b) **`/dev/vhost-vsock` udev rule** dla `qemu:///session`
  (dziś vsock pomijany przy instalacji → agent się nie połączy) —
  reguła `KERNEL=="vhost-vsock", MODE="0660", GROUP="kvm"` lub doc; (c)
  **autounattend locale auto-detect z ISO** (mamy `--locale`, ręczne) —
  czytać język z `install.wim`/ISO; (d) **virtio-win driver ISO** by
  przełączyć dysk boot z SATA na virtio-blk (perf, DEC-0016 reconsider).
- **GUI ISO auto-download (Fido backend).** Wizard (`gui/`) ma krok
  `Step1Iso`, ale `iso_downloader` to Phase-5 stub bez `HttpScrapeBackend`
  — UI jest, pobierania nie ma. Implementuj Fido-style download MS ISO.
- **CrossDesk Lean Windows profile (opt-in).** PowerShell
  `infra/lean_profile.ps1` z `<FirstLogonCommands>`. Removes Edge/
  Cortana/OneDrive/Tips/Games/Skype/Teams personal/Xbox; **keeps**
  .NET/VC++/Windows Update/Defender/AV+video drivers. Opt-in via
  `crossdesk install --lean`. Land przed Phase 4 → RAIL latency tests
  na representative image. Acceptance: Office + Adobe + VS install +
  activate normally na lean.
- **`crossdesk install` real call sites for steps 2-7.** 7-step state
  machine shipped jako idempotent stubs; `generate_credentials` real,
  reszta "hardware-gated" exit 1. Real wiring: `iso_download` (Phase 5
  scrape), `libvirt_domain` (`infra/launch-vm.py`), `autounattend` (Lean
  profile integration), `win_install` (libvirt boot), `agent_register`
  (mTLS PKI gen + Windows-side cert install), `healthcheck` (Hello +
  heartbeat probe). `[HW]`

### Phase 3 follow-ups
- **Two-layer health check — synthetic AuthContext bypass + probe-driven
  SOFT_RECOVERY short-circuit.** Observability MVP shipped; bypass-and-
  short-circuit czeka na ADR (touch security model). `[~PARTIAL]`
  **`[user-approval]`**

### Post-MVP / winapps-parity (P1 tier)
- **Adopt 91-app catalog jako starting point.** Źródło:
  `third_party/winapps/apps/<name>/info` (91 entries). Copy non-trademark
  fields (`WIN_EXECUTABLE`, `MIME_TYPES`, `CATEGORIES`) do TOML. Skip
  SVG icons (Microsoft/Adobe trademark unclear); generate icons z `.exe`
  resources at discovery time. (Dziś 20-app catalog shipped 2026-05-11;
  rozszerz do 91.)
- **Sleep/wake time sync.** Prefer `qemu-guest-agent` + `virsh domtime`;
  fallback: WinApps marker-file approach via gRPC (host writes
  "host-resumed" signal on D-Bus suspend wakeup → guest agent
  `w32tm /resync`). `[HW]`
- **GUI launcher / taskbar applet.** Extend Qt6/QML installer wizard
  (`gui/`) → permanent applet: VM start/stop/pause/reboot + app picker.
  WinApps' Yad-based launcher to porównanie.
- **Desktop notifications via D-Bus.** ✅ `DBusNotifier` shipped
  2026-05-23 (`integrations/notifications.py`): real dbus-next aio call,
  sync/async context detection via `asyncio.get_running_loop()`. Wired
  to 3 call sites via `SubprocessNotifier` interface compatibility.

### Resilience & observability (public-beta)
✅ **ZMERGOWANE do `main`** (`0f31d52` i dalsze) — zapis „NIE merged" był
nieprawdą, poprawiony 2026-07-14. Pełny stan:
[`status.md`](status.md) "Resilience & observability". Z audytu/diagnozy
2026-06-12: gdy komponent zewnętrzny pada (FreeRDP itd.), host tego nie
wykrywał/logował/notyfikował.
- **✅ FreeRDP supervision** — `display/rail_supervisor.py` reap+log+notify;
  per-app capture log; `FreeRDPInvocation.wait()`. Naprawia zombie xfreerdp.
- **✅ Notifier ożywiony w prod** — daemon wpina `SubprocessNotifier` do
  RailManager+Heartbeat (były dead-code).
- **✅ Graceful shutdown + crash catchall** — SIGTERM/SIGINT, `daemon_crashed` log.
- **✅ Log do rotującego pliku** — `crossdesk logs` działa bez journald.
- **Real `LibvirtDomainEventSource`** — Phase-3, **`[HW]`** (lands z real
  libvirt controller; reactor+mock seam już shipped+testowany).
- **`crossdesk logs --component guest`** — wymaga **nowego RPC host→guest
  (proto = boundary)**; `[user-approval]`. Dziś stub P2.
- **Live-verify realnego crashu FreeRDP** na żywej VM (notyfikacja+log+brak
  zombie) — kod+unit-tested, live zostaje.

### Operations & lifecycle (post-MVP)
- **`crossdesk doctor` — pre-flight diagnostic.** Expanded 2026-05-23:
  added `check_cpu_virt_extensions`, `check_vsock_module`,
  `check_qemu_version`, `check_config_dir_writable`; `--gpu` flag wired
  to GPU_CHECKS. Remaining: wiring as pre-step for `crossdesk install`
  + free disk check. `[~PARTIAL]`
- **`crossdesk uninstall` — clean removal.** `[~PARTIAL 2026-07-05 `8261a35`]**
  Domena (`undefine`: destroy-if-running + `undefineFlags(NVRAM)`),
  `crossdesk-*.desktop`, cached ISO, install state (+ VM disk), config
  (`--keep-config` zachowuje `vm.toml`) — **kod kompletny + testy**. Świadomie
  BEZ `--remove-all-storage`: nasz dysk znika z state-dir, a flaga próbowałaby
  skasować file-backed CD-ROM źródła (w tym ISO Windowsa usera). **Zostaje:**
  (a) live-verify pełnego usunięcia na realnym libvirt (Phase 2); (b) ✅ shipped
  `427b15e` — interaktywny confirm (EOF-safe: piped stdin = „nie"), `--force`
  pomija; `--dry-run` bez zmian.
- **`crossdesk logs --component guest` — guest gRPC log pull.** Host
  log sources shipped (journalctl + JSONL + libvirt + FreeRDP); guest
  jest P2 stub ("not yet implemented"). Wire gRPC stream tail. `[~PARTIAL]`
- **First-launch experience po `crossdesk install` succeeds.** Desktop
  notification ("CrossDesk ready — run `crossdesk launch notepad`")
  via `org.freedesktop.Notifications`, brief next-steps file w
  `~/.config/crossdesk/getting-started.md`, optionally auto-launch
  Notepad jako smoke test (`--launch-test`). Don't open browsers.
- **Produkcyjny agent jako NT-service (nie console) — STABILNOŚĆ, beta-blocker.**
  Live finding 2026-06-09: console-mode agent jest związany z cyklem życia
  sesji RDP → **zamknięcie okna RAIL / takeover sesji ubija ControlSession**,
  kolejny `launch` failuje na verify-credentials ("no live guest session").
  NT-service (kod jest, autounattend instaluje) przeżywa disconnect sesji +
  reboot + nie trzyma sesji RDP (brak session-takeover, brak cmd-artefaktu).
  Wymaga produkcyjnej reinstalacji guesta z autounattend (`[HW]`).
- **Daemon reapuje zakończone xfreerdp (zombie `<defunct>`) — ops.** Live finding
  2026-06-09: daemon spawnuje xfreerdp jako subprocess ale nie `wait()`-uje po
  jego śmierci → zombie w tablicy procesów (PPID=daemon). Niegroźne, ale do
  naprawy: `asyncio` child watcher / reap na `transport`/`freerdp` poziomie
  gdy RAIL session kończy się lub jest ubijany.

### Cross-platform foundation

### Internationalization
- **CLI translations wave 2.** `apps_cmd.py` column headers wrapped
  2026-05-23; `cli/install_cmd.py`, `installer/` package — still
  English-literal. `[~PARTIAL]`

---

## P2

### Porządkowe — test hygiene / env
- **[P2] Pełna suita `pytest` wisi na macOS (leaked `_poll_wrapper` thread).**
  `pytest tests/` (bez markerów) zawiesza się ~6% na tym Macu: jeden test
  zostawia wątek pollera (`Thread-132 (_poll_wrapper)`, spoza `host/src/` — z
  zależności) i proces blokuje się w stanie `S`. `--timeout=30 --timeout-method
  =thread` hard-exituje, myląco obwiniając kolejny trywialny test
  (`test_config.py::test_load_from_toml_missing_file_returns_defaults`, który
  sam przechodzi). Na boxie Linux suita jest zielona (44 s, audyt 2026-07-06),
  więc to macOS-only + test-ordering. **Skutek praktyczny:** pre-push hook
  (odpala pełny pytest przy zmianie `host/`) wisi na macu → push z Maca wymaga
  albo boxa Linux, albo (za zgodą właściciela) `--no-verify`. Fix: znaleźć test
  zostawiający wątek (kandydat: obserwator plików / grpc aio / dbus poller bez
  teardown), dodać fixture zamykający, albo oznaczyć markerem i deselectować
  domyślnie. (Odkryte 2026-07-19 przy DEC-0019.)

### Porządkowe z audytu 2026-07-12
- **[P2] `SECURITY.md`** — repo publiczne bez kanału disclosure (skill §12).
  Krótki plik: kanał zgłoszeń, wspierane wersje (pre-release: tylko `main`),
  kto triage'uje. Publikacja = decyzja właściciela (public-facing).
- **✅ [P2] `status.md` kłamał o branchach — POPRAWIONE 2026-07-14.** Trzy
  gałęzie (`feat/resilience-logging`, `feat/fs-drive-letter`,
  `feat/usability-shared-fs`) opisane jako „NIE merged" **są w `main`** —
  zweryfikowane `git merge-base --is-ancestor`, nie na oko: `e15cf2b` (workdir),
  `0f31d52` (rail_supervisor), `1986295`+`9afb465`+`688b2a7` (Etap A),
  `configure_logging(log_file=)` w `observability/log.py`. Wszystkie zapisy
  poprawione w `status.md` i tutaj.
  **⏸ Zostaje (decyzja właściciela):** skasowanie 17 zmergowanych gałęzi na
  `origin` — akcja na współdzielonym remote, nie robię jej sam. Patrz
  `needs-owner.md`.
- **✅ [P2] Wiszące referencje do `handoff.md` — NAPRAWIONE 2026-07-14.** Plik był
  nietrackowanym scratchem sesji i wypadł z drzewa (`709363b`), zostawiając
  martwe cytaty §2.7/§2.8. Treść **odzyskana z historii** (`7f656fc`) do
  [`history/2026-06-12-fs-stage-ab-plan.md`](history/2026-06-12-fs-stage-ab-plan.md);
  wszystkie referencje w `status.md` i `backlog.md` przepięte.
- **[P2] Host bez lockfile'a Pythona** — CI i box resolvują zależności świeżo
  (`pip install -e`); `ci-cd.md` §3 chce zamrożonego locka. Decyzja
  kierunkowa: uv (`uv.lock` + `--locked` w CI) vs pip-tools.
- **[P2] `libvirt_call` na współdzielonym default executorze**
  (`libvirt_ctl/aio.py:29` — Security Review 2026-07-12, NOTE) — dedykowany
  `ThreadPoolExecutor` + test saturacji puli (N>pool_size zawieszonych
  wywołań nie głodzi innych `run_in_executor`).
- **[~PARTIAL 2026-07-14] `zizmor` — zainstalowany na boxie, brakuje joba w CI.**
  Izolowany venv (`~/.local/share/zizmor-venv`, symlink `~/.local/bin/zizmor`,
  wersja 1.27.0) + konfiguracja `.github/zizmor.yml` (polityka pinowania).
  Jest realną bramką lokalną (użyty do zamknięcia fali `05653c7`). **Zostaje:**
  job w `security.yml` = item A6 w `loop-spec.md`. Poniższy oryginalny opis:
- **[P2] `zizmor` nieobecny lokalnie i w CI** — zainstalować na boxie (audyt
  statyczny; dziś odpalony jednorazowo przez `uvx`) i rozważyć job w
  `security.yml`.
- **[NOTE] pre-commit bumpuje timestampy `architecture.md`/`ignorefiles.md`
  przy każdym commicie** — toolkit 2026-07-11 (NEW-PROJECT §8.2) uznaje
  timestamp-bump za kłamiący sygnał świeżości (git log wystarcza). Świadoma
  decyzja z maja (opcja b) — utrzymać albo wyłączyć: właściciel.
- **[NOTE] SHA w starych wpisach audit-log nie rozwiązują się** po rewrite
  historii 2026-07-07 (np. `13df5d1` z wpisu 07-06) — historyczne, bez akcji.

### Display
- **Per-frame display latency benchmark.** Add do microbench harness:
  "RAIL CREATED event → first frame drawn" na known-good test app.
  Wayland-native vs XWayland. `[HW]`
- **Looking Glass jako documented alternative.** Document w
  `docs/DISPLAY.md`; users run LG directly jeśli chcą; nie integrujemy.

### Peripherals
- **Smart card / PCSC-Lite passthrough.** FreeRDP `/smartcard` + `pcscd`
  host package. Required for corporate workflows (banking PKI, gov auth).
  Document host-side `libccid` setup.
- **USB allow-list z libudev hotplug.** Host-side libudev watcher
  attach/detach via libvirt `virsh attach-device` based on
  vendor:product allow-list w config. Default `deny-all`.
- **Camera USB passthrough.** Default: cała USB webcam via libvirt
  `<hostdev>`. Document `obs-v4l2sink` virtual-webcam alternative.
- **FIDO2 best-effort documentation.** No native FreeRDP channel; users
  rely na USB passthrough HID. Document procedure; nie obiecujemy
  first-class support.
- **Threat-model rows per peripheral.** One row w `docs/THREAT_MODEL.md`
  per enabled peripheral. **`[user-approval]`**

### Observability
- **Optional Prometheus exporter (community).** Small script polluje
  `GetMetrics` + exposes `/metrics` HTTP endpoint. Out of core; document
  contract for community contribution.
- **Microbench harness reads from histograms.** Performance regression
  checks w CI consume `heartbeat_rtt_seconds` + `launch_duration_seconds`
  histograms. Tied do perf-budgets work.

### Performance
- **Self-hosted KVM runner z `hardware-smoke` workflow.** Real-hardware
  numbers gated by PR label + hardware availability. Runner doesn't
  exist; wire workflow file ready. `[HW]`
- **Trend analysis.** Weekly metric summary over time. Useful gdy mamy
  months of history.

### Versioning
- **Deprecation tracking.** MINOR adding field obsoleting older →
  one-time warning at startup do MAJOR removal. Tooling: registry w
  `proto/DEPRECATED.md` z deprecation dates.

### Distribution
- **Update mechanism docs per distro.** README install section explaining
  `apt update`, `dnf upgrade`, `yay -Sua`. Distinct from `crossdesk
  upgrade` (in-VM agent).
- **Distribution-time GPG signing dla deb/rpm.** Release key offline.
- **Community documentation for adding new distros.** Gentoo ebuild
  template, SBo build script template. Nie shippujemy — ułatwiamy
  community.

### Lifecycle
- **Power profile docs.** User-facing docs covering laptop battery-saver
  / lid-close-suspend policy interactions; recommended `crossdesk`
  configuration per scenario.

### Internationalization
- **Weblate (or similar) integration.** Hosted translation service tak
  translators nie wymagają git. Contingent on community contribution
  volume.
- **Plural-form audit.** gettext `ngettext` dla pluralized strings.
  Few expected; revisit po first Polish translation pass.
- **Locale-aware number/date formatting.** File sizes, timestamps
  user-visible output. `locale.format_string` Python; Qt handles GUI
  natively.
- **RTL language readiness.** When first RTL translation arrives
  (Arabic / Hebrew), audit GUI layouts. Qt handles most automatically.
  OOS until needed.

### GPU passthrough
- **Per-distro automated setup beyond docs.** Auto-apply kernel cmdline
  + initramfs config via `crossdesk gpu setup --commit` dla 4 primary
  distros. Each distro module w `infra/gpu_setup/<distro>/`.
- **GPU performance benchmarks.** `host/benches/bench_gpu_filter_latency.py`
  — Photoshop-class filter completion time na known image. Real-hardware
  only; `hardware-smoke` workflow. `[HW]`

### Looking Glass
- **`docs/USER_GUIDE_DESKTOP_MODE.md`.** When RAIL vs Desktop,
  trade-offs, LG audio troubleshooting via Scream.

### Software rendering
- **Investigate llvmpipe optimizations.** Light investigation, no
  commitment. Newer llvmpipe versions / specific Mesa tuning może
  flipnąć "doesn't work" apps.

### Phase 1
- **Locale + timezone propagation.** Read host `timedatectl` + locale
  env at `infra/launch-vm.py` install + inject do `autounattend.xml`
  `<TimeZone>` + `<UserLocale>`. Skip TimeSync.ps1 marker-file mechanism
  jeśli `qemu-guest-agent` enabled (`virsh domtime` covers post-suspend).
- **Detect Windows 11 IoT Enterprise LTSC + short-circuit redundant
  debloat steps.** Read `install.wim` edition string; jeśli LTSC, skip
  matching `Remove-AppxPackage` (no-ops). LTSC requires enterprise
  licensing → few hobbyist users hit this.

### Phase 4 (RAIL Display Integration — beat winapps)
- **HiDPI auto-detect — beat winapps here.** Their model: `RDP_SCALE`
  config knob 3 discrete values. Ours: read Wayland `wl_output.scale`
  / X11 RANDR at launch, pick closest FreeRDP-supported scale
  (100/140/180 in 3.x), re-launch on monitor change. "No config knob,
  just works." (Basic auto-detect shipped; advanced features tu.)
- **Multi-monitor RAIL — beat winapps here.** Their README warns
  `/multimon` causes black screens. Forward each RAIL window to
  appropriate output via WM hints. Same module as HiDPI.

### Post-MVP / winapps-parity (P2 tier)
- **Typed config for redirections.** WinApps' `RDP_FLAGS` is free-form
  string. Replace z typed TOML: `enable_audio`, `enable_clipboard`,
  `enable_printer`, `usb_devices: list[str]`. Map → FreeRDP flags w
  host code. User nie widzi raw FreeRDP syntax. (Typed config dla
  peripherals już istnieje; rozszerz na pozostałe redirections.)
- **Auto-derive MIME types from registry.** Read `HKCR\<ext>` +
  `HKCR\<progid>\shell\open\command` during discovery → MIME associations
  automatic. WinApps hand-curates (unscalable).
- **Auto-extract icons from `.exe` resources.** → **promoted to P1
  "RAIL window icons"** (Display & forwarding) per user request
  2026-06-02; see that entry for the full agent+host design. This P2 line
  remains only as the *discovery-time* variant (extract icons for the app
  catalog / launcher), distinct from the live per-window RAIL icon path.

### Operations & lifecycle (post-MVP P2 tier)
- **`crossdesk vm snapshot create|list|restore|delete`.** Wraps
  `virsh snapshot-create-as` / `snapshot-list` / `snapshot-revert` /
  `snapshot-delete`. UX: "checkpoint before risky software." Requires
  VM stopped/paused for safe snapshots. Document storage growth.
- **`crossdesk upgrade` — update CrossDesk + in-VM agent.** Host
  packages via installer mechanism, then hot-swap `agent.exe` via gRPC
  `ControlService.UpgradeAgent`: stream binary, agent stages, restart NT
  service. Forward-compat check vs protocol-version field. Patrz P1
  Versioning `crossdesk upgrade` agent hot-swap (related).
- **`crossdesk export-state` / `import-state` — backup/move the
  install.** Tarball `~/.config/crossdesk/` + `~/.local/state/crossdesk/`
  + libvirt domain XML dump. `--include-disk` for full portability
  (~30GB). Critical insurance — losing `vm.toml` = losing Windows access.

### Cross-platform foundation
- **`cargo deny` rule** preventing direct imports of `libvirt-python`,
  `socket.socket(AF_VSOCK)`, `tokio::net::VsockStream` outside
  abstraction layer.

### Tech debt
- **[P1, audyt 2026-07-22] Bump otel rozdwoił stack gRPC w agencie Windows.**
  `opentelemetry` 0.27→0.32 przeciągnął tranzytywnie **drugi** `tonic` i **drugi**
  `prost` (`cargo tree -i tonic@0.14.6` → `opentelemetry-otlp 0.32 → observability
  → agent-svc`); `guest cargo-deny` skoczyło **16 → 24** (same `duplicate`, 0 vulns),
  a `agent.exe` waży **5 664 256 B** wobec **5,2 MB** zapisanych w `PLAN.md` #7 —
  ok. **+9%** za eksporter, którego domyślnie nikt nie włącza. Do 2026-07-21 otel
  0.27 używał **tego samego** `tonic 0.12` co my. Opcje: (a) revert obu merge'ów
  otel (najtańsze — OTLP jest opt-in), (b) zrobić sprzężoną migrację prost/tonic
  0.14 z pozycji niżej i zejść do jednego stacku, (c) zaakceptować. *Rek.: (b),
  a jeśli migracja nie rusza w tym tygodniu — (a).*
- **✅ [P1, audyt 2026-07-22] ZROBIONE `b2d2680` — ścieżka OTLP nie miała żadnego testu.** `build_otlp_layer`
  (`guest/crates/observability/src/lib.rs:59`) przeszedł breaking-change API, a
  w całym crate'cie jest **jeden** `#[test]` i testuje writer JSON. Inwariant
  DEC-0002 („zero telemetry by default") nie ma strażnika regresji. Fix tani:
  test asertujący `None` przy nieustawionym i przy pustym
  `OTEL_EXPORTER_OTLP_ENDPOINT`.
- **✅ [P1, audyt 2026-07-22] ZROBIONE `ad80f72` — `architecture.md` + `README.md`
  obiecywały whole-`$HOME` jako default, DEC-0019 zmienił to 2026-07-19.** Kod: `shared_folder_scope` =
  **`documents`** (`config/peripherals.py:180`). Dokumentacja: `.claude/architecture.md:29`
  i `:67`, `README.md:47` i `:120`, `.claude/loop-spec.md:29` i `:172` (wpisy
  dziennika z datami są historyczne — zostają). `README` jest user-facing, więc
  mówi użytkownikowi nieprawdę o zasięgu sharingu od `ddbd34d`.
- **[P2, audyt 2026-07-22] 7 gałęzi `ratunek/stash-*` ma 73 dni** (8-10 maja).
  Diff wobec `main` to niemal same usunięcia (starsze snapshoty), więc pewnie nic
  unikalnego — ale nikt tego nie potwierdził. Do triażu i skasowania albo jawnego
  „zostają, bo X".
- **[P2, audyt 2026-07-22] Krok 5 audytu jest niewykonalny — brak mastera toolkitu.**
  `~/DevProjects/claude-toolkit` **nie istnieje na tym boxie** (został na MacBooku),
  a skill `weekly-audit` i `.claude/rules/audit.md` odsyłają do `NEW-PROJECT.md §9.2`
  jako kanonicznego źródła; cały `.claude/rules/` opisuje się jako „kopie masterów".
  Status kroku: **DEGRADED**. Decyzja właściciela: sklonować toolkit tutaj, czy
  uznać kopie w repo za samodzielne mastery i wyciąć odwołania.
- **[P2, audyt 2026-07-22] Trzy warstwy gate'ów cicho nie działają lokalnie** —
  `buf`, `qmllint`, `gitleaks` raportują `n/a`. `ci-cd.md` §1: „Ciche `skip` jest
  awarią gate'a". CI je pokrywa, więc to nie dziura w merge'u, ale lokalny pre-push
  daje fałszywe poczucie kompletu.
- **[P2, Security Review 2026-07-22, SEC-03] Majory `upload-artifact` v7 /
  `download-artifact` v8** — Actions ignorują nieznane `with:` **bez błędu**, więc
  gdyby major przemianował `if-no-files-found: error`, ochrona przed pustym
  artefaktem znika po cichu. Zapasowo działa `fail_on_unmatched_files: true`
  (`release.yml:267`). Domyka jeden dry-run `workflow_dispatch` przed pierwszym
  tagiem (razem z C-1).
- **[2026-07-22] Trzy bumpy dependabota to migracje, nie bumpy — odrzucone
  przy fali merge'ów.** Pozostałe 14 z 17 weszło do `main`; te trzy **łamią
  build** i wymagają realnej pracy, nie zatwierdzenia:
  - `dependabot/cargo/guest/prost-types-0.14.4` **+**
    `dependabot/cargo/guest/tonic-build-0.14.6` — **sprzężone**. Workspace stoi
    na `tonic 0.12` / `prost 0.13`; sam `prost-types 0.14` daje 12 błędów
    `E0277` (derive `::prost::Message` nie spełnia bounda z `prost-0.13`).
    tonic-build 0.14 dodatkowo wyniósł codegen do osobnego `tonic-prost-build`
    (stąd −311 linii w jego `Cargo.lock`), więc `build.rs` w `crates/proto`
    trzeba przepisać. Zakres: cała trójka prost/tonic/tonic-build naraz +
    regeneracja stubów guesta.
  - `dependabot/cargo/gui/cxx-qt-build-0.9.1` — 0.7→0.9 zmienia API
    `QmlModule`: `qml_files` to dziś `Vec<QmlFile>` (było `&[&str]`), a
    `qrc_files` **zniknęło**. To dokładnie to pole, na którym stoi fix ikon
    GUI (`bbc425b`, `icons.qrc` + `CxxQtBuilder::qrc()`), więc migracja musi
    skończyć się live-verify okna managera, nie samym `cargo check`.
  - `dependabot/cargo/gui/gui-minor-patch-5b558cd62c` — **czwarty**, wykryty
    dopiero przy pushu: zmergowany, potem zrewertowany (`7c9ebe4`). Grupa
    podbija `cxx` 1.0.194→1.0.198, ale wygenerowany mostek cxx-qt 0.7 wciąż
    emituje symbole `cxxbridge1$194$…` → `cargo test` nie linkuje (mold:
    undefined symbol, ~kilkadziesiąt sztuk). **`cargo check` tego NIE łapie**,
    bo nie linkuje — złapał dopiero pre-push. `cxx` jest więc de facto
    przypięty do wersji, z którą generuje cxx-qt 0.7.3; odblokuje go dopiero
    migracja cxx-qt-build 0.9 powyżej. Warto rozważyć jawny pin `cxx` w
    `gui/Cargo.toml`, żeby dependabot nie proponował tego w kółko.
  Trzy pierwsze gałęzie zostawione na `origin` **celowo** — to jedyny ślad
  po tych bumpach. Czwartą GitHub skasował sam przy merge'u (auto-delete),
  więc jej jedynym śladem jest revert `7c9ebe4` i ten wpis.
- **[2026-07-22] `notify_forced_stop` krzyczy CRITICAL na śmierć, którą sami
  zlecamy.** `DomainEventReactor.on_event` (`lifecycle/domain_events.py:130`)
  rozróżnia `destroyed` od `crashed`, ale pilność notyfikacji dobiera tak samo
  — a przy przejazdach kryterium #6 (`virsh destroy`) to my naciskamy spust.
  Do tego `SubprocessNotifier` nie ma dedup ani rate-limitu, a `config/` nie ma
  wyłącznika (daemon wpina notifiera bezwarunkowo, `daemon.py:201`) — więc
  serię zerwań FreeRDP widać jako serię bannerów. Precedens: `launch_cmd.py:233`
  wyciął już jedno źródło zamiast naprawić mechanizm. Fix: pole
  `notifications.enabled` + `min_interval_s` z dedup po `(summary, category)`
  i degradacja zamierzonej śmierci do NORMAL.
- **[C-3, planning-addendum audytu 2026-07-07] `lifecycle/coordinator.py`
  suspend/resume blokuje event-loop.** `suspend()`/`resume()` (dawniej
  `:139,162`) blokują na ścieżce D-Bus PrepareForSleep + delegacji z mgmt.
  Świadomie WYŁĄCZONE z branch 3 (deadline-bound libvirt) bo coordinator
  mutuje stan FSM (`fsm_group`) — offload do wątku wymaga projektu
  thread-safety, nie mechanicznego owinięcia w `libvirt_call`. Trigger: przed
  live-verify suspend/resume (#5) na `backend=real`.
- **`// type: ignore[override]` ergonomics watch.** Bidirectional gRPC
  servicers ominęto przez `AsyncIterator`. Jeśli grpc-stubs bump narrows
  parent signature, override może resurface; eyes on
  `crossdesk_host.proto.*_pb2_grpc.pyi` after every regeneration.
- **Feature-gate Phase-5 fs-mount mocks.** `mock_generate_release_ack()`
  ([`guest/crates/fs-mount/src/flush.rs:31`](../guest/crates/fs-mount/src/flush.rs))
  zwraca hardcoded `total_bytes_written: 1024`; wołane bezwarunkowo z
  `agent-svc/src/filesystem.rs:98` (bez `#[cfg(feature)]`). Phase-5 stub
  (zob. `status.md`), ale brak cfg-gate = placeholder trafia do
  prod-builda. Schować za `mock` feature jak reszta. (audyt 2026-05-31)
- **~~mTLS failure-mode testy~~ — ZWERYFIKOWANE JAKO ZROBIONE (2026-07-05).**
  Item z audytu 2026-05-31 jest **nieaktualny**: dedykowane testy failure-mode
  istnieją i pokrywają krytyczną ścieżkę mTLS/auth. `test_mtls_handshake.py`
  napędza **realny** handshake gRPC po loopbacku i asertuje odrzucenie na
  warstwie TLS dla: brak cert klienta, cert podpisany złym/niezaufanym CA, cert
  wygasły (nigdy nie dochodzą do dispatchu). `test_auth_validator.py` (unit)
  pokrywa cert-pinning (fingerprint mismatch), brak cert, malformed PEM,
  sequence-regression/skip-forward, concurrent streams. `test_auth_rejection_paths.py`
  pokrywa per-plane (Control/Heartbeat/Filesystem) odrzucenia. `test_security_edges.py`
  dokłada nonce/sequence edge-cases. („hostname-validation" nie jest zadaniem
  AuthValidatora — to warstwa TLS, pokryta wrong-CA/expired w handshake teście.)
- **AGENTS.md „Repository layout" drift.** Sekcja listuje 5 podkatalogów
  `host/src/crossdesk_host/`, faktycznie 23 (m.in. `cli/`, `doctor/`,
  `abstractions/`, `lifecycle/`, `filesystem_ctl/`…). AGENTS.md =
  boundary file → edycja wymaga zgody właściciela. (audyt 2026-05-31)
- **FreeRDP `/app:` quoted-`cmd:` tokenizer warning (Phase-5 latent).**
  Na FreeRDP 3.24 klauzula z `cmd:"<plik>"` *przed* kolejnymi sub-keyami
  (`hidef:`/`name:`/`workdir:`) emituje `[get_next_comma]: Invalid quoted
  argument` (po jednym na trailing sub-key; non-fatal, parse dochodzi do TCP
  connect). **Dziś uśpione** — `cmd_arg` jest zawsze `""` (`request.file_path`
  → JIT-mount to Phase-5, niewpięte; oba call-site'y `AppLaunchSpec` mają
  pustą `argv`), więc shipowana klauzula A1 (program+icon+hidef+name+workdir,
  bez `cmd:`) parsuje się czysto (0 błędów, zweryfikowane na żywym
  `xfreerdp3` 3.24.2, też ścieżki ze spacjami). Gdy Phase-5 wepnie
  file-open: dać `cmd:` na końcu klauzuli, zrezygnować z cudzysłowu, albo
  użyć `/args-from`; dodać test `workdir`+`cmd` razem. (review A1 2026-06-04)

---

## Czeka na decyzję właściciela

Wymaga zgody na touch boundary plików per `AGENTS.md` "File boundaries"
(proto, THREAT_MODEL, DECISIONS, REQUIREMENTS, MVP_SCOPE, GOALS, ROADMAP).

- **Kierunek systemu plików — ROZSTRZYGNIĘTE 2026-06-12: A → potem B.**
  Praca przeniesiona do P0 „Filesystem bridge — kierunek A→B" (góra pliku);
  plan wykonawczy [`history/2026-06-12-fs-stage-ab-plan.md`](history/2026-06-12-fs-stage-ab-plan.md)
  §2.7 (Etap A) + §2.8 (Etap B). Tu zostaje
  tylko część `[user-approval]` Etapu B: **ADR + THREAT_MODEL row dla
  trwałego scoped VirtioFS mount** — owner autoryzuje gdy Etap B startuje
  (po smoke-teście sterownika virtio-win VirtioFS).
- **`docs/THREAT_MODEL.md` flips po Stage 4 LogonUserW shipped**
  (`auth.verify-credentials.v1` residual risk wymaga uzupełnienia)
  i **`docs/VERSIONING.md` capability promotion** (`auth.verify-
  credentials.v1` z planned → stable). Patrz `status.md` "Verify-
  credentials real LogonUserW".
- **TA7 row w `docs/THREAT_MODEL.md`** (GPU passthrough firmware threat
  — patrz P1 sekcja).
- **C8 IVSHMEM channel w `docs/THREAT_MODEL.md`** (LG IVSHMEM trust
  surface — patrz P1 sekcja).
- **Threat-model rows per peripheral** (P2 sekcja).
- **Phase 3 synthetic AuthContext bypass + SOFT_RECOVERY short-circuit
  ADR** — touch security model (P1 sekcja).
- **Domain name dla hosted package repos (deb / rpm)** — open question
  per AGENTS.md "Pending user-decision reminders". Ostatnio pytano
  2026-05-07; ~4-tygodniowa kadencja.
- **Code signing strategy dla `agent.exe`** (Sigstore vs EV cert) —
  deferred jako not-yet-justified. Ask before v0.1.0 release packaging
  begins.

## Zablokowane

> **Główny blocker („brak Linux+KVM boxa") ZNIKNĄŁ 2026-07** — box jest żywy,
> Fazy 1–4 zweryfikowane na żywo. To co zostało „zablokowane" to teraz tylko
> pozycje na **genuine hardware, którego ten box nie ma** (klasa C w
> [`status.md`](status.md) „Gating"):

- **Self-hosted `linux-kvm-smoke` CI runner** — potrzebny Proxmox/dedykowany
  runner (nie ten laptop-dev-box).
- **GPU passthrough / Looking Glass** — passthrough-capable multi-GPU host.
- **Multi-monitor RAIL** — 2+ fizyczne ekrany.

Wszystko inne oznaczone `[HW]` wyżej, co wymaga tylko *tego* boxa (real libvirt,
VirtioFS, perf, suspend/resume), jest **odblokowane** — patrz `PLAN.md` NEXT.
