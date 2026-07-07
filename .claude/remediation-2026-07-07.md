# Remediation plan — 2026-07-07 audit (0 P0 / 5 P1 / 14 P2)

Planned by Fable 2026-07-07. Source: `.claude/audit-log.md` §"Warstwa głęboka
(agent, 2026-07-07)". Every finding re-verified against the current tree
(`main` @ f6a8574) before planning; corrections vs the audit text are marked
**[CORRECTED]**. Executor: the autonomous loop (Opus, box autonomy, PUSH=ON).

**Hard constraints (apply to every branch):**
- Sole author Szymon Paczos. **NO Co-Authored-By trailer** (standing owner
  decision; history was just rewritten to enforce it).
- Branch from freshly-rebased `main`; ONE concern per branch; Conventional
  Commits; `git merge --no-ff` on green gates; never `--no-verify`; never
  force-push `main`.
- Boundary files (AGENTS.md, REQUIREMENTS.md, DECISIONS.md, THREAT_MODEL.md,
  MVP_SCOPE.md, GOALS.md, ROADMAP.md, proto/**) are owner-only → drafts go to
  `.claude/needs-owner.md`, never applied.
- Host gates: `cd host && black --check src tests && ruff check src && mypy
  --strict src && pytest -q` all green. Rust branches: `cargo check` +
  clippy-clean. Tests hermetic: no real `$HOME`, no network, no real libvirt
  (autouse guard `13c765f` stays green), `tmp_path`/`monkeypatch` only.
- Secrets-at-rest: create at 0600 via `os.open(..., O_CREAT|O_WRONLY|O_TRUNC,
  0o600)` — never write-then-chmod.

---

## 1. Triage (19 findings)

| # | Finding | Verified state | Bucket |
|---|---------|----------------|--------|
| P1-1 | [SEC] VM RDP password plaintext in daemon log | CONFIRMED — `freerdp/real.py:133` logs full argv; `/p:` from `rail_command.py:139`; `redaction.py` value-blind. **Widened:** `observability/log.py` `_RotatingFileWriter` opens the JSONL log 0644 (init `:52` + `_rotate` `:81`); per-app capture logs (`real.py:143`) also 0644 | **A** → branch 1 |
| P1-2 | [SEC] `autounattend.prepared.xml` world-readable with real password | CONFIRMED — `cli/install_cmd.py:230-231` `write_text()` | **A** → branch 2 |
| P1-3 | [SEC] Blocking libvirt calls on asyncio loop, no deadline | CONFIRMED — `ipc/control.py:220-221`, `ipc/heartbeat.py:270,274` (dispatch at `:350`). **[CORRECTED — surface wider]:** also `ipc/management.py:527,546,562` and `ipc/filesystem.py:110,163` are servicer-reachable. `lifecycle/coordinator.py:139,162` blocks too but is not servicer-driven → parked (C-3) | **A** → branch 3 |
| P1-4 | [SLOP] Daemon never logs selected libvirt backend | CONFIRMED — `daemon.py:132-138`, zero log lines | **A** → branch 4 |
| P1-5 | [TEST] mock→`on_session_ready=None` guard untested | CONFIRMED — `daemon.py:184-189`, inline in `main()`, only `test_daemon_suspend_guard.py` touches daemon | **A** → branch 4 |
| P2-1 | [SEC] PKI key write-then-chmod race | CONFIRMED — `installer/pki.py:76-84` `_write_key` | **A** → branch 2 |
| P2-2 | [SEC] guest `icon_png` written unvalidated | CONFIRMED — `display/window_icon.py` `offer()` checks emptiness only | **A** → branch 5 |
| P2-3 | [SEC] `linux-kvm-smoke` label-gated, not same-repo-gated | CONFIRMED — `.github/workflows/ci.yml:310` | **A** → branch 6 |
| P2-4 | [SEC] PKGBUILD `sha256sums=('SKIP')` | CONFIRMED — `packaging/aur/PKGBUILD:35`. No release tarball exists yet to pin against | **C-1** |
| P2-5 | [SLOP] stale ignorefiles.md: `DBusNotifier._send_sync` "no-op" | CONFIRMED stale — `_send_sync` schedules a real `_send_async` dbus-next call | **A** → branch 9 |
| P2-6 | [SLOP] `installer/drive_map.py` 0 prod callers, unregistered | CONFIRMED — only `tests/test_drive_map.py` imports it | **A** → branch 9 |
| P2-7 | [SLOP] PLAN.md #10 + backlog.md claim `--force`/confirm missing | CONFIRMED drift — shipped in `cli/uninstall_cmd.py:29-56` (confirm prompt, EOF-safe, `--force`) | **A** → branch 9 |
| P2-8 | [TEST] no marker-gated integration test for `RealLibvirtController` destructive paths | CONFIRMED — `test_libvirt_real.py` covers only pure `_with_domain_uuid` | **C-2** |
| P2-9 | [ARCH] architecture.md omits `bind_kind` seam | CONFIRMED — "Transport: gRPC over AF_VSOCK…" no seam mention; loop-editable | **A** → branch 9 |
| P2-10 | [ARCH] AGENTS.md "22 subpackages" vs actual | CONFIRMED — actual count 20 (21 dirs minus `__pycache__`). Boundary file | **B-1** — ✅ owner-signed + APPLIED 2026-07-07 |
| P2-11 | [ARCH] REQUIREMENTS.md missing `bind_kind`/`libvirt.backend`/`shared_folder_*` | CONFIRMED — zero grep hits. Boundary file | **B-2** — ✅ owner-signed + APPLIED 2026-07-07 (markers: all 🔄) |
| P2-12 | [ARCH] `uninstall.py:111-115` re-derives state/config dirs | CONFIRMED — `uninstall.py:98-123` hardcodes 4 paths; canonical derivations live in `config/__init__.py:58-67` (private, zero-arg) + `installer/state.py:31-35` (own copy) | **A** → branch 8 |
| P2-13 | [ARCH] two `i18n:` commits off-convention | CONFIRMED historical (`d4da63f`, `9575347`, `df17a0b i18n(pl):`); `scripts/i18n.sh` does NOT generate subjects | **D-1** |
| P2-14 | [DEPS] stale ignore RUSTSEC-2026-0202 in `gui/.cargo/audit.toml` | **[CORRECTED]** — ran `cargo deny check advisories` in `gui/`: the unmatched ignore is **RUSTSEC-2025-0134** (rustls-pemfile; gui has no tonic → 0 lockfile hits). **RUSTSEC-2026-0202 is ACTIVE and must stay** (cxx 1.0.194 in `gui/Cargo.lock`). Guest keeps 0134 (rustls-pemfile ×2 in its lockfile) | **A** → branch 7 |

Bucket counts: **A = 14 findings / 9 branches · B = 2 · C = 2 (+1 planning
addendum) · D = 1.**

---

## 2. Execution plan — ordered branches (bucket A)

Order: security first (1→2→3), then the pre-live-verify daemon work (4), then
remaining code (5→8), docs last (9). All branches are independent (no shared
files) — the loop may run them strictly in this order, one merge each.

### Branch 1 — `fix/rdp-secret-logging` (closes P1-1)

The active leak: every managed launch on the live box writes the VM RDP
password into a 0644 log.

**Edits:**
1. `host/src/crossdesk_host/observability/redaction.py`
   - Add:
     ```python
     _ARGV_SECRET_FLAGS = ("/p:", "/pth:")
     _ARGV_REDACTED = "<redacted>"

     def redact_secret_flags(argv: Sequence[str]) -> list[str]:
         """Mask FreeRDP credential flag values (/p: password, /pth:
         pass-the-hash) in an argv, element-wise."""
         out: list[str] = []
         for arg in argv:
             for flag in _ARGV_SECRET_FLAGS:
                 if arg.startswith(flag):
                     arg = flag + _ARGV_REDACTED
                     break
             out.append(arg)
         return out
     ```
     (import `Sequence` from `typing`; export via `observability/__init__.py`
     alongside `mask_sensitive`.)
   - Append to `_FORBIDDEN_PATTERNS` (backstop — catches any FUTURE call site
     that logs a raw argv; negative lookahead so the redacted form passes):
     ```python
     r"/p:(?!<redacted>)\S",
     r"/pth:(?!<redacted>)\S",
     ```
     This also closes the `mask_sensitive` gap (crash reporter): a traceback
     line containing `/p:hunter2` now masks whole-line.
2. `host/src/crossdesk_host/freerdp/real.py:133` — log the redacted argv:
   ```python
   logger.info(
       "spawning FreeRDP RAIL session: %s",
       " ".join(redact_secret_flags(full_argv)),
   )
   ```
   (`RailSession.argv` keeps the real argv in memory — needed by the spawn;
   verified nothing else logs it: no `session.argv` log sites in
   rail_supervisor/rail_manager/management.)
3. `host/src/crossdesk_host/freerdp/real.py:143` — open the per-app capture
   log 0600: `log_path.open("ab")` → 
   `open(log_path, "ab", opener=lambda p, f: os.open(p, f, 0o600))`.
4. `host/src/crossdesk_host/observability/log.py` `_RotatingFileWriter` —
   0600 on the daemon JSONL log:
   - `__init__` (`:52`): `path.open("a", encoding="utf-8")` → same `opener=`
     pattern with 0o600; add a best-effort `os.chmod(path, 0o600)` wrapped in
     `try/except OSError` first, to repair a pre-existing 0644 file.
   - `_rotate` (`:81`): same opener on the `"w"` reopen. (The `os.replace`d
     `.1` backup inherits the source file's 0600 — no extra step.)

**Tests (all hermetic):**
- `tests/test_redaction.py`:
  - `redact_secret_flags` masks `/p:hunter2` → `/p:<redacted>` and
    `/pth:abcd`, leaves `/u:user`, `/v:host`, `/cert:tofu` untouched.
  - `_value_contains_forbidden("/p:hunter2")` hits; the redacted string
    `"/p:<redacted>"` does NOT hit (lookahead works).
  - `mask_sensitive("cmd /p:hunter2 x\n")` masks the whole line.
- `tests/test_freerdp_real_resolution.py` (new test): monkeypatch
  `CROSSDESK_FREERDP_BIN=/bin/true`, `spawn_rail(["/v:h:1", "/p:hunter2"])`
  with `caplog` at INFO → assert `"hunter2"` appears in NO record and
  `"/p:<redacted>"` appears in the spawn line. (`/bin/true` exits 0 —
  hermetic; no `log_label` → no file writes.)
- `tests/test_log_file.py`: after `configure_logging(log_file=tmp_path/...)`
  + one log line → file mode `& 0o777 == 0o600`; force a rotation (small
  `max_bytes` — construct `_RotatingFileWriter` directly) → both current and
  `.1` are 0600; pre-create the file `0o644` → repaired to 0600 on init.

**Gates:** mypy --strict (new function fully typed), ruff, black, pytest.
**Ratchet:** the two backstop patterns run under `CROSSDESK_STRICT_LOG=1`
(pytest default) — any future log call whose value carries an unredacted
`/p:`/`/pth:` raises `RedactionViolation` and fails the suite. That IS the
frozen floor; no extra grep gate needed.
**Verify (real path):**
```sh
cd host && CROSSDESK_FREERDP_BIN=/bin/true python -c "
import logging; logging.basicConfig(level=logging.INFO)
from crossdesk_host.freerdp.real import RealFreeRDPInvocation
import io, sys; buf = io.StringIO()
h = logging.StreamHandler(buf); logging.getLogger().addHandler(h)
RealFreeRDPInvocation().spawn_rail(['/v:h:1','/p:hunter2'])
out = buf.getvalue(); assert 'hunter2' not in out and '/p:<redacted>' in out, out
print('OK: password redacted in spawn log')"
```

---

### Branch 2 — `fix/secret-file-perms` (closes P1-2, P2-1)

One concern: secret-bearing files are born 0600, never chmod-raced.

**Edits:**
1. `host/src/crossdesk_host/cli/install_cmd.py` `_prepare_autounattend`
   (`:230-231`) — replace `out.write_text(text, encoding="utf-8")`:
   ```python
   fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
   with os.fdopen(fd, "w", encoding="utf-8") as fh:
       os.fchmod(fd, 0o600)  # repair a pre-existing looser copy in state-dir
       fh.write(text)
   ```
   (`os` already imported; `os.fdopen` owns the fd.)
2. `host/src/crossdesk_host/installer/pki.py` `_write_key` (`:76-84`) — same
   fd-based pattern for the PEM bytes (`os.fdopen(fd, "wb")`), `os.fchmod`
   inside, DELETE the trailing `path.chmod(0o600)`. `_write_cert` (public
   material, 0644) stays as-is.

**Tests:**
- `tests/test_install_cmd.py`: `_prepare_autounattend(...)` into `tmp_path`
  → result mode `& 0o777 == 0o600` and password substituted; pre-create the
  dest at 0o644 with stale content → after the call mode is 0600 (repair
  path).
- `tests/test_installer_pki.py`: wrap `ensure_install_pki(tmp_path)` in
  `old = os.umask(0o000)` / `finally: os.umask(old)` → both `.key` files are
  0600 anyway (proves perms come from `os.open`, not umask luck); certs
  remain 0644.

**Gates:** standard host gates.
**Ratchet:** the two perms assertions freeze the floor; any regression to
`write_text`/`write_bytes` on these files fails the suite.
**Verify:**
```sh
cd host && python -c "
import tempfile, pathlib, os
from crossdesk_host.cli.install_cmd import _prepare_autounattend
d = pathlib.Path(tempfile.mkdtemp()); s = d/'a.xml'
s.write_text('x __CROSSDESK_PASSWORD__')
p = _prepare_autounattend(s, 'en-US', 's3cret', d)
assert oct(p.stat().st_mode & 0o777) == '0o600', oct(p.stat().st_mode)
print('OK: autounattend.prepared.xml is 0600')"
```

---

### Branch 3 — `fix/libvirt-loop-deadlines` (closes P1-3)

No blocking libvirt call reachable from a gRPC servicer runs on the event
loop, and every one has a deadline. This must land BEFORE the P0 live-verify
runs the daemon with `backend=real`.

**Edits:**
1. NEW `host/src/crossdesk_host/libvirt_ctl/aio.py`:
   ```python
   """Executor offload + deadline for blocking libvirt calls made from
   async context. backend.md: 'libvirt event-loop deadlines — pick one'."""
   import asyncio
   from typing import Callable, TypeVar

   T = TypeVar("T")
   LIBVIRT_OP_TIMEOUT_SECONDS = 30.0

   async def libvirt_call(
       fn: Callable[[], T], *, timeout: float = LIBVIRT_OP_TIMEOUT_SECONDS
   ) -> T:
       loop = asyncio.get_running_loop()
       return await asyncio.wait_for(loop.run_in_executor(None, fn), timeout)
   ```
   (On timeout the executor thread keeps running — unavoidable; callers log
   and proceed. Export from `libvirt_ctl/__init__.py`.)
2. `host/src/crossdesk_host/ipc/control.py:220-221` — offload the hook,
   preserve READY-after-finalize ordering:
   ```python
   if self.on_session_ready is not None:
       try:
           await libvirt_call(self.on_session_ready)
       except asyncio.TimeoutError:
           logger.warning(
               "on_session_ready timed out after %.0fs; finalize left "
               "unmarked — it will retry on the next Hello",
               LIBVIRT_OP_TIMEOUT_SECONDS,
           )
   ```
   Non-timeout exceptions propagate exactly as today (stream aborts, agent
   reconnects, finalize retries). Note `finalize_steady_state` already
   swallows libvirt `RuntimeError` internally (returns `"error"`).
3. `host/src/crossdesk_host/daemon.py:184-185` — guard concurrent Hellos
   (two streams could now run finalize concurrently in threads):
   ```python
   _finalize_once = threading.Lock()
   def _finalize_steady_state() -> None:
       if not _finalize_once.acquire(blocking=False):
           return  # a finalize is already in flight; idempotent retry later
       try:
           finalize_steady_state(libvirt_ctl)
       finally:
           _finalize_once.release()
   ```
   (module `import threading`; keep this INSIDE `main()` as a closure with
   the lock created alongside — branch 4 relocates selection, not this.)
4. `host/src/crossdesk_host/ipc/heartbeat.py` — `_dispatch_recovery_action`
   becomes `async def`; call site `:350` becomes
   `if await self._dispatch_recovery_action(out):`. Inside:
   - graceful_shutdown (`:270`): `await libvirt_call(self.libvirt_ctl.graceful_shutdown)`;
     on `asyncio.TimeoutError` → `logger.warning("heartbeat_graceful_shutdown_timeout")`,
     `return False` (FSM escalates on continued misses — self-healing).
   - hard_destroy (`:274`): `await libvirt_call(self.libvirt_ctl.hard_destroy)`;
     on `asyncio.TimeoutError` → `logger.critical("heartbeat_hard_destroy_timeout")`,
     still `return True` (break the channel; domain state unknown, the next
     channel's FSM re-evaluates). Other exceptions propagate as today.
5. `host/src/crossdesk_host/ipc/management.py:527,546,562` — wrap the three
   direct calls: `await libvirt_call(self.libvirt_ctl.suspend)` etc. The
   existing `except Exception` already converts to `ActionAck(ok=False)`;
   add a preceding `except asyncio.TimeoutError:` returning
   `ActionAck(ok=False, detail="libvirt call timed out after 30s")` (bare
   `str(TimeoutError())` is empty). The `coordinator.on_prepare_for_sleep()`
   / `on_resumed()` arms are NOT wrapped (coordinator mutates FSM state —
   not thread-safe; parked as C-3).
6. `host/src/crossdesk_host/ipc/filesystem.py:110,163` — 
   `await libvirt_call(lambda: self.filesystem_ctl.detach_share(ack.share_id))`
   and `await libvirt_call(lambda: self.filesystem_ctl.attach_share(share_id, str(validated.canonical)))`.
   Exceptions (incl. TimeoutError) propagate as RuntimeError does today —
   bounded instead of a hang.

**Tests:**
- NEW `tests/test_libvirt_aio.py`: `libvirt_call(lambda: 42)` → 42; a fn
  raising `RuntimeError` propagates; `libvirt_call(lambda: time.sleep(0.5), timeout=0.05)`
  raises `asyncio.TimeoutError` in <0.5 s; loop stays live during a blocked
  call (run a competing `asyncio.sleep(0)`-counting task; assert it ticked).
- `tests/test_control_service.py` (reuse its hello-driving fixtures):
  on_session_ready that `time.sleep(0.3)` + monkeypatched module timeout
  0.05 → Hello still reaches READY, timeout warning in caplog; fast hook →
  called exactly once, READY.
- `tests/test_heartbeat_boot_probe.py` or NEW `tests/test_heartbeat_recovery_dispatch.py`:
  fake controller recording calls → HARD_DESTROY out → returns True +
  `hard_destroy` called once; controller blocking 0.5 s + timeout 0.05 →
  returns True + `heartbeat_hard_destroy_timeout` logged; GRACEFUL arm same
  pattern → returns False.
- `tests/test_management_service.py`: `HardDestroy` with a blocking
  controller (timeout monkeypatched small) → `ok=False`, detail mentions
  timeout.
- All use in-memory fakes — the autouse anti-real-libvirt guard is untouched.

**Gates:** mypy --strict (async signature change is internal — no Protocol
edits), ruff, black, pytest.
**Ratchet:** add to `.claude/audit.sh` metrics a grep gate:
```sh
# direct blocking libvirt calls from servicers (must go through libvirt_call)
grep -rn 'self\.\(libvirt_ctl\|filesystem_ctl\)\.[a-z_]*(' host/src/crossdesk_host/ipc/ | grep -v 'libvirt_call' | wc -l   # expect 0
```
(bound-method references passed TO `libvirt_call` don't match — only direct
invocations do).
**Verify:**
```sh
cd host && python -c "
import asyncio, time
from crossdesk_host.libvirt_ctl.aio import libvirt_call
async def m():
    t0 = time.monotonic()
    try: await libvirt_call(lambda: time.sleep(5), timeout=0.1)
    except asyncio.TimeoutError: pass
    assert time.monotonic() - t0 < 1.0
asyncio.run(m()); print('OK: blocked libvirt call is deadline-bounded')"
```

---

### Branch 4 — `fix/daemon-backend-select` (closes P1-4 + P1-5)

Shared call site — one branch: extract the selection into a testable helper,
log it, test both arms.

**Edits:** `host/src/crossdesk_host/daemon.py` — extract from `main()`
(`:126-138` + `:179-189`) a module-level helper (keeps the lazy
`RealLibvirtController` import; `test_daemon_suspend_guard.py` proves daemon
is importable in tests):
```python
def select_libvirt_backend(
    cfg: "Config",
) -> tuple[LibvirtController, Optional[Callable[[], None]]]:
    """Instantiate the configured libvirt controller and, for the REAL
    backend only, the on-first-Hello steady-state finalize hook. The mock
    gets no hook: running finalize against it would mark the step done
    without redefining anything, masking the P0 data-loss path."""
    if cfg.libvirt.backend == "real":
        from crossdesk_host.libvirt_ctl.real import RealLibvirtController

        ctl: LibvirtController = RealLibvirtController(
            domain_name=cfg.libvirt.domain_name
        )
        logger.info(
            "libvirt_backend_selected", kind="real",
            domain_name=cfg.libvirt.domain_name,
        )
        return ctl, _make_finalize_hook(ctl)
    logger.warning(
        "libvirt_backend_selected", kind="mock",
        # mock = lifecycle actions are no-ops; recovery cannot touch a real VM
    )
    return LibvirtControllerMock(), None
```
plus `_make_finalize_hook(ctl)` returning the single-flight closure from
branch 3 (lock per hook instance). `main()` shrinks to
`libvirt_ctl, on_session_ready = select_libvirt_backend(cfg)`. Use only
allow-listed structlog fields (`kind`, `domain_name`) — the redaction
processor enforces the list. `Callable` import exists via `typing`.

Sequencing note: branches 3 and 4 both touch the finalize-hook wiring in
`daemon.py`. Land 3 first; branch 4 then MOVES the closure+lock into
`_make_finalize_hook` unchanged.

**Tests:** NEW `tests/test_daemon_backend_select.py`:
- cfg with `libvirt.backend="mock"` (construct `Config` directly) →
  `(LibvirtControllerMock, None)` + `structlog.testing.capture_logs()`
  contains `libvirt_backend_selected` with `kind="mock"` at warning.
- cfg with `backend="real"` → isinstance `RealLibvirtController`, hook is
  not None (do NOT call it — it would read the real state file), info log
  with `kind="real"`. Constructor is lazy (no libvirt import/connection) so
  the autouse guard stays green.
- Hook single-flight: build the hook around a controller whose
  `redefine_steady_state` blocks on a `threading.Event`; two concurrent
  executor invocations → underlying finalize entered once (guarded by the
  non-blocking lock). (Skip if branch 3 already covers it there — one home
  for this test, not two.)

**Gates:** standard host gates.
**Ratchet:** the two arm-tests freeze the mock→None guard — the exact
refactor-flip the audit feared now fails the suite.
**Verify:**
```sh
cd host && python -c "
from crossdesk_host.daemon import select_libvirt_backend
from crossdesk_host.config import Config
ctl, hook = select_libvirt_backend(Config())
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
assert isinstance(ctl, LibvirtControllerMock) and hook is None
print('OK: default config selects mock with no finalize hook')"
```

---

### Branch 5 — `fix/icon-png-validation` (closes P2-2)

**Edits:** `host/src/crossdesk_host/display/window_icon.py` — validate the
guest-controlled bytes at the boundary, FIRST thing in `offer()` (before the
pending lookup, so a bogus icon doesn't burn a valid expectation):
```python
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_MAX_ICON_BYTES = 1 << 20  # 1 MiB; real 256×256 extractions run ~72 KiB

def offer(self, icon_png: bytes) -> Optional[str]:
    if not icon_png:
        return None
    if not icon_png.startswith(_PNG_MAGIC) or len(icon_png) > _MAX_ICON_BYTES:
        logger.warning(
            "rejected window icon: %d bytes, header %s",
            len(icon_png), icon_png[:8].hex(),
        )
        return None
    ...existing pending logic...
```

**Tests:** `tests/test_window_icon.py`:
- non-PNG bytes (`b"MZ..."`) → None, nothing written, pending expectation
  PRESERVED (a subsequent valid offer still applies).
- `_PNG_MAGIC + b"\0" * (1 << 20)` (oversize) → None.
- `_PNG_MAGIC + b"idat"` → applies, file written (signature+cap only — we
  are not a decoder; defense-in-depth for gdk-pixbuf et al.).
- UPDATE existing fixtures that offer arbitrary bytes (e.g. `b"png-bytes"`)
  to be `_PNG_MAGIC`-prefixed — they would now be rejected.

**Gates:** standard. **Ratchet:** tests freeze the boundary check.
**Verify:**
```sh
cd host && python -c "
from crossdesk_host.display.window_icon import WindowIconStore
import tempfile, pathlib
s = WindowIconStore(icon_dir=pathlib.Path(tempfile.mkdtemp()))
s.expect('x', 'X'); assert s.offer(b'not a png') is None
print('OK: non-PNG icon rejected')"
```

---### Branch 6 — `chore/ci-fork-gate` (closes P2-3)

**Edits:** `.github/workflows/ci.yml:310`:
```yaml
    if: >-
      contains(github.event.pull_request.labels.*.name, 'hardware-smoke') &&
      github.event.pull_request.head.repo.full_name == github.repository
```
Add one comment line above: fork PRs never reach the self-hosted runner even
if a collaborator mislabels them (pwn-request guard).

**Tests:** none runnable locally (Actions).
**Gates:** run `actionlint` if on PATH (best-effort); YAML parse via
`python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"`.
**Ratchet:** the condition itself.
**Verify:** `grep -q 'head.repo.full_name == github.repository' .github/workflows/ci.yml && echo OK`

---

### Branch 7 — `chore/gui-stale-advisory` (closes P2-14 **[CORRECTED]**)

The audit misattributed the stale ignore. Measured with
`cargo deny check advisories` in `gui/`: unmatched = **RUSTSEC-2025-0134**
(rustls-pemfile — gui has no tonic; 0 lockfile hits). **RUSTSEC-2026-0202
stays** (cxx 1.0.194 is in `gui/Cargo.lock`, advisory actively matched).
Guest keeps 0134 (rustls-pemfile ×2 in `guest/Cargo.lock`).

**Edits:**
- `gui/deny.toml:37` — remove `"RUSTSEC-2025-0134"` + its comment lines.
- `gui/.cargo/audit.toml:10` — same removal; fix the header comment
  ("Mirrors guest/deny.toml" → note the deliberate divergence: gui has no
  tonic, so no rustls-pemfile ignore).

**Tests:** n/a (config). **Gates:** `cd gui && cargo check --quiet` still
green (untouched code).
**Ratchet:** none mechanical (cargo-deny has no fail-on-unmatched-ignore
knob); the weekly audit's static layer counts deny issues — expect gui
4→3.
**Verify:** `cd gui && cargo deny check advisories 2>&1 | grep -c advisory-not-detected` → `0` (and exit "advisories ok").

---

### Branch 8 — `fix/uninstall-dir-source` (closes P2-12)

**Edits:**
1. `host/src/crossdesk_host/config/__init__.py` — publicize the derivations
   with an optional home (call-time resolution preserved for HOME
   monkeypatching):
   ```python
   def user_config_dir(home: Optional[Path] = None) -> Path:
       return (home or Path.home()) / ".config" / "crossdesk"
   def user_state_dir(home: Optional[Path] = None) -> Path: ...  # .local/state/crossdesk
   def user_data_dir(home: Optional[Path] = None) -> Path: ...   # .local/share/crossdesk
   def user_cache_dir(home: Optional[Path] = None) -> Path: ...  # .cache/crossdesk
   ```
   Field factories switch to the public names (`default_factory=user_config_dir`
   — zero-arg call uses the default). Delete the private variants.
2. `host/src/crossdesk_host/uninstall.py:98-123` — replace the four literal
   derivations: desktop-files dir stays literal (it's a freedesktop path, not
   a crossdesk dir), `iso_cache` → `user_cache_dir(h)`, `install_state` →
   `user_state_dir(h)`, `config` → `user_config_dir(h)`.
3. `host/src/crossdesk_host/installer/state.py:31-35` —
   `_default_state_file()` returns `user_state_dir() / "install.state.json"`
   (docstring about call-time resolution stays true).
4. Sweep: `grep -rn '"\.cache" / "crossdesk"\|".local" / "state" / "crossdesk"\|".config" / "crossdesk"' host/src/`
   — route any remaining literal (expected: `iso_downloader` cache,
   `install_cmd._install_pki_dir`) through the helpers IF it is a pure
   one-line swap; anything needing behavior thought is left and listed in
   the commit message. No refactor bundling.

**Tests:** `tests/test_uninstall.py` — existing home-param tests stay green;
NEW consistency test: for `home=tmp_path`, the report's removed/skipped
targets equal `user_*_dir(tmp_path)` outputs (kills any future divergence).
`tests/test_config.py` — `Paths()` defaults unchanged.
**Gates:** standard; mypy --strict on the new signatures.
**Ratchet:** the consistency test is the freeze.
**Verify:**
```sh
cd host && python -c "
import pathlib
from crossdesk_host.config import user_state_dir
from crossdesk_host.installer.state import default_state_file
assert default_state_file() == user_state_dir() / 'install.state.json'
print('OK: single-source state dir')"
```

---

### Branch 9 — `docs/audit-tracking-sweep` (closes P2-5, P2-6, P2-7, P2-9; parks C-items; routes B-drafts)

All loop-editable tracking files; one concern: post-audit truth.

**Edits:**
1. `.claude/ignorefiles.md`:
   - DELETE the `DBusNotifier._send_sync` row (P2-5) — it schedules a real
     `dbus_next` call since 2026-05-23; the manifest claim "body is literal
     no-op" is false.
   - ADD row (P2-6): `host/src/crossdesk_host/installer/drive_map.py` —
     "Etap A host-side generator shipped but unwired (0 production callers,
     tested-only). Live findings flipped the mechanism (Run-key path dead;
     MPR `/persistent:yes` restore is the lever); wiring waits on the
     one-time-trigger decision — see `status.md` Etap A. Dead-code audits
     should ignore." Since: 2026-07-07.
2. `PLAN.md` acceptance-table row #10 (P2-7): replace the tail "Zostaje
   live-verify pełnego usunięcia + opcjonalny `--force`/confirm (backlog)"
   with "Zostaje live-verify pełnego usunięcia (confirm-prompt + `--force`
   shipped `427b15e`)".
3. `.claude/backlog.md` "Operations & lifecycle" uninstall item (P2-7):
   rewrite "(b) `--force` + confirm prompt (dziś brak potwierdzenia…)" →
   "(b) ✅ shipped `427b15e` — interactive confirm (EOF-safe: piped stdin =
   no), `--force` skips; `--dry-run` unchanged."
4. `.claude/architecture.md` Transport bullet (P2-9): append "Bind seam:
   `transport.bind_kind = auto|tcp|vsock` (DEC-0017 dev path — every live
   milestone so far ran `tcp` loopback via SLIRP)." (Pre-commit hook bumps
   the timestamp itself.)
5. `.claude/backlog.md` — park the C-items (see §4): PKGBUILD checksum pin
   (Distribution & packaging), marker-gated real-libvirt destructive test
   (under P0 "A7-live install-path findings"), lifecycle-coordinator
   executor offload (P2 Tech debt).
6. ~~needs-owner §8 routing~~ — DROPPED: both B-drafts were owner-signed and
   applied 2026-07-07 during planning (see §3); resolution already recorded
   in `needs-owner.md` → Resolved.

**Tests/Gates:** none (docs); pre-commit timestamp hooks fire normally.
**Verify:** `grep -c "427b15e" PLAN.md .claude/backlog.md` → ≥1 each;
`grep -q bind_kind .claude/architecture.md && echo OK`;
`grep -q drive_map .claude/ignorefiles.md && echo OK`.

---

## 3. Needs-owner drafts (bucket B) — ✅ RESOLVED 2026-07-07

Owner signed "apply" interactively during planning (B-1: apply; B-2: apply
with all-🔄 markers). Both edits are APPLIED on `docs/owner-signed-drafts`
and recorded in `needs-owner.md` → Resolved. Branch 9 step 6 (routing these
drafts) is therefore DROPPED. Original drafts kept below for the record.

### B-1 (P2-10) — `AGENTS.md:102` subpackage count

CURRENT: `│   ├── src/crossdesk_host/   # 22 subpackages; key ones:`
PROPOSED: `│   ├── src/crossdesk_host/   # 20 subpackages; key ones:`
(Measured 2026-07-07: 20 packages — abstractions, catalog, cli, config,
display, doctor, filesystem_ctl, freerdp, installer, integrations, ipc,
jit_mount, libvirt_ctl, lifecycle, observability, proto, recovery,
transport, utils, watchdog. The §6 refresh applied 2026-07-05 wrote 22.)

### B-2 (P2-11) — `docs/REQUIREMENTS.md` missing config surfaces

Per the "new configuration field" pattern (AGENTS.md), three shipped
config surfaces have no F-row. Proposed additions (owner sets the status
markers; composes with the open "F-marker re-baseline" needs-owner item):

Under **F4 (Transport & control plane)**:
```
- F4.4 🔄 — Transport bind seam: `transport.bind_kind = auto | tcp | vsock`
  (default `auto`). `tcp` binds 127.0.0.1 only (DEC-0017 dev/bring-up path;
  no external listener); `vsock` is the production target.
- F4.5 🔄 — Daemon libvirt backend seam: `libvirt.backend = mock | real`
  (default `mock`). `real` drives `qemu:///session` and activates the
  post-install steady-state finalize and real heartbeat recovery.
```
Under **F6 (Filesystem)**:
```
- F6.4 🔄 — Opt-in shared folder (Stage A/B, DEC-0018):
  `shared_folder_enabled` (default off), `shared_folder_scope =
  home | documents | custom` (default `home` when enabled),
  `shared_folder_path`, `shared_folder_drive_letter` (D–Z, default Z),
  `shared_folder_redirect_documents` / `_redirect_desktop`.
```

---

## 4. Parked (bucket C) — backlog entries land in branch 9

- **C-1 (P2-4) PKGBUILD `sha256sums=('SKIP')`.** Trigger: the FIRST tagged
  release tarball (v0.1.0 acceptance #12 packaging test). Action then:
  `updpkgsums` against the published tarball + regenerate `.SRCINFO`; add
  the pin to the release checklist. Until a tarball exists there is nothing
  to hash.
- **C-2 (P2-8) marker-gated `RealLibvirtController` destructive-path
  integration test.** Trigger: owner greenlight of the P0 live-verify
  (needs-owner ▶ item). Action then: pytest marker `live_libvirt`
  (deselected by default), covering `define_and_start` →
  `redefine_steady_state` → `hard_destroy` → `undefine` against a
  disposable throwaway domain (never `windows-guest`), run as part of the
  live-verify cycle so acceptance #6 becomes regression-guarded.
- **C-3 (planning addendum, not an audit finding)
  `lifecycle/coordinator.py:139,162`** — `suspend()`/`resume()` block the
  loop on the D-Bus PrepareForSleep path and the mgmt-delegated path.
  Excluded from branch 3 because the coordinator mutates FSM state
  (`fsm_group`) — offloading to a thread needs a thread-safety design, not
  a mechanical wrap. Trigger: before suspend/resume live-verify (#5) on
  `backend=real`. Park as P2 Tech debt.

## 5. Won't-do (bucket D)

- **D-1 (P2-13) two historical `i18n:` commit subjects.** Fixing them means
  rewriting `main` history again immediately after the co-author-purge
  rewrite — every downstream hash churns for zero runtime value. Going
  forward: `chore(i18n): …` (rules already mandate Conventional Commits;
  `scripts/i18n.sh` generates no subjects, so nothing to patch).

---

## 6. Loop execution notes

- Sequence: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9. Branches are file-disjoint
  except 3→4 (both touch `daemon.py` finalize wiring — land 3 first, 4
  relocates the closure).
- Per branch: fresh `git pull --rebase origin main` → branch → implement →
  gates green → `merge --no-ff` → push (PUSH=ON). NO Co-Authored-By.
- Estimated loop iterations: 6–9 (branches 1–3 one each; 4+5, 6+7, 8+9 may
  pair within an iteration if gates stay green).
- Nothing here touches proto/, THREAT_MODEL, or any boundary file.
- After branch 9, `.claude/audit-log.md` findings are all dispositioned:
  14 fixed in code/docs, 2 owner-signed + applied, 3 parked with triggers,
  1 declined. Do not edit audit-log.md itself (audit rules: append-only
  during audits).

**Summary: 9 branches (4 security-first), ~6–9 loop iterations; 2
needs-owner drafts — both owner-signed and APPLIED 2026-07-07; 3 parked
with explicit triggers; 1 won't-do.**

---

## Progress

Execution loop tracking. Each checkbox is ticked in its own branch (merges
with the work, no direct commits to main).

- [x] branch 1 — fix/rdp-secret-logging (P1-1)
- [ ] branch 2 — fix/secret-file-perms (P1-2, P2-1)
- [ ] branch 3 — fix/libvirt-loop-deadlines (P1-3)
- [ ] branch 4 — fix/daemon-backend-select (P1-4, P1-5)
- [ ] branch 5 — fix/icon-png-validation (P2-2)
- [ ] branch 6 — chore/ci-fork-gate (P2-3)
- [ ] branch 7 — chore/gui-stale-advisory (P2-14)
- [ ] branch 8 — fix/uninstall-dir-source (P2-12)
- [ ] branch 9 — docs/audit-tracking-sweep (P2-5, P2-6, P2-7, P2-9)

### Execution notes (deviations / environment findings)

- **Black-drift (environment, pre-existing, not caused by this loop):** the
  venv's `black` is 26.5.1 with default line-length 88, but the project's
  real formatting standard is 120 (ruff `line-length = 120`); neither git
  hook nor CI runs black, so `black --check src tests` is structurally red on
  `main` (85 pre-existing files, pure 88-vs-120 wrapping drift). True
  enforced gate = ruff + mypy --strict + pytest (pre-push hook). This loop
  uses those as the merge gate, keeps its own edited files clean, and does
  NOT reformat the 85 pre-existing files (out of scope for every branch).
