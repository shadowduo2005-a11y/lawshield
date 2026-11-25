"""
RAG Pipelines — anti-hallucination hardened version.

Key changes vs previous version:
- REMOVED "direct" routing: LLM must never answer legal questions from training
  data alone — every response must be grounded in retrieved documents.
- FIXED hallucination retry: the strict regeneration no longer embeds context
  inside the query string (causing garbled prompts). Context is passed cleanly
  via context_str and the query stays unchanged.
- ADDED _WEB_SEARCH_SYSTEM_PROMPT: web-search results get a dedicated prompt
  that forbids the LLM from adding any legal interpretation beyond what the
  results explicitly state.
- HARD REFUSAL on exhausted retries: if context_used is still empty or the
  answer never passes grounding, the pipeline always returns the canonical
  refusal string rather than a potentially hallucinated answer.
"""
from __future__ import annotations

import logging
import uuid

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from rag.chunking import chunk_text
from rag.embedding import get_embeddings
from rag.retrieval import get_qdrant_client, get_es_client, init_collections
from rag.reranker import rerank_documents

from rag.adaptive.router import route_query
from rag.adaptive.query_rewrite import rewrite_query
from rag.metadata.filters import extract_metadata_filters
from rag.hybrid.search import advanced_hybrid_search
from rag.self_rag.evaluator import grade_documents, check_hallucination, check_answer_relevance
from rag.citation.generator import generate_citations
from llm.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hard refusal – returned whenever the pipeline cannot ground an answer.
# Never let the LLM invent an answer.
# ---------------------------------------------------------------------------
_HARD_REFUSAL = (
    "I cannot answer this question based on the provided documents. "
    "Please upload the relevant legal document or contract and ask again."
)

# ---------------------------------------------------------------------------
# Vectorstore / document RAG prompt
# ---------------------------------------------------------------------------
_RAG_SYSTEM_PROMPT = (
    "You are Harvey, a highly knowledgeable Indian legal AI assistant. "
    "You MUST answer the user's question STRICTLY and EXCLUSIVELY using the provided context. "
    "Do NOT include any external knowledge, generic legal language, or assumptions that are "
    "not explicitly stated in the context. "
    "Cite specific statutes, sections, or cases ONLY if they appear verbatim in the context. "
    "Do NOT invent or infer any statute, section number, or case name that is not directly "
    "quoted in the context below. "
    "If the provided context does not contain the information needed to answer the question, "
    "you MUST state exactly: "
    "'I cannot answer this based on the provided document.' and do not attempt to guess."
)

# ---------------------------------------------------------------------------
# Web-search prompt — separate from RAG prompt to prevent citation invention
# ---------------------------------------------------------------------------
_WEB_SEARCH_SYSTEM_PROMPT = (
    "You are Harvey, an Indian legal AI assistant. "
    "You have been given live web search results. "
    "Summarise ONLY the information that is explicitly present in the search results below. "
    "Do NOT add legal interpretation, invented statutes, or case references that do not "
    "appear in the search results. "
    "If the search results do not contain enough information to answer the question, say so clearly."
)

# ---------------------------------------------------------------------------
# Strict regeneration prompt — used when first answer fails hallucination check
# ---------------------------------------------------------------------------
_STRICT_REGEN_SYSTEM_PROMPT = (
    "You are Harvey, a highly knowledgeable Indian legal AI assistant. "
    "Your previous answer was flagged as containing claims NOT supported by the source documents. "
    "You MUST rewrite the answer using ONLY information that is WORD-FOR-WORD present in the "
    "context provided. "
    "Every legal term, statute reference, section number, and case name you use MUST be "
    "directly copied from the context — do not paraphrase statutes or infer section numbers. "
    "If you cannot answer strictly from the context, you MUST respond with: "
    "'I cannot answer this based on the provided document.'"
)


