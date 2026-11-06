#!/usr/bin/env bash
# Sztuczna bramka nr 3 — sam werdykt, bez mianownika.
#
# Bez liczby obejrzanych rzeczy nie da się sprawdzić ani warunku „zero na
# zielono", ani rozjazdu z drugim źródłem — dlatego brak mianownika jest
# porażką, a nie brakiem ozdoby. gate-selfcheck.sh ma to odrzucić.
set -uo pipefail
printf 'Sprawdzone. Wszystko w porzadku.\n'
exit 0
