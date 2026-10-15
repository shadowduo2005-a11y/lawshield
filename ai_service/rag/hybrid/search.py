"""
rag/hybrid/search.py — Advanced Hybrid Search (Dense Vector + BM25 Sparse Search).

Combines Qdrant dense vector search with Elasticsearch BM25 / Local TF-IDF sparse search.
Uses Reciprocal Rank Fusion (RRF) with exact keyword match boosting over expanded candidate pools.
"""
from __future__ import annotations

import logging
import re
from typing import Optional, List, Dict, Any
from collections import Counter

logger = logging.getLogger(__name__)

_K = 60  # RRF constant


def _rrf_score(rank: int) -> float:
    return 1.0 / (_K + rank + 1)


def _tfidf_score(query_tokens: List[str], doc: str) -> float:
    doc_tokens = re.findall(r"[a-z0-9]+", doc.lower())
    if not doc_tokens:
        return 0.0
    doc_freq = Counter(doc_tokens)
    doc_len = len(doc_tokens)
    score = 0.0
    for token in set(query_tokens):
        if token in doc_freq:
            tf = doc_freq[token] / doc_len
            score += tf
    return score


def advanced_hybrid_search(
    query: str,
    collection_name: str = "documents",
    top_k: int = 20,
    metadata_filter: Optional[dict] = None,
    domain_terms: Optional[List[str]] = None,
) -> List[dict]:
    """Retrieve top-K candidate chunks using Hybrid Dense Vector + Sparse BM25 RRF fusion.

    Returns candidate dicts with text, metadata, vector rank, sparse rank, and combined RRF score.
    """
    if not domain_terms:
        domain_terms = []

    qdrant_payloads: List[dict] = []
    es_payloads: List[dict] = []

    # ── 1. Dense Search (Qdrant) ──────────────────────────────────────────────
    try:
        from qdrant_client.http.models import FieldCondition, Filter, MatchValue
        from rag.embedding import get_embeddings
        from rag.retrieval import get_qdrant_client

        q_client = get_qdrant_client()
        query_vector = get_embeddings().embed_query(query)

        q_filter = None
        if metadata_filter:
            conditions = [
                FieldCondition(key=f"metadata.{k}", match=MatchValue(value=v))
                for k, v in metadata_filter.items()
            ]
            q_filter = Filter(must=conditions)

            try:
                response = q_client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    query_filter=q_filter,
                    limit=top_k,
                )
                qdrant_payloads = [
                    {
                        "text": point.payload.get("text", ""),
                        "metadata": point.payload.get("metadata", {}),
                        "score": getattr(point, "score", 0.0),
                    }
                    for point in response.points if point.payload.get("text")
                ]
            except Exception as filter_exc:
                logger.warning("Filtered Qdrant query failed (%s); trying unfiltered", filter_exc)
                qdrant_payloads = []

        if not qdrant_payloads:
            response = q_client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=None,
                limit=top_k,
            )
            qdrant_payloads = [
                {
                    "text": point.payload.get("text", ""),
                    "metadata": point.payload.get("metadata", {}),
                    "score": getattr(point, "score", 0.0),
                }
                for point in response.points if point.payload.get("text")
            ]

    except Exception as exc:
        logger.error("Qdrant dense search failed: %s", exc)

    # ── 2. Sparse Search (Elasticsearch BM25 or Local TF-IDF Fallback) ───────
    try:
        from rag.retrieval import get_es_client
        es_client = get_es_client()

        if es_client is not None:
            must_clauses: List[dict] = [{"match": {"text": query}}]
            if metadata_filter:
                for k, v in metadata_filter.items():
                    must_clauses.append({"match": {f"metadata.{k}": v}})

            es_response = es_client.search(
                index=collection_name,
                body={"query": {"bool": {"must": must_clauses}}, "size": top_k},
            )
            es_payloads = [
                {
                    "text": hit["_source"].get("text", ""),
                    "metadata": hit["_source"].get("metadata", {}),
                    "score": hit.get("_score", 0.0),
                }
                for hit in es_response["hits"]["hits"]
                if hit["_source"].get("text")
            ]
    except Exception as exc:
        logger.debug("ES search failed (%s); using local sparse fallback", exc)

    if not es_payloads and qdrant_payloads:
        query_tokens = re.findall(r"[a-z0-9]+", query.lower())
        if query_tokens:
            scored = [
                (p, _tfidf_score(query_tokens, p["text"])) for p in qdrant_payloads
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            es_payloads = [p for p, s in scored if s > 0]

    # ── 3. Reciprocal Rank Fusion & Domain Keyword Boost ──────────────────────
    candidates_by_text: Dict[str, dict] = {}

    for rank, item in enumerate(qdrant_payloads):
        txt = item["text"]
        if txt not in candidates_by_text:
            candidates_by_text[txt] = {
                "text": txt,
                "metadata": item.get("metadata") or {},
                "vector_rank": rank + 1,
                "vector_score": item.get("score", 0.0),
                "sparse_rank": None,
                "sparse_score": 0.0,
                "rrf_score": 0.0,
            }
        candidates_by_text[txt]["rrf_score"] += _rrf_score(rank)

    for rank, item in enumerate(es_payloads):
        txt = item["text"]
        if txt not in candidates_by_text:
            candidates_by_text[txt] = {
                "text": txt,
                "metadata": item.get("metadata") or {},
                "vector_rank": None,
                "vector_score": 0.0,
                "sparse_rank": rank + 1,
                "sparse_score": item.get("score", 0.0),
                "rrf_score": 0.0,
            }
        else:
            candidates_by_text[txt]["sparse_rank"] = rank + 1
            candidates_by_text[txt]["sparse_score"] = item.get("score", 0.0)

        candidates_by_text[txt]["rrf_score"] += _rrf_score(rank)

    # Apply exact domain keyword boost
    for txt, cand in candidates_by_text.items():
        txt_lower = txt.lower()
        title_lower = (cand["metadata"].get("section_title") or "").lower()
        kw_boost = 0.0
        for dterm in domain_terms:
            dt = dterm.lower()
            if dt in title_lower:
                kw_boost += 0.03
            elif dt in txt_lower:
                kw_boost += 0.01
        cand["rrf_score"] += kw_boost

    sorted_candidates = sorted(
        candidates_by_text.values(), key=lambda x: x["rrf_score"], reverse=True
    )

    logger.info("Hybrid search retrieved %d merged candidates", len(sorted_candidates))
    return sorted_candidates[:top_k]
