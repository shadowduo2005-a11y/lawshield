"""
logs.py – sets up structured JSON logging integrated with OpenTelemetry span details.

Provides a custom JsonFormatter that automatically injects trace_id, span_id,
and request_id into all log payloads.
"""
from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

from opentelemetry import trace

# Context variable to hold the current HTTP request_id
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    """
    Format log records as structured JSON.
    
    Automatically extracts OpenTelemetry trace context and request_id if available.
    """

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        """Override to output strict ISO 8601 UTC timestamps."""
        created = datetime.fromtimestamp(record.created, tz=timezone.utc)
        if datefmt:
            return created.strftime(datefmt)
        return created.isoformat()

    def format(self, record: logging.LogRecord) -> str:
        # Fetch active OpenTelemetry span details
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context() if current_span else None
        
        trace_id = None
        span_id = None
        
        if span_context and span_context.is_valid:
            trace_id = format(span_context.trace_id, "032x")
            span_id = format(span_context.span_id, "016x")

        # Compile JSON payload
        log_payload = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id,
            "span_id": span_id,
            "request_id": request_id_ctx.get(),
        }

        # Include exception details if present
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


def configure_logging() -> None:
    """
    Overrides the root logger handler to format logs as structured JSON.
    """
    root_logger = logging.getLogger()
    # Remove existing handlers to avoid duplicate output formatting
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JsonFormatter())
    
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)
    
    # Also attach to uvicorn loggers so HTTP access logs are structured
    logging.getLogger("uvicorn.access").handlers = [console_handler]
    logging.getLogger("uvicorn.error").handlers = [console_handler]
    # Prevent uvicorn loggers from propagating to root (duplicate logs)
    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("uvicorn.error").propagate = False
    
    logging.info("Structured JSON logging configured successfully (ISO 8601).")
