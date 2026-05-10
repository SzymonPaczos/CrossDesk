# Translations

Source-of-truth translation catalogs for CrossDesk's user-facing
strings. Strategy and rationale: [`docs/I18N.md`](../docs/I18N.md).

Two surfaces, two toolchains:

| Surface | Tool | Source format | Compiled format | Lookup at runtime |
|---------|------|---------------|-----------------|-------------------|
| Python CLI / host messages | gettext | `.po` | `.mo` | `crossdesk_host.i18n._("...")` |
| Qt6/QML GUI | Qt Linguist | `.ts` | `.qm` | `qsTr("...")` |

The Python catalogs live here under `i18n/`. The Qt catalogs live
next to the GUI source under
[`gui/crates/crossdesk-gui/i18n/`](../gui/crates/crossdesk-gui/i18n/)
because Qt's resource system expects them there. `scripts/i18n.sh`
wraps both extraction toolchains so contributors do not have to
remember the per-stack incantation.

## Layout

```
i18n/
├── README.md                          (this file)
├── crossdesk-host.pot                 gettext template — extracted from host/ Python sources
└── pl/
    └── LC_MESSAGES/
        └── .gitkeep                   placeholder; crossdesk-host.po lands here once translated
```

The compiled `.mo` is **not** checked in — it is built from `.po` at
package time by the distro packagers (deb/rpm/AUR all run `msgfmt`
in their build steps; see `docs/PACKAGING.md`) and ends up at
`/usr/share/locale/<lang>/LC_MESSAGES/crossdesk-host.mo`.

For a developer-mode lookup the `crossdesk_host.i18n` module also
probes `i18n/` directly (one level up from `host/src/`), so running
`msgfmt i18n/pl/LC_MESSAGES/crossdesk-host.po -o
i18n/pl/LC_MESSAGES/crossdesk-host.mo` is enough to test a Polish
build out-of-tree.

## Workflow for adding / updating translations

### Re-extract strings (after editing source code)

```sh
./scripts/i18n.sh extract
```

This runs `xgettext` over the host Python tree to refresh
`i18n/crossdesk-host.pot`, and `lupdate` over the QML tree to
refresh `gui/crates/crossdesk-gui/i18n/crossdesk_*.ts`. Both are
idempotent — re-running with no source changes leaves the templates
byte-identical (modulo timestamps, which xgettext writes as a header
comment).

### Add a new language

```sh
msginit --locale=de --input=i18n/crossdesk-host.pot \
        --output=i18n/de/LC_MESSAGES/crossdesk-host.po
```

For Qt: copy `gui/crates/crossdesk-gui/i18n/crossdesk_en.ts` to
`crossdesk_<lang>.ts` and translate via Qt Linguist or any text
editor (it is XML).

### Compile catalogs locally (dev sanity check)

```sh
./scripts/i18n.sh compile
```

Runs `msgfmt` over each `.po` under `i18n/<lang>/LC_MESSAGES/` and
`lrelease` over each `.ts` under `gui/crates/crossdesk-gui/i18n/`.
Output `.mo` / `.qm` files are gitignored — distro packagers
regenerate them.

## Required system tools

`scripts/i18n.sh` shells out to standard freedesktop / Qt tooling.
Install on:

| Distro       | Packages                                         |
|--------------|--------------------------------------------------|
| Debian/Ubuntu | `gettext qttools5-dev-tools qt6-tools-dev-tools` |
| Fedora       | `gettext qt6-linguist`                           |
| Arch         | `gettext qt6-tools`                              |
| macOS (dev)  | `brew install gettext qt`                        |

`xgettext`, `msginit`, `msgfmt`, `msgmerge` come from the `gettext`
package on every distro. `lupdate` and `lrelease` come from Qt's
linguist tools — they are not strictly needed for a Python-only
contribution but `scripts/i18n.sh` will skip the GUI step if they
are missing rather than fail the whole run.

## Conventions

- **Strings are English first.** Source code authors write the
  English string in the `_("...")` / `qsTr("...")` call site;
  translators only ever see the extracted templates.
- **Logs are not translated.** Per `docs/I18N.md` "Strings we don't
  translate", `structlog` event names, error codes, and config field
  names stay English so support questions are language-neutral.
- **No string concatenation.** Use full sentences inside `_(...)` so
  translators can reorder words. Polish in particular has different
  word order from English.
- **Plurals via `ngettext("%d window", "%d windows", n)`.** English
  has two plural forms; Polish has three. `gettext` handles the
  selection from the `.po` header — translators do not write code.
