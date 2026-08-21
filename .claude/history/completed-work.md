# Completed work — archiwum

Append-only. Najnowsze na górze. Granular `WORK_LOG.md` zostaje w
roocie — tutaj trafia tylko streszczenie tematów po zamknięciu fazy
/ większego bloku prac.

Pełna granularność per-commit START/END — `WORK_LOG.md` "Recent".
Per-task plik raportu sesji — `.claude/history/YYYY-MM-DD-temat.md`.

## Audytowe sweepy

- **2026-07-07** — Remediation of the 2026-07-07 audit — 14 findings fixed
  across 9 branches (security-first: RDP-secret redaction + 0600 secret files
  + libvirt loop deadlines + backend-select logging, then icon validation,
  CI fork gate, stale advisory, uninstall dir single-source, docs sweep), 3
  parked with triggers (C-1 PKGBUILD pin, C-2 marker-gated live-libvirt test,
  C-3 coordinator offload), 1 declined (D-1 historical i18n commit subjects).
  Plan: [2026-07-07-remediation.md](2026-07-07-remediation.md).
- **2026-05-20** — Senior engineering audit (Slop Score 27/100). 14 hot
  issues + fix plan. Plik: [2026-05-20-audit-senior.md](2026-05-20-audit-senior.md) +
  [2026-05-20-audit-fix-plan.md](2026-05-20-audit-fix-plan.md).
- **2026-05-11** — Six-fazowy automated audit (linters auto-fix, dead
  code, rust safety, docs publicznych API, testy, raport). Branch
  `chore/audit-2026-05-11` (zmergowany 2026-05-11). Plik:
  [2026-05-11-audit-automated.md](2026-05-11-audit-automated.md).
- **2026-05-09** — Pierwszy manualny code-quality audit (`gitleaks`,
  `pip-audit`, `cargo audit`, `bandit`, `semgrep`, `ruff S/B/RUF/...`,
  `vulture`, `interrogate`, `cargo machete`, `cargo deny`, `shellcheck`,
  `actionlint`, `tokei`). Pre-v1.0. Plik:
  [2026-05-09-audit-manual.md](2026-05-09-audit-manual.md).

## Fazy / bloki prac

- **Phase 1 — VM bootstrap + NT service** (✅ ukończona). VM bring-up,
  autounattend, NT service skeleton, pierwsze gRPC handshake. Granularny
  trace w `WORK_LOG.md` 2026-05-07 → 2026-05-09.
- **Phase 2 — Transport** (w trakcie). gRPC z mTLS + AuthContext +
  bidi streams shipped; AF_HYPERV vsock dial poza dev nieuruchomione.
  Granularny trace w `WORK_LOG.md` 2026-05-09 → ongoing.

## P1 batch — 2026-05-23

- **DBusNotifier real implementation** — `integrations/notifications.py`
  replaced Phase 7 no-op stub with real dbus-next aio call; sync/async
  context detection; `ignorefiles.md` stub entry removed.
- **`crossdesk config migrate` CLI** — new `cli/config_cmd.py` +
  argparse wiring in `main.py`; handles missing file, legacy v1, future
  version error, non-integer version; 6 tests in `test_config_cmd.py`.
- **Doctor checks expansion** — added `check_cpu_virt_extensions`,
  `check_vsock_module`, `check_qemu_version`, `check_config_dir_writable`
  to `doctor/checks.py`; `--gpu` flag in `doctor_cmd.py` wired to
  `GPU_CHECKS`; 13 tests in `test_doctor_checks.py`.
- **CLI i18n wave 2** — `apps_cmd.py` column headers wrapped in `_()`.
- **Windows registry real implementation** — replaced Phase 8 stub in
  `guest/crates/registry-scan/src/windows_impl.rs` with full
  `RegEnumKeyExW` + `RegGetValueW` walker covering App Paths +
  Uninstall HKLM 64/32 + Uninstall HKCU; `registry-scan` added as dep
  in `agent-svc/Cargo.toml`.

## Migracja FOLLOWUPS → backlog

- **2026-05-23** — Fold FOLLOWUPS.md (1260 linii) w `.claude/backlog.md`.
  Archiwum oryginalnego pliku:
  [2026-05-23-followups-archive.md](2026-05-23-followups-archive.md).
  Decyzja w `.claude/rules/decisions.md` DEC-META-001.

## 2026-08-21 — sposób audytu przebudowany na claude-toolkit 2026.08.21

Kopie toolkitu `2026.08.06` → `2026.08.21` (`toolkit-sync.sh`, lock zielony,
jedno zadeklarowane odstępstwo). `rules/audit.md` przestał być drugą,
równoległą checklistą i jest **nakładką** na masterowe punkty 1–25 — `contrib`
pokazał 16 pozycji projektu wobec 8 w masterze przy zielonym `check`, bo plik
nie jest kopią. Przyjęte: `references/kontrola-glebokosci.md` (14 → 25
punktów), 8 konwencji dereferencjonowanych przez nowe punkty, drugi skill
audytowy `audyt-naprawczy` (z trzema odstępstwami CrossDeska: boundary files
poza automatem, prefiks gałęzi `audyt/`, zawis pytest = `n/a`), szablony
audytowe. `audit.sh` rozdziela trzy stany (liczba · `n/a` · `BLOCKED`), ma
nagłówek maszynowy, Krok 00, higienę repo, aktualność runtime'ów i tryb
`CROSSDESK_AUDIT_DRYRUN=1`. Decyzja: DEC-META-009.

Pierwszy przebieg nowej metody znalazł: P0 `pre-push` potwierdzony lekturą
(`:222-228` skanuje dysk, nie commit), nowy P1 (`:323` myli awarię `cd`
ze znaleziskiem, przez co bramka jest niemierzalna), rozjazd
`requires-python 3.9` vs CI 3.12, oraz nieprzenośny `find -printf` w samym
masterze toolkitu (zgłoszone, nie łatane lokalnie).
