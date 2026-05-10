#!/usr/bin/env sh
# i18n.sh — extract / compile CrossDesk translation catalogs.
#
# Wraps two toolchains so contributors do not have to remember the
# per-stack incantation:
#
#   gettext  → Python CLI strings under host/  → i18n/crossdesk-host.pot
#   Qt       → QML strings under gui/          → gui/crates/crossdesk-gui/i18n/crossdesk_*.ts
#
# Strategy: docs/I18N.md.  Layout: i18n/README.md.
#
# Usage:
#   ./scripts/i18n.sh extract   # refresh .pot + .ts from source
#   ./scripts/i18n.sh compile   # build .mo + .qm for local sanity check
#
# Both subcommands are idempotent — re-running on an unchanged tree
# leaves outputs byte-identical (ignoring the POT-Creation-Date
# header, which xgettext always rewrites; we strip it below to keep
# diffs clean for CI).

set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST_SRC="$REPO_ROOT/host/src"
GUI_QML="$REPO_ROOT/gui/crates/crossdesk-gui/qml"
GUI_I18N="$REPO_ROOT/gui/crates/crossdesk-gui/i18n"
PY_POT="$REPO_ROOT/i18n/crossdesk-host.pot"

require() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'i18n.sh: missing required tool: %s\n' "$1" >&2
        printf '  install via your distro package manager — see i18n/README.md\n' >&2
        return 1
    fi
}

cmd_extract() {
    require xgettext

    printf 'extract: scanning %s for _() calls...\n' "$HOST_SRC"
    # --add-comments grabs translator-targeted comments so a line like
    #     # TRANSLATORS: shown when no VM has been provisioned yet
    # rides along into the .po as a header for that msgid.
    #
    # cd into the repo root + pass relative input paths so the .pot
    # reference comments (#: host/src/...) are portable across
    # contributors' checkouts. Without that, xgettext bakes the
    # absolute filesystem path into every entry.
    (
        cd "$REPO_ROOT"
        find host/src -type f -name '*.py' \
            ! -path "*/proto/*" \
            -print0 \
          | xargs -0 xgettext \
                --language=Python \
                --keyword=_ \
                --keyword=N_ \
                --from-code=UTF-8 \
                --add-comments=TRANSLATORS \
                --package-name=crossdesk-host \
                --package-version=0.1.0 \
                --copyright-holder='CrossDesk contributors' \
                --foreign-user \
                --output="i18n/crossdesk-host.pot"
    )

    # Strip the always-changing POT-Creation-Date so re-runs produce
    # zero diff when no source string has changed. Translators see
    # the same header xgettext writes; the date is informational.
    if [ -f "$PY_POT" ]; then
        sed -i.bak -E 's/^"POT-Creation-Date:.*"$/"POT-Creation-Date: FROZEN\\n"/' "$PY_POT"
        rm -f "$PY_POT.bak"
        printf 'extract: wrote %s\n' "$PY_POT"
    fi

    if command -v lupdate >/dev/null 2>&1; then
        printf 'extract: scanning %s for qsTr() calls...\n' "$GUI_QML"
        # lupdate writes both en and pl .ts files in place. The XML
        # diffs are review-friendly; lupdate preserves existing
        # translations on re-run.
        for ts in "$GUI_I18N"/crossdesk_*.ts; do
            [ -f "$ts" ] || continue
            lupdate -recursive "$GUI_QML" -ts "$ts" -no-obsolete >/dev/null
        done
        printf 'extract: refreshed %s\n' "$GUI_I18N"/crossdesk_*.ts
    else
        printf 'extract: lupdate not installed — skipping QML extraction\n' >&2
        printf '         install Qt linguist tools to generate .ts updates\n' >&2
    fi
}

cmd_compile() {
    require msgfmt

    for po in "$REPO_ROOT/i18n"/*/LC_MESSAGES/*.po; do
        [ -f "$po" ] || continue
        mo="${po%.po}.mo"
        msgfmt --output-file="$mo" "$po"
        printf 'compile: %s -> %s\n' "$po" "$mo"
    done

    if command -v lrelease >/dev/null 2>&1; then
        for ts in "$GUI_I18N"/crossdesk_*.ts; do
            [ -f "$ts" ] || continue
            lrelease "$ts" >/dev/null
            printf 'compile: %s -> %s\n' "$ts" "${ts%.ts}.qm"
        done
    else
        printf 'compile: lrelease not installed — skipping QML compile\n' >&2
    fi
}

case "${1:-}" in
    extract) cmd_extract ;;
    compile) cmd_compile ;;
    *)
        printf 'usage: %s {extract|compile}\n' "$0" >&2
        exit 2
        ;;
esac
