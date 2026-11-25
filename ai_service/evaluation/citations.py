"""
citations.py – evaluates the precision and grounding accuracy of citations
in the generated answer.

Integrates with the Phase 11 Citation Engine (CitationBuilder + CitationVerifier).
"""
from __future__ import annotations

import logging
from typing import List

from agents.citation.builder import CitationBuilder
from agents.citation.verifier import CitationVerifier

logger = logging.getLogger(__name__)


class CitationEvaluator:
    """
    Evaluator to calculate citation accuracy and completeness.

    ``CitationVerifier`` only has static methods so we call them directly
    rather than holding an instance.  ``CitationBuilder`` is instantiated
    once and uses lazy LLM loading internally (no upfront model allocation).
    """

    def __init__(self) -> None:
        # CitationBuilder is lazy-loaded internally — safe to instantiate here
        self.builder = CitationBuilder()

    def evaluate_citation_accuracy(self, answer: str, source_text: str) -> float:
        """
        Calculates Citation Accuracy: the ratio of verified/grounded citations
        in the generated answer.

        Formula: verified_citations / total_citations

        A score of 1.0 is also returned when the answer contains *no* citations
        (no incorrect citations present → maximum accuracy).

        Parameters
        ----------
        answer : str
            The generated answer text potentially containing legal citations.
        source_text : str
            The grounding source text against which citations are verified.

        Returns
        -------
        float
            Accuracy score in [0.0, 1.0].
        """
        citations = self.builder.extract_from_text(answer)
        if not citations:
            # No citations present → nothing incorrect → perfect accuracy
            return 1.0

        verified_count = 0
        for citation in citations:
            res = CitationVerifier.verify(citation, source_text)
            if res.get("verified", False) or res.get("confidence", 0.0) >= 0.5:
                verified_count += 1

        accuracy = round(verified_count / len(citations), 2)
        logger.info(
            "Citation Accuracy: %d/%d verified (%.2f)",
            verified_count,
            len(citations),
            accuracy,
        )
        return accuracy

    def evaluate_citation_completeness(
        self, answer: str, expected_citations: List[str]
    ) -> float:
        """
        Measures Citation Completeness: are all expected key citations referenced
        in the generated answer?

        Formula: found_expected / total_expected

        Parameters
        ----------
        answer : str
            The generated answer text.
        expected_citations : List[str]
            List of citation strings (e.g. ``["Section 54", "Income Tax Act"]``)
            that should appear in the answer.

        Returns
        -------
        float
            Completeness score in [0.0, 1.0].
        """
        if not expected_citations:
            return 1.0

        answer_upper = answer.upper()
        found = sum(
            1 for cit in expected_citations if cit.upper() in answer_upper
        )
        completeness = round(found / len(expected_citations), 2)
        logger.info(
            "Citation Completeness: %d/%d expected citations found (%.2f)",
            found,
            len(expected_citations),
            completeness,
        )
        return completeness
