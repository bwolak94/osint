"""OpenTelemetry instrumentation for the OSINT API.

Exports traces and metrics via OTLP (gRPC by default).
Set OTEL_EXPORTER_OTLP_ENDPOINT to your collector (e.g. http://otelcol:4317).
All instrumentation is a no-op when OTEL_ENABLED=false (default).
"""

from __future__ import annotations

import os

import structlog

log = structlog.get_logger(__name__)

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "osint-api")
OTEL_EXPORTER_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")


def setup_telemetry(app=None) -> None:  # type: ignore[type-arg]
    """Bootstrap OTel providers.  Call once from app factory."""
    if not OTEL_ENABLED:
        log.info("otel_disabled", reason="OTEL_ENABLED != true")
        return

    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME as RES_SERVICE_NAME
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        resource = Resource.create({RES_SERVICE_NAME: OTEL_SERVICE_NAME})

        # Trace provider
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_EXPORTER_ENDPOINT))
        )
        trace.set_tracer_provider(tracer_provider)

        # Metric provider
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=OTEL_EXPORTER_ENDPOINT),
            export_interval_millis=30_000,
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)

        # Auto-instrument frameworks
        if app is not None:
            FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()

        log.info("otel_initialized", endpoint=OTEL_EXPORTER_ENDPOINT, service=OTEL_SERVICE_NAME)

    except ImportError as exc:
        log.warning("otel_packages_missing", error=str(exc), hint="pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-sqlalchemy opentelemetry-instrumentation-httpx")


def get_tracer(name: str = OTEL_SERVICE_NAME):  # type: ignore[return]
    """Return the global tracer (no-op if OTel disabled)."""
    if not OTEL_ENABLED:
        return _NoopTracer()
    from opentelemetry import trace
    return trace.get_tracer(name)


class _NoopSpan:
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def set_attribute(self, *_): pass
    def record_exception(self, *_): pass
    def set_status(self, *_): pass


class _NoopTracer:
    def start_as_current_span(self, name: str, **__):  # noqa: ARG002
        return _NoopSpan()
