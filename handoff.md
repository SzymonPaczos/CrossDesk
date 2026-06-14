# CrossDesk — Session Handoff (zaktualizowany 2026-06-12)

> **Plik tymczasowy.** Świeży agent czyta TEN plik, by kontynuować. NIE
> commituj go (zostaw untracked). PL + angielskie terminy techniczne.
> Kanon stanu: `.claude/status.md`, otwarte prace: `.claude/backlog.md`.

---

## 0. Dla świeżego agenta — zacznij tu
1. Sekcja 1 (gdzie jesteśmy) → **2.7 (PLAN ETAPU A — to jest następna praca;
   decyzja FS ROZSTRZYGNIĘTA 2026-06-12: A → potem B)** → 3 (live state /
   restart) → 7 (CO DALEJ).
2. Sekcja 8 = test report. Sekcja 9 = gotchas (NIE ucz się od nowa).
3. Sekcja 10 = twarde zasady (NIE push; można wznosić/ubijać VM).
4. **Audyt zrobiony 2026-06-12** (`.claude/audit-log.md` na górze): 0 P0,
   0 P1, 4 P2 — wszystkie 4 naprawione tego samego dnia na branchu
   `chore/audit-p2-fixes` (NIE zmergowany; razem z ratchetami: pre-push+CI
   ruff obejmuje `tests/`, coverage floor `fail_under=75`, audit.sh widzi
   venv, deny.toml przycięte). Werdykt slop-check: NOT slop.
5. **Branche czekające na merge właściciela:** `feat/usability-shared-fs`
   (9 commitów, usability+A1) oraz `chore/audit-p2-fixes` (8 commitów, od
   main). Etap A buduje NA usability branchu — patrz §2.7 krok 0.

---

## 1. TL;DR — gdzie jesteśmy (2026-06-09)

Rdzeń produktu działa na żywo (Linux+KVM): `crossdesk launch <app>` → daemon →
verify-credentials (realny LogonUserW) → FreeRDP RAIL → **Windows app jako
natywne okno Linuksa**, z ikoną Windows i scoped współdzielonym folderem.
Branch: **`feat/usability-shared-fs`** @ `7e36f55` (9 commitów; NIE merged,
NIE pushed). Bramki zielone: mypy --strict 121, host 870 testów, ruff src/.

