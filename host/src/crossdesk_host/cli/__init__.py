"""crossdesk CLI subcommand modules."""

from crossdesk_host.cli import (
    apps_cmd,
    credentials_cmd,
    doctor_cmd,
    install_cmd,
    main,
    metrics_cmd,
    uninstall_cmd,
    version_cmd,
)

__all__ = [
    "apps_cmd",
    "credentials_cmd",
    "doctor_cmd",
    "install_cmd",
    "main",
    "metrics_cmd",
    "uninstall_cmd",
    "version_cmd",
]
