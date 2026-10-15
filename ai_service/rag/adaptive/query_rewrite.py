"""
Adaptive RAG – Query Rewriter.

Rewrites the user's natural-language query into a semantically-optimised
form for dense vector retrieval.
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage

from llm.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)


def rewrite_query(query: str) -> str:
    """Return a rewritten query optimised for vector search.

    Falls back to the original query if the LLM call fails.
    """
    model = get_llm_provider().get_model()

    prompt = f"""You are an expert at query formulation for legal semantic search.
Rewrite the user question below into a concise, keyword-rich query that maximises recall in a dense vector index.
Remove conversational filler.  Output ONLY the rewritten query, nothing else.

Original question: {query}
"""

    try:
        response = model.invoke([HumanMessage(content=prompt)])
        rewritten = response.content.strip()
        if not rewritten:
            return query
        logger.debug("Query rewritten: %r → %r", query, rewritten)
        return rewritten
    except Exception as exc:
        logger.warning("Query rewrite failed (%s); using original", exc)
        return query