**⭐ NAJNOWSZE (2026-06-12, branch `feat/fs-drive-letter` z usability):**
Decyzja FS = **A→B**. Etap A host-side ZROBIONY (config litery + workdir
UNC→`Z:\` + generator skryptu logon, 5 commitów, bramki zielone). Mechanizm
guesta ROZSTRZYGNIĘTY na żywo: **Run key NIE działa w RAIL, ale persistent
mapping (MPR) TAK** — szczegóły §2.7 „AKTUALIZACJA MECHANIZMU" + §0 pkt 4-5.
Audyt 2026-06-12 zrobiony (0 P0/P1, 4 P2 naprawione na `chore/audit-p2-fixes`).
Pozostaje: GUI-verify Save dialogu + trigger one-time + wiring provisioning.

**Co się wydarzyło w sesji 2026-06-09 (po checkpoint 2fe587e):**
- Zaimplementowano + zacommitowano **A1 (`workdir:`)** — `build_rail_argv`
  dostał param `workdir`, `_peripheral_flags` zwraca `(flags, workdir)`,
  `_launch` wpina. Adversarial review (10 agentów) → 2 realne defekty
  naprawione (walidator boundary na `shared_folder_path` + izolacja smoke
  testu). Commit `7e36f55`.
- **LIVE-VERIFY A1: PORAŻKA CELU.** Po `crossdesk launch notepad` i Ctrl+S w
  notepadzie Save dialog **defaultował do `C:\Windows\System32`**, NIE do
  folderu Linuksa. Folder działa (user dotarł doń ręcznie przez „dysk
  sieciowy"), ale `workdir` nie zadziałał — **Windows nie honoruje ścieżki
  UNC (`\\tsclient\CrossDesk`) jako CWD procesu → fallback do System32.**
- **Właściciel zakwestionował całe podejście do systemu plików** („czy nie
  przesadziliśmy z bezpieczeństwem? może mapowanie 1:1 przez funkcję VM?").
  → **Otwarta DECYZJA — sekcja 2.** Nic dalej nie implementuję bez wyboru kierunku.

**Stan żywy:** host **zrebootowany** (uptime ~kilka min) → daemon/agent/notepad
**ubite**, `/tmp/cd-daemon.log` skasowany. Bring-up od zera — sekcja 3.

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

## 3. Żywy stan + jak zrestartować (host ZREBOOTOWANY — bring-up od zera)

- **VM** `windows-guest` na `qemu:///session` — sprawdź `virsh -c qemu:///session
  list`; jeśli nie działa, wznieś (była uruchomiona Win10 Pro).
- **Daemon / agent / notepad** — ubite po reboocie. `/tmp/cd-daemon.log` skasowany.
- **X**: `DISPLAY=:0`, `XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.*`
  (sufiks ZMIENNY — `ls /run/user/1000/.mutter-Xwayland*`; w tej sesji był `.3PUAQ3`).
- **PKI/provisioning sandbox**: `~/crossdesk-provision/` (agent.exe console-build
  + pki/ + run-agent.cmd). `~/CrossDesk-Shared/` = scoped shared folder (ma pliki
  testowe z poprzednich sesji).

**Pełny bring-up (zweryfikowany w tej sesji, działa):**
```bash
# 0. (jeśli VM nie działa) wznieś windows-guest, poczekaj aż RDP 3389 wstanie:
#    ss -tlnp | grep :3389
# 1. daemon (NOWY kod, TCP bind + X dla RAIL) — BARE run_in_background command:
DISPLAY=:0 XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.<SUFIKS> \
CROSSDESK_CONFIG__TRANSPORT__BIND_KIND=tcp CROSSDESK_FREERDP_BIN=xfreerdp3 \
  /home/szymon-paczos/CrossDesk/host/.venv/bin/python -m crossdesk_host \
  > /tmp/cd-daemon.log 2>&1
#    czekaj na "gRPC server listening securely on 127.0.0.1:50051 (tcp)"
# 2. re-provision agenta (drive-redirect + console agent) — BARE run_in_background:
DISPLAY=:0 XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.<SUFIKS> \
  xfreerdp3 /v:127.0.0.1:3389 /u:crossdesk \
  /p:"$(python3 -c "import tomllib;print(tomllib.load(open('$HOME/.config/crossdesk/vm.toml','rb'))['password'])")" \
  /cert:ignore /sec:tls /drive:prov,$HOME/crossdesk-provision \
  '/app:program:C:\Windows\System32\cmd.exe,cmd:/k \\tsclient\prov\run-agent.cmd'
#    czekaj na "Session state: READY" w /tmp/cd-daemon.log (~10-30s)
# 3. launch:
XDG_RUNTIME_DIR=/run/user/1000 /home/szymon-paczos/CrossDesk/host/.venv/bin/crossdesk launch notepad
```
Regresja-test: `DISPLAY=:0 xwininfo -root -tree | grep crossdesk-notepad`.
Weryfikacja workdir w argv: `ps -ww -C xfreerdp3 -o args= | grep -o '/app:program:[^ ]*'`.

---

## 4. Commity tej sesji (`feat/usability-shared-fs`)
Bazowo 8 commitów z poprzedniej sesji (d548d2e…2fe587e — shared folder,
GUI icon fix, launch-by-path, window icons, audio default-off+pulse).
**Nowy w tej sesji:**
- `7e36f55` **feat(display): RAIL workdir → Save dialog defaults to the shared
  folder.** A1 + hardening z review: walidator boundary `shared_folder_path`
  (pusty/whitespace gdy enabled → reject; `peripherals.py model_post_init`) +
  gard absolute-path w `_peripheral_flags` (pusty/względny path → drop
  drive+workdir) + izolacja `test_smoke_inprocess` (czytał realny
  peripherals.toml) + autouse fixture izolujący `test_management_launch` +
  testy. **UWAGA: live-verify pokazał że workdir-na-UNC NIE działa (System32);
  patrz sekcja 2.** Plumbing zostaje (reusable na literę dysku).

---

## 5. Live findings tej sesji (poza FS — beta-blockery, do backlogu)
Zaobserwowane NA ŻYWO podczas bring-up (nie teoretyczne):
- **Agent (console-mode) pada gdy user zamyka notepada.** ControlSession
  zamknął się dokładnie gdy zamknięto okno → kolejny `launch` failuje na
  verify-credentials („no live guest session"). Root: console agent jest
  związany z cyklem życia sesji RDP. **Fix = produkcyjny agent jako
  NT-service** (przeżywa disconnect sesji + reboot; kod jest, autounattend
  go instaluje). To samo co handoff-§6.D / `status.md` „cmd window artifact".
- **Daemon NIE reapuje zakończonych xfreerdp → zombie `<defunct>`.**
  Po `kill` RAIL-a xfreerdp został `<defunct>`, PPID = daemon (33467). Daemon
  spawnuje subprocess ale nie `wait()`-uje po jego śmierci. Niegroźne (wpis w
  tablicy procesów), ale do naprawy (§6.D). Reap przez `asyncio` child watcher
  / `transport`-level reaping.

---

## 6. Logowanie (mamy je — NIE szukaj od nowa)
- Daemon: structlog JSON → stdout (`/tmp/cd-daemon.log` w dev). Prod → journal
  lub JSONL `~/.local/state/crossdesk/logs/crossdesk-host.jsonl`.
- FreeRDP: stderr dziedziczony przez subprocess daemona → ląduje w logu daemona.
- Agent console: `~/crossdesk-provision/agent-stdout.log`.
- CLI: `crossdesk logs [--component host|libvirt|freerdp|guest] [--follow]`.

---

## 7. CO DALEJ — priorytety (publikacja/beta)

### A. ⭐ SYSTEM PLIKÓW — ROZSTRZYGNIĘTE: Etap A teraz, B po becie.
**Wykonuj plan §2.7** (branch `feat/fs-drive-letter`, krok 0 = sequencing
gałęzi). Etap B = §2.8 (gated: smoke-test sterownika + ADR właściciela).

### B. Stabilność agenta / daemon (beta-blocker — patrz sekcja 5)
- Produkcyjny **agent jako NT-service** (nie console) — z autounattend (kod jest).
- Daemon **reapuje** zombie xfreerdp.
- `~/.local/state/crossdesk/logs/` — utworzyć w prod-setupie.

### C. Audio/clipboard e2e (domyślnie OFF)
Fix pulse jest, niezweryfikowany e2e. Zweryfikuj na produkcyjnym NT-service
agencie (nie trzyma sesji RDP → świeża negocjacja kanałów).

### D. App discovery (skalowalne „każda apka")
`registry-scan` (guest) gotowy. Brak RPC guest→host (RegistryScannerService) +
`ListDiscoveredApps` stub. **Wymaga edycji proto (boundary → zgoda).** Launch-by-path
to interim.

### E. i18n (P2)
`lrelease` nieobecny → `.qm` się nie kompilują → GUI po angielsku. `build.rs`
woła z `.ok()` (cicho).

---

## 8. Test / coverage report
- **Host (Python):** ~78% pokrycia, **870 testów** (po A1: +nowe rail_command/
  management_launch/config_peripherals). `pytest --cov=crossdesk_host`.
- **Guest (Rust):** 39 `#[test]`. **GUI (Rust):** 43 testy.
- Bramki na `7e36f55`: mypy --strict 121 clean; ruff check src/ clean; host 870
  passed / 2 skipped.
- Brak progu coverage w `pyproject.toml`. Luki: realne adaptery (HW-gated) +
  mTLS failure-mode (backlog tech-debt).

---

## 9. Gotchas (NIE ucz się od nowa — kosztowały czas)
- **A1/workdir-na-UNC NIE działa** — Windows nie bierze UNC jako CWD procesu →
  System32. Użyj litery dysku (`Z:\`) jeśli idziesz w kierunku A/B.
- **FreeRDP 3.24 brak pipewire** → `/sound:sys:pipewire` zabija RAIL connect.
  Używaj `/sound:sys:pulse`. (naprawione)
- **`/clipboard-redirect-type:text` NIE istnieje** w FreeRDP 3.x → parse fail.
  Tylko `+clipboard`. USB: `/usb:id:<vid>:<pid>`.
- **Harness: foreground `sleep` > ~10s = exit 144**, ubija bg-skrypt. Trzymaj
  sleepy <10s. **Długie procesy (daemon, xfreerdp) odpalaj jako BARE
  `run_in_background` command** (sam proces, bez pkill/sleep/&& w komendzie).
- **Session takeover**: `crossdesk launch` spawnuje xfreerdp jako `crossdesk` →
  przejmuje sesję od console-agenta (provisioning RDP dropuje exit 1), ale agent
  przeżywa (gRPC po NIC). **Zamknięcie notepada → agent pada** (console tied to
  session) → re-provision.
- **Restart daemona ⇒ agent wychodzi** ⇒ re-provision.
- **peripherals.toml ładowany świeżo per-launch**, ALE DEFAULTY `PeripheralsConfig()`
  z kodu w pamięci daemona → zmiana defaultów wymaga restartu daemona; jawne pola
  w toml działają od razu. Realny toml na hoście MA `shared_folder_enabled=true`.
- **`~/CrossDesk` == repo** → shared folder default to `~/CrossDesk-Shared`.
- **Host bywa resetowany przy obciążeniu** (był w tej sesji) → live state ulotny.
- `cargo`/`xfreerdp3` nie zawsze na PATH → `export PATH="$HOME/.cargo/bin:$PATH"`.

---

## 10. Zasady (twarde)
- **NIE pushuj na GitHub** — owner pushuje. Merge lokalnie tylko na wyraźną prośbę.
- **Można wznosić/ubijać VM-y** (owner: „komputer jest cały dla Ciebie") —
  ostrożnie (host bywał resetowany przy obciążeniu).
- **Boundary plików** (`AGENTS.md`): proto/THREAT_MODEL/DECISIONS/REQUIREMENTS/
  MVP_SCOPE/GOALS/ROADMAP/AGENTS.md — zmiana tylko za zgodą. FS Opcja B/C +
  discovery RPC + per-window icon identity wymagają edycji boundary → zapytaj.
- Branch-per-agent + Conventional Commits + gates zielone przed commitem.

---

## 11. Stan do AUDYTU (`Przygotuj wszystko do audytu`)
- **Audyt należny:** ostatni `## Audyt 2026-05-31` (>7 dni). Procedura:
  `.claude/rules/audit.md` (statyczna `.claude/audit.sh` + warstwa głęboka) +
  skill `weekly-audit`. Audyt **diagnozuje, nie naprawia**; nie dotyka boundary.
- **Drzewo czyste** poza untracked `handoff.md` (świadomie nie-commitowany).
- **Bramki zielone** na HEAD `7e36f55` (mypy 121, ruff src/, host 870).
- **Świadome stany do nie-raportowania jako bug:** A1/workdir „nie działa" jest
  UDOKUMENTOWANE (sekcja 2 + status.md + gotchas) — to czeka-na-decyzję, nie
  swallowed defect. `🚧 mock` markery (fs-mount, iso_downloader, sleep_sync) —
  patrz `.claude/ignorefiles.md` „Partially broken / deprecated".
- **Świeży kod do przejrzenia w audycie:** commit `7e36f55` (display/
  rail_command.py, ipc/management.py, config/peripherals.py + testy).
- Latent (uśpiony, w backlogu Tech-debt): quoted-`cmd:` tokenizer warning gdy
  Phase-5 wepnie file-open.

---

## 12. Sugerowany pierwszy ruch następnej sesji
1. **Domknij DECYZJĘ o systemie plików (sekcja 2)** — wróć do właściciela
   z opcjami A/B/C/D (pytanie było zadane, user je przerwał). To odblokowuje betę.
2. Jeśli właściciel chce audyt najpierw: uruchom `weekly-audit` (repo gotowe,
   sekcja 11).
3. Po decyzji FS: implementuj wybrany kierunek; jeśli A — przekieruj `workdir`
   na literę dysku + agent-side map/shell-redirect, live-verify Ctrl+S.

*Koniec. Stan: feat/usability-shared-fs @ 7e36f55, drzewo czyste (poza handoff.md).
Host zrebootowany. Audyt należny (>7 dni). Blokada #1: decyzja o systemie plików.*
