# PLAN — droga do v0.1.0

**Jedyny board „co dalej".** Jak chcesz wiedzieć co robić — patrzysz tu i
nigdzie indziej. Reszta to: [`status.md`](.claude/status.md) (znane problemy),
[`needs-owner.md`](.claude/needs-owner.md) (czeka na Twoją decyzję),
[`backlog.md`](.claude/backlog.md) (post-MVP / kiedyś — NIE do v0.1.0).

> Aktualizacja: 2026-07-14. Sprzęt (Linux+KVM box, `windows-guest`) jest żywy —
> Fazy 1–4 działają end-to-end na żywo (install → agent → NT-service → RAIL
> render Notepada i Painta jako natywne okna Linuksa, FS Stage A). Do v0.1.0
> zostało wąsko.
>
> **2026-07-14 — właściciel otworzył dwie bramki:** (1) destrukcyjny cykl P0
> (świeży install → finalize → destroy+create) jest **AUTORYZOWANY**; (2) fala
> CI/supply-chain (`.github/**`) jest **AUTORYZOWANA** do wykonania i merge'a.
> Kolejność pracy i pełna kolejka: [`loop-spec.md`](.claude/loop-spec.md)
> (Faza A: kod/CI → Faza B: destrukcyjny cykl → Faza C: live na świeżym gościu).

---

## TERAZ (jeden front)

