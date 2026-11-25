"""
reasoning package init.
Exposes LegalReasoningAgent, LegalReviewerAgent, LegalVerifierAgent, and LegalConfidenceScorer.
"""
from .chain_of_thought import LegalReasoningAgent
from .reviewer import LegalReviewerAgent
from .verifier import LegalVerifierAgent
from .confidence import LegalConfidenceScorer

__all__ = [
    "LegalReasoningAgent",
    "LegalReviewerAgent",
    "LegalVerifierAgent",
    "LegalConfidenceScorer",
]
