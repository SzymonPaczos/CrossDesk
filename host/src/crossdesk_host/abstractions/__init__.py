"""Cross-language abstraction Protocols per DEC-0005.

Each Linux-or-Windows-only dependency has its `Protocol` defined here so
production code parameterises over it and tests pass mock implementations
that enforce the same invariants.
"""
