# Rejestr decyzji (META)

Decyzje META o procesie/workflow projektu. Status: **aktywna** chyba że
oznaczone inaczej.

> **Decyzje techniczne stacku** — patrz [`docs/DECISIONS.md`](../../docs/DECISIONS.md)
> (kanoniczny rejestr ADR `DEC-NNNN`). Plik ten trzyma TYLKO META-decyzje:
> jak pracujemy, gdzie żyje stan, jakie konwencje obowiązują. Boundary
> z `AGENTS.md` na `docs/DECISIONS.md` jest podtrzymane — edycja
> DEC-NNNN wymaga zgody właściciela.

---

## DEC-META-001 — Adopcja konwencji claude-toolkit §9.9

**Data:** 2026-05-23 · **Status:** aktywna

Projekt adoptuje układ plików stanu wg cyklu życia z
`~/DevProjects/claude-toolkit/conventions/project-state-layout.md` +
`NEW-PROJECT.md` §9.9. Konkretnie:

- `.claude/backlog.md` — jedyne źródło otwartej pracy (P0/P1/P2 +
  "czeka na decyzję" + "zablokowane"). FOLLOWUPS.md został tu
  sfoldowany; archiwum w `.claude/history/2026-05-23-followups-archive.md`.
- `.claude/status.md` — known-issues / bieżące breakages.
- `.claude/rules/` — TYLKO trwałe instrukcje (audyt, decisions, general,
  backend). Stan przejściowy poza `rules/`.
- `.claude/history/` — archiwum (`completed-work.md` append-only +
  raporty sesji z datą w nazwie).
- `WORK_LOG.md` — świadome odstępstwo (zob. DEC-META-003).

**Powód:** Spójność cross-projektowa, jeden punkt wejścia dla nowej sesji.

## DEC-META-002 — `docs/DECISIONS.md` pozostaje kanoniczny dla ADR

**Data:** 2026-05-23 · **Status:** aktywna

ADR `DEC-NNNN` żyją w `docs/DECISIONS.md` (techniczne decyzje stacku:
proto, transport, packaging, GPU passthrough itd.). Ten plik
(`.claude/rules/decisions.md`) trzyma TYLKO META-decyzje workflow'owe
(prefiks `DEC-META-NNN`).

**Powód:** `AGENTS.md` "File boundaries" zabrania edycji
`docs/DECISIONS.md` bez zgody właściciela. Duplikacja DEC-NNNN do
`.claude/` byłaby źródłem driftu. Separacja ról jest czystsza.

**Jak stosować:** Audyt sprawdza zgodność z **OBOMA** plikami (zob.
`.claude/rules/audit.md` §7).

## DEC-META-003 — `WORK_LOG.md` pozostaje w roocie

**Data:** 2026-05-23 · **Status:** aktywna

`WORK_LOG.md` (koordynacja multi-agent START/END) pozostaje w roocie
repo, nie jest przenoszony do `.claude/active-work.md` ani do
`.claude/history/` mimo że łamie regułę §9.9 "stan przejściowy poza
rooekm".

**Powód:** `AGENTS.md` workflow steps 6 i 13 definiują WORK_LOG.md jako
plik pushowany bezpośrednio do `main` (jedyny wyjątek od no-direct-main).
Przeniesienie wymusiłoby zmianę protocolu i conflict resolution dla
agentów już używających ścieżki w roocie. Trade-off zaakceptowany.

**Jak stosować:** Audyt nie raportuje WORK_LOG.md jako odstępstwa
§9.9 (już udokumentowane tutaj).

## DEC-META-004 — Inline `FOLLOWUPS:NNN` w kodzie zostają niezmienione

**Data:** 2026-05-23 · **Status:** aktywna

Po fold FOLLOWUPS.md → backlog.md komentarze w kodzie/testach typu
`# FOLLOWUPS:665` lub `(FOLLOWUPS:1019 follow-up)` **pozostają**.
Rozwiązują się przeciwko archiwum
`.claude/history/2026-05-23-followups-archive.md`.

**Powód:** ~30+ plików źródłowych miałoby line-number drift (numery linii
FOLLOWUPS:NNN nie mapują się 1-do-1 na nowy backlog). Adnotacje są
historyczne, nie load-bearing; agent grepujący "FOLLOWUPS:665" znajdzie
ten sam content w archiwum.

**Jak stosować:** Nowe komentarze referencyjne piszemy jako
`# backlog: <area> <pNN>` (np. `# backlog: peripherals P1 audio`)
zamiast line-numerów. Audyt nie raportuje istniejących FOLLOWUPS:NNN
adnotacji.

## DEC-META-005 — Skipped-on-purpose lista z FOLLOWUPS

**Data:** 2026-05-23 · **Status:** aktywna

Lista 8 pozycji "Skipped on purpose (do not implement)" z dawnego
FOLLOWUPS.md została wchłonięta tutaj. Te decyzje **NIE wracają jako
feature requests** bez decyzji właściciela. Pełne uzasadnienia w
[`docs/COMPARISON_WINAPPS.md`](../../docs/COMPARISON_WINAPPS.md) §7.

- Docker / Podman backends — kolizja z `qemu:///session` constraint
  (zob. DEC-0003).
- `dockur/windows` container image — j.w.
- Static `\\tsclient\home` mount — security regression vs JIT VirtioFS.
- Bash-driven control flow — niekompatybilne z async Python + mypy.
- `compose.yaml` — irrelevant bez Dockera.
- `renovate.json` / WinApps' `flake.nix` — różny packaging stack (nasz
  flake.nix jest osobnym artefaktem).
- Verbatim AGPLv3 file copies z `third_party/winapps/` —
  license-incompatible.
- Tiny11 / Tiny10 / community-modified ISOs — unauthorized MS source
  modification; superseded by Lean Windows profile.

**Jak stosować:** Jeśli ktoś zaproponuje którąkolwiek z tych ścieżek,
przekieruj do tej listy + COMPARISON_WINAPPS §7.
