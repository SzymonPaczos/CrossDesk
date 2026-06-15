"""``crossdesk launch <app-id>`` — start a registered Windows app as a RAIL window.

Flow: check the daemon is reachable (its management Unix socket exists),
send a desktop notification, then call the management ``Launch`` RPC over
that socket. The daemon resolves the app, gates on the guest credential
check, and spawns the FreeRDP RAIL session (see
``crossdesk_host.ipc.management.ManagementServiceServicer.Launch``).

Why a socket-exists check before the RPC: it's instant and gives a clean
"VM not running" message (with a GUI nudge) without paying the gRPC import
on the common down-path. A missing socket is definitive — the daemon
always creates it at startup.

The actual RAIL window only appears once a guest with an RDP server is
running; without it the daemon's Launch returns ``ok=false`` and we print
the daemon's error (e.g. "no guest session connected"). The host-side
wiring is exercised end-to-end against a mock FreeRDP in the in-process
test harness.
"""

from __future__ import annotations

import argparse
import logging
import os
import pathlib
import shutil
import subprocess
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


def _gui_is_running() -> bool:
    """Best-effort check whether ``crossdesk-gui`` is already running.

    Used by the daemon-offline branch in :func:`_launch` so repeated
    invocations (Dolphin's "Open in Windows app", an ms-word:// URL
    handler, etc.) don't pile up a desktop-notification storm or a
    stack of duplicate GUI windows.

    Returns ``True`` if pgrep finds a matching process for the current
    user. Returns ``False`` on any error — better to spawn a (possibly
    second) GUI than to suppress feedback entirely.
    """
    pgrep = shutil.which("pgrep")
    if pgrep is None:
        return False
    try:
        result = subprocess.run(
            [pgrep, "-u", str(os.getuid()), "-x", "crossdesk-gui"],
            capture_output=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _spawn_gui() -> bool:
    """Spawn ``crossdesk-gui`` detached from the current process.

    Returns ``True`` if the spawn was attempted (binary exists on PATH).
    Returns ``False`` if the binary is missing — the caller should fall
    back to the stderr message so the user has some signal.
    """
    if shutil.which("crossdesk-gui") is None:
        return False
    try:
        subprocess.Popen(
            ["crossdesk-gui"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True


def _resolve_display_name(app_id: str) -> str:
    """Return a human-readable name for *app_id*.

    Lookup order:
    1. Curated catalog (``infra/apps/curated.toml``) — authoritative.
    2. Static fallback table (covers the most common IDs without I/O).
    3. ``app_id.title()`` — guaranteed non-empty last resort.
    """
    # A raw Windows .exe path: use the executable's base name, not the whole
    # path, as the friendly label (e.g. C:\Games\RobinHood\RobinHood.exe →
    # "RobinHood").
    if ":" in app_id and ("\\" in app_id or "/" in app_id):
        import re

        base = re.split(r"[\\/]", app_id.strip())[-1]
        return base[:-4] if base.lower().endswith(".exe") else base

    try:
        from crossdesk_host.catalog.curated import load_curated

        for entry in load_curated():
            if entry.id == app_id:
                return entry.display_name
    except Exception:
        # Catalog load is best-effort; a missing file or parse error
        # must not abort a launch request.
        pass  # nosec B110 — intentional best-effort, see comment above

    return _KNOWN_NAMES.get(app_id, app_id.title())


class _LaunchError(RuntimeError):
    """Daemon RPC could not be completed (connection refused, timeout,
    transport error). Carries a user-facing message."""


def _send_launch(sock: str, app_id: str, file_path: Optional[str], *, timeout: float = 10.0) -> object:
    """Call the management ``Launch`` RPC over the daemon's Unix socket.

    Returns the ``LaunchResponse``. The gRPC stack is imported lazily here
    so the daemon-down path (and ``--help``) don't pay for it. Wraps any
    ``grpc.RpcError`` in :class:`_LaunchError` so the caller maps it to a
    clean stderr message + exit code.
    """
    import grpc

    from crossdesk_host.proto.crossdesk.v1 import mgmt_pb2, mgmt_pb2_grpc

    request = mgmt_pb2.LaunchRequest(app_id=app_id, file_path=file_path or "")
    try:
        with grpc.insecure_channel(f"unix://{sock}") as channel:
            stub = mgmt_pb2_grpc.ManagementServiceStub(channel)
            return stub.Launch(request, timeout=timeout)
    except grpc.RpcError as exc:
        detail = exc.details() if hasattr(exc, "details") else str(exc)
        raise _LaunchError(detail or str(exc)) from exc


def add_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("launch", help="Launch a Windows app as a RAIL window")
    p.add_argument(
        "app",
        metavar="APP",
        help=(
            "Catalog app id (e.g. notepad, word) OR a Windows .exe path to "
            r"launch any installed program (e.g. 'C:\\Games\\Game\\game.exe')"
        ),
    )
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
        file_path=args.file,
        notifier=notifier,
    )


def _launch(
    app_id: str,
    *,
    file_path: Optional[str] = None,
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
        msg = _("VM not running. Start it with: crossdesk vm start")
        print(msg, file=sys.stderr)
        # Previously this fired notify_vm_failed_to_start(), which spammed
        # the desktop notification tray every time Dolphin's
        # "Open in Windows app" or an ms-word:// URL handler invoked us
        # while the daemon was down. Instead: open the GUI so the user
        # has one window to start the VM from, and skip spawning if a
        # GUI is already up.
        if not _gui_is_running():
            _spawn_gui()
        return 1

    # Notify the user before kicking off the (eventually async) launch
    # so feedback is immediate even if RAIL setup takes a moment.
    notifier.notify(
        summary="CrossDesk",
        body=_("Starting {name}…").format(name=display_name),
    )

    # Drive the real RAIL spawn through the daemon's management Launch RPC.
    try:
        response = _send_launch(sock, app_id, file_path)
    except _LaunchError as exc:
        print(_("Launch failed: {err}").format(err=exc), file=sys.stderr)
        return 1

    if not getattr(response, "ok", False):
        print(
            _("Launch failed: {err}").format(err=getattr(response, "error", "")),
            file=sys.stderr,
        )
        return 1

    print(_("Launching {name}…").format(name=display_name))
    return 0
