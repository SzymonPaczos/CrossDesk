#!/usr/bin/env bash
# Source this file after taking a class lock. Release before waiting for another class.
# The caller owns traps: stop the child process group before releasing its slot.
HS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
HS_HELPER="$HS_DIR/heavy-slot.py"
HS_MAYBE=0

hs_take() {
  local class=$1 desc=$2 start=$SECONDS token rc
  local max=${GATE_MAX_WAIT_SECONDS:-3600} poll=${GATE_POLL_SECONDS:-5} next=0
  case $max in ''|*[!0-9]*) return 4 ;; esac
  [ -f "$HS_HELPER" ] || { echo 'heavy-slot: brak pomocnika – bieg zablokowany' >&2; return 4; }
  [ "$HS_MAYBE" = 1 ] && return 0
  if [ -n "${GATE_HEAVY_SLOT:-}" ]; then
    if python3 -I "$HS_HELPER" check --token "$GATE_HEAVY_SLOT"; then return 0; fi
    unset GATE_HEAVY_SLOT
  fi
  HS_MAYBE=1
  while :; do
    rc=0
    token=$(python3 -I "$HS_HELPER" try --holder "$$" --class "$class" --desc "$desc") || rc=$?
    case $rc in
      0) export GATE_HEAVY_SLOT="$token"; return 0 ;;
      1) ;;
      *) hs_release; return 4 ;;
    esac
    if [ $((SECONDS - start)) -ge "$next" ]; then
      echo "heavy-slot: oczekiwanie na slot ($desc)" >&2
      next=$((SECONDS - start + 60))
    fi
    if [ "$max" -gt 0 ] && [ $((SECONDS - start)) -ge "$max" ]; then
      hs_release
      return 124
    fi
    sleep "$poll" || { hs_release; return 4; }
  done
}

hs_release() {
  [ "$HS_MAYBE" = 1 ] || return 0
  HS_MAYBE=0
  unset GATE_HEAVY_SLOT
  python3 -I "$HS_HELPER" release --holder "$$"
}
