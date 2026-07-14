# FS Stage A → B — execution plan (recovered from the retired `handoff.md`)

> **Provenance.** Recovered 2026-07-14 from `handoff.md` at commit `7f656fc`
> (§2, which contains the §2.7 / §2.8 plans that `backlog.md` and `status.md`
> still cite). `handoff.md` was untracked session-scratch and was dropped from
> the tree in `709363b`, which left every one of those citations dangling —
> flagged as P2 in the 2026-07-12 audit.
>
> **This is history, not a live plan.** The live board is [`PLAN.md`](../../PLAN.md);
> the live FS state is [`status.md`](../status.md); the decision that supersedes
> parts of it is DEC-0018 (whole-`$HOME` Stage B default). Content below is
> verbatim from `7f656fc`.

---

## 2. ⭐ SYSTEM PLIKÓW — DECYZJA ROZSTRZYGNIĘTA 2026-06-12: **A → potem B**

**Właściciel wybrał: Etap A (litera dysku + redirect Dokumenty) na betę,
Etap B (VirtioFS) jako follow-up.** Plan wykonawczy: §2.7 (A) + §2.8 (B).
Sekcje 2.1–2.6 niżej = oryginalny kontekst decyzji (zachowany jako tło —
NIE re-analizuj opcji od zera).

### 2.1 Problem (user request ×4)
Użytkownik chce: appka Windows zapisuje plik **tam, gdzie user łatwo go znajdzie
z Linuksa**, bez szukania „dziwnego dysku sieciowego". Idealnie: Save dialog
otwiera się od razu na folderze Linuksa; jeszcze lepiej „Pulpit/Dokumenty
Windows = folder Linuksa".

### 2.2 Jak (NIE) rozwiązaliśmy to dotąd — przypomnienie
- **Docelowy endgame** (`docs/THREAT_MODEL.md` C5, `proto/crossdesk/v1/
  filesystem.proto`, crate `guest/crates/fs-mount/`): **JIT VirtioFS** — przy
  otwarciu pliku host hot-pluguje mount **tylko katalogu tego pliku**, jako
  litera dysku, potem odmontowuje. Maksymalnie ciasne. **ALE to mock/Phase-5 —
  NIEzbudowane.** `infra/launch-vm.py` NIE ma dziś żadnego `<filesystem>`/
  virtiofs/9p.
- **Co realnie działa dziś:** scoped FreeRDP `/drive:CrossDesk` redirect →
  guest widzi `\\tsclient\CrossDesk` = JEDEN folder (`~/CrossDesk-Shared`),
  opt-in, default OFF (`PeripheralsConfig.shared_folder_*`). To jest ten
  „dziwny dysk sieciowy". Działa DWUKIERUNKOWO (zweryfikowane). To **jeden
  folder, NIE całe $HOME.**
- **Co świadomie odrzuciliśmy** (DEC-META-005, `docs/COMPARISON_WINAPPS.md` §7):
  WinApps' statyczny `\\tsclient\home` = **całe `$HOME`** wystawione zawsze.