**→ Faza C: live na świeżym gościu.** Ostatni realny blocker (#6) **padł
2026-07-14** — patrz niżej. Gość jest żywy, zdrowy i świeżo zainstalowany.
Zostało: **#2** (launch p50), **#3** (FS Stage B live), **#4** (heartbeat RTT),
**#5** (suspend/resume), **#8** (microbench), **#11** (README przejazd),
**#12** (packaging) + burn-in. Kolejka: [`loop-spec.md`](.claude/loop-spec.md) Faza C.

### ✅ ZAMKNIĘTE 2026-07-14 — cała ścieżka VM-death → recovery

Destrukcyjny cykl (Faza B) + naprawa P0 zamknęły to end-to-end na żywym Windowsie:

1. **Data-loss (`hard_destroy` bootował instalator)** — finalize odpala na pierwszym
   Hello, trwała konfiguracja idzie z `cdrom boot=1 + ISO` na **`disk boot=1` +
   oba CD `(EJECTED)`**. Recovery bootuje dysk; `autounattend` nie ma jak wystartować.
2. **Brak detektora śmierci VM** — odsłonięty przez live-verify: `virsh destroy` →
   daemon **nie reagował w ogóle** (FSM heartbeatu tyka ze strumienia, który śmierć
   VM zamyka). Brakowały **trzy** rzeczy: realne `LibvirtDomainEventSource`, recovery
   w `DomainEventReactor` (tylko logował), oraz `LibvirtController.start()` — bo
   `hard_destroy()` robi `destroy()+create()`, a `destroy()` na martwej domenie rzuca.
3. **Zmierzone:** wykrycie **1 s** · domena wstaje **6 s** · **agent wraca 25 s**
   (budżet 90 s). Wcześniej: 60 s ciszy i trup.

Uwaga zachowana świadomie: **czyste wyłączenie gościa NIE jest wskrzeszane** (tylko
`destroyed`/`crashed`/`failed`) — inaczej walczylibyśmy z użytkownikiem.

## NEXT (do v0.1.0 — wszystko wykonalne na tym boxie)

- **FS Stage B live** — virtio-fs mount jednego folderu (default whole-`$HOME`,
  DEC-0018) + Save dialog ląduje w folderze Linuksa. To jest MVP-floor **zamiast
  JIT** (kryt. #3 wymaga re-definicji — patrz needs-owner). Host-side gotowe;
  live mount do odpalenia.
- **Suspend/resume bez false HARD_DESTROY** (#5) — live na boxie; blokada
  (coordinator zamrażał event-loop) zdjęta 2026-07-14 (`c4cb6e8`).
  (#6 recovery → front „TERAZ". #9 `doctor` i #10 `uninstall` — ✅ LIVE-VERIFIED,
  patrz tabela.)
- **Pomiary N1** (#2 launch, #4 heartbeat, #8 microbench) — harness gotowy,
  realne liczby na boxie.
- **README quick-start** (#11) — realny przejazd „od zera do okna".
- **1 format pakietu instaluje** (#12) — AUR PKGBUILD + agent bundling gotowe,
  test instalacji.
- **M5 burn-in** — ≥2 Windows × cykle, żeby złapać flaki.

## LATER (post-MVP — NIE blokuje v0.1.0)

Pełna lista w [`backlog.md`](.claude/backlog.md). Skrót: GPU passthrough ·
Looking Glass · Wayland-native RAIL · multi-monitor · peripherals (audio/
clipboard/printer/USB/mic/camera) · deb/rpm + repo domain · app-discovery RPC ·
Stage C JIT-per-file FS · i18n wave 2 · code-signing · self-hosted CI runner.

---

## Twardy definition-of-done — 12 kryteriów akceptacji v0.1.0

Źródło: `docs/MVP_SCOPE.md` „Acceptance criteria". `MVP done` = wszystkie ✅.

Legenda: **✅ live** = zweryfikowane na żywym boxie · **🔲 box** = wykonalne
teraz, do odpalenia · **🔨 code** = wymaga jeszcze kodu · **⛔** = zablokowane ·
**⚠️ boundary** = definicja kryterium wymaga podpisu właściciela.

| # | Kryterium (MVP_SCOPE) | Stan | Nota |
|---|---|---|---|
| 1 | `install` ≤25 min / ≤2 min attended | ✅ live | **RE-VERIFIED 2026-07-14**: `uninstall --force` → świeży `install --locale pl-PL` → agent auto-online, zero ręcznych kroków. CLI wraca po 16 s; Windows + agent gotowe ~12 min. Cross-distro OVMF-fix testowany tylko na tym boxie → 🔲 |
| 2 | `launch notepad` → natywne okno ≤3 s p50 | ✅ live ⚠️ | **LIVE-MEASURED 2026-07-14 (`472b0e8`)**: komenda → zmapowane okno X (xdotool, 6 przejazdów) — **p50 = 2,748 s** przy budżecie 3 s → **PASS, ale tylko 8% zapasu**; **max 5,311 s wychodzi poza budżet**. **Rozbicie**: host-side Launch RPC = **7,5 ms p50** (~0,3% czasu!), reszta to FreeRDP negocjujący RDP+RAIL z gościem **po** powrocie RPC. Budżet mierzy więc handshake RDP, nie nasz kod. Pierwszy launch po boocie gościa **nie dał okna** (znany wyścig z verify-creds) |
| 3 | plik -> app Windows przez skonfigurowany share | 🔲 box | **Boundary ZDJETY** — MVP_SCOPE **juz** mowi Stage B (persistent virtio-fs, default whole-`$HOME`, DEC-0018), nie JIT; re-definicja weszla 2026-07-05. Zostaje sam live-verify mountu Stage B + Save dialog |
| 4 | heartbeat RTT <20 ms p50 | ✅ live | **LIVE-MEASURED 2026-07-14 (`eca3a0c`)**: 179 realnych round-tripów przez mTLS do agenta NT-service — **p50 = 2,46 ms** (budżet 20 ms, ~8× zapasu), p95 2,99 ms, p99 4,67 ms, max 6,43 ms. Metryka wcześniej **nie istniała jako histogram** — nazwa `heartbeat_rtt_seconds` była w `MetricNames` bez zapisującego, a FSM zwijał RTT do EWMA i gubił rozkład |
| 5 | suspend/resume bez false HARD_DESTROY | 🔲 box | LifecycleCoordinator gotowy; live-verify |
| 6 | kill VM (`virsh destroy`) → recovery ≤90 s | ✅ live | **LIVE-VERIFIED 2026-07-14 (`414c879`)**: `virsh destroy` → wykryte w **1 s** (`vm_lifecycle_event`) → auto-recovery → domena wstaje w 6 s → **agent z powrotem w 25 s** (budżet 90 s), bootując DYSK bez nośników. Zero udziału człowieka. Wymagało trzech brakujących elementów: `LibvirtDomainEventSource` (nie istniał), recovery w reaktorze (tylko logował), `LibvirtController.start()` (nie było czym wystartować martwej domeny) |
| 7 | CI green Ubuntu; `agent.exe` cross-compile | ✅ live | **SPELNIONE** — marker boundary byl **przeterminowany**: re-definicja (macOS -> Linux) weszla do MVP_SCOPE **2026-07-05**. Zweryfikowane 2026-07-14: wszystkie joby main CI **success**, a `cargo build --release --target x86_64-pc-windows-gnu -p agent-svc` produkuje **realny PE32+ Windows x86-64** (5,2 MB) — nie tylko `cargo check`, ktory robi CI |
| 8 | microbench pass vs baselines | ✅ live | **ZROBIONE 2026-07-14 (`7ee8b60`)** — bramka wczesniej **nie bramkowala**: 6 z 11 baseline'ow mialo `0` (collect-only), reszta to atrapy z do 66% luzu. Zastapione **zmierzonymi** wartosciami z ubuntu-latest (3 zielone buildy, rozrzut 1-3%, baseline = najgorszy z trzech). Sentinel: regresja +25% jest **lapana**. **Job microbench w CI: zielony** na zaostrzonych liczbach |
| 9 | `doctor` = 0 na dobrym hoście, błędy na złym | ✅ live | LIVE-VERIFIED 2026-07-05: na tym boxie `doctor` = **exit 0**, 10/10 OK (cpu_virt svm, kvm, vsock, qemu 10.2, freerdp, ovmf, libvirt, disk 135GB, config, vm_creds); zły host (`CROSSDESK_OVMF_CODE` bogus) → `ovmf [fail]` + **exit 1** |
| 10 | `uninstall` czyste usunięcie | ✅ live | **LIVE-VERIFIED 2026-07-14** (`uninstall --force`): domena destroy+undefine, state-dir z dyskiem 29 GB, config, nvram, `.desktop` — usunięte, exit 0. Backup poza state-direm i ISO użytkownika **nietknięte**; `--dry-run` wcześniej pokazał dokładny plan |
| 11 | README quick-start działa dla zwykłego usera | 🔨 | ISO-honesty naprawione; realny przejazd do zrobienia |
| 12 | ≥1 format pakietu instaluje bez ręcznego kopiowania | 🔲 box | AUR + agent bundling gotowe; test instalacji |

**Stan: 8 z 12 kryteriow ✅ live** (#1, #2, #4, #6, #7, #8, #9, #10). Zostaje: **#3** (mount Stage B live), **#5** (suspend/resume live), **#11** (realny przejazd README), **#12** (test pakietu). **Zadne nie czeka juz na Twoj podpis** — oba boundary (#3, #7) okazaly sie od dawna rozstrzygniete, a board o tym nie wiedzial.

**Podsumowanie (po live-verify 2026-07-14):** destrukcyjny cykl przejechany —
**#1 re-verified**, **#10 zamknięte**, a **data-loss half #6 zamknięta i
udowodniona na żywym Windowsie**. Board mylił się jednak co do **#6**: naprawa
`hard_destroy` była **konieczna, ale niewystarczająca** — recovery nigdy się nie
wyzwala, bo **nie ma detektora śmierci VM** (nowy front „TERAZ”). Zmierzony
reconnect: **105 s** przy budżecie 90 s.

Zostaje: **#6** (detektor + budżet), 2 kryteria do re-definicji przez właściciela
(#3, #7 — needs-owner §7), oraz Faza C na świeżym gościu (**#2, #3, #4, #5, #8,
#11, #12** + burn-in). Gość jest żywy i zdrowy — Faza C może ruszyć od zaraz.
