"""
Self-RAG LangGraph implementation — Exception-Aware & Legal Specificity Hardened.

Implements the exact Self-RAG state graph architecture:
  __start__ -> decide_retrieval
    ├── (direct)   -> generate_direct -> __end__
    └── (retrieve) -> retrieve -> is_relevant
                        ├── (no rel)   -> no_answer_found -> __end__
                        └── (relevant) -> generate_from_context -> is_sup
                                            ├── (hallucinated) -> revise_answer -> is_sup
                                            └── (accept)       -> is_use
                                                                    ├── (END)      -> __end__
                                                                    ├── (unhelpful)-> rewrite_question -> retrieve
                                                                    └── (failed)   -> no_answer_found -> __end__
"""
from __future__ import annotations

import logging
from typing import List, TypedDict, Dict, Any, Optional

from langgraph.graph import StateGraph, END

from rag.adaptive.router import route_query
from rag.adaptive.query_rewrite import rewrite_query
from rag.expansion import expand_query
from rag.metadata.filters import extract_metadata_filters
from rag.hybrid.search import advanced_hybrid_search
from rag.reranker import rerank_documents
from rag.debug import RAGDebugSession, log_debug_session
from rag.self_rag.evaluator import (
    grade_documents,
    check_hallucination,
    check_answer_relevance,
)
from rag.citation.generator import generate_citations
from rag.citation.validator import validate_and_sanitize_grounding
from llm.providers.factory import get_llm_provider
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

_HARD_REFUSAL = (
    "I cannot answer this question based on the provided documents. "
    "Please upload the relevant legal document or contract and ask again."
)

_RAG_SYSTEM_PROMPT = (
    "You are Harvey, an expert legal AI assistant operating in STRICT DOCUMENT QA MODE.\n\n"
    "CRITICAL GROUNDING RULES:\n"
    "1. You MUST answer the user's question STRICTLY and EXCLUSIVELY using the provided retrieved context.\n"
    "2. Do NOT use your general legal knowledge or external statutes (such as Indian Contract Act, Information Technology Act, "
    "Indian Evidence Act, Indian Penal Code / IPC) UNLESS they are explicitly quoted in the retrieved context below.\n"
    "3. Every legal claim and conclusion MUST be directly traceable to the retrieved document.\n"
    "4. If a piece of information is NOT present in the retrieved context (e.g. employee salary, specific dates), state clearly: "
    "'The provided context does not mention [information].' Do NOT invent or estimate numbers, statutes, or terms.\n\n"
    "REQUIRED ANSWER FORMAT (for rules, permissions, and prohibitions):\n"
    "General Rule:\n"
    "<State the primary rule / prohibition directly from the document>\n\n"
    "Exceptions:\n"
    "<State any explicit exceptions or permitted uses from the document>\n\n"
    "Conditions / Safeguards:\n"
    "<List mandatory conditions required for any exception to apply>\n\n"
    "Citations:\n"
    "<Cite only provided document identifiers like [Doc 1], [Doc 2]>\n\n"
    "OTHER RULES:\n"
    "- If no exceptions are found in context, state: 'No exception is identified in the retrieved context.' "
    "Do not state that 'the document contains no exceptions' unless explicitly established by the text."
)

_STRICT_REGEN_SYSTEM_PROMPT = (
    "You are Harvey, a highly knowledgeable Indian legal AI assistant. "
    "Your previous answer was flagged as containing claims NOT supported by the source documents. "
    "You MUST rewrite the answer using ONLY information that is WORD-FOR-WORD present in the "
    "context provided. "
    "Every legal term, statute reference, section number, and case name you use MUST be "
    "directly copied from the context — do not paraphrase statutes or infer section numbers. "
    "Before stating that no exception exists, check if any retrieved clause lists exceptions or conditions. "
    "If you cannot answer strictly from the context, you MUST respond with: "
    "'I cannot answer this based on the provided document.'"
)


class SelfRAGState(TypedDict):
    question: str
    original_question: str
    documents: List[str]
    doc_objs: List[dict]
    generation: str
    retrieval_decision: str
    is_relevant: bool
    is_supported: bool
    is_useful: bool
    revision_count: int
    rewrite_count: int
    max_revisions: int
    max_rewrites: int
    collection_name: str
    metadata_filter: dict
    answer: str
    debug_session: Optional[RAGDebugSession]


