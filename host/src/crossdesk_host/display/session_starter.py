"""RAIL spawn gate — verify guest credentials before starting FreeRDP.

Cheap auth health-check (DEC-0001 + FOLLOWUPS:928-935) wrapping
:class:`FreeRDPInvocation.spawn_rail`. Without it FreeRDP starts,
hits the actual logon attempt asynchronously, and only then errors
out — costly (process tree teardown, RAIL window re-creation later)
and confusing for the user.

With it: ``coordinator.verify`` runs over the existing OpenSession
bidi stream (VerifyCoordinator pushes a ServerFrame, guest's
``credentials.rs`` calls LogonUserW, replies). On non-OK we raise
:class:`AuthHealthCheckFailed` with a ``repair_hint`` ready to print.
"""

from __future__ import annotations

import logging
from typing import Optional

from crossdesk_host.abstractions.freerdp import FreeRDPInvocation, RailSession
from crossdesk_host.installer import credentials as creds_mod
from crossdesk_host.installer.credentials import VerifyResult, VmCredentials
from crossdesk_host.ipc.verify_coordinator import VerifyCoordinator

logger = logging.getLogger(__name__)


class AuthHealthCheckFailed(RuntimeError):
    """Raised when guest credential check fails before FreeRDP spawn.

    ``result.repair_hint`` is set on the wrapped :class:`VerifyResult`
    and is the user-facing instruction. Surface it in the UI/log
    instead of the bare exception message.
    """

    def __init__(self, result: VerifyResult) -> None:
        super().__init__(
            f"VerifyCredentials failed (status={result.status_label}): "
            f"{result.detail}"
        )
        self.result = result


async def spawn_rail_with_auth_check(
    invocation: FreeRDPInvocation,
    coordinator: VerifyCoordinator,
    argv: list[str],
    *,
    creds: Optional[VmCredentials] = None,
    verify_timeout: float = 5.0,
) -> RailSession:
    """Verify creds against the guest, then spawn the FreeRDP RAIL session.

    Two-phase: (1) ``coordinator.verify`` — single round-trip, ~ms; (2)
    ``invocation.spawn_rail`` — FreeRDP process spawn, ~hundreds of ms.
    Phase 1 must succeed; otherwise raise :class:`AuthHealthCheckFailed`
    so the caller surfaces the repair hint rather than letting FreeRDP
    fail downstream.

    Args:
        invocation: real or mock FreeRDP wrapper
        coordinator: must already have an active session registered
            (raises :class:`NoActiveSession` from the coordinator otherwise)
        argv: full xfreerdp argv (typically built by ``rail_command``)
        creds: optional explicit credentials; loaded from vm.toml if omitted
        verify_timeout: seconds to wait for the guest reply

    Raises:
        AuthHealthCheckFailed: guest LogonUserW probe rejected the creds
        FileNotFoundError: vm.toml missing (and creds not provided)
        NoActiveSession: no guest registered with the coordinator
        asyncio.TimeoutError: guest didn't reply in ``verify_timeout``
    """
    result = await creds_mod.verify_with_guest(
        coordinator, creds=creds, timeout=verify_timeout
    )
    if not result.ok:
        logger.warning(
            "spawn_rail blocked by auth health-check: status=%s detail=%s",
            result.status_label,
            result.detail,
        )
        raise AuthHealthCheckFailed(result)
    return invocation.spawn_rail(argv)
