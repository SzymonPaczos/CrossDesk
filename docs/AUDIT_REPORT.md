# Code-quality audit — 2026-05-09

Comprehensive sweep of the v0.1.0 + v1.0 codebase using a stack of
open-source scanners. Run captured here so the next round can diff
against it.

## Stack

| Layer | Tool | Verdict |
|---|---|---|
| Secret detection | `gitleaks` (worktree + git history) | ✅ no leaks in tracked files |
| Python deps CVE | `pip-audit` | ✅ 0 vulns |
| Rust deps CVE (guest) | `cargo audit` | ✅ 0 vulns, 1 unmaintained |
| Rust deps CVE (gui) | `cargo audit` | ✅ 0 vulns, 0 warnings |
| Python security lint | `bandit -ll` | ✅ 0 medium/high findings |
| Multi-lang static | `semgrep --config=auto` | ⚠️ 1 medium (subprocess in launch-vm.py) + 8 expected `unsafe` markers |
| Python lint extra | `ruff S,B,RUF,SIM,UP,N,A,C4,T20,PT` | ⚠️ 873 raw → ~30 actionable |
| Dead code | `vulture` | ✅ ~3 false positives only |
| Docstring coverage | `interrogate` | ⚠️ 40.5% (target: 60%+) |
| Rust unused deps | `cargo machete` | ⚠️ 11 reports, ~3 actionable |
| License compliance | `cargo deny` (no config) | ⚠️ needs deny.toml; package crates missing `license` field |
| Shell quality | `shellcheck` | ⚠️ 2 minor (SC1091/SC2240 in pre-commit) |
| GitHub Actions | `actionlint` | ✅ clean |
| LoC stats | `tokei` | ℹ️ 27,252 lines of code |

## Stats (`tokei`)

| Language | Files | Code | Comments | Blanks |
|---|--:|--:|--:|--:|
| Python | 155 | 14,236 | 557 | 2,826 |
| Rust | 46 | 2,358 | 149 | 383 |
| QML | 16 | 1,109 | 28 | 154 |
| Shell | 4 | 1,260 | 626 | 420 |
| BASH | 1 | 732 | 185 | 118 |
| Protocol Buffers | 5 | 527 | 269 | 108 |
| TOML | 15 | 559 | 77 | 79 |
| Markdown | 37 | (10,078 lines docs) | — | — |
| **TOTAL (excl docs)** | — | **~27,252** | **~2,800** | **~7,100** |

Coverage on the Python side is **75%** per `pytest --cov`; Rust unit
tests run ~50 cases across the workspace.

---

## Critical findings (act before v1.0)

### 1. `cargo deny` needs a config file

Without `deny.toml` the default policy rejects every license including
ours, producing 198 false-positive errors. Real findings buried in the
noise:

- **Our internal crates lack a `license` field** in their
  `Cargo.toml` files (8 crates: agent-svc, fs-mount, ipc-vsock,
  observability, proto, rail-bridge, registry-scan, xtask). The
  workspace declares `GPL-3.0-or-later` but per-crate manifests
  don't inherit. **Fix:** add `license.workspace = true` to each
  crate's `[package]` table, plus `license = "GPL-3.0-or-later"` to
  `[workspace.package]`.
- **Duplicate dep versions**: 9 different crates have multiple
  versions in the dep tree (windows-sys 2-3 versions, wit-bindgen
  ×2, several windows_x86_64_*, etc). These are typically third-
  party transitive issues; tracking but not blocking.

**Action:** add `deny.toml` allowlisting our license set
(GPL-3.0-or-later for first-party + MIT/Apache-2.0/BSD-3 for deps),
add per-crate `license` fields. The current cargo-deny output is
unusable without this.

### 2. `rustls-pemfile` flagged unmaintained (RUSTSEC-2025-0134)

Pulled in transitively via `tonic v0.12.3`. Upstream archived the
crate; users should migrate to `rustls-pki-types` `PemObject` API.

**Action:** wait for `tonic` to update — they own the dep. Add
`#[allow]` in `cargo audit` config OR pin a workaround. No CVE,
just a maintenance flag.

### 3. Docstring coverage 40.5% (interrogate)

