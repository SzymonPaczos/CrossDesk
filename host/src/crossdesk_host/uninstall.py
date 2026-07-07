"""crossdesk uninstall.

Idempotent removal of every artefact a normal install creates:
- libvirt domain ``windows-guest`` (destroy + undefine)
- ``~/.local/share/applications/crossdesk-*.desktop``
- cached ISO under ``~/.cache/crossdesk/iso/``
- install state under ``~/.local/state/crossdesk/`` (includes the VM disk)
- credential file ``~/.config/crossdesk/vm.toml`` (unless ``--keep-config``)

Each step is wrapped in a try/except so a partially-installed system
can still be cleaned up — uninstall must succeed end-to-end even when
the install never finished. Steps that touch the live system
(libvirt domain delete, cached ISO size up to ~6 GB) get a dry-run
mode for testing without side effects.

The libvirt domain is torn down through a ``LibvirtController`` the caller
passes in (the CLI resolves the real, Linux-only one; tests pass a mock), so
this module stays import-clean on non-Linux dev hosts. It runs *first* so the
guest isn't holding its disk open when the state directory is removed.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.config import user_cache_dir, user_config_dir, user_state_dir


@dataclass
class UninstallReport:
    removed: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)


def _rm_path(path: Path, dry_run: bool, report: UninstallReport, label: str) -> None:
    if not path.exists():
        report.skipped.append(f"{label}: {path} not present")
        return
    if dry_run:
        report.removed.append(f"{label}: would remove {path}")
        return
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        report.removed.append(f"{label}: {path}")
    except OSError as exc:
        report.failed.append(f"{label}: {path}: {exc}")


def _rm_glob(
    parent: Path, pattern: str, dry_run: bool, report: UninstallReport, label: str
) -> None:
    if not parent.exists():
        report.skipped.append(f"{label}: {parent} not present")
        return
    matched = list(parent.glob(pattern))
    if not matched:
        report.skipped.append(f"{label}: no matches for {pattern} in {parent}")
        return
    for entry in matched:
        _rm_path(entry, dry_run, report, label)


def _rm_domain(
    ctl: LibvirtController, dry_run: bool, report: UninstallReport
) -> None:
    label = "libvirt_domain"
    if dry_run:
        report.removed.append(f"{label}: would destroy + undefine")
        return
    try:
        ctl.undefine()
        report.removed.append(f"{label}: destroyed + undefined")
    except RuntimeError as exc:
        report.failed.append(f"{label}: {exc}")


def uninstall(
    home: Path | None = None,
    keep_config: bool = False,
    dry_run: bool = False,
    libvirt_ctl: Optional[LibvirtController] = None,
) -> UninstallReport:
    h = home or Path.home()
    report = UninstallReport()

    # Domain first: destroy + undefine before removing the state dir that holds
    # its disk. ``None`` (file-only callers / older tests) skips this step.
    if libvirt_ctl is not None:
        _rm_domain(libvirt_ctl, dry_run, report)

    _rm_glob(
        h / ".local" / "share" / "applications",
        "crossdesk-*.desktop",
        dry_run,
        report,
        "desktop_files",
    )
    _rm_path(
        user_cache_dir(h),
        dry_run,
        report,
        "iso_cache",
    )
    _rm_path(
        user_state_dir(h),
        dry_run,
        report,
        "install_state",
    )
    if not keep_config:
        _rm_path(
            user_config_dir(h),
            dry_run,
            report,
            "config",
        )
    else:
        report.skipped.append("config: --keep-config")

    return report
