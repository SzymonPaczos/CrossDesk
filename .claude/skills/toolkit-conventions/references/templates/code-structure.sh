#!/usr/bin/env bash
# Struktura modułów — `conventions/code-structure.md`, sekcja „Egzekwowanie".
#
# Konwencja mówi wprost, co MUSI blokować merge: cykle, zakazane kierunki
# importów, `export *` oraz importy do wnętrza cudzego modułu. Do dziś żaden
# skrypt tego nie sprawdzał, więc zdanie „MUSZĄ blokować" znaczyło tyle, ile
# pamiętał recenzent.
#
# Mianownik: liczba modułów, które bramka otworzyła, i liczba pominiętych.
# Zero obejrzanych modułów przy repozytorium, które moduły MA, kończy się
# kodem 1 — bo to nie jest czysty kod, tylko filtr, który zjadł materiał.
#
# Sygnały maszynowe:
#   CODE_MODULES            ile plików źródłowych obejrzano  (mianownik)
#   CODE_MODULES_SKIPPED    ile pominięto (node_modules, dist, generowane)
#   CODE_BARREL_STARS       `export *` — blokuje
#   CODE_DEEP_IMPORTS       import do wnętrza cudzego modułu — blokuje
#   CODE_CYCLES             cykle w grafie importów względnych — blokuje
#   CODE_CYCLES_SCOPE       zakres pomiaru cykli albo powód `n/a`
#   CODE_OVERSIZED          moduły powyżej progu linii — zapadka
#   CODE_UNOWNED_UTILS      moduły `utils`/`helpers` bez właściciela — raport
#
# Użycie:
#   code-structure.sh [--format text|signals] [--max-lines N] [--baseline] [ŚCIEŻKA]
#
# Kody wyjścia: 0 = czysto, 1 = naruszenie blokujące, 2 = błąd użycia.
set -uo pipefail

FORMAT=text
MAX_LINII=400
USTAW_BASELINE=0
CEL=.

while [ $# -gt 0 ]; do
    case "$1" in
        --format)     FORMAT="${2:-}"; shift 2 ;;
        --max-lines)  MAX_LINII="${2:-}"; shift 2 ;;
        --baseline)   USTAW_BASELINE=1; shift ;;
        -h|--help)    sed -n '2,28p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done

cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

BASELINE=.claude/code-structure.baseline
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# ── Mianownik ───────────────────────────────────────────────────────────────
# Kandydaci przed filtrem i po filtrze liczeni osobno. Wykluczenie niepoliczone
# jest miejscem, w którym materiał znika bez śladu w wyniku bramki.
# Materiał znany-zły jest celowo zepsuty i bramka nie ma prawa go oceniać —
# ale wyklucza się go JAWNIE i liczy w CODE_MODULES_SKIPPED, bo wykluczenie
# niepoliczone jest miejscem, w którym znika materiał.
git ls-files -- '*.ts' '*.tsx' '*.js' '*.jsx' '*.mjs' '*.cjs' '*.py' 2>/dev/null \
    | sort -u > "$TMP/kandydaci"
KANDYDATOW="$(grep -c . "$TMP/kandydaci" || true)"
grep -vE '(^|/)(node_modules|dist|build|out|coverage|\.next|vendor|generated|__pycache__)/|(^|/)fixtures/known-(good|bad)/' "$TMP/kandydaci" \
    | grep -vE '\.(min|generated|bundle|d)\.[a-z]+$' > "$TMP/pliki" || true
MODULOW="$(grep -c . "$TMP/pliki" || true)"
POMINIETYCH=$(( KANDYDATOW - MODULOW ))

if [ "$KANDYDATOW" -eq 0 ]; then
    printf 'CODE_MODULES: n/a — git nie zna w tym repozytorium plików .ts/.js/.py\n'
    printf 'CODE_MODULES_SKIPPED: 0\n'
    exit 0
fi
if [ "$MODULOW" -eq 0 ]; then
    printf 'CODE_MODULES: 0\n'
    printf 'CODE_MODULES_SKIPPED: %s\n' "$POMINIETYCH"
    printf '\n❌ Bramka nie obejrzała ani jednego modułu, choć git zna %s plików źródłowych.\n' "$KANDYDATOW" >&2
    printf '   Wszystkie wpadły w filtr katalogów wygenerowanych — to nie jest czysta\n' >&2
    printf '   struktura, tylko brak pomiaru. Czym to sprawdzić: `git ls-files "*.ts" "*.py"`\n' >&2
    exit 1
fi

# ── 1. `export *` ───────────────────────────────────────────────────────────
# Konwencja: „Ogólne barrel files z `export *` są zabronione. Jawny `public.ts`
# z ręczną listą eksportów jest dopuszczalny." Ręczna lista to `export { … }`,
# więc gwiazdka jest naruszeniem także w `public.ts`.
: > "$TMP/gwiazdki"
while IFS= read -r plik; do
    case "$plik" in *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) ;; *) continue ;; esac
    grep -nE '^[[:space:]]*export[[:space:]]+\*' "$plik" 2>/dev/null \
        | sed "s|^|$plik:|" >> "$TMP/gwiazdki"
