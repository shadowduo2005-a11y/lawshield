"""
guardrails package
Public interface for Guardrails AI input/output validation, legal safety, and PII masking.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from masking.replacement import MaskingState
from .input_guards import InputGuardrailPipeline
from .output_guards import OutputGuardrailPipeline
from .validators import (
    JurisdictionalSafetyValidator,
    LegalCitationValidator,
    LegalDisclaimerValidator,
    LegalDomainValidator,
    PIIPresidioValidator,
    PromptInjectionValidator,
    RepetitionLoopValidator,
    SecretLeakValidator,
)

# Global shared pipeline instances for standard conversational routing
_default_input_pipeline = InputGuardrailPipeline()
_default_output_pipeline = OutputGuardrailPipeline()


def validate_input(text: str, state: Optional[MaskingState] = None) -> Tuple[str, MaskingState]:
    """Run default input guardrails and PII masking via Presidio Anonymizer Engine."""
    return _default_input_pipeline.validate_and_mask(text, state=state)


def validate_output(
    answer: str,
    state: Optional[MaskingState] = None,
    context_chunks: Optional[List[str]] = None,
    enforce_disclaimer: bool = False,
    user_question: Optional[str] = None,
) -> str:
    """Run default output guardrails, citation verification, safety checks, and PII restoration."""
    return _default_output_pipeline.validate_and_restore(
        answer,
        state=state,
        context_chunks=context_chunks,
        enforce_disclaimer=enforce_disclaimer,
        user_question=user_question,
    )


__all__ = [
    "InputGuardrailPipeline",
    "OutputGuardrailPipeline",
    "validate_input",
    "validate_output",
    "PIIPresidioValidator",
    "LegalCitationValidator",
    "PromptInjectionValidator",
    "SecretLeakValidator",
    "LegalDomainValidator",
    "LegalDisclaimerValidator",
    "JurisdictionalSafetyValidator",
    "RepetitionLoopValidator",
]