def decide_retrieval_node(state: SelfRAGState) -> dict:
    """Decides whether retrieval is needed or direct generation can answer."""
    question = state["question"]
    decision = route_query(question)
    logger.info("Self-RAG decide_retrieval: %s", decision)
    return {"retrieval_decision": decision}


def generate_direct_node(state: SelfRAGState) -> dict:
    """Generates a direct response without context retrieval (e.g. greetings, general talk)."""
    question = state["question"]
    model = get_llm_provider().get_model()
    try:
        response = model.invoke([
            SystemMessage(content="You are Harvey, a friendly and helpful Indian legal AI assistant."),
            HumanMessage(content=question),
        ])
        ans = response.content
    except Exception as exc:
        logger.error("generate_direct failed: %s", exc)
        ans = "Hello! How can I assist you with your legal questions today?"
    return {"generation": ans, "answer": ans}


def retrieve_node(state: SelfRAGState) -> dict:
    """Retrieves candidate document chunks using expanded hybrid search + specificity reranking."""
    q = state["question"]
    orig_q = state.get("original_question") or q
    collection = state.get("collection_name") or "documents"
    meta_filter = state.get("metadata_filter") or {}

    # 1. Domain & Exception Query Expansion
    expanded = expand_query(orig_q)
    opt_query = rewrite_query(expanded["search_query"])
    extracted_filters = extract_metadata_filters(q)
    if meta_filter:
        extracted_filters.update(meta_filter)

    # 2. Hybrid Retrieval over 20 candidates
    candidates = advanced_hybrid_search(
        query=opt_query,
        collection_name=collection,
        top_k=20,
        metadata_filter=extracted_filters if extracted_filters else None,
        domain_terms=expanded["domain_terms"],
    )

    if not candidates and extracted_filters:
        candidates = advanced_hybrid_search(
            query=opt_query,
            collection_name=collection,
            top_k=20,
            metadata_filter=None,
            domain_terms=expanded["domain_terms"],
        )

    if not candidates:
        candidates = advanced_hybrid_search(
            query=orig_q,
            collection_name=collection,
            top_k=20,
            metadata_filter=None,
            domain_terms=expanded["domain_terms"],
        )

    # 3. Legal Specificity & Exception Reranking (top 5-6)
    reranked = rerank_documents(
        query=orig_q,
        documents=candidates,
        top_k=6,
        domain_terms=expanded["domain_terms"],
        is_exception_query=expanded["is_exception_query"],
    ) if candidates else []

    top_docs = [r["text"] for r in reranked]

    # Initialize Debug Session
    debug_sess = RAGDebugSession(
        original_query=orig_q,
        expanded_query=expanded["search_query"],
        rewritten_query=opt_query,
        is_exception_query=expanded["is_exception_query"],
        domain_terms=expanded["domain_terms"],
        retrieved_candidates=candidates,
        reranked_chunks=reranked,
        final_context_chunks=reranked,
    )

    logger.info("Self-RAG retrieve: %d candidates -> %d reranked chunks", len(candidates), len(top_docs))
    return {
        "documents": top_docs,
        "doc_objs": reranked,
        "debug_session": debug_sess,
    }


def is_relevant_node(state: SelfRAGState) -> dict:
    """Grades document relevance to filter out irrelevant chunks."""
    question = state.get("original_question") or state["question"]
    docs = state.get("documents", [])
    doc_objs = state.get("doc_objs", [])

    if not docs:
        return {"is_relevant": False, "documents": [], "doc_objs": []}

    relevant = grade_documents(question, docs)
    if not relevant:
        relevant = docs

    is_rel = len(relevant) > 0
    rel_objs = [obj for obj in doc_objs if obj.get("text") in relevant] or doc_objs
    logger.info("Self-RAG is_relevant: %s (%d relevant docs)", is_rel, len(relevant))
    return {"is_relevant": is_rel, "documents": relevant, "doc_objs": rel_objs}


