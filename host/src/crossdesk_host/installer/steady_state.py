"""Post-install steady-state finalize.

A fresh ``crossdesk install`` defines the libvirt domain with the Windows
install ISO on ``<boot order='1'>`` — and leaves it there for the VM's whole
life. That is the data-loss trap (P0): a later ``hard_destroy`` (the
heartbeat-FSM recovery = ``destroy`` + ``create`` against the *persistent*
config) re-boots the installer, and ``autounattend.xml`` reinstalls Windows
over the disk. The fix is to redefine the domain to a steady state (installed
disk on ``<boot order='1'>``, both CD-ROMs ejected) once the agent proves the
install finished — i.e. after the first successful agent Hello.

The install and the redefine happen in two different processes: the install
CLI exits long before the guest finishes installing and the agent connects
(~12 min later), and it is the daemon that owns the live control-plane session.
So the install *persists* the steady-state XML next to the install state
(:func:`persist_steady_state_xml`), and the daemon runs :func:`finalize_steady_state`
on the first Hello. The finalize is idempotent — it marks a ``steady_state``
step ``done`` in ``install.state.json`` and no-ops thereafter — and retries on a
later reconnect if the redefine failed, so a transient libvirt error doesn't
leave the trap armed.

Decoupling the XML through a file (rather than rebuilding it in the daemon)
keeps the daemon out of the ``DomainSpec`` business: the install already knows
the disk path / ISOs / firmware, writes the exact steady-state XML, and the
daemon just applies it. ``redefine_steady_state`` injects the live domain's
UUID at apply time so ``defineXML`` updates the config in place.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal, Optional

from crossdesk_host.abstractions.libvirt import LibvirtController
from crossdesk_host.installer import state
from crossdesk_host.installer.domain_xml import (
    DomainSpec,
    build_steady_state_domain_xml,
)
from crossdesk_host.utils import atomic_write

logger = logging.getLogger(__name__)

STEADY_STATE_XML_FILENAME = "steady-state.xml"
STEADY_STATE_STEP = "steady_state"

FinalizeResult = Literal["applied", "already", "absent", "error"]
"""Outcome of a :func:`finalize_steady_state` call:

- ``applied`` — the redefine ran and the step is now marked done.
- ``already`` — the step was already done; nothing to do (idempotent).
- ``absent`` — no steady-state XML to apply (not a fresh install; e.g. a dev
  daemon that never ran ``crossdesk install``).
- ``error`` — the redefine raised; left un-marked so the next Hello retries.
"""


def _xml_path(state_path: Path) -> Path:
    return state_path.parent / STEADY_STATE_XML_FILENAME


def persist_steady_state_xml(
    spec: DomainSpec, *, state_path: Optional[Path] = None
) -> Path:
    """Write the steady-state domain XML for *spec* next to the install state.

    Called by the install once the domain is defined. The daemon reads this
    file on the first agent Hello to redefine the persistent domain — see
    :func:`finalize_steady_state`. Returns the path written.
    """
    if state_path is None:
        state_path = state.default_state_file()
    xml_path = _xml_path(state_path)
    atomic_write(xml_path, build_steady_state_domain_xml(spec))
    return xml_path


def finalize_steady_state(
    ctl: LibvirtController, *, state_path: Optional[Path] = None
) -> FinalizeResult:
    """Redefine the persistent domain to its post-install steady state, once.

    Idempotent and retrying: no-ops after the first success (``done`` step),
    no-ops when there's no install to finalize (no XML), and leaves the step
    un-marked on a libvirt error so a later Hello retries. Safe to call on
    every session-ready.
    """
    if state_path is None:
        state_path = state.default_state_file()

    try:
        s = state.load(state_path)
    except (ValueError, OSError) as exc:
        # A corrupt / schema-mismatched state file: we can't tell whether the
        # redefine already ran, so don't touch libvirt. Surface it — the trap
        # stays armed but that's visible, not a silent wrong redefine.
        logger.warning("steady_state_finalize_state_unreadable error=%s", exc)
        return "error"

    if s.is_done(STEADY_STATE_STEP):
        return "already"

    xml_path = _xml_path(state_path)
    if not xml_path.is_file():
        return "absent"
    domain_xml = xml_path.read_text(encoding="utf-8")

    try:
        ctl.redefine_steady_state(domain_xml)
    except RuntimeError as exc:
        logger.warning("steady_state_finalize_failed error=%s", exc)
        return "error"

    s.mark(STEADY_STATE_STEP, "done")
    state.save(s, state_path)
    logger.info("steady_state_finalize_applied domain_xml=%s", xml_path)
    return "applied"
