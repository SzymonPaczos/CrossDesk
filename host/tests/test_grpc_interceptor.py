"""TraceContextInterceptor integration test.

Spins up an in-process gRPC server with the interceptor mounted,
calls a unary handler that emits a log line via the observability
facade, and asserts that the emitted log carries the trace IDs from
the incoming ``traceparent`` metadata.
"""

from __future__ import annotations

import io
import json

import grpc
import pytest

from crossdesk_host.observability import (
    configure_logging,
    generate_root,
    get_logger,
    metadata_pair,
)
from crossdesk_host.observability.grpc_interceptor import TraceContextInterceptor


# Tiny inline echo service so we don't need to invent a proto for the
# test. gRPC-python's generic handler accepts a method on a fictitious
# service name as long as the stub agrees.
async def _echo_handler(request_iter, context):  # type: ignore[no-untyped-def]
    log = get_logger("host.tests.interceptor")
    log.info("handler_invoked")
    async for req in request_iter:
        yield req


def _generic_handler() -> grpc.GenericRpcHandler:
    rpc_method_handler = grpc.stream_stream_rpc_method_handler(
        _echo_handler,
        request_deserializer=lambda b: b,
        response_serializer=lambda b: b,
    )
    return grpc.method_handlers_generic_handler("Echo", {"Loop": rpc_method_handler})


@pytest.fixture
async def server_port_and_buffer() -> "tuple[int, io.StringIO]":
    buf = io.StringIO()
    configure_logging(stream=buf)

    server = grpc.aio.server(interceptors=[TraceContextInterceptor()])
    server.add_generic_rpc_handlers((_generic_handler(),))
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    try:
        yield port, buf
    finally:
        await server.stop(grace=0.5)


async def test_interceptor_binds_traceparent_to_log_context(
    server_port_and_buffer: "tuple[int, io.StringIO]",
) -> None:
    port, buf = server_port_and_buffer
    ctx = generate_root()

    async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
        stub_call = channel.stream_stream(
            "/Echo/Loop",
            request_serializer=lambda b: b,
            response_deserializer=lambda b: b,
        )
        call = stub_call(metadata=[metadata_pair(ctx)])
        await call.write(b"ping")
        await call.done_writing()
        async for _ in call:
            break

    text = buf.getvalue().strip().splitlines()
    handler_lines = [json.loads(line) for line in text if "handler_invoked" in line]
    assert handler_lines, f"no handler log line in:\n{buf.getvalue()}"
    assert handler_lines[0]["trace_id"] == ctx.trace_id
    assert handler_lines[0]["span_id"] == ctx.span_id


async def test_interceptor_mints_root_when_no_traceparent(
    server_port_and_buffer: "tuple[int, io.StringIO]",
) -> None:
    port, buf = server_port_and_buffer

    async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
        stub_call = channel.stream_stream(
            "/Echo/Loop",
            request_serializer=lambda b: b,
            response_deserializer=lambda b: b,
        )
        call = stub_call()
        await call.write(b"ping")
        await call.done_writing()
        async for _ in call:
            break

    text = buf.getvalue().strip().splitlines()
    handler_lines = [json.loads(line) for line in text if "handler_invoked" in line]
    assert handler_lines, f"no handler log line in:\n{buf.getvalue()}"
    # Without an upstream traceparent, the interceptor mints a root —
    # IDs are non-empty hex of the right length.
    assert len(handler_lines[0]["trace_id"]) == 32
    assert len(handler_lines[0]["span_id"]) == 16
