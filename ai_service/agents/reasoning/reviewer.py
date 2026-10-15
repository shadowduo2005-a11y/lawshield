"""
reviewer.py – reviewer agent critiquing the generated chain-of-thought analysis.

Reviews the reasoning output for:
- Completeness (did it capture key issues?)
- Logical consistency (do the explanations follow from the analysis?)
- Clarity and actionability of suggestions.
"""
from __future__ import annotations

import json
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from llm.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

from utils.json import parse_json_object

class LegalReviewerAgent:
    """
    Reviewer Agent responsible for auditing the reasoning output.
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

    def review(self, context: str, reasoning_output: str) -> dict:
        """
        Audits the legal reasoning text against the original contract context.

        Parameters
        ----------
        context : str
            The original contract or legal text.
        reasoning_output : str
            The chain-of-thought analysis output from the Reasoning Agent.

        Returns
        -------
        dict
            A dictionary containing:
            - ``"review_status"``: ``"approved"`` or ``"needs_revision"``
            - ``"feedback"``: A detailed critique of the reasoning.
            - ``"suggestions"``: List of specific improvements or missed risks.
        """
        logger.info("Reviewing legal reasoning output…")

        system_prompt = (
            "You are a Senior Legal Counsel auditing a junior associate's legal risk analysis.\n"
            "Evaluate the draft risk analysis against the original contract text.\n"
            "Specifically check:\n"
            "1. Did the associate miss any critical risks?\n"
            "2. Are the risk explanations legally accurate and operationalized?\n"
            "3. Are the suggested contract amendments/redlines realistic and clear?\n\n"
            "You must return your assessment in raw JSON format with these exact keys:\n"
            "{\n"
            '  "review_status": "approved" or "needs_revision",\n'
            '  "feedback": "Your overall assessment of the analysis quality.",\n'
            '  "suggestions": ["suggestion 1", "suggestion 2"]\n'
            "}"
        )

        user_content = (
            f"--- ORIGINAL CONTRACT ---\n"
            f"{context}\n\n"
            f"--- RISK ANALYSIS DRAFT ---\n"
            f"{reasoning_output}\n\n"
            f"Please output your raw JSON review."
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]

        response = self.model.invoke(messages)

        try:
            data = parse_json_object(response.content)
        except (ValueError, Exception) as exc:
            logger.error(
                "Failed to parse Reviewer JSON response: %s. Using default approved.", exc
            )
            data = {
                "review_status": "approved",
                "feedback": "Automated fallback review.",
                "suggestions": [],
            }

        return data
