"""Desktop-environment integrations.

Each subpackage exposes an abstraction Protocol plus one or more
concrete implementations:

- :mod:`keyring` — KWallet (KDE) / libsecret (GNOME) / file (fallback)
  / mock (tests). Stores VM credentials securely under a desktop-managed
  vault when possible.
- :mod:`portal` — ``org.freedesktop.portal.OpenURI`` so MIME-routed
  files end up in the right Windows app even from sandboxed callers.
- :mod:`mime` — register MIME associations + ``.desktop`` actions on
  install; deregister on uninstall.
- :mod:`notifications` — native ``org.freedesktop.Notifications``
  (replaces the ``notify-send`` shell-out shipped in Week 11) with
  action buttons + urgency support.

Mac dev: every backend ships a Null implementation that compiles
cleanly and silently no-ops, so the Manager / daemon code path
never branches on platform.
"""
