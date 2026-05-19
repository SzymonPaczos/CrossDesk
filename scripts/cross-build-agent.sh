#!/bin/sh
# Cross-rs end-to-end build for agent.exe.
#
# Cross-rs only mounts the cargo workspace (guest/) into the build
# container, so guest/crates/proto/build.rs's repo-relative path
# `../../../proto` escapes the mount and fails. We resolve this by
# vendoring a fresh copy of proto/ into guest/proto-vendored/ before
# invoking cross; the build.rs preference order picks it up
# (CROSSDESK_PROTO_DIR > guest/proto-vendored > ../../../proto).
#
# Usage:
#   scripts/cross-build-agent.sh                                 # debug
#   scripts/cross-build-agent.sh --release                       # release
#   scripts/cross-build-agent.sh --release --target …            # custom target
#
# Requirements: cross (`cargo install cross --git
# https://github.com/cross-rs/cross`) and a Docker / Podman daemon.

set -eu

REPO_ROOT="$(git rev-parse --show-toplevel)"
PROTO_SRC="$REPO_ROOT/proto"
VENDORED="$REPO_ROOT/guest/proto-vendored"
TARGET="${TARGET:-x86_64-pc-windows-gnu}"

if [ ! -d "$PROTO_SRC" ]; then
    echo "fatal: $PROTO_SRC missing" >&2
    exit 1
fi

if ! command -v cross >/dev/null 2>&1; then
    echo "fatal: cross not on PATH — install with:" >&2
    echo "  cargo install cross --git https://github.com/cross-rs/cross" >&2
    exit 1
fi

echo "→ vendoring proto/ to $VENDORED ..."
rm -rf "$VENDORED"
mkdir -p "$VENDORED"
cp -R "$PROTO_SRC"/. "$VENDORED"/

echo "→ cross build --target $TARGET $* ..."
cd "$REPO_ROOT/guest"
cross build --target "$TARGET" -p agent-svc "$@"

echo "✅ agent.exe in guest/target/$TARGET/<profile>/agent.exe"