done < "$TMP/pliki"
GWIAZDEK="$(grep -c . "$TMP/gwiazdki" || true)"

# ── 2. Import do wnętrza cudzego modułu ─────────────────────────────────────
# Publiczne API właściciela to korzeń jego katalogu albo jawny `public`.
# Ścieżka wbijająca się głębiej (`.../features/orders/internal/repo`) omija
# je z definicji. Wzorzec katalogów jest projektowy — stąd `--owners`.
WLASCICIELE='features|modules|packages|apps|domains'
: > "$TMP/deep"
while IFS= read -r plik; do
    case "$plik" in *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) ;; *) continue ;; esac
    grep -noE "['\"][^'\"]*(${WLASCICIELE})/[A-Za-z0-9_.-]+/[^'\"]+['\"]" "$plik" 2>/dev/null \
        | grep -vE "/(public|index)(\.[tj]sx?)?['\"]$" \
        | sed "s|^|$plik:|" >> "$TMP/deep"
done < "$TMP/pliki"
DEEP="$(grep -c . "$TMP/deep" || true)"

# ── 3. Cykle w grafie importów względnych ───────────────────────────────────
# Zakres jest wąski i jest to napisane wprost: bez konfiguracji projektu nie da
# się rozwiązać aliasów, a graf zbudowany z połowy krawędzi milczałby o cyklach,
# których nie widzi. Wąski zakres z etykietą jest uczciwy; szeroki bez niej nie.
CYKLI=0
ZAKRES_CYKLI="importy względne (./ i ../) w plikach .ts/.js/.py"
if command -v python3 >/dev/null 2>&1; then
    # Heredoc poza `$( )`: bash 3.2 (macOS) gubi cudzysłowy w heredoku
    # wewnątrz podstawienia komendy i kończy się „unexpected EOF".
    python3 - "$TMP/pliki" > "$TMP/cykle" <<'PYEOF'
import os, re, sys

