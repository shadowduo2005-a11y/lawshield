"""
benchmark.py – runs legal QA evaluations, measures latencies, and aggregates
quality reports across all six key metrics.

Metrics evaluated per benchmark run
------------------------------------
- Hallucination Rate  – fraction of answer claims not grounded in context
- Retrieval Recall    – fraction of expected keywords present in retrieved chunks
- Citation Accuracy   – fraction of answer citations verified against source
- Faithfulness        – RAGAS: claims supported by context
- Context Recall      – RAGAS: ground-truth facts present in context
- Response Quality    – LLM-as-a-judge score (1–5 stars, scaled to 0–1)
- Latency             – wall-clock seconds per test case
- Agent Success Rate  – fraction of test cases that executed without error

The LLM model used for response generation and quality scoring is lazy-loaded.
All sub-evaluators (RagasEvaluator, HallucinationEvaluator) are also lazy.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
import re

from langchain_core.messages import HumanMessage, SystemMessage
from llm.providers.factory import get_llm_provider
from .ragas import RagasEvaluator
from .retrieval import RetrievalEvaluator
from .hallucination import HallucinationEvaluator
from .citations import CitationEvaluator

logger = logging.getLogger(__name__)

# Keys included in the per-case result dicts
_PER_CASE_KEYS = [
    "query",
    "success",
    "latency_seconds",
    "hallucination_rate",
    "retrieval_recall",
    "retrieval_f1",
    "citation_accuracy",
    "faithfulness",
    "context_recall",
    "response_quality",
]


class BenchmarkEvaluator:
    """
    Runs a benchmark suite over legal QA datasets to evaluate pipeline quality.

    Sub-evaluators are created lazily on first use to avoid unnecessary LLM
    model instantiation at import time.
    """

    def __init__(self, provider_name: str | None = None) -> None:
        self.provider_name = provider_name
        self._model = None          # Lazy-loaded (generation + quality judge)
        self._ragas: Optional[RagasEvaluator] = None
        self._hallucination: Optional[HallucinationEvaluator] = None
        self._citation: Optional[CitationEvaluator] = None

    # ------------------------------------------------------------------
    # Lazy property accessors
    # ------------------------------------------------------------------

    @property
    def model(self):
        if self._model is None:
            self._model = get_llm_provider(self.provider_name).get_model()
        return self._model

    @property
    def ragas(self) -> RagasEvaluator:
        if self._ragas is None:
            self._ragas = RagasEvaluator(self.provider_name)
        return self._ragas

    @property
    def hallucination(self) -> HallucinationEvaluator:
        if self._hallucination is None:
            self._hallucination = HallucinationEvaluator(self.provider_name)
        return self._hallucination

    @property
    def citation(self) -> CitationEvaluator:
        if self._citation is None:
            self._citation = CitationEvaluator()
        return self._citation

    # ------------------------------------------------------------------
    # Main benchmark runner
    # ------------------------------------------------------------------

    def run_benchmark(self, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Runs evaluation over a list of test cases and aggregates metrics.

        Parameters
        ----------
        test_cases : List[Dict[str, Any]]
            Each dict should contain:
            - ``"query"``             : str
            - ``"ground_truth"``      : str
            - ``"contexts"``          : List[str]
            - ``"expected_keywords"`` : List[str]

        Returns
        -------
        Dict[str, Any]
            Consolidated quality report with aggregated metrics AND per-case results.
        """
        logger.info(
            "Starting evaluation benchmark run for %d test cases…", len(test_cases)
        )

        total_cases = len(test_cases)
        if total_cases == 0:
            return self._empty_report()

        # Running totals
        totals: Dict[str, float] = {
            "latency": 0.0,
            "successes": 0.0,
            "hallucination_rate": 0.0,
            "retrieval_recall": 0.0,
            "retrieval_f1": 0.0,
            "citation_accuracy": 0.0,
            "faithfulness": 0.0,
            "context_recall": 0.0,
            "quality_score": 0.0,
        }
        per_case_results: List[Dict[str, Any]] = []

        for case in test_cases:
            query = case.get("query", "")
            ground_truth = case.get("ground_truth", "")
            contexts = case.get("contexts", [])
            expected_keywords = case.get("expected_keywords", [])

            case_result: Dict[str, Any] = {"query": query, "success": False}
            start_time = time.time()

            try:
                # ── 1. Generate answer ─────────────────────────────────────
                answer = self._generate_response(query, contexts)
                latency = round(time.time() - start_time, 3)

                # ── 2. Hallucination rate ──────────────────────────────────
                halluc_rate = self.hallucination.evaluate_hallucination_rate(answer, contexts)

                # ── 3. Retrieval metrics ───────────────────────────────────
                ret_metrics = RetrievalEvaluator.calculate_metrics(contexts, expected_keywords)
                ret_recall = ret_metrics["retrieval_recall"]
                ret_f1 = ret_metrics["retrieval_f1"]

                # ── 4. Citation accuracy ───────────────────────────────────
                source_text = "\n\n".join(contexts)
                cit_acc = self.citation.evaluate_citation_accuracy(answer, source_text)

                # ── 5. RAGAS: Faithfulness ─────────────────────────────────
                faithfulness = self.ragas.evaluate_faithfulness(answer, contexts)

                # ── 6. RAGAS: Context Recall ───────────────────────────────
                context_recall = self.ragas.evaluate_context_recall(ground_truth, contexts)

                # ── 7. Response quality (1–5 → 0–1) ───────────────────────
                quality = self._evaluate_quality(query, answer, ground_truth)
                quality_scaled = quality / 5.0

                # Accumulate
                totals["latency"] += latency
                totals["successes"] += 1
                totals["hallucination_rate"] += halluc_rate
                totals["retrieval_recall"] += ret_recall
                totals["retrieval_f1"] += ret_f1
                totals["citation_accuracy"] += cit_acc
                totals["faithfulness"] += faithfulness
                totals["context_recall"] += context_recall
                totals["quality_score"] += quality_scaled

                case_result.update({
                    "success": True,
                    "latency_seconds": latency,
                    "hallucination_rate": halluc_rate,
                    "retrieval_recall": ret_recall,
                    "retrieval_f1": ret_f1,
                    "citation_accuracy": cit_acc,
                    "faithfulness": faithfulness,
                    "context_recall": context_recall,
                    "response_quality": round(quality_scaled, 2),
                })

            except Exception as exc:
                logger.error("Failed to evaluate test case '%s': %s", query, exc)
                case_result["latency_seconds"] = round(time.time() - start_time, 3)

            per_case_results.append(case_result)

        n_ok = int(totals["successes"])
        avg = lambda key: round(totals[key] / n_ok, 2) if n_ok > 0 else 0.0
        avg_latency = round(totals["latency"] / n_ok, 3) if n_ok > 0 else 0.0

        report = {
            # ── Aggregate metrics ─────────────────────────────────────
            "hallucination_rate":  avg("hallucination_rate"),
            "retrieval_recall":    avg("retrieval_recall"),
            "retrieval_f1":        avg("retrieval_f1"),
            "citation_accuracy":   avg("citation_accuracy"),
            "faithfulness":        avg("faithfulness"),
            "context_recall":      avg("context_recall"),
            "response_quality":    avg("quality_score"),
            # ── Operational metrics ───────────────────────────────────
            "avg_latency_seconds": avg_latency,
            "agent_success_rate":  round(n_ok / total_cases, 2),
            "success_rate":        round(n_ok / total_cases, 2),  # Backward compat alias
            "cases_evaluated":     total_cases,
            # ── Per-case debugging ────────────────────────────────────
            "per_case_results":    per_case_results,
        }

        logger.info(
            "Evaluation benchmark complete. Agent success rate: %.2f",
            report["agent_success_rate"],
        )
        return report

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _generate_response(self, query: str, contexts: List[str]) -> str:
        """Generates an answer from the query and retrieved context."""
        joined_context = "\n\n".join(contexts) if contexts else "(No context provided)"
        prompt = (
            f"Context information is below.\n"
            f"---------------------\n"
            f"{joined_context}\n"
            f"---------------------\n"
            f"Given the context information and not prior knowledge, answer the query.\n"
            f"Query: {query}\n"
            f"Answer:"
        )
        return self.model.invoke([HumanMessage(content=prompt)]).content

    def _evaluate_quality(
        self, query: str, answer: str, ground_truth: str
    ) -> float:
        """LLM-as-a-judge score from 1.0 to 5.0 for response quality."""
        system_prompt = (
            "You are a response quality judge. Evaluate the generated Answer against the "
            "Ground Truth answer for the given Query. Grade the response quality from 1 to 5 "
            "based on accuracy, clarity, and completeness.\n"
            "Respond with ONLY a single digit between 1 and 5 (e.g. 4)."
        )
        user_content = (
            f"Query: {query}\n\n"
            f"Ground Truth: {ground_truth}\n\n"
            f"Generated Answer: {answer}"
        )
        try:
            response = self.model.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content),
            ])
            match = re.search(r"\b([1-5])\b", response.content)
            return float(match.group(1)) if match else 3.0
        except Exception as exc:
            logger.error("Failed to evaluate quality: %s", exc)
            return 3.0

    @staticmethod
    def _empty_report() -> Dict[str, Any]:
        return {
            "hallucination_rate": 0.0,
            "retrieval_recall": 1.0,
            "retrieval_f1": 1.0,
            "citation_accuracy": 1.0,
            "faithfulness": 1.0,
            "context_recall": 1.0,
            "response_quality": 1.0,
            "avg_latency_seconds": 0.0,
            "agent_success_rate": 1.0,
            "success_rate": 1.0,
            "cases_evaluated": 0,
            "per_case_results": [],
        }
