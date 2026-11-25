"""
Adaptive RAG – Router.

Decides which data source should answer the query:
  - "vectorstore" : internal Qdrant / ES legal corpus
  - "web_search"  : live internet (for current events, recent legislation)
  - "direct"      : LLM can answer without retrieval (definitions, small-talk)
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage

from llm.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

_VALID_SOURCES = {"vectorstore", "web_search", "direct"}


def route_query(query: str) -> str:
    """Return the data source that best matches the query."""
    model = get_llm_provider().get_model()

    prompt = f"""You are a routing agent for a legal AI system.
Choose the best data source to answer the user's question.

Options:
- "vectorstore"  – for questions about internal legal documents, case law, or contracts already uploaded
- "web_search"   – for current news, recent legislation, or anything that requires live internet data
- "direct"       – for simple definitions, greetings, or questions the LLM can answer without external data

Respond with ONLY one of the three option strings.

Question: {query}
"""

    try:
        response = model.invoke([HumanMessage(content=prompt)])
        answer = response.content.strip().lower().strip('"').strip("'")

        for source in _VALID_SOURCES:
            if source in answer:
                logger.info("Adaptive router chose: %s", source)
                return source
    except Exception as exc:
        logger.warning("Adaptive routing failed (%s); defaulting to vectorstore", exc)

    return "vectorstore"
