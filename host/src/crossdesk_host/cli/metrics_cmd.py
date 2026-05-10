"""``crossdesk metrics`` — print a snapshot of daemon metrics.

Connects to the management Unix socket (``$XDG_RUNTIME_DIR/crossdesk-host.sock``,
or the daemon's fallback path) and calls :rpc:`ManagementService.GetMetrics`.

Two output modes:

- Default: a human-readable table grouped by metric type (counter,
  gauge, histogram). Histogram rows show p50 / p95 / p99 / min / max /
  count.
- ``--json``: the raw RPC response serialised through
  ``google.protobuf.json_format.MessageToDict`` so other tools (jq,
  microbench harness) can parse it without a proto dependency.

``--prefix`` is repeatable and acts as a server-side filter: only
metrics whose name starts with one of the prefixes are returned. With
no ``--prefix`` the daemon ships every registered metric.

The CLI uses gRPC's async client because the servicer lives in an
``asyncio`` server; we wrap it in :func:`asyncio.run` so the entry
point stays synchronous (argparse contract).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import List

import grpc
from google.protobuf import json_format

from crossdesk_host.i18n import _
from crossdesk_host.ipc.management import mgmt_socket_path
from crossdesk_host.proto.crossdesk.v1 import mgmt_pb2, mgmt_pb2_grpc

# Keep client-side connect+RPC bounded so the CLI never hangs against
# a daemon that's stuck or being restarted; the management plane is
# in-process and replies immediately when healthy.
_CONNECT_TIMEOUT_SECONDS = 2.0
_RPC_TIMEOUT_SECONDS = 5.0


def add_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("metrics", help="Print daemon metrics snapshot")
    p.add_argument(
        "--prefix",
        action="append",
        default=[],
        metavar="NAME",
        help="Filter metrics by name prefix (repeatable). Empty = all.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit the raw RPC response as JSON.",
    )
    p.add_argument(
        "--socket",
        default=None,
        metavar="PATH",
        help="Override management socket path (default: $XDG_RUNTIME_DIR/crossdesk-host.sock).",
    )


def run(args: argparse.Namespace) -> int:
    sock = args.socket or str(mgmt_socket_path())
    prefixes: List[str] = list(args.prefix or [])
    try:
        response = asyncio.run(_fetch_metrics(sock, prefixes))
    except grpc.aio.AioRpcError as exc:
        # Identifier strings (status codes) stay English; framing
        # is i18n-wrapped per docs/I18N.md.
        print(
            _("error talking to daemon at {socket}: {code} {detail}").format(
                socket=sock, code=exc.code().name, detail=exc.details() or ""
            ),
            file=sys.stderr,
        )
        return 1
    if args.emit_json:
        print(_format_json(response))
    else:
        print(_format_human(response))
    return 0


async def _fetch_metrics(socket: str, prefixes: List[str]) -> mgmt_pb2.GetMetricsResponse:
    target = f"unix://{socket}"
    async with grpc.aio.insecure_channel(target) as channel:
        # ``channel_ready()`` raises FUTURE_TIMEOUT_DURATION as a
        # plain asyncio.TimeoutError if the socket is missing — we
        # catch that explicitly and let the wrapping AioRpcError flow
        # cover normal RPC failures.
        try:
            await asyncio.wait_for(channel.channel_ready(), _CONNECT_TIMEOUT_SECONDS)
        except asyncio.TimeoutError as exc:
            raise grpc.aio.AioRpcError(
                code=grpc.StatusCode.UNAVAILABLE,
                initial_metadata=grpc.aio.Metadata(),
                trailing_metadata=grpc.aio.Metadata(),
                details=f"could not connect to {socket}",
            ) from exc
        stub = mgmt_pb2_grpc.ManagementServiceStub(channel)
        request = mgmt_pb2.GetMetricsRequest(name_prefix=prefixes)
        response: mgmt_pb2.GetMetricsResponse = await stub.GetMetrics(
            request, timeout=_RPC_TIMEOUT_SECONDS
        )
        return response


def _format_json(response: mgmt_pb2.GetMetricsResponse) -> str:
    payload = json_format.MessageToDict(
        response,
        preserving_proto_field_name=True,
        always_print_fields_with_no_presence=True,
    )
    return json.dumps(payload, indent=2, sort_keys=True)


def _format_human(response: mgmt_pb2.GetMetricsResponse) -> str:
    if not response.metrics:
        return _("no metrics registered")
    counters: List[mgmt_pb2.Metric] = []
    gauges: List[mgmt_pb2.Metric] = []
    histograms: List[mgmt_pb2.Metric] = []
    for m in response.metrics:
        if m.type == mgmt_pb2.Metric.Type.COUNTER:
            counters.append(m)
        elif m.type == mgmt_pb2.Metric.Type.GAUGE:
            gauges.append(m)
        elif m.type == mgmt_pb2.Metric.Type.HISTOGRAM:
            histograms.append(m)
    sections: List[str] = []
    if counters:
        sections.append(_render_scalar_section(_("counters"), counters, integer=True))
    if gauges:
        sections.append(_render_scalar_section(_("gauges"), gauges, integer=False))
    if histograms:
        sections.append(_render_histogram_section(histograms))
    return "\n\n".join(sections)


def _render_scalar_section(
    title: str, metrics: List[mgmt_pb2.Metric], *, integer: bool
) -> str:
    width = max(len(m.name) for m in metrics)
    lines = [f"# {title}"]
    for m in sorted(metrics, key=lambda x: x.name):
        if integer:
            value: str = str(int(m.scalar))
        else:
            value = f"{m.scalar:g}"
        lines.append(f"  {m.name:<{width}}  {value}")
    return "\n".join(lines)


def _render_histogram_section(metrics: List[mgmt_pb2.Metric]) -> str:
    width = max(len(m.name) for m in metrics)
    header = (
        f"  {'name':<{width}}  {'count':>8}  "
        f"{'p50':>10}  {'p95':>10}  {'p99':>10}  {'min':>10}  {'max':>10}"
    )
    lines = [f"# {_('histograms')}", header]
    for m in sorted(metrics, key=lambda x: x.name):
        h = m.histogram
        lines.append(
            f"  {m.name:<{width}}  {h.count:>8}  "
            f"{h.p50:>10.6f}  {h.p95:>10.6f}  {h.p99:>10.6f}  "
            f"{h.min:>10.6f}  {h.max:>10.6f}"
        )
    return "\n".join(lines)


# Re-export to keep imports parallel with the other cli/*_cmd modules.
__all__ = ["add_subparser", "run"]
