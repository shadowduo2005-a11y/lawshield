"""
monitoring.py – combines logging, tracing, metrics, and implements FastAPI/ASGI middleware.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from opentelemetry import trace

from .tracing import initialize_tracing, get_tracer
from .logs import configure_logging, request_id_ctx
from .metrics import record_http_request

logger = logging.getLogger(__name__)


def initialize_observability() -> None:
    """
    Consolidates the initialization of tracing, metrics, and logging frameworks.
    """
    initialize_tracing()
    configure_logging()
    logging.info("Observability systems initialized.")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to instrument HTTP endpoints.
    
    Responsibilities:
    - Generates a unique request ID and sets it in context for structured logs.
    - Wraps request execution in an active OpenTelemetry span.
    - Exports request latency and status codes to Prometheus metrics.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        method = request.method
        path = request.url.path
        
        # Avoid tracing the metrics endpoint to reduce noise
        if path == "/metrics":
            return await call_next(request)

        # Generate a unique request ID and store it in ContextVar for logs
        req_id = str(uuid.uuid4())
        token = request_id_ctx.set(req_id)

        tracer = get_tracer("ai-service-http")
        start_time = time.time()
        status_code = 500  # Default to 500 in case of unhandled exception

        # Wrap request execution in an active OpenTelemetry span
        with tracer.start_as_current_span(f"HTTP {method} {path}") as span:
            span.set_attribute("http.method", method)
            span.set_attribute("http.route", path)
            span.set_attribute("http.request_id", req_id)
            
            try:
                response = await call_next(request)
                status_code = response.status_code
                span.set_attribute("http.status_code", status_code)
                # Inject request ID into response headers
                response.headers["X-Request-ID"] = req_id
                return response
                
            except Exception as exc:
                span.set_attribute("http.status_code", status_code)
                span.record_exception(exc)
                from opentelemetry.trace.status import Status, StatusCode  # noqa: PLC0415
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise exc
                
            finally:
                duration = time.time() - start_time
                # Export metrics to Prometheus registry
                record_http_request(method, path, status_code, duration)
                # Reset ContextVar
                request_id_ctx.reset(token)
