"""Opt-in OTLP span exporter.

CrossDesk emits W3C-traced gRPC traffic everywhere (DEC-0006); this
module makes the spans available to any user-supplied OTel collector
(Tempo, Jaeger, Honeycomb, …). It is **off by default** — importing
this module touches no global state and opens no sockets. The host
daemon explicitly invokes :func:`configure_otlp_exporter` early in
startup, gated on an environment variable.

Environment-variable contract (read by ``daemon.py``):

* ``CROSSDESK_OTLP_ENDPOINT`` — collector URL (e.g.
  ``https://otel.example.com:4317``). Empty / unset means "exporter
  off"; the daemon never reaches into the OTel SDK in that case.
* ``CROSSDESK_OTLP_INSECURE`` — set to ``1`` (or ``true``/``yes``)
  to allow plaintext ``http://`` collector endpoints. Default is
  TLS-only because OTLP carries trace IDs that may correlate to
  sensitive workload names; see ``docs/OBSERVABILITY.md`` for the
  rationale.

This file deliberately sticks to spans for the first iteration. OTel
metrics + log-record export are tracked separately (``FOLLOWUPS.md``);
mixing them in here would inflate the PR and force every daemon to
pay the metrics-pipeline import cost even when only spans are wanted.
"""

from __future__ import annotations

import os
from typing import Optional

from crossdesk_host.observability.log import get_logger

# Tracer-provider singletons live inside the OpenTelemetry SDK; we
# touch them only when the user opts in. Importing the SDK eagerly
# at module load would defeat the "free import" guarantee, so the
# import is deferred into the configure call.

_logger = get_logger("host.observability.otlp")

_TRUTHY = frozenset({"1", "true", "yes", "on"})

ENV_ENDPOINT = "CROSSDESK_OTLP_ENDPOINT"
ENV_INSECURE = "CROSSDESK_OTLP_INSECURE"

# Service-resource attribute name used in every span — matches the
# OTel semantic-conventions key. Hard-coded rather than imported from
# `opentelemetry.semconv` so this module stays import-free until the
# user opts in.
_SERVICE_NAME = "crossdesk-host"

_configured = False


def _is_truthy(value: Optional[str]) -> bool:
    return value is not None and value.strip().lower() in _TRUTHY


def configure_otlp_exporter(
    endpoint: Optional[str],
    *,
    insecure: bool = False,
) -> None:
    """Install a global OTel tracer provider that exports spans via
    OTLP/gRPC to ``endpoint``.

    No-op when ``endpoint`` is empty or ``None`` — the function exists
    so the daemon can call it unconditionally without first checking
    the environment.

    Idempotent in the sense that a repeat call with the same args is
    safe (logs a warning and returns); a repeat call with a different
    endpoint also returns without rebuilding the provider, because the
    OTel SDK does not support hot-swapping the global provider in a
    way that does not race in-flight spans.
    """
    global _configured

    if not endpoint:
        return

    if _configured:
        _logger.warning(
            "otlp_exporter_already_configured",
            endpoint=endpoint,
        )
        return

    # Imports are deferred so unconfigured daemons pay nothing at
    # import time. The OTel SDK pulls in protobuf, grpc, importlib_-
    # metadata and a handful of side-effecting modules; that cost is
    # only justified when the operator has actually opted in.
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": _SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=insecure)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _configured = True
    _logger.info(
        "otlp_exporter_configured",
        endpoint=endpoint,
        insecure=insecure,
    )


def configure_from_env() -> None:
    """Read ``CROSSDESK_OTLP_ENDPOINT`` / ``CROSSDESK_OTLP_INSECURE``
    and call :func:`configure_otlp_exporter`. No-op when the endpoint
    var is unset or empty — explicitly the only way this module ever
    touches the network.
    """
    endpoint = os.environ.get(ENV_ENDPOINT, "").strip()
    if not endpoint:
        return
    insecure = _is_truthy(os.environ.get(ENV_INSECURE))
    configure_otlp_exporter(endpoint, insecure=insecure)


def _reset_for_tests() -> None:
    """Test-only — clears the configured flag so a test can re-invoke
    ``configure_otlp_exporter`` after monkeypatching the SDK imports.
    Not part of the public surface; kept module-private with a leading
    underscore so importers can spot the smell.
    """
    global _configured
    _configured = False
