"""
RAG agent node – semantic search over uploaded documents and session context.
"""
from __future__ import annotations

import logging

from langchain_core.messages import AIMessage

from graph.state import AgentState
from rag.pipelines import ask_question_pipeline, _direct_llm_answer, _HARD_REFUSAL

logger = logging.getLogger(__name__)


async def rag_node(state: AgentState) -> dict:
    """Queries the RAG pipeline for answers related to uploaded documents."""
    logger.info("RAG node: querying vector store.")

    user_query = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )

    try:
        result = await ask_question_pipeline(user_query)
        answer = result.get("answer", _HARD_REFUSAL)
    except Exception as exc:
        logger.error("RAG pipeline failed for query %r: %s", user_query, exc, exc_info=True)
        answer = _HARD_REFUSAL

    # Fallback to in-session document text if vectorstore returned hard refusal
    if answer == _HARD_REFUSAL:
        draft = state.get("draft_content", "")
        research = state.get("research_data", [])
        session_docs = []
        if draft:
            session_docs.append(f"[Session Contract Document]\n{draft}")
        if research:
            session_docs.append("[Session Research Content]\n" + "\n---\n".join(research))

        if session_docs:
            context_str = "\n\n---\n\n".join(session_docs)
            logger.info("RAG vectorstore yielded refusal; grounding answer on session document context.")
            try:
                answer = _direct_llm_answer(user_query, context_str=context_str)
            except Exception as direct_exc:
                logger.error("Direct fallback LLM answer failed: %s", direct_exc)

    logger.info("RAG node completed (%d chars).", len(answer))
    return {
        "messages": [AIMessage(content=answer)],
    }
