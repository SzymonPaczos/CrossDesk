#!/usr/bin/env bash
#
# test-gates.sh — testy SAMYCH bramek, nie kodu projektu.
#
# Powód istnienia (conventions/rules-as-gates.md §9): gate, który sprawdzono
# wyłącznie na zdrowym repo, dowodzi tylko tego, że nie krzyczy bez powodu.
# Wartość gate'a leży w tym, że BLOKUJE — a to trzeba udowodnić osobno.
# Gate bez testu negatywnego cicho przestaje działać przy pierwszym refaktorze.
#
# Hermetyczne: każdy test dostaje własne repozytorium w tempdirze. Zero
# kontaktu z prawdziwym repo, siecią i remote'ami.
#
# Uruchomienie: bash templates/test-gates.sh [ścieżka/do/.githooks/pre-push]

set -uo pipefail

HOOK="${1:-.githooks/pre-push}"
[ -f "$HOOK" ] || { printf 'Nie znaleziono hooka: %s\n' "$HOOK" >&2; exit 2; }
HOOK="$(cd "$(dirname "$HOOK")" && pwd)/$(basename "$HOOK")"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0
FAIL=0
ok()  { printf '  ✅ %s\n' "$1"; PASS=$((PASS + 1)); }
bad() { printf '  ❌ %s\n' "$1"; [ -n "${2:-}" ] && printf '%s\n' "$2"; FAIL=$((FAIL + 1)); }

# Świeże repo z jednym wypchniętym commitem bazowym.
# Echo: <katalog repo> <sha bazowy na remote>
new_repo() {
    local d="$TMP/r$RANDOM$RANDOM"
    mkdir -p "$d"
    git init -q --initial-branch=main "$d/repo" >/dev/null
    git init -q --bare "$d/remote.git" >/dev/null
    (
        cd "$d/repo" || exit 1
        git remote add origin ../remote.git
        git config user.email gate@test.invalid
        git config user.name  gate-test
        mkdir -p .githooks
        cp "$HOOK" .githooks/pre-push
        chmod +x .githooks/pre-push
        git config core.hooksPath .githooks
        printf 'const a = 1;\n' > app.js
        git add -A && git commit -qm base
        git push -q --no-verify origin main
        git fetch -q origin
    ) >/dev/null 2>&1 || return 1
    printf '%s %s\n' "$d/repo" "$(git -C "$d/repo" rev-parse origin/main)"
}

# Uruchamia hook tak, jak zrobiłby to git: refy na stdin.
run_hook() {
    local repo="$1" local_sha="$2" remote_sha="$3"
    ( cd "$repo" && printf 'refs/heads/main %s refs/heads/main %s\n' \
        "$local_sha" "$remote_sha" | ./.githooks/pre-push origin ../remote.git ) 2>&1
}

expect_block() {
    local name="$1" repo="$2" local_sha="$3" remote_sha="$4" out rc
    out="$(run_hook "$repo" "$local_sha" "$remote_sha")"; rc=$?
    if [ "$rc" -ne 0 ]; then ok "$name"; else bad "$name (hook zwrócił 0)" "$out"; fi
}

expect_pass() {
    local name="$1" repo="$2" local_sha="$3" remote_sha="$4" out rc
    out="$(run_hook "$repo" "$local_sha" "$remote_sha")"; rc=$?
    if [ "$rc" -eq 0 ]; then ok "$name"; else bad "$name (hook zwrócił $rc)" "$out"; fi
}

echo "Testy bramki pre-push: $HOOK"
echo

# --- 1. Antywzorzec A1: working tree czystszy niż commit ---------------------
# Najważniejszy test w tym pliku. Hook czytający pliki z dysku przechodzi tu
# zielono, mimo że na remote poleciałby commit z sekretem.
echo "1. Commit z sekretem, poprawka tylko w working tree"
read -r REPO BASE <<<"$(new_repo)"
(
    cd "$REPO" || exit 1
    printf 'const x = 1;\napi_key = "SUPERTAJNE12345"\n' > app.js  # pre-push-allow-secret: atrapa w fixturze dowodzącym, że gate sekretów blokuje
    git add -A && git commit -qm "feat: sekret"
    printf 'const x = 1;\napi_key = process.env.KEY\n' > app.js   # NIE commitujemy
) >/dev/null 2>&1
BAD_SHA="$(git -C "$REPO" rev-parse HEAD)"
expect_block "blokuje sekret obecny w commicie mimo czystego working tree" \
    "$REPO" "$BAD_SHA" "$BASE"

# --- 2. Brak fałszywych alarmów ---------------------------------------------
echo "2. Zdrowy commit"
(cd "$REPO" && git add -A && git commit -qm "fix: sekret do env") >/dev/null 2>&1
GOOD_SHA="$(git -C "$REPO" rev-parse HEAD)"
expect_pass "przepuszcza commit bez sekretu" "$REPO" "$GOOD_SHA" "$BASE"

# --- 3. Usunięcie gałęzi (local sha = same zera) -----------------------------
echo "3. Usunięcie gałęzi"
ZERO="0000000000000000000000000000000000000000"
expect_pass "nie wywraca się przy usuwaniu gałęzi" "$REPO" "$ZERO" "$BASE"

# --- 4. Nowa gałąź (remote sha = same zera) ----------------------------------
echo "4. Nowa gałąź, nieznana remote'owi"
read -r REPO2 _ <<<"$(new_repo)"
(
    cd "$REPO2" || exit 1
    git checkout -qb feat/nowa
    printf 'secret = "ABCDEFGH12345"\n' > cfg.py  # pre-push-allow-secret: druga atrapa tego samego fixture'u
    git add -A && git commit -qm "feat: nowa galaz"
) >/dev/null 2>&1
NEW_SHA="$(git -C "$REPO2" rev-parse HEAD)"
expect_block "wykrywa sekret na gałęzi nieobecnej na remote" \
    "$REPO2" "$NEW_SHA" "$ZERO"

# --- 5. Antywzorzec A2: gate nie urywa się w środku --------------------------
# Jeśli set -e ubija hook po pierwszym advisory grepie, ostatnia warstwa
# nigdy nie drukuje swojego nagłówka.
echo "5. Wszystkie warstwy wykonane do końca"
OUT="$(run_hook "$REPO" "$GOOD_SHA" "$BASE")"
if printf '%s' "$OUT" | grep -q 'TODO/FIXME'; then
    ok "ostatnia warstwa gate'a wykonała się (brak cichego urwania)"
else
    bad "gate urwał się przed ostatnią warstwą" "$OUT"
fi

# --- 6. Higiena: brak osieroconych worktree ----------------------------------
echo "6. Sprzątanie po sobie"
COUNT="$(git -C "$REPO" worktree list --porcelain | grep -c '^worktree ')"
if [ "$COUNT" -eq 1 ]; then
    ok "hook nie zostawił tymczasowych worktree"
else
    bad "hook zostawił $((COUNT - 1)) osieroconych worktree"
fi

echo
printf 'Wynik: %d zdanych, %d niezdanych\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
