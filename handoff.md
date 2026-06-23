# CrossDesk — Session Handoff (overnight Mac run → Ubuntu morning)

> Cross-machine transfer artifact (committed so a `git pull` carries it).
> Start here, then read `.claude/loop-spec.md` (the autonomous-loop contract),
> `.claude/needs-owner.md` (parked decisions), and memory `v010_release_plan`.
> PL/EN mixed; code + docs are English.

## 0. TL;DR for the next session (on Ubuntu)

The Mac (hardware-free) loop ran overnight and merged 7 items to **local
`main`** (NOT pushed — owner pushes). The **full host suite is GREEN**
(914→ tests, 0 failures) — the long-standing `transport_mock` flaky is fixed.
Everything live (RAIL render, real libvirt, NT-service, virtio-fs) is still
🔵 box-gated and waits for this Ubuntu machine / the Proxmox box. Next:
push, let Ubuntu CI run, then continue the loop on Linux where it can also
**live-verify**.

## 1. What landed tonight (local `main`, unpushed)

main is **+57 over origin/main**. Tonight's merges (newest first):

- `chore(nix)` — flake.nix missing runtime deps (pydantic/pycdlib/otel) so a
  Nix build doesn't ImportError. *nix-build unverified (no nix on Mac).*
- `docs(readme)` — honest install (`--iso-path`, no fake auto-download) +
  honest status banner (pre-alpha; core live-verified, rest in progress).
- `chore(ci)` — **re-enabled Ubuntu CI** on push-to-main + PR (was frozen for
  billing). Ubuntu-only + Python 3.12, cost-bounded; heavy security sweep
  stays weekly. **This is the server-side gate for the loop.**
- `feat(installer)` — **A2b per-install PKI**: each install mints its own
  CA + host + guest leaf (was one shared dev keypair). `installer/pki.py` +
  `_resolve_mtls_pki` rewire + 9 tests (incl. distinct-CA-per-install).
- `fix(test)` — **transport_mock isolation**: the 6 order-dependent failures
  were a Python-3.12 `grpc.aio` + `get_event_loop` interaction; an autouse
  per-test loop fixes it. **Suite now fully green** (also unblocks CI on 3.12).

Earlier in the session (also on local main, part of the +57):
- M0 consolidation (fs-drive-letter agent stack + audit-p2-fixes +
  resilience-logging) reconciled onto main; 2 real integration seams fixed.
- A2a suspend-protection wired into the daemon + fail-closed invariant
  (real libvirt refuses to start without the D-Bus suspend listener) — the
  #1 data-loss defuse.
- The autonomous-loop artifacts: `.claude/loop-spec.md` + `.claude/needs-owner.md`.

## 2. Current state

- **Gates green:** mypy --strict 125 files; ruff src/+tests/; **host pytest
  full suite 0 failures** (was 6 transport_mock + 1 date-bomb, both fixed);
  guest cargo test+clippy and gui were green at consolidation.
- **Local only, NOT pushed.** Owner pushes (see §6).
- Working tree clean; on `main`.

## 3. The plan & the loop

- **Plan + decisions:** memory `v010_release_plan` + `.claude/loop-spec.md`
  work queue. Bar = full MVP v0.1.0. FS decided: Stage B (max usefulness) for
  1.0, Stage C (JIT) as a post-1.0 user-selectable mode. NT-service = hard
  prereq. Hardware-free P0 first (A2a done, A2b done).
- **Loop contract:** `.claude/loop-spec.md` — pick highest-priority unblocked
  item, gate, merge, park owner/box-gated work. Toggles: PUSH=OFF, ENV=mac.
  **On Ubuntu/Proxmox, flip ENV and start picking 🔵 items** (live-verify).
- **Parked owner decisions:** `.claude/needs-owner.md` — review in batches.

## 4. Morning flow on Ubuntu (suggested)

1. `git pull` (gets all +57 + this handoff).
2. **Push** (see §6) so Ubuntu CI runs — first real Linux run of the suite;
   it will also run the `linux_only` tests skipped on the Mac (may surface
   Linux-specific issues to fix here).
3. Enable GitHub Actions billing (or make repo public) so CI actually fires.
4. **Run the loop on Ubuntu** (ENV=proxmox-box once the box is up; until then
   Ubuntu can do the remaining hardware-free items + any Linux verification a
   plain Ubuntu host allows). The big 🔵 wins need the Windows-guest VM
   (Proxmox): A3 real-libvirt enable, A4 NT-service agent, A5-live virtio-fs,
   A6 second app render, A7 real install, M5 burn-in.

## 5. Next unblocked work (the 🔵 queue — needs the box)

Top of `.claude/loop-spec.md` "Needs the box": A3 (enable real
LibvirtController + lifecycle live — A2a protection is now in place so this is
safe), A4 (NT-service agent live + sc-failure), A5-live (virtio-fs mount +
Save dialog), A6 (second app + peripherals), A7 (real install run), A1
(self-hosted runner stand-up). Remaining hardware-free: B diagnostics
(actionable install errors), A5-host (virtio-fs domain XML — speculative,
better with the driver), A7-logic (install idempotency).

## 6. Push instructions (the "simplified push")

The suite is green now, so a push shouldn't need bypassing. Owner pushes:
```sh
git push origin main
```
The pre-push hook runs a security review + ruff + (optional) scanners. If it
blocks on something unrelated/known and you explicitly accept it, that's the
only time `--no-verify` is justified (owner's call — the loop never uses it).
After pushing, Ubuntu CI runs automatically (ci.yml now triggers on
push-to-main). Delete the throwaway `handoff.md` + any stale `origin/*`
branches when convenient.

## 7. Gotchas (don't re-learn these)

- **Py 3.12 `grpc.aio` + event loop:** sync tests that build `grpc.aio.server()`
  need a current event loop; pytest-asyncio leaves none after async tests on
  3.12. Pattern fixed in test_transport_mock via an autouse loop fixture.
- **Date-bomb tests:** a fixed calendar date + relative `--since` window
  silently fails once the clock passes it (fixed one in test_logs_cmd; watch
  for the pattern).
- **pytest hang on Mac:** `--timeout-method=thread` os._exit's the run on the
  first slow test; use `--timeout-method=signal` to get accurate locations +
  let the run continue.
- **venv was stale:** `pip install -e .` synced missing runtime deps
  (pycdlib) — re-run if imports fail after a pull.
- **No push from the agent** — owner pushes. Local merges only.
- **Boundary files** (proto/THREAT_MODEL/DECISIONS/REQUIREMENTS/MVP_SCOPE/
  GOALS/ROADMAP/AGENTS.md): draft → `.claude/needs-owner.md`, never edit.

*End. main @ +57 local, suite green, unpushed. Next: push → Ubuntu CI →
continue the loop on Linux (live-verify on Proxmox when up).*
