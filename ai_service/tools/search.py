"""
tools/search.py – Internal legal knowledge base search tool.
Wraps the hybrid RAG retrieval pipeline to find case law, statutes, and legal documents.
"""
from __future__ import annotations

import logging

from langchain_core.tools import tool

from rag.hybrid.search import advanced_hybrid_search

logger = logging.getLogger(__name__)


@tool
def legal_search(query: str, top_k: int = 5) -> str:
    """
    Searches the internal legal knowledge base for case law, statutes, sections, or regulations.
    Uses a hybrid BM25 + semantic vector search for high-recall and high-precision retrieval.

    Returns the top matching legal document chunks, each numbered and separated clearly.
    If no results are found, instructs the agent to broaden the query.

    Args:
        query: A specific legal question or keyword phrase.
               Examples: "Section 54 capital gains exemption", "breach of contract elements"
        top_k: Maximum number of results to return (default: 5, max recommended: 10).
    """
    if not query or not query.strip():
        return "Error: Query cannot be empty."

    top_k = max(1, min(top_k, 10))  # Clamp to [1, 10]

    try:
        retrieved_texts = advanced_hybrid_search(query, top_k=top_k)

        if not retrieved_texts:
            return (
                f"No relevant legal documents found for: '{query}'. "
                "Try broadening your query or using different keywords."
            )

        # Format numbered results for readability
        formatted = []
        for i, text in enumerate(retrieved_texts, start=1):
            formatted.append(f"[Result {i}]\n{text.strip()}")

        return f"\n{'─' * 60}\n".join(formatted)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Legal search failed for query '%s': %s", query, e)
        return f"Error executing legal search: {e}"
