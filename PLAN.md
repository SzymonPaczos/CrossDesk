# PLAN — droga do v0.1.0

**Jedyny board „co dalej".** Jak chcesz wiedzieć co robić — patrzysz tu i
nigdzie indziej. Reszta to: [`status.md`](.claude/status.md) (znane problemy),
[`needs-owner.md`](.claude/needs-owner.md) (czeka na Twoją decyzję),
[`backlog.md`](.claude/backlog.md) (post-MVP / kiedyś — NIE do v0.1.0).

> Aktualizacja: 2026-07-05. Sprzęt (Linux+KVM box, `windows-guest`) jest żywy —
> Fazy 1–4 działają end-to-end na żywo (install → agent → NT-service → RAIL
> render Notepada i Painta jako natywne okna Linuksa, FS Stage A). Do v0.1.0
> zostało wąsko.

---

## TERAZ (jeden front)

**→ P0 `hard_destroy` steady-state XML** — blokuje akceptację **#6** (kill VM →
recovery) i wpięcie realnego `LibvirtController` do lifecycle (A3). Problem:
domena trzyma install-ISO na `boot order=1` przez całe życie; recovery
(`destroy`+`create`) bootuje install-ISO → autounattend **reinstaluje Windows na
dysku = utrata danych** (dziś latentne, daemon = mock-libvirt).

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
- 🔲 **ZOSTAJE (box-gated, = A3 + live)**: (a) wpiąć realny `LibvirtController`
  do daemona (dziś twardo mock, `daemon.py:126`) — to aktywuje `on_session_ready`
  finalize; (b) live-verify na realnym libvirt, że po redefinicji destroy+create
  bootuje dysk (nie ISO). Dopiero to zamyka #6. Szczegóły: [`status.md`](.claude/status.md).

## NEXT (do v0.1.0 — wszystko wykonalne na tym boxie)

- **FS Stage B live** — virtio-fs mount jednego folderu (default whole-`$HOME`,
  DEC-0018) + Save dialog ląduje w folderze Linuksa. To jest MVP-floor **zamiast
  JIT** (kryt. #3 wymaga re-definicji — patrz needs-owner). Host-side gotowe;
  live mount do odpalenia.
- **Suspend/resume bez false HARD_DESTROY** (#5) + **recovery ≤90s** (#6) —
  live na boxie, po naprawie P0.
- **`uninstall` live** (#10) — kod kompletny; live-verify realnego usunięcia
  (undefine niszczy `windows-guest` → zrobić z rozwagą / po becie).
  `uninstall --dry-run` na realnym CLI potwierdzony (domena+pliki, exit 0).
  (#9 `doctor` — ✅ LIVE-VERIFIED, patrz tabela.)
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
| 1 | `install` ≤25 min / ≤2 min attended | ✅ live | A7-live: świeży install → agent auto-online ~12 min zero-touch. Cross-distro (Fedora/Arch) OVMF-fix jest, ale testowane tylko na tym boxie → 🔲 |
| 2 | `launch notepad` → natywne okno ≤3 s p50 | ✅ live / 🔨 | Render live (Notepad+Paint). Formalny pomiar ≤3 s p50 do zrobienia |
| 3 | `.txt` → Open with Notepad → **JIT** mount, detach po zamknięciu | ⚠️ boundary / 🔲 | DEC-0018: MVP-floor = **Stage B** (persistent), nie JIT. Kryterium przeczy in-scope — re-def do podpisu (needs-owner §7). Stage B mount: 🔲 box |
| 4 | heartbeat RTT <20 ms p50 | 🔲 box | FSM gotowy; realny pomiar na boxie |
| 5 | suspend/resume bez false HARD_DESTROY | 🔲 box | LifecycleCoordinator gotowy; live-verify |
| 6 | kill VM (`virsh destroy`) → recovery ≤90 s | ⛔ P0 | **Blokuje: `hard_destroy` reinstaluje Windows.** To jest front „TERAZ" |
| 7 | CI green macOS + Ubuntu; `agent.exe` cross-compile | ⚠️ boundary | `agent.exe` ✅, Ubuntu CI ✅. „macOS matrix" martwe (Mac zvacuumowany) — re-def do podpisu (needs-owner §7) |
| 8 | microbench pass vs baselines | 🔲 box | harness gotowy; realne liczby |
| 9 | `doctor` = 0 na dobrym hoście, błędy na złym | ✅ live | LIVE-VERIFIED 2026-07-05: na tym boxie `doctor` = **exit 0**, 10/10 OK (cpu_virt svm, kvm, vsock, qemu 10.2, freerdp, ovmf, libvirt, disk 135GB, config, vm_creds); zły host (`CROSSDESK_OVMF_CODE` bogus) → `ovmf [fail]` + **exit 1** |
| 10 | `uninstall` czyste usunięcie | 🔲 box | Kod kompletny (`8261a35`): domena `undefine` (destroy+undefine NVRAM) + .desktop + ISO + state/disk + config. Zostaje live-verify pełnego usunięcia + opcjonalny `--force`/confirm (backlog) |
| 11 | README quick-start działa dla zwykłego usera | 🔨 | ISO-honesty naprawione; realny przejazd do zrobienia |
| 12 | ≥1 format pakietu instaluje bez ręcznego kopiowania | 🔲 box | AUR + agent bundling gotowe; test instalacji |

**Podsumowanie:** 1 realny blocker (#6 = P0 hard_destroy), 2 kryteria do
re-definicji przez właściciela (#3, #7 — needs-owner §7), reszta = „odpalić na
boxie" lub drobny kod. Żadne z powyższych nie jest już `[HW]`-blocked —
sprzęt jest.
