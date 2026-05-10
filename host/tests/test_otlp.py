"""Opt-in OTLP exporter contract tests.

These tests never open a network socket. The OTel SDK calls are
patched with ``unittest.mock`` so we can assert which constructors
ran with which args; the no-op path is exercised by simply not
setting the env var.
"""

from __future__ import annotations

from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest

from crossdesk_host.observability import otlp


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    """Each test gets a fresh exporter-not-configured state, otherwise
    the module-level _configured flag would leak across tests in
    declaration order."""
    otlp._reset_for_tests()
    yield
    otlp._reset_for_tests()


def test_configure_with_empty_endpoint_is_noop() -> None:
    """``configure_otlp_exporter("")`` and ``None`` must not import
    the OTel SDK or touch the global tracer provider."""
    # No patches: if the function tried to import opentelemetry.* it
    # would still succeed since the package is installed, so we assert
    # _configured stays False as the observable signal.
    otlp.configure_otlp_exporter("")
    assert otlp._configured is False

    otlp.configure_otlp_exporter(None)
    assert otlp._configured is False


def test_configure_from_env_noop_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """``configure_from_env`` is the daemon's entry point — when the
    env var is missing it must do absolutely nothing."""
    monkeypatch.delenv(otlp.ENV_ENDPOINT, raising=False)
    monkeypatch.delenv(otlp.ENV_INSECURE, raising=False)

    # Patch the SDK constructors; if any of them are called the test
    # fails — proves the no-op contract.
    with patch.object(otlp, "_is_truthy", side_effect=AssertionError("called")):
        otlp.configure_from_env()
    assert otlp._configured is False


def test_configure_from_env_noop_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicitly-empty env var (``CROSSDESK_OTLP_ENDPOINT=``) is
    semantically the same as unset — operators sometimes set it to
    an empty string in systemd unit files to disable a default."""
    monkeypatch.setenv(otlp.ENV_ENDPOINT, "")
    otlp.configure_from_env()
    assert otlp._configured is False


def test_configure_with_endpoint_installs_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When given a real endpoint, the function must build a
    ``TracerProvider`` with an ``OTLPSpanExporter`` and a
    ``BatchSpanProcessor`` and set it as the global provider."""
    fake_trace = MagicMock(name="opentelemetry.trace")
    fake_exporter_cls = MagicMock(name="OTLPSpanExporter")
    fake_resource_cls = MagicMock(name="Resource")
    fake_provider_cls = MagicMock(name="TracerProvider")
    fake_processor_cls = MagicMock(name="BatchSpanProcessor")

    fake_provider = fake_provider_cls.return_value
    fake_resource = fake_resource_cls.create.return_value
    fake_exporter = fake_exporter_cls.return_value
    fake_processor = fake_processor_cls.return_value

    # Patch the imports inside the function body. The deferred-import
    # pattern means we patch via sys.modules rather than the otlp
    # module's own namespace.
    import sys

    fake_trace_mod = MagicMock()
    fake_trace_mod.set_tracer_provider = fake_trace.set_tracer_provider
    fake_exporter_mod = MagicMock()
    fake_exporter_mod.OTLPSpanExporter = fake_exporter_cls
    fake_resource_mod = MagicMock()
    fake_resource_mod.Resource = fake_resource_cls
    fake_sdk_trace_mod = MagicMock()
    fake_sdk_trace_mod.TracerProvider = fake_provider_cls
    fake_sdk_export_mod = MagicMock()
    fake_sdk_export_mod.BatchSpanProcessor = fake_processor_cls

    monkeypatch.setitem(sys.modules, "opentelemetry", MagicMock(trace=fake_trace_mod))
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", fake_trace_mod)
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
        fake_exporter_mod,
    )
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.resources", fake_resource_mod)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.trace", fake_sdk_trace_mod)
    monkeypatch.setitem(
        sys.modules, "opentelemetry.sdk.trace.export", fake_sdk_export_mod
    )

    otlp.configure_otlp_exporter("https://otel.example:4317")

    fake_resource_cls.create.assert_called_once_with({"service.name": "crossdesk-host"})
    fake_provider_cls.assert_called_once_with(resource=fake_resource)
    fake_exporter_cls.assert_called_once_with(
        endpoint="https://otel.example:4317", insecure=False
    )
    fake_processor_cls.assert_called_once_with(fake_exporter)
    fake_provider.add_span_processor.assert_called_once_with(fake_processor)
    fake_trace_mod.set_tracer_provider.assert_called_once_with(fake_provider)
    assert otlp._configured is True


def test_configure_passes_insecure_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``insecure=True`` must reach the OTLPSpanExporter constructor —
    this is the http://-allowing knob."""
    fake_exporter_cls = MagicMock(name="OTLPSpanExporter")

    import sys

    monkeypatch.setitem(
        sys.modules,
        "opentelemetry",
        MagicMock(trace=MagicMock()),
    )
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", MagicMock())
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
        MagicMock(OTLPSpanExporter=fake_exporter_cls),
    )
    monkeypatch.setitem(
        sys.modules, "opentelemetry.sdk.resources", MagicMock(Resource=MagicMock())
    )
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.sdk.trace",
        MagicMock(TracerProvider=MagicMock()),
    )
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.sdk.trace.export",
        MagicMock(BatchSpanProcessor=MagicMock()),
    )

    otlp.configure_otlp_exporter("http://collector.local:4317", insecure=True)
    fake_exporter_cls.assert_called_once_with(
        endpoint="http://collector.local:4317", insecure=True
    )


def test_configure_from_env_reads_endpoint_and_insecure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end env-var contract: setting both vars must result in
    a configure call with the parsed values."""
    monkeypatch.setenv(otlp.ENV_ENDPOINT, "https://otel.example:4317")
    monkeypatch.setenv(otlp.ENV_INSECURE, "1")

    captured = {}

    def fake_configure(endpoint: str, *, insecure: bool = False) -> None:
        captured["endpoint"] = endpoint
        captured["insecure"] = insecure

    monkeypatch.setattr(otlp, "configure_otlp_exporter", fake_configure)
    otlp.configure_from_env()

    assert captured == {
        "endpoint": "https://otel.example:4317",
        "insecure": True,
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("", False),
        ("nope", False),
        (None, False),
    ],
)
def test_truthy_parser(raw: str, expected: bool) -> None:
    """The insecure-flag parser accepts the canonical truthy strings
    documented in the module docstring; everything else is falsy."""
    assert otlp._is_truthy(raw) is expected


def test_repeat_configure_with_same_endpoint_warns_and_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling configure twice must not double-install — second call
    logs a warning and returns. The first set of SDK constructors
    should have run; the second should not."""
    construction_calls = {"count": 0}

    def counting_provider(*args: object, **kwargs: object) -> MagicMock:
        construction_calls["count"] += 1
        return MagicMock()

    import sys

    monkeypatch.setitem(sys.modules, "opentelemetry", MagicMock(trace=MagicMock()))
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", MagicMock())
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
        MagicMock(OTLPSpanExporter=MagicMock()),
    )
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.sdk.resources",
        MagicMock(Resource=MagicMock()),
    )
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.sdk.trace",
        MagicMock(TracerProvider=counting_provider),
    )
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.sdk.trace.export",
        MagicMock(BatchSpanProcessor=MagicMock()),
    )

    otlp.configure_otlp_exporter("https://otel.example:4317")
    otlp.configure_otlp_exporter("https://otel.example:4317")

    assert construction_calls["count"] == 1
    assert otlp._configured is True
