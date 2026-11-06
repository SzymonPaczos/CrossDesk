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

# Użycie: dependency-currency.sh [ŚCIEŻKA]
#
# Ścieżka jest OBOWIĄZKOWĄ częścią kontraktu, choć ma domyślną wartość `.`.
# Bez niej skrypt mierzył wyłącznie katalog bieżący i cicho ignorował podany
# argument: uruchomiony jako `dependency-currency.sh /inne/repo` zwracał liczby
# o katalogu, w którym stała powłoka. Dwa różne repozytoria dawały wtedy
# identyczny wynik — czyli dokładnie objaw z `rules-as-gates.md` §11, tyle że
# w samej bramce. Jedna komenda, jedno wołanie, jeden mierzony katalog.
set -u

CEL=.
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done
cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

EOL_WARN_DAYS="${EOL_WARN_DAYS:-180}"
EOL_API="${EOL_API:-https://endoflife.date/api/v1/products}"
STRICT_EOL="${STRICT_EOL:-0}"
FAIL_ON_DEGRADED="${FAIL_ON_DEGRADED:-0}"

eol_count=0
warn_count=0
outdated_direct=0
outdated_major=0
degraded=()
# Mianownik: ile rzeczy w ogóle obejrzano. „0 przeterminowanych" bez tych
# liczb nie odróżnia repozytorium czystego od repozytorium, w którym skrypt
# nie znalazł ani jednego manifestu.
runtimes_checked=0
manifests_found=0
deps_examined=0
# Manifesty, po których bramka faktycznie przeszła. Zestawienie z listą
# manifestów znanych gitowi pokazuje ekosystemy, o których ta bramka milczy —
# a milczenie zliczone jako „zero przeterminowanych" jest tą samą awarią, co
# lista tras bez strażnika zwracająca pustkę.
ODWIEDZONE="$(mktemp)"; trap 'rm -f "$ODWIEDZONE"' EXIT
odwiedzony() { printf '%s\n' "$1" >> "$ODWIEDZONE"; }

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
  # GNU `date -d` albo BSD `date -j -f` (macOS).
  target=$(date -d "$1" +%s 2>/dev/null || date -j -f '%Y-%m-%d' "$1" +%s 2>/dev/null) || return 1
  now=$(date +%s)
  echo $(( (target - now) / 86400 ))
}

