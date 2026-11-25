"""
output_guards.py
Output validation, grounding verification, and deanonymization pipeline using Guardrails AI.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from guardrails import Guard
from masking.masking_pipeline import restore_text
from masking.replacement import MaskingState
from .validators import (
    JurisdictionalSafetyValidator,
    LegalCitationValidator,
    LegalDisclaimerValidator,
    RepetitionLoopValidator,
    SecretLeakValidator,
)

logger = logging.getLogger(__name__)


class OutputGuardrailPipeline:
    """
    Executes output validations on LLM generated answers before presentation to user:
    1. Repetition loop mitigation (severing degenerate model loops and restoring statutory facts)
    2. Jurisdictional safety enforcement (replacing US refusal boilerplate with Indian legal analysis)
    3. Secret and system credential leak prevention
    4. Document citation accuracy and ungrounded statute removal
    5. Legal disclaimer enforcement (optional per query scope)
    6. PII restoration / deanonymization back to original values
    """

    def __init__(self, require_disclaimer: bool = False) -> None:
        self.guard = Guard().use(
            RepetitionLoopValidator(on_fail="fix"),
            JurisdictionalSafetyValidator(on_fail="fix"),
            SecretLeakValidator(on_fail="fix"),
            LegalCitationValidator(on_fail="fix"),
            LegalDisclaimerValidator(require_disclaimer=require_disclaimer, on_fail="fix"),
        )

    def validate_and_restore(
        self,
        answer: str,
        state: Optional[MaskingState] = None,
        context_chunks: Optional[List[str]] = None,
        enforce_disclaimer: bool = False,
        user_question: Optional[str] = None,
    ) -> str:
        """
        Validate generated answer, verify citations against retrieved chunks,
        check legal disclaimers, and restore masked PII tokens to original strings.
        """
        if not answer or not answer.strip():
            return answer

        # Intercept document RAG refusals and convert to general statutory analysis per user specification
        ans_lower = answer.lower()
        if any(ref in ans_lower for ref in ("i cannot answer this question based on the provided documents", "i cannot answer this based on the provided document", "please upload the relevant legal document")):
            from rag.fallback import generate_domain_fallback_answer
            answer = generate_domain_fallback_answer(user_question or answer)

        metadata = {
            "context_chunks": context_chunks or [],
            "enforce_disclaimer": enforce_disclaimer,
            "user_question": user_question,
        }

        try:
            result = self.guard.validate(answer, metadata=metadata)
            validated_text = str(result.validated_output or answer)
        except Exception as exc:
            logger.error("Output guardrail pipeline exception: %s", exc)
            validated_text = answer

        # Perform deanonymization / restoration of PII placeholders
        if state is not None:
            validated_text = restore_text(validated_text, state)

        return validated_text
