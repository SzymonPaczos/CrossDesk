"""crossdesk CLI subcommand modules."""

from crossdesk_host.cli import (
    credentials_cmd,
    doctor_cmd,
    install_cmd,
    main,
    uninstall_cmd,
)

__all__ = [
    "credentials_cmd",
    "doctor_cmd",
    "install_cmd",
    "main",
    "uninstall_cmd",
]