check_runtimes() {
  say "== Runtime: wsparcie =="
  found=0
  while IFS='|' read -r product cycle source; do
    [ -n "${product:-}" ] || continue
    found=1
    runtimes_checked=$((runtimes_checked + 1))
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

# Monorepo trzyma package.json w apps/web, frontend/ czy web/ — sprawdzanie
# wyłącznie korzenia milczało o całym froncie i wychodziło na zielono.
check_node() {
  local pkgi
  pkgi="$(git ls-files 'package.json' '*/package.json' '*/*/package.json' 2>/dev/null \
          | grep -v node_modules | head -5)"
  [ -n "$pkgi" ] || return 0
  have npm || { na "node — brak npm"; return 0; }
  local korzen="$PWD"
  for pkg in $pkgi; do
    odwiedzony "$pkg"
    cd "$korzen/$(dirname "$pkg")" || continue
    [ -d node_modules ] || { na "node — $pkg bez node_modules; npm outdated nie ma czego porównać"; continue; }
    check_node_katalog "$pkg"
  done
  cd "$korzen" || true
  return 0
}

# Ile zależności bezpośrednich deklaruje manifest — liczba niezależna od tego,
# ile z nich `npm outdated` uznał za przeterminowane.
zadeklarowanych_node() {
  have python3 || { printf '0'; return; }
  python3 - "$1" <<'PYEOF' 2>/dev/null || printf '0'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    print(0); raise SystemExit
n = 0
for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
    n += len(d.get(key) or {})
print(n)
PYEOF
}

check_node_katalog() {
  local skad="$1"
  deps_examined=$((deps_examined + $(zadeklarowanych_node package.json)))
  # `npm outdated` kończy się kodem niezerowym, GDY COŚ ZNAJDZIE. Oceniamy treść.
  out=$(npm outdated --json 2>/dev/null)
  if [ -z "$out" ] || [ "$out" = "{}" ]; then
    say "[OK  ] node — $skad: brak przeterminowanych zależności bezpośrednich"
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
      say "[RPT ] node — $skad: $n przeterminowanych bezpośrednich, w tym $m o major"
    fi
  else
    na "node — brak python3/jq do odczytu wyniku"
  fi
}

# `pip list --outdated` opisuje AKTYWNY interpreter, nie katalog, w którym
# stoimy. Uruchomiony poza środowiskiem projektu zwraca ten sam wynik dla
# każdego repozytorium — liczbę o powłoce audytora, nie o kodzie. Liczba,
# która nie zmienia się między projektami, jest gorsza od `n/a`, bo wygląda
# jak pomiar. Dlatego pytamy wyłącznie pipa z środowiska projektu.
pip_projektu() {
  if [ -x .venv/bin/pip ]; then printf '%s' .venv/bin/pip; return 0; fi
  if [ -x venv/bin/pip ]; then printf '%s' venv/bin/pip; return 0; fi
  case "${VIRTUAL_ENV:-}" in
    "$PWD"|"$PWD"/*) command -v pip 2>/dev/null; return $? ;;
  esac
  return 1
}

check_python() {
  { [ -f pyproject.toml ] || [ -f requirements.txt ]; } || return 0
  [ -f pyproject.toml ] && odwiedzony pyproject.toml
  [ -f requirements.txt ] && odwiedzony requirements.txt
  PIP="$(pip_projektu)" || {
    na "python — nie ma środowiska w projekcie (.venv/ ani aktywnego venv);
       pip spoza projektu opisałby powłokę audytora, nie to repo"
    return 0
  }
  zainstalowanych=$("$PIP" list --format=json 2>/dev/null \
    | python3 -c 'import json,sys
try: print(len(json.load(sys.stdin)))
except Exception: print(0)' 2>/dev/null)
  deps_examined=$((deps_examined + ${zainstalowanych:-0}))
  out=$("$PIP" list --outdated --format=json 2>/dev/null)
  if [ -z "$out" ]; then
    na "python — $PIP nie zwrócił wyniku (środowisko bez instalacji zależności?)"
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
      say "[RPT ] python — $n przeterminowanych, w tym $m o major ($PIP; pip nie rozdziela bezpośrednich od tranzytywnych)"
    fi
  else
    na "python — brak python3 do odczytu wyniku"
  fi
}

check_go() {
  [ -f go.mod ] || return 0
  odwiedzony go.mod
  have go || { na "go — brak narzędzia"; return 0; }
  deps_examined=$((deps_examined + $(go list -m all 2>/dev/null | grep -c . || printf 0)))
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

# Manifesty liczone z gita, czyli z innej ścieżki niż przejście po ekosystemach
# wyżej. Rozjazd „manifesty są, zależności zero, nic nie zgłoszone jako
# niezmierzone" znaczy, że skrypt szukał nie tam.
MANIFESTY="$(git ls-files \
    'package.json' '*/package.json' \
    'requirements.txt' '*/requirements.txt' \
    'pyproject.toml' '*/pyproject.toml' \
    'go.mod' '*/go.mod' \
    'composer.json' '*/composer.json' \
    'Gemfile' '*/Gemfile' \
    'Cargo.toml' '*/Cargo.toml' 2>/dev/null \
  | grep -v node_modules | sort -u)"
manifests_found="$(printf '%s' "$MANIFESTY" | grep -c . || true)"
[ -n "${manifests_found:-}" ] || manifests_found=0

# Manifest, którego żaden `check_*` nie dotknął, dostaje jawne `n/a`. Bez tego
# repozytorium w ekosystemie, którego ta bramka nie zna, wychodziło na zielono
# z liczbą zero — i wyglądało identycznie jak repozytorium bez długu.
manifests_visited=0
while IFS= read -r m; do
  [ -n "$m" ] || continue
  if grep -qxF "$m" "$ODWIEDZONE" 2>/dev/null; then
    manifests_visited=$((manifests_visited + 1))
  else
    na "$m — ekosystem, którego ta bramka nie zna; dopisz check_* albo przyjmij brak pomiaru"
  fi
done <<EOF
$MANIFESTY
EOF

say "SUMMARY"
say "DEPS_MANIFESTS: $manifests_found"
say "DEPS_MANIFESTS_VISITED: $manifests_visited"
say "DEPS_EXAMINED: $deps_examined"
say "RUNTIMES_CHECKED: $runtimes_checked"
say "RUNTIMES_EOL: $eol_count"
say "RUNTIMES_WARN: $warn_count"
say "DIRECT_OUTDATED: $outdated_direct (major: $outdated_major)"
say "OLDEST_OUTDATED_DAYS: n/a (narzędzia ekosystemów nie podają dat wydania)"
if [ "${#degraded[@]}" -gt 0 ]; then
  say "DEGRADED: ${#degraded[@]} — patrz wpisy [N/A ] wyżej"
else
  say "DEGRADED: 0"
fi

if [ "$manifests_found" -gt 0 ] && [ "$deps_examined" -eq 0 ] && [ "${#degraded[@]}" -eq 0 ]; then
  say "STATUS: BEZ_MIANOWNIKA"
  printf '\n❌ Git zna %s manifestów zależności, a bramka obejrzała zero zależności\n' "$manifests_found" >&2
  printf '   i nie zgłosiła ani jednego [N/A ]. To nie jest projekt bez zależności,\n' >&2
  printf '   tylko pomiar, który się nie odbył. Czym to sprawdzić: `git ls-files | grep -E "package.json|pyproject.toml|go.mod"`\n' >&2
  exit 1
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
