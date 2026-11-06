# WORK_GRAPH — <nazwa zadania>

**Task-Id:** <slug>
**Coordinator:** <run/osoba>
**Evidence sink:** <PR + required check | `.claude/reviews/<sha>.md`>
**Repair loops:** maksymalnie 2, potem `BLOCKED` i decyzja właściciela
**Exit condition:** <co dokładnie kończy ten graf>
**Integration owner:** <rola odbierająca wyniki i sprzątająca po merge>

Zapisany graf jest kontraktem, nie notatką. Zakresy Builderów muszą być
rozłączne; wspólny plik ma dokładnie jednego właściciela.

## Nody

### <id-noda>

- **owner_role:** Builder | Scout | Reviewer | Security Reviewer
- **scope:** <konkretne ścieżki; wypisz też, czego node NIE dotyka>
- **inputs:** <pliki, dowody Scouta, decyzje>
- **acceptance:** <sprawdzalny warunek, nie „działa">
- **gates:** <komendy, które muszą przejść>
- **depends_on:** <id innych nodów | brak>
- **risk_triggers:** <co wymusza Security Reviewera: auth, sekrety, migracje,
  parsery niezaufanych danych, workflowy, release>
- **branch:** `<typ>/<slug>`
- **worktree:** <ścieżka osobnego worktree, jeśli równolegle>
- **review_of / review_sha:** <dla ról oceniających: odebrany Builder albo pełny SHA>

ID rzeczywistego uruchomienia, uchwyt wyniku i stan wykonawcy należą do
runtime ledgeru. Przydział w tym planie nie potwierdza uruchomienia roli.
Rejestruj natywny task ID per worker oraz osobno wynik gotowy/odebrany.
Wykonawczy plan JSON, receipts, zdarzenia i cleanup opisuje
[`agent-runtime/README.md`](agent-runtime/README.md). Wybrany plan jest
kanoniczny w swoim zakresie; drugi format odsyła do niego zamiast kopiować stan.

### <id-noda-owner-gate>

Nody wymagające działania właściciela oznacz jawnie — agent ich nie wykona
i nie wolno mu ich raportować jako zrobione.

- **owner_role:** właściciel (poza zakresem sesji agenta)
- **acceptance:** <np. weryfikacja na fizycznym sprzęcie, zgoda na produkcję>

## Kolejność merge

<lista nodów w kolejności; wskaż, co blokuje co>

## Po integracji

Po merge integrator sprawdza listę worktree i raportuje
`POST_INTEGRATION: removed <n> | kept <powód, następny krok>`.
Brudne, zajęte i zablokowane checkouty pozostają; push/PR nie zastępuje merge.

## Czego ten graf świadomie nie obejmuje

<non-goals — chroni przed scope creepem w trakcie>
