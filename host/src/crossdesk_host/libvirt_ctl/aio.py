"""Executor offload + deadline for blocking libvirt calls made from an
async context.

``backend.md``: "libvirt event-loop deadlines — pick one". libvirt's Python
bindings are synchronous and can block for seconds (a hung domain, a slow
storage backend); calling them straight from a gRPC servicer coroutine would
stall the whole event loop. ``libvirt_call`` runs the blocking call in a
thread and bounds it with ``asyncio.wait_for``.

The pool is **dedicated**, not asyncio's default one, because a timed-out
libvirt call keeps its thread: the C call cannot be cancelled, so the thread
stays blocked until libvirt returns — possibly never, which is exactly the
hung-libvirtd case the deadline exists for. On the shared default executor
those stuck threads accumulate until the pool is full, and from then on *every*
``run_in_executor`` in the daemon starves, including work with nothing to do
with libvirt. Here a libvirt storm can only starve libvirt.

The bound also makes the deadline stronger than it looks: calls beyond
``LIBVIRT_MAX_WORKERS`` are *queued* rather than started, and a queued future
is genuinely cancellable, so ``wait_for`` reclaims them on the deadline instead
of leaking one thread each.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

T = TypeVar("T")

LIBVIRT_OP_TIMEOUT_SECONDS = 30.0

# Small on purpose. libvirt serialises RPCs per connection, so extra threads buy
# almost no throughput — while each one is a thread a wedged libvirtd can hold
# forever. This caps the blast radius at four leaked threads.
LIBVIRT_MAX_WORKERS = 4

_executor = ThreadPoolExecutor(
    max_workers=LIBVIRT_MAX_WORKERS, thread_name_prefix="libvirt"
)


async def libvirt_call(
    fn: Callable[[], T], *, timeout: float = LIBVIRT_OP_TIMEOUT_SECONDS
) -> T:
    """Run blocking ``fn`` in the libvirt pool and await it with a deadline.

    Raises ``asyncio.TimeoutError`` if ``fn`` does not return within ``timeout``
    seconds. A call that already started keeps its thread until it returns
    (unavoidable); callers log and proceed rather than hang the loop.
    """
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(loop.run_in_executor(_executor, fn), timeout)


def shutdown_libvirt_executor() -> None:
    """Drop queued libvirt calls and stop accepting new ones.

    ``wait=False`` is deliberate: a thread parked inside a libvirt C call would
    otherwise hold daemon shutdown open indefinitely — the failure mode this
    module exists to contain.
    """
    _executor.shutdown(wait=False, cancel_futures=True)
