#!/usr/bin/env bash
# Zadanie CI wykonało pracę albo zawiodło — `conventions/ci-pipeline-architecture.md` §5.
#
# Job kończący się powodzeniem w siedem sekund, bo brak sekretu wyłączył
# wszystkie jego kroki warunkiem `if:`, jest w raporcie nieodróżnialny od joba,
# który przebiegł i było czysto. Mapa wdrożenia policzyła taki job do jedenastu
# zielonych; log samego joba pisał wprost, że niczego nie dowodzi.
#
# To jest reguła mianownika (`rules-as-gates.md` §15) przeniesiona o poziom
# wyżej: **mianownikiem joba jest liczba kroków, które faktycznie się wykonały**,
# a zero przy zielonym wyniku jest porażką tak samo jak zero zebranych testów.
#
# Pięć naruszeń, wszystkie blokujące:
#   1. job, w którym KAŻDY krok stoi pod warunkiem, i żaden krok nie umie
#      zawieść przy niespełnionym warunku — może zzielenieć nic nie zrobiwszy;
#   2. `continue-on-error: true` — krok bramkowy, który nie umie przewrócić joba;
#   3. wymuszanie sukcesu w treści kroku (`|| true` na końcu, `--exit-zero`,
#      `|| :`) — kod wyjścia przestaje być werdyktem;
#   4. `git diff --exit-code` bez `HEAD` na generacie — porównanie idzie wtedy
#      z INDEKSEM, więc `git add` ucisza strażnika, a kontrakt w commicie
#      zostaje nieaktualny;
#   5. tryb nagrywania w środowisku bramki (`*_RECORD=1`, `*UPDATE_SNAPSHOT*`) —
#      to jest tryb człowieka odświeżającego baseline, nigdy tryb bramki:
#      zamienia suitę w zieloną z konstrukcji.
#
# Sygnały maszynowe:
#   CI_STEPS                  ile kroków obejrzano                 (mianownik)
#   CI_JOBS                   ile zadań
#   CI_JOBS_ALL_CONDITIONAL   zadania mogące zzielenieć bez pracy — blokuje
#   CI_CONTINUE_ON_ERROR      kroki i zadania, które nie umieją zawieść — blokuje
#   CI_FORCED_SUCCESS         wymuszony kod wyjścia zero — blokuje
#   CI_DIFF_WITHOUT_HEAD      strażnik generatu porównujący z indeksem — blokuje
#   CI_RECORDING_MODE         tryb nagrywania w środowisku bramki — blokuje
#
# Użycie: ci-effective-work.sh [--format text|signals] [ŚCIEŻKA]
# Kody wyjścia: 0 = czysto, 1 = naruszenie blokujące, 2 = błąd użycia.
set -uo pipefail

FORMAT=text
CEL=.
while [ $# -gt 0 ]; do
    case "$1" in
        --format) FORMAT="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,38p' "$0"; exit 0 ;;
        -*) printf 'nieznana opcja: %s\n' "$1" >&2; exit 2 ;;
        *)  CEL="$1"; shift ;;
    esac
