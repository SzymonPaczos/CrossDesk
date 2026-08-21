#!/usr/bin/env bash
# Szkielet bramki aktualności — conventions/dependency-currency.md
#
# Kopiuj do projektu (np. .ci/dependency-currency.sh) i dopisz ekosystemy,
# których używacie. Skrypt świadomie NIE aktualizuje niczego: liczy dystans,
# sprawdza wsparcie runtime'ów i kończy jednym statusem.
#
# Tryby (zmienne środowiskowe):
#   STRICT_EOL=1         runtime po dacie EOL kończy przebieg kodem 1
#   FAIL_ON_DEGRADED=1   brak narzędzia lub brak sieci kończy przebieg kodem 2
#   EOL_WARN_DAYS=180    ile dni przed EOL zaczyna się ostrzeżenie
#   EOL_API=...          bazowy adres źródła danych o wsparciu
#
# Zasada nadrzędna: brak narzędzia i brak sieci to `n/a`, nigdy zero ustaleń.
# Dlatego skrypt nie używa `set -e` — polecenia typu `outdated` zwracają kod
# niezerowy, gdy COŚ ZNALAZŁY, i milczą, gdy nie mają czego sprawdzić.

set -u

EOL_WARN_DAYS="${EOL_WARN_DAYS:-180}"
EOL_API="${EOL_API:-https://endoflife.date/api/v1/products}"
STRICT_EOL="${STRICT_EOL:-0}"
FAIL_ON_DEGRADED="${FAIL_ON_DEGRADED:-0}"

eol_count=0
warn_count=0
outdated_direct=0
outdated_major=0
degraded=()

have() { command -v "$1" >/dev/null 2>&1; }
say()  { printf '%s\n' "$*"; }
na()   { degraded+=("$1"); say "[N/A ] $1"; }

# --- wykrycie zadeklarowanych wersji runtime'ów -----------------------------
# Każdy wpis: <produkt w źródle danych>|<wersja>|<skąd>
# Nazwa produktu jest FAKTEM DATOWANYM — zweryfikuj ją w źródle, nie z pamięci.
detect_runtimes() {
  if [ -f .python-version ]; then
    printf 'python|%s|.python-version\n' \
      "$(head -n1 .python-version | tr -d ' \r' | cut -d. -f1,2)"
  elif [ -f pyproject.toml ]; then
    v=$(grep -m1 -oE 'requires-python[[:space:]]*=[[:space:]]*"[^"]+"' pyproject.toml \
        | grep -oE '[0-9]+\.[0-9]+' | head -n1)
    [ -n "${v:-}" ] && printf 'python|%s|pyproject.toml\n' "$v"
  fi

  if [ -f .nvmrc ]; then
    printf 'nodejs|%s|.nvmrc\n' \
      "$(head -n1 .nvmrc | tr -d ' v\r' | cut -d. -f1)"
  elif [ -f package.json ]; then
    v=$(grep -m1 -oE '"node"[[:space:]]*:[[:space:]]*"[^"]+"' package.json \
        | grep -oE '[0-9]+' | head -n1)
    [ -n "${v:-}" ] && printf 'nodejs|%s|package.json engines\n' "$v"
  fi

  if [ -f go.mod ]; then
    v=$(grep -m1 -oE '^go[[:space:]]+[0-9]+\.[0-9]+' go.mod | grep -oE '[0-9]+\.[0-9]+')
    [ -n "${v:-}" ] && printf 'go|%s|go.mod\n' "$v"
  fi

  [ -f .ruby-version ] && printf 'ruby|%s|.ruby-version\n' \
    "$(head -n1 .ruby-version | tr -d ' \r' | cut -d. -f1,2)"

  if [ -f composer.json ]; then
    v=$(grep -m1 -oE '"php"[[:space:]]*:[[:space:]]*"[^"]+"' composer.json \
        | grep -oE '[0-9]+\.[0-9]+' | head -n1)
    [ -n "${v:-}" ] && printf 'php|%s|composer.json\n' "$v"
  fi
}