Target threshold (interrogate's default) is 80%. Below-average
modules:

| Module | Coverage | Notes |
|---|--:|---|
| `watchdog/fsm.py` | 19% | The Phase 3 SPOF module — needs dosctrings for every state |
| `watchdog/ewma.py` | 29% | Pure helpers; docstrings missing |
| `recovery/snapshot.py` | 50% | Phase 9 module |
| `mgmt_pb2_grpc.py` | 56% | Auto-generated; ignore |

**Action:** docstring sweep across Phase 3 + Phase 9 modules. ~2 hours.

### 4. `infra/launch-vm.py` subprocess flagged (semgrep)

`subprocess.run(cmd, check=True)` where `cmd` is built from various
paths. Not actually dangerous (the script is dev-only and `cmd`
is composed from CLI args + hardcoded binary names), but worth
acknowledging with a `# noqa: S603` comment + brief justification.

---

## Tier 2 — actionable lint (≈30 fixes, ~1 hour)

### `print()` usage outside CLI (ruff T201, 27 findings)

Most are in `cli/*_cmd.py` files where `print()` is the legitimate
user-facing output. Three options:

1. Add `# noqa: T201` per-line where intentional.
2. Mark whole CLI module as exempt via `[tool.ruff.lint.per-file-ignores]`
   (cleanest):
   ```toml
   "src/crossdesk_host/cli/*_cmd.py" = ["T201"]
   ```
3. Switch CLI to a logger or `click.echo`.

**Recommendation:** option 2 — CLI is the canonical place for stdout.

### `try/except/pass` instead of `contextlib.suppress` (SIM105, 12)

Mostly in cleanup paths:

```python
try:
    os.unlink(tmp)
except OSError:
    pass
```

→

```python
with contextlib.suppress(OSError):
    os.unlink(tmp)
```

Cosmetic, no behaviour change.

### `pytest.raises(Exception)` too broad (PT011, 12 + B017, 4)

Tests that expect any exception. Tighten to specific types
(`ValueError`, `OSError`, etc) so a regression that throws the wrong
exception fails the test loudly.

Files: `test_credentials.py`, `test_install_state_concurrency.py`,
`test_iso_downloader_edges.py`, `test_hidpi.py`,
`test_install_state.py`, `test_iso_downloader_edges.py`.

### `subprocess` partial path (S607, 3) — accepted

`subprocess.run(["xdg-mime", ...], ...)` — partial path is
intentional (we want the binary from PATH). Add `# noqa: S607`
with rationale.

### Generator naming (N802, 3) — accepted

`OpenSession`, `Channel`, `ShareChannel` etc are gRPC servicer
methods; the proto generator dictates the name. Add per-file
`N802` ignore for `crossdesk_host/ipc/*.py`.

### `__all__` not sorted (RUF022, 3) — auto-fix available

Run `ruff check --fix --select=RUF022`.

### Single `try/except: pass` (S110, 1) in `gnome.py:86`

```python
try:
    item.delete()
except Exception:
    pass
```

Real finding — should at least log the exception so a misbehaving
keyring doesn't fail silently.

**Action:** wrap in `logger.warning("gnome_keyring_delete_failed", error=str(exc))`.

---

## Tier 3 — nice-to-have, lower priority

### Unused deps (`cargo machete`, ~3 actionable)

True positives:

| Crate | Deps |
|---|---|
| `registry-scan` | `anyhow`, `tracing` (Phase 8 stub doesn't use them yet) |
| `agent-svc` | `tracing-subscriber` (only main.rs uses; check if dev-only) |
| `observability` | `serde` (declared but unused) |

**Action:** drop `anyhow` + `tracing` from `registry-scan` until Phase 8
Week 34 wires the windows walker. Cosmetic.

### Vulture dead code (3 real, ~10 false positives)

Real:
- `iso_downloader.py:50: unused variable 'dest'` — Protocol method
  parameter; vulture confused. False positive.
- `management.py:182: unsatisfiable 'if False:'` — typing hack to
  make method a generator. Could be cleaner with `cast(...)`.
- `libvirt_ctl/real.py:14: unused TYPE_CHECKING import` — false
  positive.

Action: skip; vulture's false-positive rate is high in proto-heavy
codebases.

### Shellcheck (2 minor in pre-commit)

```
.githooks/pre-commit:14: SC1091/SC2240 — nvm.sh sourcing
```

Not blocking; the comment in the hook explains why we tolerate
sourcing without `-x` introspection.

---

## Tier 4 — docs gap-fill (Phase 9 polish)

Beyond the docstring coverage already noted:

- Add module-level docstrings to `watchdog/__init__.py` and
  `recovery/__init__.py` exports (already covered, double-check).
- Document the proto-to-Python type mapping for the new mgmt RPCs;
  GUI client developers will read this first.

---

## Recommended fix queue (priority-ordered)

1. **Add `license.workspace` to all guest + gui crate manifests** (5 min)
2. **`per-file-ignores` for CLI T201 + IPC N802** (5 min)
3. **`gnome.py:86` log instead of swallow** (3 min)
4. **Tighten `pytest.raises(Exception)` to specific types** (~30 min)
5. **Auto-fix RUF022 `__all__` sort** (`ruff check --fix`)
6. **Drop unused `anyhow`/`tracing` from `registry-scan`** (2 min)
7. **`# noqa: S607`/`S603` annotations with rationale** (10 min)
8. **Docstring sweep on `watchdog/fsm.py` + `watchdog/ewma.py`** (~1 h)
9. **`deny.toml` config + per-crate `license` fields** (15 min)
10. **`SIM105` cleanup (12 cases)** (~10 min)

Estimated total to land everything actionable: ~3 hours.

## How to re-run

```bash
# Security tier
gitleaks detect --source .
cd guest && cargo audit && cd ../gui && cargo audit
pip-audit -r <(host/.venv/bin/pip freeze | grep -v '^-e ')
$HOME/.local/bin/bandit -r host/src/crossdesk_host -ll
semgrep --config=p/security-audit --config=p/python --config=p/rust .

# Quality tier
host/.venv/bin/python -m ruff check --select=S,B,RUF,SIM,UP,N,A,C4,T20,PT host/src host/tests
$HOME/.local/bin/vulture host/src --min-confidence 80
$HOME/.local/bin/interrogate -v host/src

# Stats
tokei . -e third_party -e gui/target -e guest/target -e host/.venv

# Rust deeper
cd guest && cargo machete && cargo deny check
```
