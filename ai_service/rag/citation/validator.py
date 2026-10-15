"""
rag/citation/validator.py — Grounding & Citation Validation Guardrail.

Enforces strict document grounding:
1. Strips ungrounded external statutes (e.g. Indian Contract Act, IT Act, IPC, Evidence Act)
   if they do not appear in the retrieved context chunks.
2. Validates all [Doc N] references against the retrieved document list and strips orphan citations.
3. Ensures clean formatting of General Rule, Exceptions, Conditions, and Citations.
"""
from __future__ import annotations

import logging
import re
from typing import List

logger = logging.getLogger(__name__)

# List of common external statutes that LLMs hallucinate into Document QA responses
_EXTERNAL_STATUTE_PATTERNS = [
    r"(?i)\bIndian Contract Act(?:,\s*\d+)?\b",
    r"(?i)\bInformation Technology Act(?:,\s*\d+)?\b",
    r"(?i)\bIT Act(?:,\s*\d+)?\b",
    r"(?i)\bIndian Evidence Act(?:,\s*\d+)?\b",
    r"(?i)\bIndian Penal Code\b",
    r"(?i)\bIPC\s+Section\s+\d+\b",
    r"(?i)\bBharatiya Nyaya Sanhita\b",
    r"(?i)\bBNS\s+Section\s+\d+\b",
]


def sanitize_external_statutes(text: str, context_chunks: List[str]) -> str:
    """Remove external statute references from text if they do not appear in context_chunks."""
    text_lower = text.lower()
    if any(k in text_lower for k in ("not addressed in your uploaded", "not addressed in your documents", "under statutory indian criminal law", "under indian criminal law", "under indian legal principles", "under the bharatiya nyaya sanhita", "section 103 of the bharatiya nyaya sanhita", "however, under indian")):
        logger.info("Grounding Guardrail: Text is a general statutory explanation or fallback; skipping external statute stripping.")
        return text

    combined_context = "\n".join(context_chunks).lower()

    sanitized = text
    for pattern in _EXTERNAL_STATUTE_PATTERNS:
        matches = list(re.finditer(pattern, sanitized))
        for m in matches:
            statute_text = m.group(0)
            if statute_text.lower() not in combined_context:
                logger.warning(
                    "Grounding Guardrail: Stripping ungrounded external statute reference %r",
                    statute_text,
                )
                # Strip the ungrounded statute mention cleanly
                sanitized = re.sub(re.escape(statute_text), "", sanitized)

    # Clean up any leftover double spaces or empty bullet mentions from stripped terms
    sanitized = re.sub(r"[ \t]{2,}", " ", sanitized)
    sanitized = re.sub(r"(?m)^\s*[\-\•]\s*$", "", sanitized)
    return sanitized.strip()


def validate_doc_citations(text: str, num_docs: int) -> str:
    """Validate that every [Doc N] citation corresponds to a real chunk index 1..num_docs."""
    if num_docs == 0:
        return re.sub(r"\[Doc\s+\d+\]", "", text)

    def _replace(match: re.Match) -> str:
        n = int(match.group(1))
        if 1 <= n <= num_docs:
            return match.group(0)
        logger.warning(
            "Citation Validator: Stripping orphan citation %s (only %d docs in context)",
            match.group(0),
            num_docs,
        )
        return ""

    return re.sub(r"\[Doc\s+(\d+)\]", _replace, text)


def validate_and_sanitize_grounding(answer: str, context_chunks: List[str]) -> str:
    """Master validation: checks both citation validity and external statute grounding."""
    if not answer:
        return answer

    # 1. Strip orphan citations
    ans = validate_doc_citations(answer, len(context_chunks))

    # 2. Strip external statute hallucinations not present in context
    ans = sanitize_external_statutes(ans, context_chunks)

    return ans