# --- odpytanie źródła danych o wsparcie -------------------------------------
# Zwraca: isEol|eolFrom|isMaintained|latest   albo puste, gdy nie ustalono.
eol_lookup() {
  product="$1"; cycle="$2"
  have curl || return 1
  body=$(curl -sS --max-time 20 --retry 2 "$EOL_API/$product" 2>/dev/null) || return 1
  [ -n "$body" ] || return 1
  if have jq; then
    printf '%s' "$body" | jq -r --arg v "$cycle" '
      .result.releases[]? | select(.name == $v)
      | "\(.isEol)|\(.eolFrom // "")|\(.isMaintained)|\(.latest.name // "")"' 2>/dev/null
  elif have python3; then
    printf '%s' "$body" | CYCLE="$cycle" python3 -c '
import json, os, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
for r in d.get("result", {}).get("releases", []):
    if r.get("name") == os.environ["CYCLE"]:
        print("%s|%s|%s|%s" % (r.get("isEol"), r.get("eolFrom") or "",
                               r.get("isMaintained"),
                               (r.get("latest") or {}).get("name") or ""))
        break
' 2>/dev/null
  else
    return 1
  fi
}

days_until() {  # $1 = YYYY-MM-DD ; wypisuje liczbę dni (ujemna = po terminie)
  target=$(date -d "$1" +%s 2>/dev/null) || return 1
  now=$(date +%s)
  echo $(( (target - now) / 86400 ))
}

check_runtimes() {
  say "== Runtime: wsparcie =="
  found=0
  while IFS='|' read -r product cycle source; do
    [ -n "${product:-}" ] || continue
    found=1
    info=$(eol_lookup "$product" "$cycle")
    if [ -z "${info:-}" ]; then
      na "$product $cycle ($source) — nie ustalono wsparcia (brak sieci, narzędzia lub nieznany cykl)"
      continue
    fi
    IFS='|' read -r is_eol eol_from maintained latest <<EOF
$info
EOF
    if [ "$is_eol" = "true" ]; then
      eol_count=$((eol_count + 1))
      d=$(days_until "$eol_from" 2>/dev/null || echo "?")
      say "[EOL ] $product $cycle ($source) — wsparcie zakończone $eol_from (${d#-} dni temu)"
    else
      d=$(days_until "$eol_from" 2>/dev/null || echo "")
      if [ -n "$d" ] && [ "$d" -lt "$EOL_WARN_DAYS" ]; then
        warn_count=$((warn_count + 1))
        say "[WARN] $product $cycle ($source) — EOL za $d dni ($eol_from); najnowsza: ${latest:-n/a}"
      else
        say "[OK  ] $product $cycle ($source) — wspierany do ${eol_from:-n/a}; najnowsza: ${latest:-n/a}"
      fi
    fi
  done <<EOF
$(detect_runtimes)
EOF
  [ "$found" = "1" ] || na "runtime — brak zadeklarowanej wersji w repozytorium"
}

# --- dystans zależności bezpośrednich ---------------------------------------
count_major_drift() {  # stdin: linie "current latest"
  awk '{ split($1,a,"."); split($2,b,"."); if (b[1] > a[1]) n++ } END { print n+0 }'
}

