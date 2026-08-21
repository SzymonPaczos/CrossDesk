# CLAUDE.md

Auto-load list for Claude Code sessions in CrossDesk. The canonical
source of project knowledge is [AGENTS.md](AGENTS.md) — that's the
human-readable navigation map and coding ruleset, referenced from
README.md. This file just tells the agent harness which rule files to
load.

## Load these files

- @PLAN.md — **jedyny board „co dalej" do v0.1.0** (TERAZ / NEXT /
  LATER + 12 kryteriów akceptacji). Zaczynaj tu.
- @AGENTS.md — project navigation, coding rules, agent workflow,
  file boundaries.
- @.claude/rules/general.md — universal prohibitions, commit
  conventions, branch-per-agent rule, coordination protocol.
- @.claude/rules/backend.md — Python (host) + Rust (guest)
  path-specific rules.
- @.claude/rules/audit.md — **nakładka** CrossDeska na audyt: konkretyzacja
  punktów 1–26 z `.claude/skills/weekly-audit/references/kontrola-glebokosci.md`
  (ścieżki, grepy, wyjątki, P0/P1/P2). Sama procedura żyje w skillu.
- @.claude/rules/quality-gates-and-dod.md — katalog bramek, tryby, odstępstwa
  i definicja ukończenia. Kopia z claude-toolkit (adopcja 2026-08-21).
- @.claude/rules/test-evidence.md — co dowodzi pojedynczy test: cofnij naprawę,
  test MUSI zrobić się czerwony. Kopia z claude-toolkit (adopcja 2026-08-21).
- @.claude/rules/decisions.md — META-decyzje (proces / workflow /
  layout); ADR `DEC-NNNN` żyją w `docs/DECISIONS.md`.
- @.claude/rules/ci-cd.md — baseline CI/CD i supply chain (SHA-pinning,
  permissions, lockfile, release provenance). Kopia z claude-toolkit
  (adopcja 2026-07-12, DEC-META-008).
- @.claude/rules/rules-as-gates.md — zamiana powtarzalnie łamanych reguł
  w mechaniczne gate'y (report-mode → blokada).
- @.claude/rules/change-provenance.md — ślad intencji w commicie
  (`Intent` / `Task-Ref` / `Gates`, tryb raportowy WARN); bez atrybucji
  AI (D-006). Szablon: `.gitmessage`.
- @.claude/architecture.md — stack snapshot (timestamp bumped by
  pre-commit hook so it lands in the commit, not as drift).
- @.claude/ignorefiles.md — dead code / generated artifacts manifest.
- @.claude/backlog.md — post-MVP / parking (NIE board MVP — to jest
  PLAN.md). Długi ogon + kontekst techniczny.
- @.claude/status.md — bieżące breakages / partial implementations.
- @.claude/needs-owner.md — zaparkowane decyzje właściciela + drafty
  boundary (czeka na podpis).

WORK_LOG.md ceremony jest **wycofany** (2026-07-05) — nie ładuj, nie
dopisuj START/END. Historia: `git log` + `history/completed-work.md`.

## Audit reminder

Sprawdź `.claude/audit-log.md` przy starcie sesji — jeśli ostatni wpis
`## Audyt YYYY-MM-DD` jest >7 dni, zaproponuj cotygodniowy audyt: skill
`weekly-audit` (procedura), `.claude/rules/audit.md` (nakładka CrossDeska).
Ten sam preflight, w trybie raportowym, siedzi w `.githooks/pre-push`.
**Krok 00 audytu wyprzedza wszystko** — `toolkit-sync.sh check .` zanim
spojrzysz na kod; audyt na nieaktualnej checkliście melduje „czysto".

## One-time setup per clone

Hooks live under `.githooks/` and need activation after `git clone`:

```sh
chmod +x .githooks/pre-commit .githooks/pre-push .githooks/post-commit .githooks/commit-msg
git config core.hooksPath .githooks
git config commit.template .gitmessage
```

The `core.hooksPath` and `commit.template` settings are per-clone (they
live in `.git/config`, not tracked) — re-run after every fresh clone.

## Kopie audytowe — NIE ładuj do sesji

Kopie masterów toolkitu czytane **tylko podczas audytu** (i przy pracy nad
bramkami). Trzymanie ich poza load-listą jest świadome: ~1300 linii w każdym
kontekście sesji to koszt bez pokrycia, skoro konsumentem jest jeden skill.

- `.claude/skills/weekly-audit/` — procedura (Kroki 00–5) + `references/`
  z 25 punktami kontroli głębokiej. Wejście: skill `weekly-audit`.
- `.claude/skills/audyt-naprawczy/` — ten sam protokół **zakończony naprawą**
  klas dowodliwych bramką (commit na klasę, gałąź `audyt/RRRR-MM-DD`).
  Uruchamiaj **tylko** na wyraźne „audyt z naprawą". W CrossDesku obowiązują
  odstępstwa z `rules/audit.md` — najważniejsze: **boundary files są wyłączone
  z automatu, także z naprawy zepsutych odsyłaczy**.
- `.claude/rules/multi-agent-delivery.md` + `.claude/agents/` (Security
  Reviewer, Red Team) — pełny kontrakt zespołu multi-agent jest NIEaktywny
  (solo owner + jeden agent, DEC-META-008).
- `.claude/rules/security-verification-gates.md` — które skanery blokują
  merge, a które tylko raportują (punkt 21).
- `.claude/rules/ci-pipeline-architecture.md` — topologia bramek; CrossDesk
  czyta ją przez **§11a** (profil local-first/hybrydowy), punkt 24.
- `.claude/rules/repo-hygiene-gates.md` — mechaniczne sygnały higieny repo
  i ekspozycji na utratę danych (punkt 14).
- `.claude/rules/dependency-currency.md` — dystans do bieżących wersji i EOL
  runtime'ów (punkt 15). **Runtime po EOL = P0.**
- `.claude/rules/pull-request-review.md` — punkt 23. CrossDesk merguje lokalnie
  bez PR-ów; czytane przez odpowiedniki (merge + trailer `Gates:`).
- `.claude/rules/issue-reporting.md` — punkt 25; wymóg reprodukcji stosuje się
  do wpisów w `backlog.md` / `status.md`.
- `.claude/templates/` — `audit-log-entry.md` (wzorzec wpisu),
  `test-gates.sh` (dowód, że bramka BLOKUJE), `dependency-currency.sh`.

## Synchronizacja z masterem

Kopie toolkitu są stemplowane w `.claude/toolkit.lock`; świadome odstępstwa
(dziś: sekcja projektowa w `agents/security-reviewer.md`) w
`.claude/toolkit.local`. **Krok 00 każdego audytu:**

```sh
bash ../claude-toolkit/scripts/toolkit-sync.sh check .
```

Błędu w regule nie łataj w kopii — poprawka idzie do mastera i wraca przez
`update`.

## Why this layout

`AGENTS.md` is the entry point for human contributors and is referenced
from `README.md`. Rather than duplicate its contents into a separate
`CLAUDE.md`, this file is a thin shim that delegates. The
`.claude/rules/*` files are stack-agnostic guardrails extracted from
`universals.md` (kept in the repo as a reference template); they're
intentionally short so an agent can load them every session without
ceremony.