pliki = [l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
zbior = set(pliki)
ROZSZ_TS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

def rozwiaz_ts(zrodlo, spec):
    baza = os.path.normpath(os.path.join(os.path.dirname(zrodlo), spec))
    kandydaci = [baza + r for r in ROZSZ_TS]
    kandydaci += [os.path.join(baza, "index" + r) for r in ROZSZ_TS]
    kandydaci += [os.path.join(baza, "public" + r) for r in ROZSZ_TS]
    for k in kandydaci:
        k = os.path.normpath(k)
        if k in zbior:
            return k
    return None

def rozwiaz_py(zrodlo, kropki, modul):
    katalog = os.path.dirname(zrodlo)
    for _ in range(kropki - 1):
        katalog = os.path.dirname(katalog)
    czesc = modul.replace(".", "/") if modul else ""
    baza = os.path.normpath(os.path.join(katalog, czesc)) if czesc else katalog
    for k in (baza + ".py", os.path.join(baza, "__init__.py")):
        k = os.path.normpath(k)
        if k in zbior:
            return k
    return None

graf = {}
re_ts = re.compile(r"""(?:from|import\()\s*['"](\.[^'"]*)['"]""")
re_py = re.compile(r"""^\s*from\s+(\.+)([A-Za-z0-9_.]*)\s+import""", re.M)
for p in pliki:
    try:
        tresc = open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        continue
    cele = set()
    if p.endswith(ROZSZ_TS):
        for spec in re_ts.findall(tresc):
            c = rozwiaz_ts(p, spec)
            if c:
                cele.add(c)
    elif p.endswith(".py"):
        for kropki, modul in re_py.findall(tresc):
            c = rozwiaz_py(p, len(kropki), modul)
            if c:
                cele.add(c)
    graf[p] = cele

# Tarjan — liczba silnie spójnych składowych o rozmiarze > 1 albo z pętlą własną.
indeks, niski, na_stosie, stos, licznik, cykle = {}, {}, set(), [], [0], [0]
def odwiedz(v):
    prace = [(v, iter(graf.get(v, ())))]
    indeks[v] = niski[v] = licznik[0]; licznik[0] += 1
    stos.append(v); na_stosie.add(v)
    while prace:
        wierzch, it = prace[-1]
        postep = False
        for w in it:
            if w not in indeks:
                indeks[w] = niski[w] = licznik[0]; licznik[0] += 1
                stos.append(w); na_stosie.add(w)
                prace.append((w, iter(graf.get(w, ()))))
                postep = True
                break
            if w in na_stosie:
                niski[wierzch] = min(niski[wierzch], indeks[w])
        if postep:
            continue
        prace.pop()
        if prace:
            rodzic = prace[-1][0]
            niski[rodzic] = min(niski[rodzic], niski[wierzch])
        if niski[wierzch] == indeks[wierzch]:
            skladowa = []
            while True:
                x = stos.pop(); na_stosie.discard(x); skladowa.append(x)
                if x == wierzch:
                    break
            if len(skladowa) > 1 or wierzch in graf.get(wierzch, ()):
                cykle[0] += 1

for v in graf:
    if v not in indeks:
        odwiedz(v)
print(cykle[0])
PYEOF
    CYKLI="$(cat "$TMP/cykle")"
    [ -n "${CYKLI:-}" ] || { CYKLI=0; ZAKRES_CYKLI="n/a — graf importów nie zbudował się"; }
else
    CYKLI=0
    ZAKRES_CYKLI="n/a — brak python3, grafu importów nie da się zbudować"
fi

# ── 4. Rozmiar modułu (zapadka) i moduły bez właściciela (raport) ───────────
: > "$TMP/duze"
while IFS= read -r plik; do
    n="$(wc -l < "$plik" 2>/dev/null | tr -d ' ')"
    [ -n "${n:-}" ] || continue
    [ "$n" -gt "$MAX_LINII" ] && printf '%s\t%s\n' "$n" "$plik" >> "$TMP/duze"
done < "$TMP/pliki"
DUZYCH="$(grep -c . "$TMP/duze" || true)"

BEZ_WLASCICIELA="$(grep -cE '(^|/)(utils|helpers|misc|common)\.(ts|tsx|js|jsx|mjs|cjs|py)$|(^|/)(utils|helpers|misc)/' "$TMP/pliki" || true)"

# ── Wyjście ─────────────────────────────────────────────────────────────────
if [ "$FORMAT" = text ]; then
    if [ "$GWIAZDEK" -gt 0 ]; then
        printf 'Barrel files z `export *` — publiczne API modułu ma być listą, nie gwiazdką:\n'
        head -20 "$TMP/gwiazdki" | sed 's/^/  ❌ /'
        printf '\n'
    fi
    if [ "$DEEP" -gt 0 ]; then
        printf 'Importy do wnętrza cudzego modułu — omijają jego publiczne API:\n'
        head -20 "$TMP/deep" | sed 's/^/  ❌ /'
        printf '\n'
    fi
    if [ "$DUZYCH" -gt 0 ]; then
        printf 'Moduły powyżej %s linii:\n' "$MAX_LINII"
        sort -rn "$TMP/duze" | head -10 | awk '{printf "  · %6s linii  %s\n", $1, $2}'
        printf '\n'
    fi
fi

printf 'CODE_MODULES: %s\n' "$MODULOW"
printf 'CODE_MODULES_SKIPPED: %s — node_modules, dist, build, generated, pliki .min/.d.ts\n' "$POMINIETYCH"
printf 'CODE_BARREL_STARS: %s\n' "$GWIAZDEK"
printf 'CODE_DEEP_IMPORTS: %s\n' "$DEEP"
printf 'CODE_CYCLES: %s\n' "$CYKLI"
printf 'CODE_CYCLES_SCOPE: %s\n' "$ZAKRES_CYKLI"
printf 'CODE_OVERSIZED: %s (próg %s linii)\n' "$DUZYCH" "$MAX_LINII"
printf 'CODE_UNOWNED_UTILS: %s\n' "$BEZ_WLASCICIELA"

if [ "$USTAW_BASELINE" -eq 1 ]; then
    mkdir -p .claude
    printf '%s\n' "$DUZYCH" > "$BASELINE"
    printf 'Założono baseline %s = %s\n' "$BASELINE" "$DUZYCH"
    exit 0
fi

STATUS=0
if [ "$GWIAZDEK" -gt 0 ]; then
    printf '\n❌ %s razy `export *`. Konsument nie widzi, co moduł obiecuje, a usunięcie\n' "$GWIAZDEK" >&2
    printf '   eksportu przestaje być widoczne w diffie. Zamień na jawną listę w `public.ts`.\n' >&2
    STATUS=1
fi
if [ "$DEEP" -gt 0 ]; then
    printf '\n❌ %s importów sięga do wnętrza cudzego modułu, z pominięciem jego publicznego\n' "$DEEP" >&2
    printf '   API. Zmiana pliku wewnętrznego psuje wtedy kod, który o niej nie wie.\n' >&2
    STATUS=1
fi
if [ "$CYKLI" -gt 0 ]; then
    printf '\n❌ %s cykli w grafie importów (%s). Moduł w cyklu nie ma\n' "$CYKLI" "$ZAKRES_CYKLI" >&2
    printf '   kolejności inicjalizacji i nie da się go wziąć osobno do testu.\n' >&2
    STATUS=1
fi
if [ -f "$BASELINE" ]; then
    PROG="$(tr -cd '0-9' < "$BASELINE")"; PROG="${PROG:-0}"
    printf 'CODE_OVERSIZED_BASELINE: %s\n' "$PROG"
    if [ "$DUZYCH" -gt "$PROG" ]; then
        printf '\n❌ REGRESJA rozmiaru: %s > %s modułów powyżej %s linii.\n' "$DUZYCH" "$PROG" "$MAX_LINII" >&2
        STATUS=1
    elif [ "$DUZYCH" -lt "$PROG" ]; then
        printf '\n✅ POSTĘP: %s < %s — zaktualizuj baseline w tym samym commicie\n' "$DUZYCH" "$PROG"
    fi
else
    printf 'CODE_OVERSIZED_BASELINE: brak (tryb raportowy dla rozmiaru)\n'
fi
exit "$STATUS"
