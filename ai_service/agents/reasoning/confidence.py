"""
confidence.py – confidence scorer for legal reasoning.

Calculates a numerical confidence score (0.0 to 1.0) based on:
1. Grounded status (from Verifier Agent)
2. Review status (from Reviewer Agent)
3. Number of warnings (from Verifier Agent)
4. Presence of structured logical sections (Analysis, Risk, Changes)
5. Clarity / completeness of the explanation

A ``detailed_breakdown()`` method is also provided for full score explainability.
"""
from __future__ import annotations

import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Required section headers in the reasoning output (checked case-insensitively)
_SECTION_HEADERS = ["ANALYSIS", "RISKS FOUND", "RISK EXPLANATIONS", "SUGGESTED CHANGES"]

# Per-warning deduction against the warning budget of 0.20
_WARNING_DEDUCTION = 0.05


class LegalConfidenceScorer:
    """
    Heuristic confidence scorer for legal reasoning outputs.

    Score breakdown (totals 1.0):
    - 0.30: Verifier Grounding Check  (True → 0.30, False → 0.00)
    - 0.30: Reviewer Approval         (approved → 0.30, needs_revision → 0.15)
    - 0.20: Warning Penalty           (no warnings → 0.20, −0.05 per warning, min 0.00)
    - 0.20: Structural Integrity      (0.05 per expected section header found)
    """

    @staticmethod
    def _compute_components(
        reasoning_output: str,
        reviewer_result: dict,
        verifier_result: dict,
    ) -> Dict[str, float]:
        """
        Returns a dictionary of score components keyed by name.
        """
        components: Dict[str, float] = {}
        output_upper = (reasoning_output or "").upper()

        # 1. Grounding check (30 %)
        grounded = verifier_result.get("grounded", False)
        components["grounding"] = 0.30 if grounded else 0.00
        logger.debug("Confidence: grounding=%.2f (grounded=%s)", components["grounding"], grounded)

        # 2. Reviewer approval (30 %)
        rev_status = reviewer_result.get("review_status", "needs_revision")
        components["reviewer"] = 0.30 if rev_status == "approved" else 0.15
        logger.debug("Confidence: reviewer=%.2f (status=%s)", components["reviewer"], rev_status)

        # 3. Warning penalty (20 %)
        warnings = verifier_result.get("warnings") or []
        num_warnings = len(warnings)
        components["warnings"] = max(0.0, 0.20 - num_warnings * _WARNING_DEDUCTION)
        logger.debug(
            "Confidence: warnings=%.2f (count=%d)", components["warnings"], num_warnings
        )

        # 4. Structural integrity (20 %)
        structural = sum(
            0.05 for header in _SECTION_HEADERS if header in output_upper
        )
        components["structure"] = structural
        logger.debug("Confidence: structure=%.2f", structural)

        return components

    @staticmethod
    def score(
        reasoning_output: str,
        reviewer_result: dict,
        verifier_result: dict,
    ) -> float:
        """
        Computes a single confidence score between 0.0 and 1.0.

        Parameters
        ----------
        reasoning_output : str
            The final reasoning text produced by the Reasoning Agent.
        reviewer_result : dict
            Output dict from ``LegalReviewerAgent.review()``.
        verifier_result : dict
            Output dict from ``LegalVerifierAgent.verify()``.

        Returns
        -------
        float
            Rounded confidence score in [0.0, 1.0].
        """
        components = LegalConfidenceScorer._compute_components(
            reasoning_output, reviewer_result, verifier_result
        )
        total = round(sum(components.values()), 2)
        logger.info("Final legal reasoning confidence score: %.2f", total)
        return total

    @staticmethod
    def detailed_breakdown(
        reasoning_output: str,
        reviewer_result: dict,
        verifier_result: dict,
    ) -> Dict[str, float | str]:
        """
        Returns a human-readable breakdown of the confidence score components.

        Returns
        -------
        dict
            Keys: ``"total"``, ``"grounding"``, ``"reviewer"``, ``"warnings"``,
            ``"structure"``, ``"reviewer_status"``, ``"warning_count"``,
            ``"sections_found"``.
        """
        components = LegalConfidenceScorer._compute_components(
            reasoning_output, reviewer_result, verifier_result
        )
        output_upper = (reasoning_output or "").upper()
        sections_found = [h for h in _SECTION_HEADERS if h in output_upper]
        warning_count = len(verifier_result.get("warnings") or [])

        return {
            "total": round(sum(components.values()), 2),
            "grounding": components["grounding"],
            "reviewer": components["reviewer"],
            "warnings": components["warnings"],
            "structure": components["structure"],
            "reviewer_status": reviewer_result.get("review_status", "needs_revision"),
            "warning_count": warning_count,
            "sections_found": sections_found,
        }