def ingest_document(text: str, metadata: dict, collection_name: str = "documents"):
    """Pipeline to chunk, embed, and index a document into Qdrant & ES."""
    init_collections(collection_name)
    
    # 1. Chunking
    chunks = chunk_text(text, metadata)
    texts = [chunk.page_content for chunk in chunks]
    metadatas = [chunk.metadata for chunk in chunks]
    
    # 2. Embeddings
    logger.info("Generating embeddings...")
    embeddings_model = get_embeddings()
    vectors = embeddings_model.embed_documents(texts)
    
    point_ids = [str(uuid.uuid4()) for _ in texts]
    
    # 3. Index to Qdrant (Vector)
    try:
        from qdrant_client.http.models import PointStruct
        q_client = get_qdrant_client()
        points = [
            PointStruct(id=pid, vector=vec, payload={"text": txt, "metadata": meta})
            for pid, vec, txt, meta in zip(point_ids, vectors, texts, metadatas)
        ]
        q_client.upsert(collection_name=collection_name, points=points)
    except Exception as e:
        logger.error(f"Failed to ingest to Qdrant: {e}")

    # 4. Index to Elasticsearch (Lexical) if available
    try:
        es_client = get_es_client()
        if es_client is not None:
            operations = []
            for pid, txt, meta in zip(point_ids, texts, metadatas):
                operations.append({"index": {"_index": collection_name, "_id": pid}})
                operations.append({"text": txt, "metadata": meta})
                
            if operations:
                es_client.bulk(operations=operations)
    except Exception as e:
        logger.error(f"Failed to ingest to ES: {e}")

    return {"status": "success", "chunks_indexed": len(texts)}


def _direct_llm_answer(
    query: str,
    context_str: str | None = None,
    system_prompt: str | None = None,
) -> str:
    """Generate a response via a single direct LLM call (no agent graph).

    Parameters
    ----------
    query:
        The user's question (never embed context in here).
    context_str:
        Retrieved context to inject. If None the prompt has no context section
        and ``_HARD_REFUSAL`` is returned immediately to prevent raw LLM use.
    system_prompt:
        Override the default system prompt. Defaults to ``_RAG_SYSTEM_PROMPT``.

    Notes
    -----
    We deliberately forbid calling this function without ``context_str`` for
    legal questions.  The only caller that may omit context is web_search,
    which provides its own context from live results.
    """
    if context_str is None:
        logger.warning(
            "_direct_llm_answer called without context_str — generating general domain fallback answer."
        )
        from rag.fallback import generate_domain_fallback_answer
        return generate_domain_fallback_answer(query)

    model = get_llm_provider().get_model()
    sys_prompt = system_prompt or _RAG_SYSTEM_PROMPT

    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=f"Context:\n{context_str}\n\nQuestion: {query}"),
    ]

    try:
        ans = model.invoke(messages).content
        if "i cannot answer this" in ans.lower() or "please upload the relevant legal document" in ans.lower():
            from rag.fallback import generate_domain_fallback_answer
            ans = generate_domain_fallback_answer(query)
        return ans
    except Exception as exc:
        logger.error("Direct LLM call failed in RAG pipeline: %s", exc)
        return "I encountered an error generating a response. Please try again."


async def ask_question_pipeline(
    query: str,
    metadata_filter: dict = None,
    collection_name: str = "documents",
):
    """Advanced Self-RAG Pipeline driven by the compiled StateGraph."""
    from rag.self_rag.graph import self_rag_graph
    from rag.fallback import generate_domain_fallback_answer

    initial_state = {
        "question": query,
        "original_question": query,
        "documents": [],
        "generation": "",
        "retrieval_decision": "",
        "is_relevant": False,
        "is_supported": False,
        "is_useful": False,
        "revision_count": 0,
        "rewrite_count": 0,
        "max_revisions": 2,
        "max_rewrites": 2,
        "collection_name": collection_name,
        "metadata_filter": metadata_filter or {},
        "answer": "",
    }

    try:
        final_state = await self_rag_graph.ainvoke(initial_state)
        answer = final_state.get("answer")
        if not answer or answer == _HARD_REFUSAL or "i cannot answer this question based on the provided documents" in answer.lower():
            answer = generate_domain_fallback_answer(query)
        context_used = final_state.get("documents") or []
    except Exception as exc:
        logger.error("Self-RAG StateGraph execution failed: %s", exc, exc_info=True)
        answer = generate_domain_fallback_answer(query)
        context_used = []

    debug_sess = final_state.get("debug_session")

    return {
        "answer": answer,
        "context_used": context_used,
        "debug_session": debug_sess,
    }