- **A1 (`workdir:`)** — próba „domyślnie zapisuj do folderu" przez ustawienie
  CWD RemoteApp-a na `\\tsclient\CrossDesk`. **NIE działa** (UNC nie może być
  CWD procesu → System32). Plumbing `workdir` w kodzie jest POPRAWNY i wielokrotnego
  użytku — zadziała wskazany na **literę dysku** (`Z:\`), nie UNC.

### 2.3 Pytanie właściciela: czy przesadziliśmy z bezpieczeństwem?
Uczciwie: część restrykcyjna (JIT-per-file) jest w większości **aspiracyjna i
niezbudowana**, nie „ściana z którą walczymy". To co realnie shipuje to już
pragmatyczny pojedynczy scoped folder. Jedyne co świadomie odrzucone to „całe
$HOME". **Jest realne miejsce, by mapowanie 1:1 JEDNEGO wybranego folderu
zrobić wygodnie, bez wystawiania wszystkiego.**

### 2.4 OPCJE (przeanalizowane z właścicielem)

| Opcja | Co | UX | Bezpieczeństwo vs dziś | Koszt |
|------|----|----|------------------------|-------|
| **A. Litera dysku + redirect Pulpit/Dokumenty** (ulepszenie obecnego rdpdr) | W gueście map share na `Z:` (`net use`) + ustaw HKCU User Shell Folders Pulpit/Personal na `Z:\` (albo folder). Save defaultuje tam; „Pulpit = folder Linuksa". `workdir:Z:\` ZADZIAŁA (litera, nie UNC). | Natywne, brak szukania | **Bez zmian** (jeden folder, session-only) | **Niski** — krok agenta przy starcie sesji, bez nowego sterownika, **bez zmiany threat-model** |
| **B. VirtioFS jednego folderu jako trwały dysk** (twoje „1:1 przez funkcję VM") | libvirt `<filesystem>` virtiofs montuje jeden folder Linuksa jako realny trwały dysk `Z:` przez sterownik virtio-win (WinFSP+virtiofs). | Natywne + szybkie + przeżywa reconnect | Złagodzone: jeden **trwały** scoped folder (wciąż nie całe $HOME) | **Średni** — sterownik virtio-win VirtioFS w gueście + `virtiofsd` na hoście + memfd w domain XML; **wymaga twojej zgody na mały update THREAT_MODEL/DECISIONS** |
| **C. Pełny JIT VirtioFS** (endgame) | Dokończyć mock: otwarcie pliku → hot-plug katalogu pliku. | Ciasne, ale samo nie rozwiązuje „gdzie zapisać NOWY plik" | Najciaśniejsze | **Wysoki** — duży Phase-5 build |
| **D. Cały $HOME** (styl WinApps) | Wystaw `$HOME`. | Najwygodniej | To co odrzuciliśmy | Mały kod, duża ekspozycja |

### 2.5 Rekomendacja (moja, do akceptacji)
- **A na betę** — robi obecny folder natywnym (dysk + Pulpit/Dokumenty na nim),
  `workdir` staje się użyteczny (wskazany na `Z:\`), zero nowych sterowników,
  **brak regresji bezpieczeństwa** (nie dotykamy threat-model). Najszybsza
  ścieżka do „po prostu działa".
- **B jako ładniejszy follow-up** — realny trwały szybki dysk; ale najpierw
  **zweryfikuj dojrzałość sterownika virtio-win VirtioFS-on-Windows** (bywał
  kapryśny), i wymaga **ADR właściciela** (lekkie złagodzenie postury — wciąż
  nie całe $HOME).
- **C** = długoterminowy ideał bezpieczeństwa, ale duży i sam nie rozwiązuje
  „domyślnej lokalizacji nowego pliku".

### 2.6 Co czeka na decyzję (TWARDE)
**Właściciel wybiera kierunek A / B / C / D** (pytanie zadane przez agenta,
użytkownik je przerwał — wrócić do tematu). Implikacje boundary:
- **B i C dotykają `docs/THREAT_MODEL.md` + `docs/DECISIONS.md`** (boundary
  files → zgoda/ADR właściciela; B = trwały scoped mount, C = promocja JIT
  z mocka).
- **A nie dotyka boundary** — czysto host+agent, można robić od razu po wyborze.
- Jeśli A: cofnąć/zmienić defaultowanie `workdir` z UNC na literę dysku (dziś
  `7e36f55` ustawia UNC → realnie pogarsza default do System32; na nie-zmergowanym
  branchu, więc OK, ale do poprawy przy wyborze kierunku).

### 2.7 PLAN ETAPU A — `feat/fs-drive-letter` (beta; bez boundary files)

> **STATUS 2026-06-12: host-side ZROBIONY + mechanizm guesta ROZSTRZYGNIĘTY
> na żywo.** Kroki 1-2 (config + workdir) + generator skryptu (krok 3 artefakt)
> zacommitowane na `feat/fs-drive-letter` (5 commitów: bb3c3f8 workdir,
> 143c7ad generator, f64cd58 persistent-fix + dwa docs). Bramki zielone.
> **Live-findings zmieniły mechanizm — czytaj „AKTUALIZACJA MECHANIZMU" niżej
> ZANIM dotkniesz krok 3.** Co zostało: GUI-verify Save dialogu + wybór
> triggera one-time + wiring provisioning. Szczegóły też w `status.md` A1.

**Cel/acceptance (live-verify na końcu):** `crossdesk launch notepad` →
Ctrl+S → Save dialog otwiera się na folderze Linuksa (`~/CrossDesk-Shared`);
zapisany plik widoczny na hoście; wyłączenie `shared_folder_enabled` →
następna sesja przywraca domyślne Dokumenty i nie zostawia martwego `Z:`
(Explorer nie wisi); wielokrotne sesje idempotentne.

**⭐ AKTUALIZACJA MECHANIZMU (live-findings 2026-06-12 — NADPISUJE krok 3):**
Eksperymenty na żywej Win10 VM (RemoteApp przez FreeRDP) ustaliły:
- ✅ `net use Z: \\tsclient\CrossDesk` działa w sesji RAIL; `Z:\` jest poprawnym
  CWD (`cd /d Z:\` OK) — litera dysku rozwiązuje problem UNC→System32.
- ❌ **Run key (HKCU/HKLM `...\Run`) NIE odpala się przy logonie RAIL** —
  `rdpinit.exe` (shell RemoteApp) pomija przetwarzanie Run keys. **Ścieżka
  (i) z oryginalnego krok 3 = MARTWA.** (Zweryfikowane: skrypt z Run key nigdy
  nie wykonał się przy świeżym logonie; lokalny marker nie powstał.)
- ✅ **Trwałe mapowanie `/persistent:yes` JEST auto-odtwarzane przez Windows
  MPR przy logonie RAIL** (MPR restore nie zależy od shella). Przeżyło
  `logoff`+świeży logon. **To jest mechanizm drive'a zamiast Run key.**
  `drive_map.py` już zmieniony na `/persistent:yes`.
- ⚠️ `workdir:Z:\` jest **racy** — workdir ustawiany przy tworzeniu procesu
  RemoteApp, a MPR odtwarza Z: ~sekundę później → może trafić w System32 zanim
  Z: gotowe. **Robust lever to redirect shell-foldera** (Documents→`Z:\` lub
  wprost →`\\tsclient\<name>` UNC), bo dialog czyta go LENIWIE gdy się otwiera
  (Z: już odtworzone). workdir:Z:\ zostaje jako best-effort (host go emituje).
  **Do rozważenia: redirect Documents→UNC może sam wystarczyć** (bez litery,
  bez wyścigu) — zweryfikuj GUI którego appki faktycznie używają (CWD vs
  Documents).

**Zrewidowany mechanizm guesta (zamiast Run key):** one-time setup w sesji
która ma share — `net use <L>: \\tsclient\<name> /persistent:yes` + reg add
User Shell Folders redirect. Persistent restore załatwia kolejne logony.
Trigger one-time (do wyboru przez następnego agenta):
- **(A) Deklaratywny `HKCU\Network\<L>` przez autounattend** — wpisz wprost
  rejestr persistent-mappingu (RemotePath=`\\tsclient\<name>`, ProviderName
  „Microsoft Terminal Services") + redirect User Shell Folders. ZERO Rust,
  zero share-przy-provisioningu. **Zweryfikuj że MPR odtworzy z samego wpisu
  rejestru** (nie testowane — testowany był `net use /persistent:yes`
  ustawiony w żywej sesji). Najprostsze jeśli działa.
- **(B) Agent-svc on-session-connect** — `WTSRegisterSessionNotification` +
  `CreateProcessAsUser` odpala wygenerowany skrypt (`drive_map.py`) w sesji
  usera. Deterministyczne, ale Rust w `agent-svc` (cross-session token).

**Krok 0 — sequencing gałęzi.** Kod shared-folder/workdir żyje na
`feat/usability-shared-fs` (NIE zmergowany). Opcje: (a) owner merguje
usability + chore/audit-p2-fixes do main → branch `feat/fs-drive-letter`
z main (preferowane); (b) bez merge: branch z `feat/usability-shared-fs`
(stacked). NIE implementować na samym usability branchu (osobny diff).

**Krok 1 — config (host, `config/peripherals.py`). ✅ ZROBIONE (bb3c3f8).**
- `shared_folder_drive_letter: str = "Z"` (walidator D-Z, upper-normalise,
  reject A/B/C), `shared_folder_redirect_documents=True`,
  `shared_folder_redirect_desktop=False`, helper `shared_folder_drive_path()`.
- Testy w `test_config_peripherals.py` (litera default/custom/reject + redirect
  defaults).

**Krok 2 — host workdir UNC→litera. ✅ ZROBIONE (bb3c3f8).**
- `_peripheral_flags` zwraca `cfg.shared_folder_drive_path()` (`Z:\`) zamiast
  UNC. Plumbing `build_rail_argv(workdir=...)` bez zmian. Gardy bez zmian.
- Testy `test_management_launch.py` zaktualizowane UNC→`Z:\` + custom letter.
- ⚠️ patrz „AKTUALIZACJA MECHANIZMU": workdir:Z:\ jest racy → traktuj jako
  best-effort warstwę, NIE jako jedyny lever.

**Krok 3 — guest skrypt logon. ✅ GENERATOR ZROBIONY (143c7ad, f64cd58);
mechanizm uruchomienia ZREWIDOWANY (patrz „AKTUALIZACJA MECHANIZMU").**
- `installer/drive_map.py::render_drive_map_script(cfg)` emituje idempotentny
  `.cmd`: `if exist \\tsclient\<name>\` → `net use <L>: … /persistent:yes` +
  reg add User Shell Folders (Documents zawsze, Desktop gdy opt-in); `else` →
  restore defaults + drop mapping. Host-baked z config (bez proto/RPC).
  9 testów (`test_drive_map.py`).
- **Run key (oryginalne (i)) MARTWE** — używaj triggera (A) deklaratywny
  `HKCU\Network` lub (B) agent-svc (patrz „AKTUALIZACJA MECHANIZMU").

**Krok 4 — uwagi techniczne:**
- User Shell Folders czytane gdy dialog się otwiera (leniwie) → robust mimo
  wyścigu mapowania. workdir czytany przy starcie procesu → racy.
- Kolizja litery: `net use <L>: /delete` tylko gdy to nasz mapping (lub
  fail-soft). `drive_map.py` robi `/delete /y` przed mapowaniem (idempotent).
- NIE dotykamy: proto, THREAT_MODEL, DECISIONS (A nie zmienia postury —
  ten sam jeden scoped folder).

**Krok 5 — live-verify (POZOSTAJE do zrobienia):**
- **GUI Save dialog:** `crossdesk launch notepad` → Ctrl+S → dialog na share.
  Wymaga narzędzi GUI (zainstaluj `xdotool` + `scrot`/`grim` — NIE było ich
  na hoście w sesji 2026-06-12) ALBO usera patrzącego (jak A1-verify).
- Najpierw przetestuj sam trigger (A) deklaratywny `HKCU\Network` — czy MPR
  odtwarza Z: z wpisu rejestru bez share przy provisioningu.
- Bring-up środowiska: §3. **Gotcha sesji:** każde `crossdesk launch`/FreeRDP
  to potencjalnie inny logon; `logoff` w gueście wymusza świeży logon do
  testów MPR-restore.
- Po sukcesie: wiring provisioning (autounattend wpis `HKCU\Network` +
  redirect, lub agent-svc) + update `status.md`/`backlog.md`.

**Szacunek pozostałości:** ~1 dzień (GUI-verify + trigger-verify + wiring).
Host-side + generator gotowe. Główne otwarte: trigger one-time + GUI-verify.

### 2.8 PLAN ETAPU B — VirtioFS (po becie; gated na ADR + smoke-test)

Provider-swap pod tym samym `Z:` — redirect z Etapu A zostaje bez zmian.
1. **Smoke-test dojrzałości sterownika** `[HW]`: na żywej VM zainstalować
   WinFSP + virtio-win VirtioFS service, zamontować testowy folder, sprawdzić:
   basic IO, duże/małe pliki, reconnect, reboot, case-sensitivity. Go/no-go.
2. **Weryfikacja `qemu:///session`**: virtiofsd + vhost-user wymaga shared
   memory (`<memoryBacking><source type='memfd'/><access mode='shared'/>`);
   sprawdzić wsparcie rootless/session w lokalnym libvirt/qemu (wersje!).
3. **ADR właściciela + THREAT_MODEL row** `[user-approval]` — trwały scoped
   mount (jeden folder, nie $HOME). Owner autoryzuje/zleca draft.
4. Host: `infra/launch-vm.py` `<filesystem driver='virtiofs'>` + memfd;
   guest: WinFSP + driver w autounattend/tools_iso.
5. Skrypt logon z Etapu A: gałąź „VirtioFS obecny → nie rób net use, dysk
   już jest; redirect bez zmian"; rdpdr `/drive:` zostaje fallbackiem.
6. Live-verify + porównanie perf rdpdr vs virtiofs (duży plik + 1000 małych).

---

