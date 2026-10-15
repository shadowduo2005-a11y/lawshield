"""
hallucination.py – evaluates hallucination rate of generated legal responses.

A hallucination rate of 0.0 means the answer is completely grounded in the
provided context.  A rate of 1.0 means every claim is unverifiable or
contradicted by the context.

The LLM model is lazy-loaded: not instantiated until first evaluation call.
"""
from __future__ import annotations

import logging
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from llm.providers.factory import get_llm_provider
from ._utils import parse_json_object

logger = logging.getLogger(__name__)


class HallucinationEvaluator:
    """
    Evaluator to calculate the hallucination rate of generated answers against
    the retrieved context sources.
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

    def evaluate_hallucination_rate(self, answer: str, contexts: List[str]) -> float:
        """
        Calculates the hallucination rate of the answer against the provided contexts.

        Parameters
        ----------
        answer : str
            The generated answer to audit.
        contexts : List[str]
            Retrieved context chunks used as the grounding source.

        Returns
        -------
        float
            Rate in [0.0, 1.0].
            0.0 = fully grounded (no hallucinations detected).
            1.0 = fully hallucinated (no claims supported by context).
        """
        if not answer:
            return 0.0

        if not contexts:
            # Without context we cannot verify grounding — conservative 1.0 warning
            logger.warning(
                "No context provided for hallucination evaluation. Returning 1.0 (unverifiable)."
            )
            return 1.0

        joined_context = "\n\n".join(contexts)
        system_prompt = (
            "You are a hallucination auditor. Compare the Answer against the Context.\n"
            "Count the number of distinct factual statements in the Answer that are CONTRADICTED "
            "by the Context or cannot be found in the Context (ungrounded/hallucinated).\n"
            "Return a raw JSON response with these exact keys:\n"
            "{\n"
            '  "total_claims": 5,\n'
            '  "hallucinated_claims": 1\n'
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
            hallucinated = data.get("hallucinated_claims", 0)
            if total <= 0:
                return 0.0
            return round(min(1.0, hallucinated / total), 2)
        except Exception as exc:
            logger.error("Failed to evaluate hallucination rate: %s", exc)
            return 0.0  # Safe fallback: assume no hallucination if evaluator fails