def generate_from_context_node(state: SelfRAGState) -> dict:
    """Generates an initial answer grounded in the retrieved context."""
    question = state.get("original_question") or state["question"]
    doc_objs = state.get("doc_objs", [])
    docs = state.get("documents", [])

    # Format context cleanly with section title headers
    context_blocks = []
    for d in doc_objs:
        sec_title = d.get("section_title") or d.get("metadata", {}).get("section_title") or "General Clause"
        sec_num = d.get("metadata", {}).get("section_number") or ""
        header = f"[Source: Section {sec_num} — {sec_title}]" if sec_num else f"[Source: {sec_title}]"
        context_blocks.append(f"{header}\n{d['text']}")

    if not context_blocks:
        context_blocks = docs

    context_str = "\n\n---\n\n".join(context_blocks)
    model = get_llm_provider().get_model()

    messages = [
        SystemMessage(content=_RAG_SYSTEM_PROMPT),
        HumanMessage(content=f"Context:\n{context_str}\n\nQuestion: {question}"),
    ]
    try:
        response = model.invoke(messages)
        gen = response.content
    except Exception as exc:
        if "429" in str(exc) or "rate limit" in str(exc).lower():
            import time
            time.sleep(2.5)
            try:
                response = model.invoke(messages)
                gen = response.content
            except Exception:
                logger.error("generate_from_context retry failed: %s", exc)
                gen = _HARD_REFUSAL
        else:
            logger.error("generate_from_context failed: %s", exc)
            gen = _HARD_REFUSAL

    return {"generation": gen}


def is_sup_node(state: SelfRAGState) -> dict:
    """Checks whether the generated answer is grounded in the retrieved documents (hallucination check)."""
    gen = state.get("generation", "")
    docs = state.get("documents", [])
    is_grounded = check_hallucination(gen, docs)
    logger.info("Self-RAG is_sup check: grounded=%s", is_grounded)
    return {"is_supported": is_grounded}


def revise_answer_node(state: SelfRAGState) -> dict:
    """Rewrites the answer using a strict word-for-word context regeneration prompt."""
    revisions = state.get("revision_count", 0) + 1
    question = state.get("original_question") or state["question"]
    docs = state.get("documents", [])
    context_str = "\n\n---\n\n".join(docs)
    model = get_llm_provider().get_model()

    messages = [
        SystemMessage(content=_STRICT_REGEN_SYSTEM_PROMPT),
        HumanMessage(content=f"Context:\n{context_str}\n\nQuestion: {question}"),
    ]
    try:
        response = model.invoke(messages)
        revised = response.content
    except Exception as exc:
        logger.error("revise_answer failed: %s", exc)
        revised = _HARD_REFUSAL

    logger.info("Self-RAG revise_answer: attempt %d", revisions)
    return {"generation": revised, "revision_count": revisions}


def is_use_node(state: SelfRAGState) -> dict:
    """Checks whether the answer actually addresses the user's question (answer relevance check)."""
    orig_question = state.get("original_question") or state["question"]
    gen = state.get("generation", "")
    docs = state.get("documents", [])

    gen_lower = gen.lower()
    if "i cannot answer" in gen_lower or "please upload the relevant legal document" in gen_lower or "based on the provided document" in gen_lower:
        from rag.fallback import generate_domain_fallback_answer
        final_ans = generate_domain_fallback_answer(orig_question)
        is_useful = True
    else:
        is_useful = check_answer_relevance(orig_question, gen)
        final_ans = gen
        if is_useful and gen != _HARD_REFUSAL and docs:
            try:
                final_ans = generate_citations(gen, docs)
            except Exception as exc:
                logger.warning("Citation generation failed in is_use: %s", exc)

            # Apply Grounding & Citation Validation Guardrail
            final_ans = validate_and_sanitize_grounding(final_ans, docs)

    debug_sess = state.get("debug_session")
    if debug_sess:
        debug_sess.generated_answer = final_ans
        log_debug_session(debug_sess)

    logger.info("Self-RAG is_use check: useful=%s", is_useful)
    return {"is_useful": is_useful, "answer": final_ans}


