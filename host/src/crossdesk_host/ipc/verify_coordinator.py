"""Server-initiated VerifyCredentials request/response correlation.

The Control plane is a bidi gRPC stream where the guest is the gRPC
client. To let the host *initiate* a VerifyCredentials check (before
spawning RAIL — DEC-0001 Windows password lifecycle, FOLLOWUPS:928-935
+ 985-994), we piggyback on the existing ``OpenSession`` stream:

  host  ── ServerFrame{verify_credentials=...} ──>  guest
  guest ── ClientFrame{verify_credentials_result=...} ──>  host

This module owns the request/response correlation. Each ``verify()``
call mints a UUID ``request_id``, parks an ``asyncio.Future`` keyed by
it, hands a ``ServerFrame`` to the active session's outbound queue, and
awaits the matching response (or times out). The
``ControlServiceServicer`` registers its outbound queue here on session
open and routes every incoming ``verify_credentials_result`` to
``deliver()`` so the future resolves.

Single-host = single-VM today (MVP), but the registry is a list to
keep the door open for multi-VM later — the first registered session
gets verify requests; if none is registered, ``verify()`` raises
``NoActiveSession`` so the call site can surface an actionable error.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from crossdesk_host.observability.trace_ctx import (
    bind_to_log_context,
    clear_log_context,
    generate_root,
)
from crossdesk_host.proto.crossdesk.v1 import common_pb2, control_pb2

# Stdlib logger (not structlog facade) on purpose: ``configure_logging``
# replaces the stdlib root handler per call, which means our log lines
# are routed to the live stream + carry the current contextvars (trace_id).
# A cached structlog facade bound at import time would keep its old
# factory pointer — see the test fixture pattern in test_smoke_inprocess.
logger = logging.getLogger(__name__)


class NoActiveSession(RuntimeError):
    """Raised when ``verify()`` is called without a registered session.

    Typically means the guest hasn't completed the ClientHello handshake
    yet, or the previous session was torn down (suspend, hard-destroy,
    network blip).
    """


class VerifyCoordinator:
    """Correlates server-initiated VerifyCredentials request/response.

    Lifecycle: created once per host process; injected into
    ``ControlServiceServicer``. Servicer calls ``register_session`` once
    handshake completes and ``unregister_session`` in the OpenSession
    finally block. Call sites (rail_manager, CLI) use ``verify()``.
    """

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[control_pb2.VerifyCredentialsResult]] = {}
        self._sessions: list[asyncio.Queue[Optional[control_pb2.ServerFrame]]] = []
        self._lock = asyncio.Lock()

    def session_count(self) -> int:
        """How many guest sessions are currently registered (mostly for tests)."""
        return len(self._sessions)

    def register_session(
        self, outbound: asyncio.Queue[Optional[control_pb2.ServerFrame]]
    ) -> None:
        """Servicer hook: call after ServerAccept is sent, before main loop."""
        self._sessions.append(outbound)
        logger.debug("VerifyCoordinator: session registered (now %d active)", len(self._sessions))

    def unregister_session(
        self, outbound: asyncio.Queue[Optional[control_pb2.ServerFrame]]
    ) -> None:
        """Servicer hook: call in OpenSession finally block.

        Also cancels any pending futures whose stream just died — call
        sites awaiting ``verify()`` get a clean ``NoActiveSession`` raise
        instead of hanging until timeout.
        """
        try:
            self._sessions.remove(outbound)
        except ValueError:
            pass
        logger.debug("VerifyCoordinator: session unregistered (now %d active)", len(self._sessions))
        if not self._sessions:
            for request_id, fut in list(self._pending.items()):
                if not fut.done():
                    fut.set_exception(
                        NoActiveSession(f"session torn down before verify {request_id} resolved")
                    )
            self._pending.clear()

    async def verify(
        self,
        username: str,
        password: str,
        domain: str = "",
        timeout: float = 5.0,
    ) -> control_pb2.VerifyCredentialsResult:
        """Send a VerifyCredentials request to the active session and await result.

        A fresh W3C trace context is minted per call, bound to
        structlog's contextvars (so every log line carries the same
        ``trace_id``), and stamped into ``ServerFrame.auth.traceparent``
        so the guest handler can log under the same root trace and
        operators can correlate host dispatch ↔ guest handler in one grep.

        Raises:
            NoActiveSession: no guest session is currently registered.
            asyncio.TimeoutError: guest did not respond within ``timeout`` seconds.
        """
        if not self._sessions:
            raise NoActiveSession("no active guest session for verify")

        request_id = str(uuid.uuid4())
        trace_ctx = generate_root()
        bind_to_log_context(trace_ctx)
        loop = asyncio.get_event_loop()
        future: asyncio.Future[control_pb2.VerifyCredentialsResult] = loop.create_future()

        async with self._lock:
            self._pending[request_id] = future

        request = control_pb2.VerifyCredentialsRequest(
            request_id=request_id,
            username=username,
            password=password,
            domain=domain,
        )
        # Stamp the current trace context so the guest can log under the
        # same trace_id and operators can correlate host dispatch ↔ guest
        # handler in one grep.
        frame = control_pb2.ServerFrame(
            verify_credentials=request,
            auth=common_pb2.AuthContext(traceparent=trace_ctx.to_traceparent()),
        )

        # Push to the first registered session. Multi-VM routing (e.g.,
        # by libvirt domain UUID) is a follow-up if/when we host more
        # than one VM concurrently.
        outbound = self._sessions[0]
        logger.info(
            "verify_credentials_dispatch request_id=%s timeout_seconds=%s",
            request_id,
            timeout,
        )
        await outbound.put(frame)

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            logger.info(
                "verify_credentials_resolved request_id=%s status=%s",
                request_id,
                int(result.status),
            )
            return result
        finally:
            async with self._lock:
                self._pending.pop(request_id, None)
            clear_log_context()

    def deliver(self, result: control_pb2.VerifyCredentialsResult) -> None:
        """Servicer hook: called when guest sends ClientFrame.verify_credentials_result.

        Resolves the matching future. Out-of-order or unknown
        ``request_id`` is logged + dropped (the requester already gave up
        via timeout, or a buggy guest is replying twice).
        """
        future = self._pending.get(result.request_id)
        if future is None:
            logger.warning(
                "VerifyCoordinator: dropping result for unknown request_id %s "
                "(probably timed out)",
                result.request_id,
            )
            return
        if future.done():
            logger.warning(
                "VerifyCoordinator: future for request_id %s already resolved",
                result.request_id,
            )
            return
        future.set_result(result)
