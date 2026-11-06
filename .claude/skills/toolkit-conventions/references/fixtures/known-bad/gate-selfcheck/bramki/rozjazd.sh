#!/usr/bin/env bash
# Sztuczna bramka nr 2 — mianownik niezerowy, ale rozjechany z drugim źródłem.
#
# Odtwarza awarię bramki sesji: „obejrzałem 9 tras" przy dwudziestu
# zadeklarowanych. Liczba jest prawdziwa względem własnego przejścia
# i fałszywa względem rzeczywistości. gate-selfcheck.sh ma to odrzucić.
set -uo pipefail
CEL="${1:-.}"
WSZYSTKICH="$(git -C "$CEL" ls-files -- '*.py' 2>/dev/null | grep -c . || true)"
printf 'FAKE_TOTAL: %s\n' "$(( WSZYSTKICH > 1 ? WSZYSTKICH - 1 : 0 ))"
printf 'FAKE_VIOLATIONS: 0\n'
exit 0
