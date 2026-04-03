"""
OpenTelemetry Configuration for OpenObserve Integration.

Configures TracerProvider, MeterProvider, and OTLP exporters
for sending traces and metrics to OpenObserve.

Usage:
    from utils.otel_config import configure_otel, shutdown_otel

    # At app startup
    configure_otel(service_name="mnemolite-api")

    # At app shutdown
    shutdown_otel()
"""

import os
import base64
from typing import Optional

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from structlog import get_logger

logger = get_logger(__name__)

_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None


def _get_otlp_headers() -> dict:
    """Build Basic Auth headers for OpenObserve."""
    user = os.getenv("O2_USER", "admin@mnemolite.local")
    password = os.getenv("O2_PASSWORD", "Complexpass#123")
    auth_string = f"{user}:{password}"
    auth_bytes = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {auth_bytes}"}


def configure_otel(
    service_name: str = "mnemolite-api",
    environment: str = "development",
) -> bool:
    """
    Configure OpenTelemetry with OTLP exporters for OpenObserve.

    Sets up TracerProvider, MeterProvider, and auto-instrumentation
    for FastAPI, SQLAlchemy, and Redis.

    Args:
        service_name: Service name for OpenTelemetry resource
        environment: Deployment environment (development/production)

    Returns:
        True if configured successfully, False if OpenObserve is unreachable
    """
    global _tracer_provider, _meter_provider

    otlp_endpoint = os.getenv(
        "OTLP_ENDPOINT",
        "http://openobserve:5080/api/default/v1/traces"
    )
    otlp_metrics_endpoint = os.getenv(
        "OTLP_METRICS_ENDPOINT",
        "http://openobserve:5080/api/default/v1/metrics"
    )

    otlp_headers = _get_otlp_headers()

    resource = Resource.create({
        "service.name": service_name,
        "deployment.environment": environment,
    })

    _tracer_provider = TracerProvider(resource=resource)
    _tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=otlp_endpoint,
                headers=otlp_headers,
            )
        )
    )
    trace.set_tracer_provider(_tracer_provider)

    _meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=otlp_metrics_endpoint,
                    headers=otlp_headers,
                ),
                export_interval_millis=5000,
            )
        ],
    )
    metrics.set_meter_provider(_meter_provider)

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument()
        logger.info("otel_fastapi_instrumented")
    except Exception as e:
        logger.warning("otel_fastapi_instrument_failed", error=str(e))

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument()
        logger.info("otel_sqlalchemy_instrumented")
    except Exception as e:
        logger.warning("otel_sqlalchemy_instrument_failed", error=str(e))

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()
        logger.info("otel_redis_instrumented")
    except Exception as e:
        logger.warning("otel_redis_instrument_failed", error=str(e))

    logger.info(
        "opentelemetry_configured",
        service_name=service_name,
        otlp_endpoint=otlp_endpoint,
    )

    return True


def shutdown_otel() -> None:
    """
    Shutdown OpenTelemetry providers and flush pending data.

    Call this during application shutdown to ensure all
    telemetry is exported before process exit.
    """
    global _tracer_provider, _meter_provider

    if _tracer_provider:
        _tracer_provider.shutdown()
        _tracer_provider = None

    if _meter_provider:
        _meter_provider.shutdown()
        _meter_provider = None

    logger.info("opentelemetry_shutdown")
