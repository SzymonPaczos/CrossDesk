# Completed work — archiwum

Append-only. Najnowsze na górze. Granular `WORK_LOG.md` zostaje w
roocie — tutaj trafia tylko streszczenie tematów po zamknięciu fazy
/ większego bloku prac.

Pełna granularność per-commit START/END — `WORK_LOG.md` "Recent".
Per-task plik raportu sesji — `.claude/history/YYYY-MM-DD-temat.md`.

## Audytowe sweepy

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

## Migracja FOLLOWUPS → backlog

- **2026-05-23** — Fold FOLLOWUPS.md (1260 linii) w `.claude/backlog.md`.
  Archiwum oryginalnego pliku:
  [2026-05-23-followups-archive.md](2026-05-23-followups-archive.md).
  Decyzja w `.claude/rules/decisions.md` DEC-META-001.
