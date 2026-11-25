"""
ragas.py – evaluates RAG quality metrics using LLM-as-a-judge prompts.

Implements three RAGAS-inspired metrics:
- Faithfulness     – are answer claims supported by the context?
- Context Recall   – does the context cover the ground-truth facts?
- Answer Relevance – does the answer actually address the user's query?

The LLM model is lazy-loaded: it is NOT instantiated until the first
evaluation call is made.
"""
from __future__ import annotations

import logging
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from llm.providers.factory import get_llm_provider
from ._utils import parse_json_object

logger = logging.getLogger(__name__)


class RagasEvaluator:
    """
    RAG Quality Evaluator implementing Faithfulness, Context Recall, and Answer Relevance.
    """

    def __init__(self, provider_name: str | None = None) -> None:
        self.provider_name = provider_name
        self._model = None  # Lazy-loaded

    @property
    def model(self):
        """Lazily initialises the LLM model on first access."""
        if self._model is None:
            self._model = get_llm_provider(self.provider_name).get_model()
        return self._model

    # ------------------------------------------------------------------
    # Faithfulness
    # ------------------------------------------------------------------

    def evaluate_faithfulness(self, answer: str, contexts: List[str]) -> float:
        """
        Measures Faithfulness: is the generated answer strictly derived from the
        retrieved contexts?

        Formula: supported_claims / total_claims

        Returns
        -------
        float
            Score in [0.0, 1.0].  1.0 = fully faithful, 0.0 = all claims unsupported.
        """
        if not answer or not contexts:
            return 0.0

        joined_context = "\n\n".join(contexts)
        system_prompt = (
            "You are a factual accuracy auditor. Analyze the provided Answer against the Context.\n"
            "Identify all distinct statements/claims made in the Answer, and check if each claim is "
            "directly supported by the Context.\n"
            "Output your audit in raw JSON format with these exact keys:\n"
            "{\n"
            '  "total_claims": 5,\n'
            '  "supported_claims": 4\n'
            "}"
        )
        user_content = (
            f"--- CONTEXT ---\n{joined_context}\n\n"
            f"--- ANSWER ---\n{answer}\n\n"
            f"Please output your raw JSON audit."
        )

        try:
            response = self.model.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content),
            ])
            data = parse_json_object(response.content)
            total = data.get("total_claims", 1)
            supported = data.get("supported_claims", 0)
            if total <= 0:
                return 1.0
            return round(min(1.0, supported / total), 2)
        except Exception as exc:
            logger.error("Failed to evaluate faithfulness: %s", exc)
            return 0.5  # Neutral fallback

    # ------------------------------------------------------------------
    # Context Recall
    # ------------------------------------------------------------------

    def evaluate_context_recall(self, ground_truth: str, contexts: List[str]) -> float:
        """
        Measures Context Recall: are all key facts from the Ground Truth present in
        the retrieved contexts?

        Formula: retrieved_facts / total_ground_truth_facts

        Returns
        -------
        float
            Score in [0.0, 1.0].  1.0 = all facts retrieved, 0.0 = nothing retrieved.
        """
        if not ground_truth or not contexts:
            return 0.0

        joined_context = "\n\n".join(contexts)
        system_prompt = (
            "You are a retrieval auditor. Analyze the provided Context against the Ground Truth.\n"
            "Identify all distinct key facts in the Ground Truth, and check if each fact is present "
            "or successfully retrieved in the Context.\n"
            "Output your audit in raw JSON format with these exact keys:\n"
            "{\n"
            '  "total_ground_truth_facts": 5,\n'
            '  "retrieved_facts": 4\n'
            "}"
        )
        user_content = (
            f"--- RETRIEVED CONTEXT ---\n{joined_context}\n\n"
            f"--- GROUND TRUTH ---\n{ground_truth}\n\n"
            f"Please output your raw JSON audit."
        )

        try:
            response = self.model.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content),
            ])
            data = parse_json_object(response.content)
            total = data.get("total_ground_truth_facts", 1)
            retrieved = data.get("retrieved_facts", 0)
            if total <= 0:
                return 1.0
            return round(min(1.0, retrieved / total), 2)
        except Exception as exc:
            logger.error("Failed to evaluate context recall: %s", exc)
            return 0.5  # Neutral fallback

    # ------------------------------------------------------------------
    # Answer Relevance
    # ------------------------------------------------------------------

    def evaluate_answer_relevance(self, query: str, answer: str) -> float:
        """
        Measures Answer Relevance: does the answer directly and completely address
        the user's query?

        Returns
        -------
        float
            Score in [0.0, 1.0].  1.0 = fully relevant, 0.0 = completely irrelevant.
        """
        if not query or not answer:
            return 0.0

        system_prompt = (
            "You are a relevance auditor. Evaluate whether the Answer directly and "
            "completely addresses the given Query.\n"
            "Output your assessment in raw JSON format with these exact keys:\n"
            "{\n"
            '  "relevance_score": 0.85\n'
            "}\n"
            "Where relevance_score is a float between 0.0 and 1.0."
        )
        user_content = (
            f"--- QUERY ---\n{query}\n\n"
            f"--- ANSWER ---\n{answer}\n\n"
            f"Please output your raw JSON assessment."
        )

        try:
            response = self.model.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content),
            ])
            data = parse_json_object(response.content)
            score = float(data.get("relevance_score", 0.5))
            return round(min(1.0, max(0.0, score)), 2)
        except Exception as exc:
            logger.error("Failed to evaluate answer relevance: %s", exc)
            return 0.5  # Neutral fallback
