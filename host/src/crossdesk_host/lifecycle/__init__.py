"""Host suspend/resume lifecycle coordination.

Pure logic in :mod:`crossdesk_host.lifecycle.coordinator`; the Linux-
specific D-Bus wiring is in :mod:`crossdesk_host.lifecycle.dbus_listener`
and only imported on demand because ``dbus-next`` is a Linux extra.
"""

from crossdesk_host.lifecycle.coordinator import LifecycleCoordinator

__all__ = ["LifecycleCoordinator"]
