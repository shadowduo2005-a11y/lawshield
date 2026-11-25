"""
Comprehensive test suite for Phase 13 (Evaluation).

Tests are fully mocked so they run without real LLM keys or network access.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from main import app
from evaluation.ragas import RagasEvaluator
from evaluation.retrieval import RetrievalEvaluator
from evaluation.hallucination import HallucinationEvaluator
from evaluation.citations import CitationEvaluator
from evaluation.benchmark import BenchmarkEvaluator


def _ai_msg(content: str) -> AIMessage:
    m = MagicMock()
    m.content = content
    m.type = "ai"
    m.tool_calls = []
    return m


class TestRagasEvaluator(unittest.TestCase):
    @patch("evaluation.ragas.get_llm_provider")
    def test_evaluate_faithfulness(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg('{"total_claims": 5, "supported_claims": 4}')
        mock_provider.return_value.get_model.return_value = mock_model

        evaluator = RagasEvaluator()
        score = evaluator.evaluate_faithfulness("Answer text", ["Context text"])
        self.assertEqual(score, 0.8)

    @patch("evaluation.ragas.get_llm_provider")
    def test_evaluate_context_recall(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg('{"total_ground_truth_facts": 10, "retrieved_facts": 9}')
        mock_provider.return_value.get_model.return_value = mock_model

        evaluator = RagasEvaluator()
        score = evaluator.evaluate_context_recall("Ground truth text", ["Context text"])
        self.assertEqual(score, 0.9)


class TestRetrievalEvaluator(unittest.TestCase):
    def test_calculate_metrics(self):
        retrieved = ["Section 54 provides capital gains exemption."]
        expected = ["capital gains", "exemption", "unrelated keyword"]
        metrics = RetrievalEvaluator.calculate_metrics(retrieved, expected)

        # 2 out of 3 expected keywords found in retrieved text -> Recall = 0.67
        self.assertEqual(metrics["retrieval_recall"], 0.67)
        # The retrieved chunk contains at least one keyword -> Precision = 1.0
        self.assertEqual(metrics["retrieval_precision"], 1.0)


class TestHallucinationEvaluator(unittest.TestCase):
    @patch("evaluation.hallucination.get_llm_provider")
    def test_evaluate_hallucination_rate(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg('{"total_claims": 10, "hallucinated_claims": 2}')
        mock_provider.return_value.get_model.return_value = mock_model

        evaluator = HallucinationEvaluator()
        score = evaluator.evaluate_hallucination_rate("Answer text", ["Context text"])
        self.assertEqual(score, 0.2)


class TestCitationEvaluator(unittest.TestCase):
    @patch("evaluation.citations.CitationBuilder")
    @patch("evaluation.citations.CitationVerifier")
    def test_evaluate_citation_accuracy(self, mock_verifier_cls, mock_builder_cls):
        # Mock builder returning 2 citations
        mock_builder = MagicMock()
        from agents.citation.builder import Citation
        c1 = Citation(source_title="Act A", section="1")
        c2 = Citation(source_title="Act B", section="2")
        mock_builder.extract_from_text.return_value = [c1, c2]
        mock_builder_cls.return_value = mock_builder

        # Mock verifier (c1 verified, c2 not verified)
        mock_verifier_cls.verify.side_effect = [
            {"verified": True, "confidence": 1.0},
            {"verified": False, "confidence": 0.0}
        ]

        evaluator = CitationEvaluator()
        score = evaluator.evaluate_citation_accuracy("Answer text with citations", "Source reference text")

        # 1 out of 2 citations verified -> Accuracy = 0.5
        self.assertEqual(score, 0.5)


class TestBenchmarkEvaluator(unittest.TestCase):
    @patch("evaluation.benchmark.get_llm_provider")
    @patch("evaluation.benchmark.RagasEvaluator")
    @patch("evaluation.benchmark.HallucinationEvaluator")
    @patch("evaluation.benchmark.CitationEvaluator")
    def test_run_benchmark_success(self, mock_cit_cls, mock_halluc_cls, mock_ragas_cls, mock_provider):
        # Mock model responses
        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            _ai_msg("Generated answer based on context."),  # _generate_response
            _ai_msg("5")  # _evaluate_quality (perfect quality score 5/5)
        ]
        mock_provider.return_value.get_model.return_value = mock_model

        # Mock sub-evaluators
        mock_halluc_cls.return_value.evaluate_hallucination_rate.return_value = 0.1
        mock_cit_cls.return_value.evaluate_citation_accuracy.return_value = 0.9

        evaluator = BenchmarkEvaluator()
        test_cases = [
            {
                "query": "What is Section 54?",
                "ground_truth": "Capital gains exemption rules.",
                "contexts": ["Section 54 exempts property capital gains."],
                "expected_keywords": ["capital gains"]
            }
        ]

        report = evaluator.run_benchmark(test_cases)

        self.assertEqual(report["cases_evaluated"], 1)
        self.assertEqual(report["success_rate"], 1.0)
        self.assertEqual(report["hallucination_rate"], 0.1)
        self.assertEqual(report["citation_accuracy"], 0.9)
        self.assertEqual(report["response_quality"], 1.0)  # 5/5 scaled to 1.0
        self.assertEqual(report["retrieval_recall"], 1.0)  # "capital gains" exists in context


class TestEvaluationRouter(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("evaluation.router.evaluator")
    def test_run_evaluation_endpoint(self, mock_evaluator):
        mock_report = {
            "hallucination_rate": 0.05,
            "retrieval_recall": 0.95,
            "citation_accuracy": 1.0,
            "response_quality": 0.9,
            "avg_latency_seconds": 1.2,
            "success_rate": 1.0,
            "cases_evaluated": 2
        }
        mock_evaluator.run_benchmark.return_value = mock_report

        payload = {
            "test_cases": [
                {
                    "query": "Q1",
                    "ground_truth": "GT1",
                    "contexts": ["C1"],
                    "expected_keywords": ["K1"]
                }
            ]
        }

        response = self.client.post("/evaluation/run", json=payload)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["cases_evaluated"], 2)
        self.assertEqual(data["hallucination_rate"], 0.05)
        self.assertEqual(data["success_rate"], 1.0)
        mock_evaluator.run_benchmark.assert_called_once()

    def test_run_evaluation_empty_bad_request(self):
        response = self.client.post("/evaluation/run", json={"test_cases": []})
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be empty", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