def rewrite_question_node(state: SelfRAGState) -> dict:
    """Rewrites/expands the user query for a retry retrieval attempt."""
    rewrites = state.get("rewrite_count", 0) + 1
    orig = state.get("original_question") or state["question"]
    broader_q = f"Provide broader legal context and exact facts for: {orig}"
    new_q = rewrite_query(broader_q)
    logger.info("Self-RAG rewrite_question: attempt %d, new_query=%r", rewrites, new_q)
    return {"question": new_q, "rewrite_count": rewrites}


def no_answer_found_node(state: SelfRAGState) -> dict:
    """Terminal fallback node when no relevant documents exist or grounding fails; returns general statutory answer."""
    orig_question = state.get("original_question") or state.get("question", "")
    logger.info("Self-RAG no_answer_found: generating domain legal fallback answer for question %r", orig_question)
    from rag.fallback import generate_domain_fallback_answer
    ans = generate_domain_fallback_answer(orig_question)
    return {"answer": ans, "documents": []}


# ── Edge Routing Functions ────────────────────────────────────────────────────

def route_decide_retrieval(state: SelfRAGState) -> str:
    decision = state.get("retrieval_decision", "retrieve")
    if decision == "direct":
        return "generate_direct"
    return "retrieve"


def route_is_relevant(state: SelfRAGState) -> str:
    if state.get("is_relevant", False):
        return "generate_from_context"
    return "no_answer_found"


def route_is_sup(state: SelfRAGState) -> str:
    if state.get("is_supported", False):
        return "is_use"
    revisions = state.get("revision_count", 0)
    max_rev = state.get("max_revisions", 2)
    if revisions < max_rev:
        return "revise_answer"
    return "no_answer_found"


def route_is_use(state: SelfRAGState) -> str:
    if state.get("is_useful", False):
        return END
    rewrites = state.get("rewrite_count", 0)
    max_rw = state.get("max_rewrites", 2)
    if rewrites < max_rw:
        return "rewrite_question"
    return "no_answer_found"


def create_self_rag_graph():
    """Compiles and returns the Self-RAG StateGraph matching the workflow diagram."""
    workflow = StateGraph(SelfRAGState)

    # Add Nodes
    workflow.add_node("decide_retrieval", decide_retrieval_node)
    workflow.add_node("generate_direct", generate_direct_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("is_relevant", is_relevant_node)
    workflow.add_node("generate_from_context", generate_from_context_node)
    workflow.add_node("is_sup", is_sup_node)
    workflow.add_node("revise_answer", revise_answer_node)
    workflow.add_node("is_use", is_use_node)
    workflow.add_node("rewrite_question", rewrite_question_node)
    workflow.add_node("no_answer_found", no_answer_found_node)

    # Set Entry Point
    workflow.set_entry_point("decide_retrieval")

    # Conditional Edge from decide_retrieval
    workflow.add_conditional_edges(
        "decide_retrieval",
        route_decide_retrieval,
        {
            "retrieve": "retrieve",
            "generate_direct": "generate_direct",
        },
    )

    # Edge generate_direct -> END
    workflow.add_edge("generate_direct", END)

    # Edge retrieve -> is_relevant
    workflow.add_edge("retrieve", "is_relevant")

    # Conditional Edge from is_relevant
    workflow.add_conditional_edges(
        "is_relevant",
        route_is_relevant,
        {
            "generate_from_context": "generate_from_context",
            "no_answer_found": "no_answer_found",
        },
    )

    # Edge generate_from_context -> is_sup
    workflow.add_edge("generate_from_context", "is_sup")

    # Conditional Edge from is_sup
    workflow.add_conditional_edges(
        "is_sup",
        route_is_sup,
        {
            "is_use": "is_use",
            "revise_answer": "revise_answer",
            "no_answer_found": "no_answer_found",
        },
    )

    # Edge revise_answer -> is_sup
    workflow.add_edge("revise_answer", "is_sup")

    # Conditional Edge from is_use
    workflow.add_conditional_edges(
        "is_use",
        route_is_use,
        {
            END: END,
            "rewrite_question": "rewrite_question",
            "no_answer_found": "no_answer_found",
        },
    )

    # Edge rewrite_question -> retrieve
    workflow.add_edge("rewrite_question", "retrieve")

    # Edge no_answer_found -> END
    workflow.add_edge("no_answer_found", END)

    return workflow.compile()


self_rag_graph = create_self_rag_graph()
