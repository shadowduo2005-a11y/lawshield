"""
Self-RAG Evaluator — anti-hallucination hardened version.

Two checks:
1. grade_documents  – filters irrelevant chunks in ONE batched LLM call (not N serial calls).
                      On LLM failure returns [] instead of all docs so the pipeline retries
                      with a rewritten query rather than feeding ungraded chunks to the generator.
2. check_hallucination – verifies the final answer is grounded in the context.
                         Automatically treats the hard-refusal string as grounded (no check needed).
"""
from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage

from llm.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)


def grade_documents(query: str, documents: list[str]) -> list[str]:
    """Return only documents relevant to the query.

    Uses a **single batched LLM call** instead of one call per document,
    reducing latency from O(N × LLM_latency) to O(LLM_latency).
    """
    if not documents:
        return []

    # Filter out completely empty chunks first
    non_empty = [d for d in documents if d.strip()]
    if not non_empty:
        return []

    model = get_llm_provider().get_model()

    # Build a numbered list of document snippets (capped at 1 500 chars each
    # to keep the prompt under the context limit)
    numbered = "\n\n".join(
        f"[{i}] {doc[:1500]}" for i, doc in enumerate(non_empty)
    )

    prompt = f"""You are a relevance grader for a legal AI retrieval system.
Given the user's question and a numbered list of document chunks, return a JSON array
of the indices (0-based) of chunks that contain information useful for answering the question.
Return ONLY a JSON array of integers, e.g. [0, 2, 3].  Return [] if none are relevant.

Question: {query}

Documents:
{numbered}
"""
    try:
        response = model.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()

        # Parse the JSON array robustly
        match = re.search(r"\[[\d,\s]*\]", raw)
        if match:
            indices: list[int] = json.loads(match.group())
        else:
            # Try to parse the whole response as JSON
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            indices = json.loads(cleaned)

        relevant = [
            non_empty[i]
            for i in indices
            if isinstance(i, int) and 0 <= i < len(non_empty)
        ]
        logger.info(
            "Document grading (batched): %d/%d chunks kept", len(relevant), len(non_empty)
        )
        return relevant

    except Exception as exc:
        logger.warning(
            "Batched document grading failed (%s); returning [] so the pipeline retries "
            "with a rewritten query rather than passing ungraded chunks to the generator.",
            exc,
        )
        # Return empty list — the caller's retry loop will rewrite the query and try again.
        # This prevents ungraded (potentially off-topic) chunks from generating hallucinations.
        return []


_HARD_REFUSAL_MARKERS = (
    "I cannot answer this question based on the provided documents",
    "I cannot answer this based on the provided document",
    "This specific scenario is not addressed in your uploaded legal documents",
    "This query is not addressed in your uploaded legal documents",
    "This topic is not addressed in your uploaded legal documents",
)


def check_hallucination(generation: str, documents: list[str]) -> bool:
    """Return True if the generation is grounded in the documents.

    Short-circuits to True (grounded) when the answer is the canonical hard
    refusal string — that string is always safe and needs no grounding check.
    Returns True (grounded) when documents is empty only because the hard
    refusal guard above should have caught that case first; if it didn't,
    we treat it as ungrounded rather than silently passing.
    """
    # If the answer is the hard refusal, it is always grounded (no LLM call needed)
    gen_lower = generation.strip().lower()
    if any(marker.lower() in gen_lower for marker in _HARD_REFUSAL_MARKERS):
        logger.info("Hallucination check: answer is hard refusal — marking as grounded.")
        return True

    if not documents:
        # No documents to compare against and the answer is not a refusal — suspicious.
        logger.warning(
            "Hallucination check: no documents provided and answer is not a refusal "
            "— marking as HALLUCINATED to force a retry."
        )
        return False

    model = get_llm_provider().get_model()
    context = "\n---\n".join(d[:1000] for d in documents)  # cap context size

    prompt = f"""You are a hallucination detector for a legal AI system.
Is EVERY factual claim in the answer below (statutes, section numbers, case names, 
contract clauses, legal rules) DIRECTLY and EXPLICITLY supported by the provided facts?
Answer with ONLY "yes" (all claims are directly supported) or "no" (any claim is 
hallucinated, inferred, or not present in the facts).

Facts:
{context}

Answer: {generation[:2000]}
"""

    try:
        response = model.invoke([HumanMessage(content=prompt)])
        ans = response.content.strip().lower()
        # Require explicit "yes" at start to avoid "No... so yes" false positives
        result = ans.startswith("yes")
        logger.info(
            "Hallucination check result: %s (Raw: %r)",
            "grounded" if result else "HALLUCINATED",
            ans,
        )
        return result
    except Exception as exc:
        logger.warning(
            "Hallucination check LLM call failed (%s); marking as HALLUCINATED to force retry",
            exc,
        )
        # On check failure, treat as hallucinated so the pipeline retries rather than
        # silently passing through an answer we couldn't verify.
        return False


def check_answer_relevance(query: str, generation: str) -> bool:
    """Return True if the generation addresses the user's question (IsUse)."""
    model = get_llm_provider().get_model()

    prompt = f"""You are an answer relevance evaluator.
Does the generated answer fully or partially address the user's original question?
Answer with ONLY "yes" (it addresses the question) or "no" (it is completely irrelevant or fails to answer the question).

Question: {query}

Answer: {generation[:2000]}
"""

    try:
        response = model.invoke([HumanMessage(content=prompt)])
        ans = response.content.strip().lower()
        result = ans.startswith("yes")
        logger.info("Answer relevance check result: %s (Raw: %r)", "relevant" if result else "IRRELEVANT", ans)
        return result
    except Exception as exc:
        logger.warning("Answer relevance check failed (%s); assuming relevant", exc)
        return True
