"""crossdesk install pipeline.

Pure-Python install orchestration. Subpackages:

- :mod:`state`  — atomic per-step persistence under ``~/.local/state``.
- :mod:`credentials` — vm.toml read/write + 0600 permissions.
- :mod:`iso_downloader` — Fido-style ISO fetch with SHA-256 gate.

The CLI wiring lives in :mod:`crossdesk_host.cli`.
"""

from crossdesk_host.installer import credentials, iso_downloader, state

__all__ = ["credentials", "iso_downloader", "state"]