done
cd "$CEL" 2>/dev/null || { printf 'nie ma katalogu: %s\n' "$CEL" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { printf 'to nie repozytorium git: %s\n' "$CEL" >&2; exit 2; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

git ls-files -- '.github/workflows/*.yml' '.github/workflows/*.yaml' 2>/dev/null | sort -u > "$TMP/pliki"
PLIKOW="$(grep -c . "$TMP/pliki" || true)"
if [ "$PLIKOW" -eq 0 ]; then
    printf 'CI_STEPS: n/a — git nie zna w tym repozytorium plików workflow\n'
    exit 0
fi
command -v python3 >/dev/null 2>&1 || {
    printf 'CI_STEPS: n/a — brak python3, workflow nie da się rozebrać\n'
    printf 'Brak narzędzia to `n/a`, nigdy zero ustaleń (rules-as-gates.md §11).\n' >&2
    exit 2
}

python3 - "$TMP/pliki" "$TMP/wynik" <<'PYEOF'
import re, sys

pliki = [l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip()]

WYMUSZONY = re.compile(r"\|\|\s*(true|:)\s*$|--exit-zero|\bexit\s+0\s*#\s*ignor")
NAGRYWANIE = re.compile(r"^\s*[A-Z0-9_]*(RECORD|UPDATE_SNAPSHOT|SNAPSHOT_UPDATE|REGEN)[A-Z0-9_]*:\s*[\"']?([^\"'\s#]+)")
DIFF = re.compile(r"git\s+diff[^\n]*--exit-code")

kroków = 0
zadan = 0
warunkowe_zadania = []
continue_on_error = []
wymuszone = []
diff_bez_head = []
nagrywanie = []

def wciecie(linia):
    return len(linia) - len(linia.lstrip())

for sciezka in pliki:
    try:
        linie = open(sciezka, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        continue

    w_jobs = False
    biezacy_job = None
    job_kroki = 0
    job_bezwarunkowe = 0
    job_ma_odmowe = False
    job_linia = 0

    def zamknij_job():
        # Job, w którym KAŻDY krok stoi pod warunkiem i nic nie umie zawieść
        # przy niespełnionym warunku, kończy się sukcesem nie wykonawszy nic.
        if biezacy_job and job_kroki > 0 and job_bezwarunkowe == 0 and not job_ma_odmowe:
            warunkowe_zadania.append("%s:%d\t%s — %d kroków, każdy pod warunkiem, żaden nie odmawia"
                                     % (sciezka, job_linia, biezacy_job, job_kroki))

    for nr, linia in enumerate(linie, start=1):
        goly = linia.strip()
        if goly.startswith("#") or not goly:
            continue

        if re.match(r"^jobs:\s*$", linia):
            w_jobs = True
            continue

        nazwa_joba = re.match(r"^  ([A-Za-z_][A-Za-z0-9_.-]*):\s*$", linia)
        if w_jobs and nazwa_joba:
            zamknij_job()
            biezacy_job = nazwa_joba.group(1)
            zadan += 1
            job_kroki = 0
            job_bezwarunkowe = 0
            job_ma_odmowe = False
            job_linia = nr
            krok_wciecie = None
            continue

        # Początek kroku: element listy z `name`, `uses`, `run` albo `id`.
        if re.match(r"^\s+- (name|uses|run|id):", linia):
            kroków += 1
            job_kroki += 1
            krok_wciecie = wciecie(linia)
            ma_warunek = False
            # Warunek kroku stoi w jego bloku, więc czytamy do przodu.
            for dalej in linie[nr:]:
                if not dalej.strip() or dalej.strip().startswith("#"):
                    continue
                if wciecie(dalej) <= krok_wciecie:
                    break
                if re.match(r"^\s+if:", dalej):
                    ma_warunek = True
                    break
            if not ma_warunek:
                job_bezwarunkowe += 1
            continue

        if re.search(r"^\s*continue-on-error:\s*true", linia):
            continue_on_error.append("%s:%d\t%s" % (sciezka, nr, goly))
        if WYMUSZONY.search(linia):
            wymuszone.append("%s:%d\t%s" % (sciezka, nr, goly[:80]))
        if DIFF.search(linia) and not re.search(r"--exit-code\s+HEAD|diff\s+HEAD", linia):
            diff_bez_head.append("%s:%d\t%s" % (sciezka, nr, goly[:80]))
        m = NAGRYWANIE.match(linia)
        if m and m.group(2) not in ("0", "false", "no", ""):
            nagrywanie.append("%s:%d\t%s" % (sciezka, nr, goly[:80]))
        # Krok, który sam odmawia przy braku warunku wstępnego, ratuje job.
        if re.search(r"\bexit\s+1\b", linia):
            job_ma_odmowe = True

    zamknij_job()

with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write("STEPS %d\nJOBS %d\nALLCOND %d\nCOE %d\nFORCED %d\nDIFF %d\nRECORD %d\n"
            % (kroków, zadan, len(warunkowe_zadania), len(continue_on_error),
               len(wymuszone), len(diff_bez_head), len(nagrywanie)))
    for etykieta, lista in (("ALLCOND", warunkowe_zadania), ("COE", continue_on_error),
                            ("FORCED", wymuszone), ("DIFF", diff_bez_head), ("RECORD", nagrywanie)):
        for l in lista:
            f.write("%s\t%s\n" % (etykieta, l))
PYEOF

odczyt() { awk -v k="$1" '$1==k {print $2}' "$TMP/wynik" | head -1; }
KROKOW="$(odczyt STEPS)"; ZADAN="$(odczyt JOBS)"
ALLCOND="$(odczyt ALLCOND)"; COE="$(odczyt COE)"
FORCED="$(odczyt FORCED)"; DIFFH="$(odczyt DIFF)"; RECORD="$(odczyt RECORD)"

if [ "$FORMAT" = text ]; then
    printf 'Workflow: %s plików, %s zadań, %s kroków\n\n' "$PLIKOW" "$ZADAN" "$KROKOW"
    for para in "ALLCOND|Zadania, które mogą zzielenieć nie wykonawszy niczego" \
                "COE|Kroki i zadania, które nie umieją przewrócić przebiegu" \
                "FORCED|Wymuszony kod wyjścia zero" \
                "DIFF|Strażnik generatu porównujący z indeksem, nie z commitem" \
                "RECORD|Tryb nagrywania w środowisku bramki"; do
        klucz="${para%%|*}"; opis="${para#*|}"
        if awk -F'\t' -v k="$klucz" '$1==k && NF>1' "$TMP/wynik" | grep -q .; then
            printf '%s:\n\n' "$opis"
            awk -F'\t' -v k="$klucz" '$1==k && NF>1 {printf "  ❌ %-34s %s\n", $2, $3}' "$TMP/wynik" | head -10
            printf '\n'
        fi
    done
fi

printf 'CI_STEPS: %s\n' "$KROKOW"
printf 'CI_JOBS: %s\n' "$ZADAN"
printf 'CI_JOBS_ALL_CONDITIONAL: %s\n' "$ALLCOND"
printf 'CI_CONTINUE_ON_ERROR: %s\n' "$COE"
printf 'CI_FORCED_SUCCESS: %s\n' "$FORCED"
printf 'CI_DIFF_WITHOUT_HEAD: %s\n' "$DIFFH"
printf 'CI_RECORDING_MODE: %s\n' "$RECORD"

if [ "${KROKOW:-0}" -eq 0 ]; then
    printf '\n❌ %s plików workflow i zero rozpoznanych kroków. Zero obejrzanych rzeczy przy\n' "$PLIKOW" >&2
    printf '   zielonym wyniku znaczy, że rozbiór nie trafił w kształt tych plików.\n' >&2
    exit 1
fi
SUMA=$(( ${ALLCOND:-0} + ${COE:-0} + ${FORCED:-0} + ${DIFFH:-0} + ${RECORD:-0} ))
if [ "$SUMA" -gt 0 ]; then
    printf '\n❌ %s zadań lub kroków może zameldować sukces, nie wykonawszy pracy albo nie\n' "$SUMA" >&2
    printf '   pozwalając sobie zawieść. Brak sekretu na własnej gałęzi ma być kodem wyjścia 1,\n' >&2
    printf '   a nie pominięciem — job, który melduje sukces bez przebiegu, produkuje zdanie\n' >&2
    printf '   „wszystko zielone" na pusto.\n' >&2
    printf '   Czym to sprawdzić: `templates/ci-effective-work.sh --format text`\n' >&2
    exit 1
fi
exit 0
