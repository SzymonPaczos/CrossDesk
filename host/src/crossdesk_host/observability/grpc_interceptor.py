"""gRPC server-side interceptor that extracts W3C ``traceparent`` from
each incoming RPC's metadata and binds the trace/span IDs to
structlog's contextvars for the duration of the call.

Mounted in ``daemon.py`` when the gRPC server is built.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Awaitable, Callable

import grpc

from crossdesk_host.observability.trace_ctx import (
    TraceContext,
    bind_to_log_context,
    clear_log_context,
    extract_from_metadata,
    generate_root,
)


def _resolve_trace(metadata: object) -> TraceContext:
    """Use upstream traceparent if present and parseable; otherwise mint
    a fresh root so this RPC still carries a coherent trace."""
    upstream = extract_from_metadata(metadata)
    return upstream if upstream is not None else generate_root()


class TraceContextInterceptor(grpc.aio.ServerInterceptor):  # type: ignore[misc]
    """Asyncio gRPC interceptor — every intercepted RPC handler runs
    with ``trace_id``/``span_id`` bound to structlog contextvars.

    gRPC-python's ``intercept_service`` runs once per RPC method
    invocation and returns the chosen handler. We don't need to
    rewrite the handler itself; we wrap each behaviour function so the
    binding happens around the actual user code, then unbinds in a
    ``finally``.
    """

    async def intercept_service(
        self,
        continuation: Callable[
            [grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler]
        ],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        handler = await continuation(handler_call_details)
        if handler is None:
            return handler
        return _wrap_handler(handler)


def _wrap_handler(handler: grpc.RpcMethodHandler) -> grpc.RpcMethodHandler:
    """Return a copy of ``handler`` whose behaviour function binds the
    trace context for the duration of the call. Covers all four
    streaming variants gRPC supports."""

    if handler.unary_unary is not None:
        original_uu = handler.unary_unary

        async def unary_unary(request: Any, context: grpc.aio.ServicerContext) -> Any:
            ctx = _resolve_trace(context.invocation_metadata())
            bind_to_log_context(ctx)
            try:
                return await original_uu(request, context)
            finally:
                clear_log_context()

        return _replace(handler, unary_unary=unary_unary)

    if handler.unary_stream is not None:
        original_us = handler.unary_stream

        async def unary_stream(
            request: Any, context: grpc.aio.ServicerContext
        ) -> AsyncIterator[Any]:
            ctx = _resolve_trace(context.invocation_metadata())
            bind_to_log_context(ctx)
            try:
                async for item in original_us(request, context):
                    yield item
            finally:
                clear_log_context()

        return _replace(handler, unary_stream=unary_stream)

    if handler.stream_unary is not None:
        original_su = handler.stream_unary

        async def stream_unary(
            request_iterator: AsyncIterator[Any],
            context: grpc.aio.ServicerContext,
        ) -> Any:
            ctx = _resolve_trace(context.invocation_metadata())
            bind_to_log_context(ctx)
            try:
                return await original_su(request_iterator, context)
            finally:
                clear_log_context()

        return _replace(handler, stream_unary=stream_unary)

    if handler.stream_stream is not None:
        original_ss = handler.stream_stream

        async def stream_stream(
            request_iterator: AsyncIterator[Any],
            context: grpc.aio.ServicerContext,
        ) -> AsyncIterator[Any]:
            ctx = _resolve_trace(context.invocation_metadata())
            bind_to_log_context(ctx)
            try:
                async for item in original_ss(request_iterator, context):
                    yield item
            finally:
                clear_log_context()

        return _replace(handler, stream_stream=stream_stream)

    return handler


def _replace(handler: grpc.RpcMethodHandler, **kwargs: object) -> grpc.RpcMethodHandler:
    """Return a new ``RpcMethodHandler`` with one behaviour replaced.
    grpc.RpcMethodHandler is a NamedTuple in current grpc-python, so
    ``_replace`` works directly; this wrapper exists for type-checker
    friendliness."""
    return handler._replace(**kwargs)
