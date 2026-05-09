"""App catalog (Phase 8).

Three tiers feed the Manager's Apps pane:

- :class:`CuratedApp` entries from ``infra/apps/curated.toml`` —
  hand-tested, ship with the host package.
- ``DiscoveredApp`` entries from the guest-side registry scanner
  (lives in ``guest/crates/registry-scan``); enumerated on demand.
- ``UserApp`` entries the user adds via the GUI (`+ Add custom .exe`)
  or the CLI (``crossdesk apps add ...``).

This module wires the *host-side* tiers — curated loader and user
loader. The discovery tier is fronted by the daemon's
``mgmt.ListDiscoveredApps`` RPC which forwards to the guest agent.
"""

from crossdesk_host.catalog.curated import CuratedApp, load_curated
from crossdesk_host.catalog.ratings import (
    Rating,
    average_rating,
    load_ratings,
)
from crossdesk_host.catalog.user_apps import UserApp, load_user_apps, save_user_app

__all__ = [
    "CuratedApp",
    "Rating",
    "UserApp",
    "average_rating",
    "load_curated",
    "load_ratings",
    "load_user_apps",
    "save_user_app",
]
