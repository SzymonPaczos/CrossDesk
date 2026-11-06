#!/usr/bin/env bash
# Trasy bez strażnika — `conventions/security-verification-gates.md`,
# „przegląd człowieka: autoryzacja per obiekt".
#
# Ta bramka powstała z konkretnej awarii, nie z teorii. Funkcja
# `unguarded_routes()` w jednej z aplikacji zwracała **pustą listę** przy
# jedenastu trasach bez strażnika, a bramka sesji meldowała sukces obejrzawszy
# 9 tras z 20 — bo chodziła po `app.routes`, a ten nie spłaszcza routerów
# dołączonych przez `include_router`. Liczba była prawdziwa względem przejścia
# i fałszywa względem rzeczywistości.
#
# Dlatego ta bramka NIE pyta aplikacji, ile ma tras. Czyta deklaracje ze
# ŹRÓDŁA — każdy dekorator trasy w każdym pliku, niezależnie od tego, czy jego
# router został gdziekolwiek dołączony. To jest ta druga ścieżka, o którą
# chodzi: liczba z aplikacji i liczba ze źródła mają się zgadzać, a gdy się
# rozjeżdżają, to wynik aplikacji jest bez wartości.
#
# Zwolnienia (trasy świadomie publiczne):
#   .claude/trasy-publiczne.txt   jeden wzorzec ścieżki w linii, po # powód
#
# Sygnały maszynowe:
#   ROUTES_TOTAL        ile deklaracji tras znaleziono w źródle  (mianownik)
#   ROUTES_FILES        w ilu plikach
#   ROUTES_ROUTERS      ile obiektów routera zadeklarowano
#   ROUTES_GUARDED      ile ma strażnika
#   ROUTES_UNGUARDED    ile nie ma — blokuje
#   ROUTES_ALLOWLISTED  ile zwolniono jako świadomie publiczne
#
# Użycie: route-guards.sh [--format text|signals] [ŚCIEŻKA]
#
# Kody wyjścia: 0 = każda trasa ma strażnika albo zwolnienie,
#               1 = trasa bez strażnika, 2 = błąd użycia.
set -uo pipefail

FORMAT=text
CEL=.
while [ $# -gt 0 ]; do
    case "$1" in
        --format) FORMAT="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done

cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

command -v python3 >/dev/null 2>&1 || {
    printf 'ROUTES_TOTAL: n/a — brak python3, deklaracji tras nie da się rozebrać\n'
    printf 'Brak narzędzia to `n/a`, nigdy zero ustaleń (rules-as-gates.md §11).\n' >&2
    exit 2
}

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
git ls-files -- '*.py' '*.ts' '*.js' '*.mjs' 2>/dev/null \
    | grep -vE '(^|/)(node_modules|dist|build|__pycache__|\.venv)/|(^|/)fixtures/known-(good|bad)/' > "$TMP/pliki" || true
PLIKOW_ZRODLA="$(grep -c . "$TMP/pliki" || true)"

ZWOLNIENIA=.claude/trasy-publiczne.txt
[ -f "$ZWOLNIENIA" ] || ZWOLNIENIA=/dev/null

python3 - "$TMP/pliki" "$ZWOLNIENIA" "$TMP/wynik" <<'PYEOF'
import re, sys

