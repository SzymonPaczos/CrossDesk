"""Integration: AuthValidator increments the rejections counter."""

from __future__ import annotations

import grpc
import pytest

from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.observability.metrics import REGISTRY, MetricNames
from crossdesk_host.proto.crossdesk.v1 import common_pb2


class _FakeAioContext:
    """Minimal stub satisfying the bits of grpc.aio.ServicerContext
    that AuthValidator touches: ``auth_context()`` returns a dict-like
    of TLS-extracted attributes; ``abort()`` raises."""

    def __init__(self) -> None:
        pass

    def auth_context(self) -> dict[str, list[bytes]]:
        return {}

    async def abort(self, code: grpc.StatusCode, detail: str) -> None:
        raise grpc.RpcError(detail)


async def test_missing_auth_increments_rejections_counter() -> None:
    validator = AuthValidator()
    counter = REGISTRY.counter(MetricNames.AUTH_CONTEXT_REJECTIONS_TOTAL)
    before = counter.value()

    ctx = _FakeAioContext()
    bogus = common_pb2.AuthContext()  # empty fingerprint → fails

    with pytest.raises(grpc.RpcError):
        await validator.verify_auth_context(ctx, bogus)  # type: ignore[arg-type]

    assert counter.value() == before + 1
