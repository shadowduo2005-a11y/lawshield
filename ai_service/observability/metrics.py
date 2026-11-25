"""
metrics.py – defines Prometheus metrics for the LawShield AI service.

Metric categories
-----------------
- HTTP request counters and latency histograms
- LLM call counters and token usage gauges
- RAG search latency histograms
- Agent execution counters and latency histograms
- Legal reasoning confidence and iteration tracking

Helper functions record_http_request(), record_llm_call(), and
record_agent_call() provide a clean API for instrumenting call sites.
"""
from __future__ import annotations

import logging
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# ── HTTP Metrics ──────────────────────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total count of HTTP requests handled.",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Histogram of HTTP request durations (seconds).",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# ── LLM Metrics ───────────────────────────────────────────────────────────────

LLM_CALLS_TOTAL = Counter(
    "llm_calls_total",
    "Total count of LLM API requests executed.",
    ["provider", "model"],
)

LLM_TOKEN_USAGE = Gauge(
    "llm_token_usage_total",
    "Total tokens consumed by LLM invocations.",
    ["provider", "model", "token_type"],  # token_type: "prompt" or "completion"
)

LLM_LATENCY_SECONDS = Histogram(
    "llm_latency_seconds",
    "Histogram of LLM invocation latencies (seconds).",
    ["provider", "model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# ── RAG / Retrieval Metrics ───────────────────────────────────────────────────

RAG_SEARCH_DURATION_SECONDS = Histogram(
    "rag_search_duration_seconds",
    "Histogram of hybrid vector + lexical search latencies (seconds).",
    ["collection_name"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

# ── Agent Metrics ─────────────────────────────────────────────────────────────

AGENT_CALLS_TOTAL = Counter(
    "agent_calls_total",
    "Total count of agent node executions.",
    ["agent_name", "status"],  # status: "success" or "error"
)

AGENT_LATENCY_SECONDS = Histogram(
    "agent_latency_seconds",
    "Histogram of agent node execution latencies (seconds).",
    ["agent_name"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# ── Legal Reasoning Metrics ────────────────────────────────────────────────────

LEGAL_REASONING_CONFIDENCE = Gauge(
    "legal_reasoning_confidence_score",
    "Confidence score calculated for legal reasoning runs.",
    ["session_id"],
)

REASONING_ITERATIONS_TOTAL = Counter(
    "reasoning_iterations_total",
    "Total reasoning iterations tracked (1 = first pass, 2 = self-corrected).",
    ["result"],  # result: "clean" or "refined"
)


# ── Helper Functions ───────────────────────────────────────────────────────────

def record_http_request(
    method: str, endpoint: str, status: int, duration: float
) -> None:
    """Records a single HTTP request's count and latency metrics."""
    HTTP_REQUESTS_TOTAL.labels(
        method=method, endpoint=endpoint, status=status
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        method=method, endpoint=endpoint
    ).observe(duration)


def record_llm_call(
    provider: str,
    model: str,
    duration: float = 0.0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """
    Records an LLM API call to Prometheus metrics.

    Parameters
    ----------
    provider : str
        Provider name (e.g. ``"gemini"``, ``"openai"``).
    model : str
        Model identifier (e.g. ``"gemini-2.5-flash"``).
    duration : float
        Wall-clock time of the LLM call in seconds.
    prompt_tokens : int, optional
        Number of prompt tokens consumed.
    completion_tokens : int, optional
        Number of completion tokens generated.
    """
    LLM_CALLS_TOTAL.labels(provider=provider, model=model).inc()
    if duration > 0:
        LLM_LATENCY_SECONDS.labels(provider=provider, model=model).observe(duration)
    if prompt_tokens:
        LLM_TOKEN_USAGE.labels(
            provider=provider, model=model, token_type="prompt"
        ).set(prompt_tokens)
    if completion_tokens:
        LLM_TOKEN_USAGE.labels(
            provider=provider, model=model, token_type="completion"
        ).set(completion_tokens)


def record_agent_call(
    agent_name: str,
    duration: float,
    success: bool = True,
) -> None:
    """
    Records an agent node execution to Prometheus metrics.

    Parameters
    ----------
    agent_name : str
        Identifier of the agent node (e.g. ``"reasoning"``, ``"citation"``).
    duration : float
        Wall-clock execution time in seconds.
    success : bool
        Whether the agent completed without error.
    """
    status = "success" if success else "error"
    AGENT_CALLS_TOTAL.labels(agent_name=agent_name, status=status).inc()
    AGENT_LATENCY_SECONDS.labels(agent_name=agent_name).observe(duration)
