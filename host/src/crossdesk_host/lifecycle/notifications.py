"""User-facing notification surface.

Wraps ``org.freedesktop.Notifications.Notify`` via ``notify-send``
(the universally-available CLI shim) so the host can surface
non-fatal but visible errors — VM won't start, RDP dropped, lifecycle
suspend/resume failure — to the user without opening a terminal.

The Protocol-based design lets tests substitute a recording mock that
captures every call without touching D-Bus. Real installs use
:class:`SubprocessNotifier`, which is a thin wrapper around
``notify-send`` and silently no-ops when the binary isn't on PATH
(headless servers, CI, Mac dev).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Protocol


class Urgency(Enum):
    LOW = "low"
    NORMAL = "normal"
    CRITICAL = "critical"


@dataclass(frozen=True)
class NotificationCall:
    """Materialised payload of one notify() invocation. Tests assert
    on the recorded list rather than spying through D-Bus."""

    summary: str
    body: str
    urgency: Urgency
    icon: str
    category: str


class Notifier(Protocol):
    def notify(
        self,
        summary: str,
        body: str = "",
        urgency: Urgency = Urgency.NORMAL,
        icon: str = "",
        category: str = "",
    ) -> None: ...


class SubprocessNotifier(Notifier):
    """Real implementation that shells out to ``notify-send``.

    Each call is best-effort: a missing binary or a non-zero exit
    silently does nothing. We deliberately don't raise — a failed
    notification mustn't take down the host daemon.
    """

    def __init__(self, app_name: str = "CrossDesk") -> None:
        self.app_name = app_name

    def notify(
        self,
        summary: str,
        body: str = "",
        urgency: Urgency = Urgency.NORMAL,
        icon: str = "",
        category: str = "",
    ) -> None:
        if shutil.which("notify-send") is None:
            return
        argv = ["notify-send", "--app-name", self.app_name, "-u", urgency.value]
        if icon:
            argv.extend(["-i", icon])
        if category:
            argv.extend(["-c", category])
        argv.append(summary)
        if body:
            argv.append(body)
        try:
            subprocess.run(argv, check=False, capture_output=True, timeout=2.0)
        except (subprocess.SubprocessError, OSError):
            return


@dataclass
class RecordingNotifier(Notifier):
    """Test double — appends each notify() to ``calls``. Use in unit
    tests that want to assert the host surfaced a particular error
    without inspecting D-Bus or spawning a subprocess."""

    calls: List[NotificationCall] = field(default_factory=list)

    def notify(
        self,
        summary: str,
        body: str = "",
        urgency: Urgency = Urgency.NORMAL,
        icon: str = "",
        category: str = "",
    ) -> None:
        self.calls.append(
            NotificationCall(
                summary=summary,
                body=body,
                urgency=urgency,
                icon=icon,
                category=category,
            )
        )
