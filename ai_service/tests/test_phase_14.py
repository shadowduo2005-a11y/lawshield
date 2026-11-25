"""
Comprehensive test suite for Phase 14 (Observability).

Tests verify tracing, metrics, structured logs, context vars, and FastAPI endpoints.
"""
from __future__ import annotations

import json
import logging
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from main import app
from observability.tracing import initialize_tracing, get_tracer, trace_agent
from observability.metrics import (
    HTTP_REQUESTS_TOTAL,
    LLM_CALLS_TOTAL,
    LLM_TOKEN_USAGE,
    AGENT_CALLS_TOTAL,
    record_http_request,
    record_llm_call,
    record_agent_call,
)
from observability.logs import JsonFormatter, configure_logging, request_id_ctx
from observability.monitoring import initialize_observability


class TestTracing(unittest.TestCase):
    @patch("observability.tracing.logger")
    def test_initialize_tracing(self, mock_logger):
        initialize_tracing()
        provider = trace.get_tracer_provider()
        self.assertTrue(isinstance(provider, TracerProvider))

    def test_get_tracer(self):
        tracer = get_tracer("test-tracer")
        self.assertIsNotNone(tracer)

    def test_trace_agent_context_manager(self):
        tracer = get_tracer("lawshield.agent.test_agent")
        
        with trace_agent("test_agent", session_id="1234", custom_attr="foo") as span:
            self.assertTrue(span.is_recording())
            # Can't easily assert span attributes without an exporter in tests,
            # but we verify the context manager yields a valid span and doesn't crash.


class TestMetrics(unittest.TestCase):
    def test_record_http_request(self):
        try:
            start_count = HTTP_REQUESTS_TOTAL.labels(method="GET", endpoint="/test", status=200)._value.get()
        except AttributeError:
            start_count = 0

        record_http_request("GET", "/test", 200, 0.05)
        end_count = HTTP_REQUESTS_TOTAL.labels(method="GET", endpoint="/test", status=200)._value.get()
        self.assertEqual(end_count, start_count + 1)

    def test_record_llm_call(self):
        try:
            start_calls = LLM_CALLS_TOTAL.labels(provider="gemini", model="gemini-2.5-flash")._value.get()
        except AttributeError:
            start_calls = 0

        record_llm_call(
            provider="gemini",
            model="gemini-2.5-flash",
            duration=1.2,
            prompt_tokens=100,
            completion_tokens=50
        )
        end_calls = LLM_CALLS_TOTAL.labels(provider="gemini", model="gemini-2.5-flash")._value.get()
        self.assertEqual(end_calls, start_calls + 1)
        
        p_tokens = LLM_TOKEN_USAGE.labels(provider="gemini", model="gemini-2.5-flash", token_type="prompt")._value.get()
        c_tokens = LLM_TOKEN_USAGE.labels(provider="gemini", model="gemini-2.5-flash", token_type="completion")._value.get()
        self.assertEqual(p_tokens, 100)
        self.assertEqual(c_tokens, 50)

    def test_record_agent_call(self):
        try:
            start_calls = AGENT_CALLS_TOTAL.labels(agent_name="reasoning", status="success")._value.get()
        except AttributeError:
            start_calls = 0

        record_agent_call("reasoning", duration=2.5, success=True)
        end_calls = AGENT_CALLS_TOTAL.labels(agent_name="reasoning", status="success")._value.get()
        self.assertEqual(end_calls, start_calls + 1)


class TestStructuredLogs(unittest.TestCase):
    def test_json_formatter(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test_file.py",
            lineno=42,
            msg="This is a test message.",
            args=(),
            exc_info=None
        )
        
        # Inject request_id into context
        token = request_id_ctx.set("req-12345")
        formatted = formatter.format(record)
        request_id_ctx.reset(token)
        
        data = json.loads(formatted)
        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "test_logger")
        self.assertEqual(data["message"], "This is a test message.")
        self.assertEqual(data["request_id"], "req-12345")
        self.assertIn("T", data["timestamp"])  # ISO 8601 format


class TestMonitoring(unittest.TestCase):
    def test_initialize_observability(self):
        with patch("observability.monitoring.configure_logging") as mock_log, \
             patch("observability.monitoring.initialize_tracing") as mock_trace:
            initialize_observability()
            mock_log.assert_called_once()
            mock_trace.assert_called_once()


class TestFastApiObservability(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check_records_metrics_and_request_id(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        
        # Verify custom request ID header was injected by middleware
        self.assertIn("x-request-id", response.headers)
        req_id = response.headers["x-request-id"]
        self.assertTrue(len(req_id) > 10)

        # Scrape metrics
        metrics_response = self.client.get("/metrics")
        self.assertEqual(metrics_response.status_code, 200)
        
        content = metrics_response.text
        self.assertIn("http_requests_total", content)
        self.assertIn("GET", content)
        self.assertIn("/health", content)


if __name__ == "__main__":
    unittest.main()
