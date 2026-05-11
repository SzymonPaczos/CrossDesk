"""``crossdesk launch <app-id>`` — start a registered Windows app as a RAIL window.

Checks whether the CrossDesk daemon is reachable (via its management
Unix socket), sends a desktop notification, and logs a Phase 4 stub
message where the actual RAIL session launch will land.

Why socket-exists instead of a gRPC ping: a socket-exists check is
instant and avoids importing the gRPC stack just to surface a "daemon
not running" message. A missing socket is definitive — the daemon
always creates it at startup.

Phase 4 wiring: the actual ``OpenSession`` call lives in
``host/src/crossdesk_host/display/rail_manager.py`` (and its
``spawn_rail`` path). When Phase 4 is ready, replace the stub log
below with a call into that module.
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys
from typing import Optional

from crossdesk_host.i18n import _
from crossdesk_host.ipc.management import mgmt_socket_path
from crossdesk_host.lifecycle.notifications import SubprocessNotifier

logger = logging.getLogger(__name__)

# Lightweight name lookup so common app IDs surface a friendlier label
# in notifications without requiring a full catalog load. The curated
# catalog (crossdesk_host.catalog.load_curated) is the authoritative
# source; this table covers the most common IDs for when the catalog
# file is absent (dev checkout, non-standard install path).
_KNOWN_NAMES: dict[str, str] = {
    "word": "Microsoft Word",
    "excel": "Microsoft Excel",
    "powerpoint": "Microsoft PowerPoint",
    "outlook": "Microsoft Outlook",
    "onenote": "Microsoft OneNote",
    "access": "Microsoft Access",
    "visio": "Microsoft Visio",
    "teams": "Microsoft Teams",
    "notepad": "Notepad",
    "paint": "Paint",
    "calc": "Calculator",
    "explorer": "File Explorer",
    "cmd": "Command Prompt",
    "powershell": "PowerShell",
    "regedit": "Registry Editor",
    "taskmgr": "Task Manager",
    "mspaint": "Paint",
    "wordpad": "WordPad",
    "winword": "Microsoft Word",
}


def _resolve_display_name(app_id: str) -> str:
    """Return a human-readable name for *app_id*.

    Lookup order:
    1. Curated catalog (``infra/apps/curated.toml``) — authoritative.
    2. Static fallback table (covers the most common IDs without I/O).
    3. ``app_id.title()`` — guaranteed non-empty last resort.
    """
    try:
        from crossdesk_host.catalog.curated import load_curated

        for entry in load_curated():
            if entry.id == app_id:
                return entry.display_name
    except Exception:
        # Catalog load is best-effort; a missing file or parse error
        # must not abort a launch request.
        pass

    return _KNOWN_NAMES.get(app_id, app_id.title())


def add_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("launch", help="Launch a registered Windows app as a RAIL window")
    p.add_argument("app", metavar="APP_ID", help="App identifier (e.g. notepad, word)")
    p.add_argument(
        "file",
        nargs="?",
        default=None,
        metavar="FILE",
        help="Optional file to open with the app",
    )


def run(args: argparse.Namespace) -> int:
    """Entry point called by ``main.main()``."""
    notifier: Optional[SubprocessNotifier] = getattr(args, "_notifier", None)
    if notifier is None:
        notifier = SubprocessNotifier(app_name="CrossDesk")

    return _launch(
        app_id=args.app,
        notifier=notifier,
    )


def _launch(
    app_id: str,
    *,
    notifier: SubprocessNotifier,
    _socket_path_override: Optional[str] = None,
) -> int:
    """Core launch logic, extracted for testability.

    Parameters
    ----------
    app_id:
        The app identifier passed on the CLI.
    notifier:
        A :class:`~crossdesk_host.lifecycle.notifications.Notifier`
        implementation (``SubprocessNotifier`` in production,
        ``RecordingNotifier`` in tests).
    _socket_path_override:
        Pin the management socket path in unit tests rather than
        resolving via ``XDG_RUNTIME_DIR``.
    """
    display_name = _resolve_display_name(app_id)

    # Daemon check: a missing socket means the daemon is not running.
    # We check existence only — connecting would require the gRPC stack
    # and is overkill for a "is anything listening?" gate.
    sock = _socket_path_override or str(mgmt_socket_path())
    if not pathlib.Path(sock).exists():
        print(
            _("VM not running. Start it with: crossdesk vm start"),
            file=sys.stderr,
        )
        return 1

    # Notify the user before kicking off the (eventually async) launch
    # so feedback is immediate even if RAIL setup takes a moment.
    notifier.notify(
        summary="CrossDesk",
        body=_("Starting {name}…").format(name=display_name),
    )

    # Phase 4 stub — the real path calls RailManager.spawn_rail() which
    # sends an OpenSession RPC to the daemon and monitors the RAIL window
    # lifecycle. Wired in the Phase 4 milestone (display/ module).
    logger.info(
        "\U0001f6a7 RAIL session launch stub — Phase 4 not yet wired, app=%s",
        app_id,
    )

    print(_("Launching {name}… (VM must be running)").format(name=display_name))
    return 0
