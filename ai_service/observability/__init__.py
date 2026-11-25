"""
observability package init.

Exposes core observability functions:
- initialize_observability, ObservabilityMiddleware
- Tracing helpers: get_tracer, trace_agent
- Metrics helpers: record_http_request, record_llm_call, record_agent_call
- Raw Prometheus metrics
"""
from .monitoring import initialize_observability, ObservabilityMiddleware
from .tracing import get_tracer, trace_agent
from .metrics import (
    record_http_request,
    record_llm_call,
    record_agent_call,
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    LLM_CALLS_TOTAL,
    LLM_TOKEN_USAGE,
    LLM_LATENCY_SECONDS,
    RAG_SEARCH_DURATION_SECONDS,
    AGENT_CALLS_TOTAL,
    AGENT_LATENCY_SECONDS,
    LEGAL_REASONING_CONFIDENCE,
    REASONING_ITERATIONS_TOTAL,
)

__all__ = [
    "initialize_observability",
    "ObservabilityMiddleware",
    "get_tracer",
    "trace_agent",
    "record_http_request",
    "record_llm_call",
    "record_agent_call",
    "HTTP_REQUESTS_TOTAL",
    "HTTP_REQUEST_DURATION_SECONDS",
    "LLM_CALLS_TOTAL",
    "LLM_TOKEN_USAGE",
    "LLM_LATENCY_SECONDS",
    "RAG_SEARCH_DURATION_SECONDS",
    "AGENT_CALLS_TOTAL",
    "AGENT_LATENCY_SECONDS",
    "LEGAL_REASONING_CONFIDENCE",
    "REASONING_ITERATIONS_TOTAL",
]