check_node() {
  [ -f package.json ] || return 0
  have npm || { na "node — brak npm"; return 0; }
  # `npm outdated` kończy się kodem niezerowym, GDY COŚ ZNAJDZIE. Oceniamy treść.
  out=$(npm outdated --json 2>/dev/null)
  if [ -z "$out" ] || [ "$out" = "{}" ]; then
    say "[OK  ] node — brak przeterminowanych zależności bezpośrednich"
    return 0
  fi
  if have python3; then
    read -r n m <<EOF
$(printf '%s' "$out" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("? ?"); sys.exit()
n = m = 0
for name, info in (d.items() if isinstance(d, dict) else []):
    info = info[0] if isinstance(info, list) and info else info
    if not isinstance(info, dict):
        continue
    cur, latest = info.get("current"), info.get("latest")
    if not cur or not latest:
        continue
    n += 1
    try:
        if int(str(latest).split(".")[0]) > int(str(cur).split(".")[0]):
            m += 1
    except ValueError:
        pass
print(n, m)
')
EOF
    if [ "$n" = "?" ]; then
      na "node — nie udało się odczytać wyniku npm outdated"
    else
      outdated_direct=$((outdated_direct + n))
      outdated_major=$((outdated_major + m))
      say "[RPT ] node — $n przeterminowanych bezpośrednich, w tym $m o major"
    fi
  else
    na "node — brak python3/jq do odczytu wyniku"
  fi
}

check_python() {
  { [ -f pyproject.toml ] || [ -f requirements.txt ]; } || return 0
  have pip || { na "python — brak pip w środowisku przebiegu"; return 0; }
  out=$(pip list --outdated --format=json 2>/dev/null)
  if [ -z "$out" ]; then
    na "python — pip nie zwrócił wyniku (środowisko bez instalacji zależności?)"
    return 0
  fi
  if have python3; then
    read -r n m <<EOF
$(printf '%s' "$out" | python3 -c '
import json, sys
try:
    items = json.load(sys.stdin)
except Exception:
    print("? ?"); sys.exit()
n = m = 0
for it in items:
    n += 1
    try:
        if int(str(it["latest_version"]).split(".")[0]) > int(str(it["version"]).split(".")[0]):
            m += 1
    except (KeyError, ValueError):
        pass
print(n, m)
')
EOF
    if [ "$n" = "?" ]; then
      na "python — nie udało się odczytać wyniku pip"
    else
      outdated_direct=$((outdated_direct + n))
      outdated_major=$((outdated_major + m))
      say "[RPT ] python — $n przeterminowanych, w tym $m o major (pip nie rozdziela bezpośrednich od tranzytywnych)"
    fi
  else
    na "python — brak python3 do odczytu wyniku"
  fi
}

check_go() {
  [ -f go.mod ] || return 0
  have go || { na "go — brak narzędzia"; return 0; }
  n=$(go list -m -u -f '{{if .Update}}{{.Path}}{{end}}' all 2>/dev/null | grep -c . )
  if [ -z "${n:-}" ]; then
    na "go — go list nie zwrócił wyniku"
  else
    outdated_direct=$((outdated_direct + n))
    say "[RPT ] go — $n modułów z dostępną aktualizacją"
  fi
}

# Dopisz tu kolejne ekosystemy (composer outdated --direct, cargo outdated,
# bundle outdated, dotnet list package --outdated). Każdy MUSI odróżniać
# „nic nie znaleziono" od „nie sprawdzono".

say "== Aktualność zależności i runtime'ów =="
say "data przebiegu: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
say ""
check_runtimes
say ""
say "== Zależności: dystans =="
check_node
check_python
check_go
say ""

say "SUMMARY"
say "RUNTIMES_EOL: $eol_count"
say "RUNTIMES_WARN: $warn_count"
say "DIRECT_OUTDATED: $outdated_direct (major: $outdated_major)"
say "OLDEST_OUTDATED_DAYS: n/a (narzędzia ekosystemów nie podają dat wydania)"
if [ "${#degraded[@]}" -gt 0 ]; then
  say "DEGRADED: ${#degraded[@]} — patrz wpisy [N/A ] wyżej"
else
  say "DEGRADED: 0"
fi

status="OK"
[ "$outdated_direct" -gt 0 ] && status="REPORT"
[ "$warn_count" -gt 0 ] && status="REPORT"
[ "${#degraded[@]}" -gt 0 ] && status="DEGRADED"
[ "$eol_count" -gt 0 ] && status="EOL"
say "STATUS: $status"

[ "$eol_count" -gt 0 ] && [ "$STRICT_EOL" = "1" ] && exit 1
[ "${#degraded[@]}" -gt 0 ] && [ "$FAIL_ON_DEGRADED" = "1" ] && exit 2
exit 0
