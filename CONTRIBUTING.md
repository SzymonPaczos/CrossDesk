# Contributing to CrossDesk

Short navigator. The deep specs live in
[`AGENTS.md`](AGENTS.md) (project layout, coding rules, workflow)
and the docs under [`docs/`](docs/). This file only points new
contributors at the entry points so the canonical sources stay
single.

## Quick start

```sh
git clone https://github.com/SzymonPaczos/CrossDesk
cd CrossDesk
chmod +x .githooks/pre-commit .githooks/pre-push .githooks/post-commit
git config core.hooksPath .githooks   # per-clone; do not skip
# Host (Python 3.9+):
cd host && python3 -m venv .venv && .venv/bin/pip install -e ".[mock,dev,linux]"
# Guest (Rust):
cd ../guest && cargo check --workspace
# GUI (Qt6/QML via CXX-Qt):
cd ../gui && cargo check --workspace
```

Full per-host stack notes live in
[`docs/CROSS_PLATFORM_DEV.md`](docs/CROSS_PLATFORM_DEV.md).

## Coding rules

Read [`AGENTS.md` "Coding rules"](AGENTS.md#coding-rules) before
opening a PR. Highlights:

- **No Docker.** Host runs against `qemu:///session` libvirt
  directly (DEC-0003).
- **No polling.** Async gRPC streams both ways.
- **Rust:** idiomatic; `unwrap()`/`expect()` need a one-line
  `// Safety:` or `// Infallible because:` comment.
- **Python:** asyncio end-to-end, full type hints, `mypy --strict`,
  `black` formatting.
- **Comments explain WHY, not WHAT.** Names already say what.
- **Diffs scoped:** a fix doesn't bundle a refactor.

Pre-commit hooks (`.githooks/pre-commit`) enforce `mypy --strict`
on touched Python and `cargo check` on touched Rust. Pre-push runs
the security review (`hardcoded secrets`, `qmllint`, optional
`cargo-audit` / `gitleaks`) — see
[`.githooks/pre-push`](.githooks/pre-push).

## Pull requests

- **Conventional Commits** (`feat:`, `fix:`, `chore:`, `refactor:`,
  `docs:`, `test:`, `style:`). The pre-push hook does not enforce
  the format but reviewers do.
- **One branch per agent / session.** See
  [`AGENTS.md` "Branch-per-agent rule"](AGENTS.md#branch-per-agent-rule).
- **Push to feature branches, not `main`.** The only file an agent
  may push directly to `main` is `WORK_LOG.md` (coordination
  metadata).
- **Wait for the maintainer to merge.** Local merges only; no
  GitHub PR queue.

## Adding a translation (i18n)

CrossDesk has two parallel translation surfaces:

| Surface | Tool | Source | Lookup |
|---------|------|--------|--------|
| Python CLI / host | `gettext` | `i18n/*.po` | `crossdesk_host.i18n._("…")` |
| Qt6 / QML GUI | Qt Linguist | `gui/crates/crossdesk-gui/i18n/*.ts` | `qsTr("…")` |

Both are wrapped by [`scripts/i18n.sh`](scripts/i18n.sh) so you
do not need to remember the per-stack incantation.

### Workflow for a new language

1. **Re-extract the latest source strings:**
   ```sh
   ./scripts/i18n.sh extract
   ```
   This refreshes `i18n/crossdesk-host.pot` (Python) and the
   `.ts` files under `gui/crates/crossdesk-gui/i18n/` (Qt). It is
   safe to run on a clean tree — no source modifications.

2. **Copy the template for the new locale:**

   Python (gettext):
   ```sh
   mkdir -p i18n/<lang>/LC_MESSAGES
   msginit \
       --input=i18n/crossdesk-host.pot \
       --output-file=i18n/<lang>/LC_MESSAGES/crossdesk-host.po \
       --locale=<lang>
   ```

   Qt (Linguist):
   ```sh
   cp gui/crates/crossdesk-gui/i18n/crossdesk_en.ts \
      gui/crates/crossdesk-gui/i18n/crossdesk_<lang>.ts
   ```
   Edit the new `.ts` file's `<TS language="...">` attribute to
   the BCP-47 tag (e.g. `de_DE`, `es_ES`, `fr_FR`).

3. **Translate.** Edit the `.po` file with any text editor or
   [`poedit`](https://poedit.net/); edit the `.ts` file with
   `linguist` (`apt install qt6-tools-dev-tools` on Ubuntu).

4. **Compile + smoke-test locally:**
   ```sh
   ./scripts/i18n.sh compile
   LANG=<lang>.UTF-8 crossdesk doctor   # quick CLI smoke
   LANG=<lang>.UTF-8 cargo run -p crossdesk-gui    # GUI smoke
   ```

5. **Add yourself to "Current language coverage" below** and open
   a PR. Title: `i18n(<lang>): initial translation`.

The compiled `.mo` / `.qm` files are **not** checked in — distro
packagers regenerate them at package time (see
[`docs/PACKAGING.md`](docs/PACKAGING.md)).

### Current language coverage

| Language | BCP-47 | Maintainer | Status |
|----------|--------|------------|--------|
| English | `en_US` | (project default) | source language, always 100% |
| Polish | `pl_PL` | @SzymonPaczos | initial translation in progress |

Add a row when you submit a new translation PR.

### Strategy and rationale

Read [`docs/I18N.md`](docs/I18N.md) for the "why two toolchains"
discussion and the rule about English source strings staying
English even in code comments.

## Where to ask

This is a young project — there is no community channel yet. File
a GitHub issue with the `question` label or email the maintainer
at the address listed in
[`docs/COMPETITION.md`](docs/COMPETITION.md).

## License

GPL-3.0-or-later. By contributing you agree your contribution may
ship under that license. Third-party vendored code lives under
[`third_party/`](third_party/) with original licenses preserved —
do **not** copy from there into the main tree without checking the
licence compatibility (notably, `third_party/winapps/` is AGPLv3).
