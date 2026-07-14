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

**→ P0 BRAK DETEKTORA ŚMIERCI VM** — to jest realny blocker **#6**, odsłonięty
przez live-verify 2026-07-14. `virsh destroy` na żywej domenie → **daemon nie
zauważa niczego**: zero linii w logu, zero eskalacji, VM leży. Root cause
(zweryfikowany, nie zgadnięty):

- FSM heartbeatu tyka z `request_iterator` strumienia gRPC → śmierć VM zamyka
  strumień → **FSM milknie i nigdy nie eskaluje do HARD_DESTROY**;
- `daemon.py` **nie wpina żadnego** źródła zdarzeń domeny (grep: 0 trafień);
- `lifecycle/domain_events.py` ma `DomainEventReactor` + `MockDomainEventSource`,
  ale **`LibvirtDomainEventSource` NIE ISTNIEJE nigdzie w `src/`**.

Uwaga projektowa na przyszłe wpięcie: `hard_destroy()` robi `destroy()`+`create()`,
a `destroy()` na **martwej** domenie rzuca `RuntimeError`. Recovery po zabiciu VM
musi wołać samo `create()`, nie `destroy()+create()`.

**Poprzedni front (`hard_destroy` steady-state XML) jest ZAMKNIĘTY** —
mechanizm live-verified 2026-07-14 na realnej domenie Windows; szczegóły niżej.

- ✅ **Mechanizm ZROBIONY (testowalny, host-side)**: `build_steady_state_domain_xml`
  (disk `boot=1`, oba CD ejected) + `redefine_steady_state` na Protocol/real/mock
  (real: `defineXML` z zachowaniem UUID żywej domeny, box-gated; czysty helper
  `_with_domain_uuid` przetestowany). 38 testów.
- ✅ **Finalize WPIĘTY (host-side, `9ac1da1`)**: `installer/steady_state.py`
  (`persist_steady_state_xml` przy `create_libvirt_domain` + idempotentny
  `finalize_steady_state`) + `ControlServiceServicer.on_session_ready` hook
  odpalany na pierwszym Hello. Idempotent (krok „steady_state" w
  `install.state.json`) + retry przy błędzie libvirt. Daemon wpina hook TYLKO dla
  realnego kontrolera (mock zamarkowałby krok „done" bez realnej redefinicji =
  maskowanie data-loss). 14 testów, cała suita zielona.
- ✅ **A3-seam ZROBIONY (host-side, `30579a6`)**: backend libvirt daemona jest
  config-selectable — `LibvirtConfig.backend = mock|real` (default mock,
  zachowanie niezmienione) + `CROSSDESK_CONFIG__LIBVIRT__BACKEND=real`. Ustawienie
  `real` na boxie napędza `qemu:///session` i AKTYWUJE `on_session_ready` finalize
  + realne recovery heartbeatu (`_assert_suspend_protection` dalej fail-close bez
  D-Bus listenera). 4 testy. Koniec „daemon twardo mock".
- ✅ **A3-seam LIVE-SMOKE-VERIFIED (box, 2026-07-05)**: daemon z `backend=real` +
  `bind_kind=tcp` wstał czysto na boxie — D-Bus suspend listener `subscribed`
  (`_assert_suspend_protection` przeszło z realnym kontrolerem) → „Server is
  running". Non-destrukcyjnie (libvirt nietykany przy starcie; `windows-guest`
  bez zmian; graceful shutdown). **Strona daemona P0 jest udowodniona gotowa.**
