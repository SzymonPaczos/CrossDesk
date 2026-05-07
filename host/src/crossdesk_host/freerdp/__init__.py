"""FreeRDP subprocess invocation per DEC-0005.

`real` spawns `xfreerdp` (with a documented version fallback chain
matching docs/EXECUTION_PLAN.md Week 8); `mock` records argv to a
list and never spawns anything.
"""
