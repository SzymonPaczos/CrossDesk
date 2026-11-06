# CrossDesk — audyt bezpieczeństwa 2026-11-06

Źródła: [`d761d6805be6e70a9a23b0276fad16b1b6e6c969`](https://github.com/SzymonPaczos/CrossDesk/tree/d761d6805be6e70a9a23b0276fad16b1b6e6c969).

Raport obejmuje metadane zależności oraz ograniczone testy offline. Nie potwierdza odporności całej aplikacji na ataki; nie wykonywano napraw automatycznych.

## Wyniki

- OSV: **307/307** dokładnych wersji publicznych pakietów crates.io sprawdzonych; **6** wersji z ostrzeżeniami; **8** problemów po połączeniu aliasów.
- CISA KEV: **0** dopasowań aliasów CVE. Oficjalny katalog `2026.11.04`, publikacja `2026-11-04T20:00:05.774Z`; pobrano `2026-11-06T00:51:32.921137+00:00`. Brak dopasowania nie oznacza bezpieczeństwa.
- Testy wybrane: **94 PASS**, exit 0. Pełny zestaw: **BLOCKED**, exit 1, trzy błędy kolekcji; brak `structlog`. W obrazie brak też `pytest_asyncio`.
- Wybrane pliki: `test_atomic_write.py`, `test_mime.py`, `test_domain_xml.py`, `test_version_negotiation.py`, `test_config_peripherals.py`, `test_drive_map.py`.
- Semgrep: 0 trafień i 0 błędów, wyłącznie dwie lokalne reguły Pythona: `shell=True` oraz `eval/exec`. Brak Rust SAST.

## Zależności wymagające przeglądu

| Wersje z locka | Klasyfikacja | Ostrzeżenie / granice poprawki OSV |
|---|---|---|
| `rustls@0.23.40` | active-security-advisory | [GHSA-2mjx-qc3c-rqvc](https://osv.dev/vulnerability/GHSA-2mjx-qc3c-rqvc), [RUSTSEC-2026-0285](https://osv.dev/vulnerability/RUSTSEC-2026-0285); `rustls@0.23.45` |
| `rustls@0.23.40` | active-security-advisory | [GHSA-c8m5-c952-6cm4](https://osv.dev/vulnerability/GHSA-c8m5-c952-6cm4), [RUSTSEC-2026-0346](https://osv.dev/vulnerability/RUSTSEC-2026-0346); `rustls@0.23.46`, `rustls@0.24.0-dev.2` |
| `rustls@0.23.40` | active-security-advisory | [GHSA-h2v8-394m-p7vv](https://osv.dev/vulnerability/GHSA-h2v8-394m-p7vv), [RUSTSEC-2026-0348](https://osv.dev/vulnerability/RUSTSEC-2026-0348); `rustls@0.23.46`, `rustls@0.24.0-dev.2` |
| `rustls@0.23.40` | active-security-advisory | [GHSA-w44r-93j7-qv28](https://osv.dev/vulnerability/GHSA-w44r-93j7-qv28), [RUSTSEC-2026-0349](https://osv.dev/vulnerability/RUSTSEC-2026-0349); `rustls@0.23.46`, `rustls@0.24.0-dev.2` |
| `rustls-pemfile@2.2.0` | unmaintained | [RUSTSEC-2025-0134](https://osv.dev/vulnerability/RUSTSEC-2025-0134); brak opublikowanej granicy poprawki |
| `cxx@1.0.194` | unsound | [RUSTSEC-2026-0202](https://osv.dev/vulnerability/RUSTSEC-2026-0202); `cxx@1.0.195` |
| `rustls-webpki@0.103.13` | active-security-advisory | [RUSTSEC-2026-0382](https://osv.dev/vulnerability/RUSTSEC-2026-0382); `rustls-webpki@0.103.16`, `rustls-webpki@0.104.0-alpha.8` |
| `tokio@1.52.3`, `tokio@1.53.0` | unsound | [RUSTSEC-2026-0386](https://osv.dev/vulnerability/RUSTSEC-2026-0386); `tokio@1.51.6`, `tokio@1.53.3` |

Granice poprawek pochodzą z zakresów OSV, mogą obejmować różne gałęzie wydań i nie stanowią automatycznej rekomendacji zmiany API. `unsound` oznacza problem poprawności/pamięci, nie należy utożsamiać go ze zwykłym komunikatem o braku utrzymania.

## Kandydaci skanera sekretów

Gitleaks: **1** kandydatów `generic-api-key`, exit 1. Przejrzano konteksty po redakcji. Nie potwierdzono działających danych uwierzytelniających. Nie zastosowano wyciszeń ani baseline. Wartości nie są publikowane.

- `.claude/templates/test-gates.sh:107`, historyczny commit `8c173e01b57f4edcbec661df7003dc24767ace01`: test-gate template/example assignment; credential status unverified; owner triage pending.

## Proponowane zadania do backlogu

Poniższe zadania są propozycjami do scalenia z istniejącym backlogiem według zakresu i identyfikatorów ostrzeżeń. Daty oznaczają proponowany ponowny przegląd; nie oznaczają wykonanej naprawy.

### AUDIT-20261106-TLS: Remediate the locked Rust TLS advisories

Priorytet: **high**. Przegląd: **2026-11-07**.

Review dependency compatibility and upgrade the relevant graph; OSV lists stable fixed boundaries rustls 0.23.46 and rustls-webpki 0.103.16. Do not blindly force transitive versions.

**Brama zamknięcia:** Exact-version OSV recheck excludes the four rustls issue groups and RUSTSEC-2026-0382; guest build/tests and TLS rejection/handshake/session regression evidence on supported targets; reviewer checks actual enabled features and attack surfaces.

### AUDIT-20261106-SOUNDNESS: Resolve cxx and tokio soundness advisories

Priorytet: **high**. Przegląd: **2026-11-07**.

Review RUSTSEC-2026-0202 and RUSTSEC-2026-0386; OSV fixed boundaries include cxx 1.0.195 and tokio 1.53.3 (also an older tokio maintenance branch). Establish API/feature applicability before updating.

**Brama zamknięcia:** Locked graph no longer matches those advisory IDs, supported-target build/tests pass, and reviewer records affected FFI exception/I/O-safety reachability.

### AUDIT-20261106-MAINTENANCE: Replace or explicitly review unmaintained rustls-pemfile

Priorytet: **medium**. Przegląd: **2026-11-13**.

Review RUSTSEC-2025-0134 and choose a supported PEM API or a time-bounded owner decision with replacement plan.

**Brama zamknięcia:** Dependency removed/replaced with regression coverage for PEM parsing, or explicit dated owner risk review; no blanket advisory suppression.

### AUDIT-20261106-FULL-EVIDENCE: Produce exact Python dependency inventory and complete Linux test evidence

Priorytet: **high**. Przegląd: **2026-11-07**.

Create/review reproducible exact Python dependency inventory in the normal development workflow; rerun the complete host suite with required dependencies/plugins. Obtain real guest/GUI Rust build/test evidence on supported targets.

**Brama zamknięcia:** Full host collection and required tests pass, missing dependencies/plugins are resolved in a reviewed environment, exact Python versions are scanned, and Rust evidence is actual execution rather than metadata or mocks. Preserve the current partial result until replaced.

### AUDIT-20261106-SECRET-TRIAGE: Close the historical gate-template secret-pattern candidate

Priorytet: **medium**. Przegląd: **2026-11-13**.

Owner reviews the redacted historical candidate and template purpose; determine whether it is an intentional example or any credential ever had a usable scope. No value is published.

**Brama zamknięcia:** Documented non-credential/test-example rationale, or credential revocation/rotation plus exposure review if confirmed; rerun the detector without silently dropping the finding.

## Dowody i ograniczenia

- Szczegóły, dokładne lock SHA256, per-package wyniki i hashe logów: [2026-11-06-security-audit.json](2026-11-06-security-audit.json).
- Testy: kontener offline, źródła tylko do odczytu, UID 65534, odebrane wszystkie capabilities, no-new-privileges, 2 CPU, 2 GiB RAM bez dodatkowego swap, 64 PID, 512 MiB tmpfs, limit pliku 8 MiB i czasu CPU 180 s. Kontenery usunięto przed promocją dowodów.
- Obraz: `sha256:7f1b0a1a50cfbac23da3b16f96bc968fd757b26dc9e54e93813d61768ea9184e`.
- Pliki audytu/metadanych nałożone na kopię testową mają osobne hashe w JSON; nie są przedstawiane jako część zamrożonego commitu.

- OSV matches exact locked package versions; it does not establish runtime reachability, active features or application exploitability.
- Identifiers and aliases are deduplicated into advisory groups. Unmaintained and unsound notices remain separately labelled; counts of classification labels can overlap.
- No application attacks or exploit attempts were run. No external model calls were made. No dependencies were installed and no images were pulled.
- Workspace/git/unknown-source packages are unverified, not counted as clean. No real Rust build or Rust tests were run: the cached image has no cargo/rustc.
- No values from secret-pattern findings, email addresses, transcripts or host-specific paths are included.
- Only the selected 94 synchronous tests passed. The full host run stopped after 3 collection errors; structlog was missing. Cached pytest_asyncio was absent too.
- Python host dependencies are ranges in pyproject.toml, without an exact reviewed application lock inventory; Python SCA is not covered.
- No live libvirt/dbus/boot services were started. No guest/GUI Rust compilation or Windows-target validation was performed.
- An unrelated 10,098,915-byte third-party documentation GIF was excluded to respect the 8 MiB per-file limit; the tracked host/LICENSE symlink was excluded.

Źródła oficjalne: [OSV API](https://google.github.io/osv.dev/post-v1-querybatch/), [katalog CISA KEV — oficjalne repozytorium](https://raw.githubusercontent.com/cisagov/kev-data/main/known_exploited_vulnerabilities.json). Zapytania OSV: `2026-11-06T00:51:29.161745+00:00` → `2026-11-06T00:51:32.945143+00:00`.