- ✅ **WYKONANE 2026-07-14 — destrukcyjny cykl PRZEJECHANY NA ŻYWO.** Świeży
  `uninstall --force` → świeży `install` → daemon `backend=real` → agent Hello →
  finalize → `virsh destroy` → `create`. **Dowody (`/tmp/cd-evidence/`):**
  - `20:36:07` — hook `on_session_ready` odpalił na **pierwszym** Hello:
    `redefine_steady_state: defineXML (eject media, disk boot=1)` →
    `steady_state_finalize_applied`; krok `steady_state` w state = **done**.
  - **Trwała konfiguracja przestawiona:** `cdrom boot=1 + ISO` → **`disk boot=1`,
    oba CD-ROM `(EJECTED)`**.
  - **Recovery `create()` bootuje DYSK** — zero nośników instalacyjnych,
    `autounattend` **nie ma jak się uruchomić**. Agent wrócił w **105 s** z tą
    samą tożsamością mTLS, dysk 9,7→9,8 GB (**nie** przeinstalowany).
  - **Ścieżka utraty danych jest definitywnie zamknięta.**

  **ALE #6 NADAL NIE JEST SPEŁNIONE** — bo blocker był gdzie indziej, niż board
  zakładał: recovery **nigdy się nie wyzwala** (brak detektora śmierci VM, patrz
  front „TERAZ"), a reconnect zajął **105 s > 90 s** budżetu. Naprawa P0 była
  **konieczna, ale niewystarczająca**.

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
| 2 | `launch notepad` → natywne okno ≤3 s p50 | ✅ live / 🔨 | Render live (Notepad+Paint). Formalny pomiar ≤3 s p50 do zrobienia |
| 3 | `.txt` → Open with Notepad → **JIT** mount, detach po zamknięciu | ⚠️ boundary / 🔲 | DEC-0018: MVP-floor = **Stage B** (persistent), nie JIT. Kryterium przeczy in-scope — re-def do podpisu (needs-owner §7). Stage B mount: 🔲 box |
| 4 | heartbeat RTT <20 ms p50 | 🔲 box | FSM gotowy; realny pomiar na boxie |
| 5 | suspend/resume bez false HARD_DESTROY | 🔲 box | LifecycleCoordinator gotowy; live-verify |
| 6 | kill VM (`virsh destroy`) → recovery ≤90 s | ⛔ P0 | **Data-loss half ZAMKNIĘTA i LIVE-VERIFIED 2026-07-14** (finalize → `disk boot=1`, oba CD ejected → `create` bootuje dysk, agent wraca, zero reinstalacji). **Ale kryterium NIE spełnione:** recovery **nigdy się nie wyzwala** — brak detektora śmierci VM (`LibvirtDomainEventSource` nie istnieje; FSM tyka ze strumienia, który śmierć VM zamyka). Do tego reconnect = **105 s > 90 s**. To jest front „TERAZ” |
| 7 | CI green macOS + Ubuntu; `agent.exe` cross-compile | ⚠️ boundary | `agent.exe` ✅, Ubuntu CI ✅. „macOS matrix" martwe (Mac zvacuumowany) — re-def do podpisu (needs-owner §7) |
| 8 | microbench pass vs baselines | 🔲 box | harness gotowy; realne liczby |
| 9 | `doctor` = 0 na dobrym hoście, błędy na złym | ✅ live | LIVE-VERIFIED 2026-07-05: na tym boxie `doctor` = **exit 0**, 10/10 OK (cpu_virt svm, kvm, vsock, qemu 10.2, freerdp, ovmf, libvirt, disk 135GB, config, vm_creds); zły host (`CROSSDESK_OVMF_CODE` bogus) → `ovmf [fail]` + **exit 1** |
| 10 | `uninstall` czyste usunięcie | ✅ live | **LIVE-VERIFIED 2026-07-14** (`uninstall --force`): domena destroy+undefine, state-dir z dyskiem 29 GB, config, nvram, `.desktop` — usunięte, exit 0. Backup poza state-direm i ISO użytkownika **nietknięte**; `--dry-run` wcześniej pokazał dokładny plan |
| 11 | README quick-start działa dla zwykłego usera | 🔨 | ISO-honesty naprawione; realny przejazd do zrobienia |
| 12 | ≥1 format pakietu instaluje bez ręcznego kopiowania | 🔲 box | AUR + agent bundling gotowe; test instalacji |

**Podsumowanie (po live-verify 2026-07-14):** destrukcyjny cykl przejechany —
**#1 re-verified**, **#10 zamknięte**, a **data-loss half #6 zamknięta i
udowodniona na żywym Windowsie**. Board mylił się jednak co do **#6**: naprawa
`hard_destroy` była **konieczna, ale niewystarczająca** — recovery nigdy się nie
wyzwala, bo **nie ma detektora śmierci VM** (nowy front „TERAZ”). Zmierzony
reconnect: **105 s** przy budżecie 90 s.

Zostaje: **#6** (detektor + budżet), 2 kryteria do re-definicji przez właściciela
(#3, #7 — needs-owner §7), oraz Faza C na świeżym gościu (**#2, #3, #4, #5, #8,
#11, #12** + burn-in). Gość jest żywy i zdrowy — Faza C może ruszyć od zaraz.
