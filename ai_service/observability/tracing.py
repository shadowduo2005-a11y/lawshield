"""
tracing.py – configures OpenTelemetry and LangSmith tracing.

Features
--------
- LangSmith tracing via LANGCHAIN_API_KEY environment variable
- OpenTelemetry TracerProvider with ``service.name`` resource attribute
- Console exporter by default; OTLP exporter when OTEL_EXPORTER_OTLP_ENDPOINT is set
- SimpleSpanProcessor in dev; BatchSpanProcessor in production (ENVIRONMENT=production)
- ``trace_agent()`` context manager for instrumenting individual agent nodes
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
_SERVICE_NAME = os.getenv("SERVICE_NAME", "lawshield-ai-service")
_ENV = os.getenv("ENVIRONMENT", "development").lower()
_IS_PRODUCTION = _ENV == "production"


def initialize_tracing() -> None:
    """
    Initializes OpenTelemetry and LangSmith tracing configurations.

    - Sets ``LANGCHAIN_TRACING_V2`` if ``LANGCHAIN_API_KEY`` is present.
    - Registers an OpenTelemetry TracerProvider with a ``service.name`` resource.
    - Uses OTLP exporter when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set,
      otherwise falls back to ConsoleSpanExporter.
    - Uses ``BatchSpanProcessor`` in production, ``SimpleSpanProcessor`` in dev.
    """
    logger.info("Initializing tracing components (env=%s)…", _ENV)

    # ── 1. LangSmith / LangChain tracing ──────────────────────────────────
    if os.getenv("LANGCHAIN_API_KEY"):
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        logger.info("LangSmith tracing is ENABLED via environment variables.")
    else:
        logger.info("LangSmith tracing is DISABLED (missing LANGCHAIN_API_KEY).")

    # ── 2. OpenTelemetry setup ─────────────────────────────────────────────
    try:
        if isinstance(trace.get_tracer_provider(), TracerProvider):
            logger.debug("OpenTelemetry TracerProvider already registered — skipping.")
            return

        resource = Resource.create({SERVICE_NAME: _SERVICE_NAME})
        provider = TracerProvider(resource=resource)

        # Exporter selection
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # noqa: PLC0415
                exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                logger.info("OTLP exporter configured: %s", otlp_endpoint)
            except ImportError:
                logger.warning(
                    "OTEL_EXPORTER_OTLP_ENDPOINT is set but opentelemetry-exporter-otlp "
                    "is not installed. Falling back to ConsoleSpanExporter."
                )
                exporter = ConsoleSpanExporter()
        else:
            exporter = ConsoleSpanExporter()
            logger.info("ConsoleSpanExporter active (set OTEL_EXPORTER_OTLP_ENDPOINT for OTLP).")

        # Processor selection
        if _IS_PRODUCTION:
            processor = BatchSpanProcessor(exporter)
            logger.info("BatchSpanProcessor configured (production mode).")
        else:
            processor = SimpleSpanProcessor(exporter)
            logger.info("SimpleSpanProcessor configured (development mode).")

        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        logger.info(
            "OpenTelemetry TracerProvider registered (service.name=%s).", _SERVICE_NAME
        )

    except Exception as exc:
        logger.error("Failed to initialize OpenTelemetry tracing: %s", exc)


def get_tracer(name: str) -> trace.Tracer:
    """Returns an OpenTelemetry tracer instance for the given instrumentation name."""
    return trace.get_tracer(name)


@contextmanager
def trace_agent(
    agent_name: str,
    session_id: Optional[str] = None,
    **attributes: str,
) -> Generator[trace.Span, None, None]:
    """
    Context manager that wraps an agent node execution in an OpenTelemetry span.

    Automatically records exceptions and marks the span status as ERROR on failure.

    Parameters
    ----------
    agent_name : str
        Human-readable agent identifier (e.g. ``"reasoning"``, ``"citation"``).
    session_id : str, optional
        Session identifier propagated as a span attribute.
    **attributes
        Additional string attributes to set on the span.

    Usage
    -----
    ::

        from observability.tracing import trace_agent

        with trace_agent("reasoning", session_id=session_id) as span:
            result = reasoning_agent.think(context)
            span.set_attribute("confidence", str(confidence_score))

    Yields
    ------
    trace.Span
        The active OpenTelemetry span, allowing callers to add custom attributes.
    """
    tracer = get_tracer(f"lawshield.agent.{agent_name}")
    with tracer.start_as_current_span(f"agent.{agent_name}") as span:
        span.set_attribute("agent.name", agent_name)
        if session_id:
            span.set_attribute("agent.session_id", session_id)
        for key, value in attributes.items():
            span.set_attribute(f"agent.{key}", str(value))
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            from opentelemetry.trace.status import Status, StatusCode  # noqa: PLC0415
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
