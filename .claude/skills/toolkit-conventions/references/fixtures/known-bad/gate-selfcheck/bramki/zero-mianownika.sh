#!/usr/bin/env bash
# Sztuczna bramka nr 1 — mianownik zero przy kodzie wyjścia 0.
#
# Odtwarza awarię „collected: 0 tests" i „ruff 0 naruszeń na zepsutej
# konfiguracji": narzędzie nie wystartowało albo szukało nie tam, a wynik
# wygląda jak czysty przebieg. gate-selfcheck.sh ma to odrzucić.
set -uo pipefail
printf 'FAKE_TOTAL: 0\n'
printf 'FAKE_VIOLATIONS: 0\n'
exit 0