pliki = [l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
zwolnienia = []
try:
    for l in open(sys.argv[2], encoding="utf-8"):
        l = l.split("#", 1)[0].strip()
        if l:
            zwolnienia.append(l)
except OSError:
    pass

# Dekorator trasy w Pythonie: @<cokolwiek>.get("/x") — nazwa obiektu jest
# nieistotna, liczy się metoda HTTP. Dzięki temu router nazwany inaczej niż
# `router` nie znika z mianownika.
DEK_PY = re.compile(
    r"^\s*@\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\.\s*(get|post|put|patch|delete|head|options|route|websocket)\s*\((.*)$")
DEK_JS = re.compile(
    r"""\b([A-Za-z_$][A-Za-z0-9_$.]*)\s*\.\s*(get|post|put|patch|delete|head|options|all|use)\s*\(\s*['"]([^'"]+)['"]""")
ROUTER_PY = re.compile(r"=\s*(APIRouter|Blueprint)\s*\(")
ROUTER_JS = re.compile(r"=\s*(?:express\s*\.\s*Router|Router)\s*\(")

# Strażnik: zależność autoryzacyjna w dekoratorze, w sygnaturze uchwytu, albo
# nałożona na cały router przy jego tworzeniu lub przy dołączaniu.
STRAZ = re.compile(
    r"dependencies\s*=|Depends\s*\(|Security\s*\(|login_required|permission_required|"
    r"requires_auth|@auth|current_user|authenticate|authorize|ensureAuth|requireAuth|passport\.",
    re.I)

trasy, routery, pliki_z_trasami = [], 0, set()
for p in pliki:
    try:
        linie = open(p, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        continue
    tresc = "\n".join(linie)
    routery += len(ROUTER_PY.findall(tresc)) + len(ROUTER_JS.findall(tresc))
    # Strażnik nałożony na cały router — obowiązuje każdą trasę w tym pliku.
    caly_plik = bool(re.search(r"(APIRouter|Blueprint)\s*\([^)]*dependencies\s*=", tresc)) \
        or bool(re.search(r"include_router\s*\([^)]*dependencies\s*=", tresc)) \
        or bool(re.search(r"app\s*\.\s*use\s*\(\s*(requireAuth|ensureAuth|passport)", tresc))

    if p.endswith(".py"):
        for i, linia in enumerate(linie):
            m = DEK_PY.match(linia)
            if not m:
                continue
            # Okno = dekorator plus nagłówek uchwytu aż do ciała funkcji.
            okno = "\n".join(linie[i:i + 12])
            koniec = okno.find("\n    ")
            sciezka = re.search(r"""['"]([^'"]*)['"]""", m.group(3))
            trasy.append((p, i + 1, m.group(2).upper(),
                          sciezka.group(1) if sciezka else "?",
                          bool(STRAZ.search(okno[:koniec if koniec > 0 else len(okno)])) or caly_plik))
            pliki_z_trasami.add(p)
    else:
        for i, linia in enumerate(linie):
            for m in DEK_JS.finditer(linia):
                if m.group(2) == "use":
                    continue
                okno = "\n".join(linie[i:i + 3])
                trasy.append((p, i + 1, m.group(2).upper(), m.group(3),
                              bool(STRAZ.search(okno)) or caly_plik))
                pliki_z_trasami.add(p)

def zwolniona(sciezka):
    return any(re.search(w, sciezka) for w in zwolnienia)

bez, zwolnione = [], 0
for p, nr, metoda, sciezka, ma_straz in trasy:
    if ma_straz:
        continue
    if zwolniona(sciezka):
        zwolnione += 1
        continue
    bez.append("%s:%s\t%s %s" % (p, nr, metoda, sciezka))

with open(sys.argv[3], "w", encoding="utf-8") as f:
    f.write("TOTAL %d\nFILES %d\nROUTERS %d\nGUARDED %d\nUNGUARDED %d\nALLOWLISTED %d\n" % (
        len(trasy), len(pliki_z_trasami), routery,
        len(trasy) - len(bez) - zwolnione, len(bez), zwolnione))
    for l in bez:
        f.write("BEZ\t%s\n" % l)
PYEOF

odczyt() { awk -v k="$1" '$1==k {print $2}' "$TMP/wynik" | head -1; }
TOTAL="$(odczyt TOTAL)"; PLIKOW="$(odczyt FILES)"; ROUTEROW="$(odczyt ROUTERS)"
ZE_STRAZ="$(odczyt GUARDED)"; BEZ_STRAZ="$(odczyt UNGUARDED)"; ZWOLNIONYCH="$(odczyt ALLOWLISTED)"

if [ "${TOTAL:-0}" -eq 0 ] && [ "${ROUTEROW:-0}" -eq 0 ]; then
    printf 'ROUTES_TOTAL: n/a — w %s plikach źródłowych nie ma deklaracji tras HTTP\n' "$PLIKOW_ZRODLA"
    printf 'ROUTES_ROUTERS: 0\n'
    printf 'ROUTES_UNGUARDED: 0\n'
    exit 0
fi
if [ "${TOTAL:-0}" -eq 0 ] && [ "${ROUTEROW:-0}" -gt 0 ]; then
    printf 'ROUTES_TOTAL: 0\n'
    printf 'ROUTES_ROUTERS: %s\n' "$ROUTEROW"
    printf '\n❌ Zadeklarowano %s routerów i zero tras. To nie jest aplikacja bez tras,\n' "$ROUTEROW" >&2
    printf '   tylko przejście, które ich nie zobaczyło — dokładnie ta awaria, dla której\n' >&2
    printf '   ta bramka powstała. Czym to sprawdzić: `git grep -nE "@[a-z_]+\\.(get|post)"`\n' >&2
    exit 1
fi

if [ "$FORMAT" = text ] && [ "${BEZ_STRAZ:-0}" -gt 0 ]; then
    printf 'Trasy bez strażnika (%s z %s zadeklarowanych w źródle):\n\n' "$BEZ_STRAZ" "$TOTAL"
    grep '^BEZ' "$TMP/wynik" | cut -f2- | head -30 | awk -F'\t' '{printf "  ❌ %-40s %s\n", $1, $2}'
    printf '\n'
fi

printf 'ROUTES_TOTAL: %s\n' "$TOTAL"
printf 'ROUTES_FILES: %s\n' "$PLIKOW"
printf 'ROUTES_SOURCE_FILES: %s — pliki źródłowe przeszukane\n' "$PLIKOW_ZRODLA"
printf 'ROUTES_ROUTERS: %s\n' "$ROUTEROW"
printf 'ROUTES_GUARDED: %s\n' "$ZE_STRAZ"
printf 'ROUTES_UNGUARDED: %s\n' "$BEZ_STRAZ"
printf 'ROUTES_ALLOWLISTED: %s\n' "$ZWOLNIONYCH"
[ -f .claude/trasy-publiczne.txt ] \
    || printf 'ROUTES_ALLOWLIST: brak .claude/trasy-publiczne.txt — trasa świadomie publiczna nie ma jak zostać zwolniona\n'

if [ "${BEZ_STRAZ:-0}" -gt 0 ]; then
    printf '\n❌ %s tras odpowiada każdemu, kto zna adres. Strażnik to zależność\n' "$BEZ_STRAZ" >&2
    printf '   autoryzacyjna przy trasie, przy routerze albo przy jego dołączeniu.\n' >&2
    printf '   Trasę świadomie publiczną wpisz do .claude/trasy-publiczne.txt z powodem.\n' >&2
    exit 1
fi
exit 0
