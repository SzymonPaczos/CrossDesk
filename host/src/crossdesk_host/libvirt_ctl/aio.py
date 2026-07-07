"""Executor offload + deadline for blocking libvirt calls made from an
async context.

``backend.md``: "libvirt event-loop deadlines — pick one". libvirt's Python
bindings are synchronous and can block for seconds (a hung domain, a slow
storage backend); calling them straight from a gRPC servicer coroutine would
stall the whole event loop. ``libvirt_call`` runs the blocking call in the
default thread-pool executor and bounds it with ``asyncio.wait_for``.
"""

import asyncio
from typing import Callable, TypeVar

T = TypeVar("T")

LIBVIRT_OP_TIMEOUT_SECONDS = 30.0


async def libvirt_call(
    fn: Callable[[], T], *, timeout: float = LIBVIRT_OP_TIMEOUT_SECONDS
) -> T:
    """Run blocking ``fn`` in a thread and await it with a deadline.

    Raises ``asyncio.TimeoutError`` if ``fn`` does not return within
    ``timeout`` seconds. On timeout the executor thread keeps running to
    completion (unavoidable — the C call can't be cancelled); callers log and
    proceed rather than hang the loop.
    """
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(loop.run_in_executor(None, fn), timeout)
