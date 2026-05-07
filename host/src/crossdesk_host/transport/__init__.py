"""Transport implementations per DEC-0005.

``real`` provides the production transport (vsock on Linux, TCP loopback
on macOS/Windows during dev). ``mock`` provides a deterministic TCP
loopback transport with failure-injection hooks for tests.
"""
