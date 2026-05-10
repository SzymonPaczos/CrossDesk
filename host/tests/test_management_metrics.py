"""GetMetrics RPC tests (FOLLOWUPS:381-385).

In-process servicer + Registry — no socket bound. Each test builds a
fresh ``Registry`` so cross-test pollution can't sneak in via the
module-level ``REGISTRY`` singleton."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from crossdesk_host.ipc.management import (
    ManagementServiceServicer,
    MgmtState,
)
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.observability.metrics import Registry
from crossdesk_host.proto.crossdesk.v1 import mgmt_pb2
from crossdesk_host.watchdog import HeartbeatFsm


def _servicer(registry: Registry) -> ManagementServiceServicer:
    libvirt = LibvirtControllerMock()
    state = MgmtState(fsm=HeartbeatFsm())
    return ManagementServiceServicer(
        state, libvirt, coordinator=None, metrics_registry=registry
    )


@pytest.fixture
def context() -> MagicMock:
    ctx = MagicMock()
    ctx.cancelled.return_value = False
    return ctx


async def test_get_metrics_empty_registry_returns_no_entries(context: MagicMock) -> None:
    registry = Registry()
    servicer = _servicer(registry)
    response = await servicer.GetMetrics(mgmt_pb2.GetMetricsRequest(), context)
    assert list(response.metrics) == []


async def test_get_metrics_serialises_counter_and_gauge(context: MagicMock) -> None:
    registry = Registry()
    registry.counter("launches_total").inc(7)
    registry.gauge("current_mounts").set(3.5)
    servicer = _servicer(registry)
    response = await servicer.GetMetrics(mgmt_pb2.GetMetricsRequest(), context)
    by_name = {m.name: m for m in response.metrics}
    assert by_name["launches_total"].type == mgmt_pb2.Metric.Type.COUNTER
    assert by_name["launches_total"].scalar == 7.0
    assert by_name["current_mounts"].type == mgmt_pb2.Metric.Type.GAUGE
    assert by_name["current_mounts"].scalar == 3.5
    # Counter/gauge land in the ``scalar`` arm of the oneof, never
    # ``histogram`` — mixing them up would silently break the CLI's
    # type-grouped renderer.
    assert by_name["launches_total"].WhichOneof("value") == "scalar"
    assert by_name["current_mounts"].WhichOneof("value") == "scalar"


async def test_get_metrics_histogram_carries_summary(context: MagicMock) -> None:
    registry = Registry()
    h = registry.histogram("heartbeat_rtt_seconds")
    for value in (0.001, 0.002, 0.003, 0.004, 0.005):
        h.observe(value)
    servicer = _servicer(registry)
    response = await servicer.GetMetrics(mgmt_pb2.GetMetricsRequest(), context)
    metric = next(m for m in response.metrics if m.name == "heartbeat_rtt_seconds")
    assert metric.type == mgmt_pb2.Metric.Type.HISTOGRAM
    assert metric.WhichOneof("value") == "histogram"
    snap = metric.histogram
    assert snap.count == 5
    # hdrhistogram is approximate; both endpoints land within ~30%.
    assert 0.0007 <= snap.min <= 0.0013
    assert 0.004 <= snap.max <= 0.0065
    assert snap.p50 > 0
    assert snap.p95 > 0
    assert snap.p99 > 0


async def test_get_metrics_prefix_filter_keeps_matching(context: MagicMock) -> None:
    registry = Registry()
    registry.counter("launches_total").inc(1)
    registry.counter("heartbeat_misses_total").inc(2)
    registry.gauge("current_mounts").set(4)
    servicer = _servicer(registry)

    response = await servicer.GetMetrics(
        mgmt_pb2.GetMetricsRequest(name_prefix=["heartbeat_"]), context
    )
    names = [m.name for m in response.metrics]
    assert names == ["heartbeat_misses_total"]


async def test_get_metrics_multiple_prefixes_ored(context: MagicMock) -> None:
    registry = Registry()
    registry.counter("launches_total").inc(1)
    registry.counter("heartbeat_misses_total").inc(2)
    registry.gauge("current_mounts").set(4)
    servicer = _servicer(registry)

    response = await servicer.GetMetrics(
        mgmt_pb2.GetMetricsRequest(name_prefix=["launches_", "current_"]), context
    )
    names = sorted(m.name for m in response.metrics)
    assert names == ["current_mounts", "launches_total"]


async def test_get_metrics_uses_module_singleton_when_no_override() -> None:
    """Production path: ``ManagementServiceServicer(...)`` without a
    ``metrics_registry=`` kwarg falls back to the module-level
    ``REGISTRY``. Verifies the wiring without mutating the singleton's
    contents (we just check identity)."""

    from crossdesk_host.observability.metrics import REGISTRY

    libvirt = LibvirtControllerMock()
    servicer = ManagementServiceServicer(MgmtState(fsm=HeartbeatFsm()), libvirt)
    assert servicer.metrics_registry is REGISTRY
