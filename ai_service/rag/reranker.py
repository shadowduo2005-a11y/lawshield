"""
rag/reranker.py — Legal Specificity & Exception-Aware Reranker.

Reranks candidate chunks by combining base semantic/token similarity with:
1. Domain Specificity Boost (specific topic clauses beat generic prohibitions)
2. Exception Relevance Boost (qualifications/exceptions receive higher priority when requested)
3. Section Heading Match Boost
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import List, Dict, Any, Union

logger = logging.getLogger(__name__)

# Exception indicator words in legal drafting
_EXCEPTION_MARKERS = re.compile(
    r"(?i)\b(except|unless|provided that|subject to|condition|conditions|permitted|allowed|approved|authorized|qualification|exception|exceptions)\b"
)


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _compute_tfidf_score(query_tokens: List[str], doc_text: str, idf: Dict[str, float]) -> float:
    doc_tokens = _tokenize(doc_text)
    if not doc_tokens:
        return 0.0
    doc_freq = Counter(doc_tokens)
    doc_len = len(doc_tokens)

    score = 0.0
    for token in set(query_tokens):
        tf = doc_freq.get(token, 0) / doc_len
        score += tf * idf.get(token, 0.0)
    return score


def rerank_documents(
    query: str,
    documents: List[Union[str, dict]],
    top_k: int = 5,
    domain_terms: List[str] = None,
    is_exception_query: bool = False,
) -> List[dict]:
    """Rerank documents using hybrid scoring with Specificity and Exception boosting.

    Returns a sorted list of candidate dicts:
    [
      {
        "text": str,
        "score": float,
        "specificity_score": float,
        "exception_score": float,
        "section_title": str,
        "metadata": dict
      }, ...
    ]
    """
    if not documents:
        return []

    if not domain_terms:
        domain_terms = []

    # Normalize documents into dicts with text and metadata
    norm_docs: List[dict] = []
    for d in documents:
        if isinstance(d, dict):
            text = d.get("text") or d.get("page_content") or ""
            meta = d.get("metadata") or {}
            sec_title = d.get("section_title") or meta.get("section_title") or ""
        else:
            text = str(d)
            meta = {}
            sec_title = ""

        # Extract title from text if present (e.g. "[Clause 10 — ARTIFICIAL INTELLIGENCE SYSTEMS]")
        if not sec_title and text.startswith("["):
            end_bracket = text.find("]")
            if end_bracket != -1:
                sec_title = text[1:end_bracket]

        norm_docs.append({
            "text": text,
            "metadata": meta,
            "section_title": sec_title,
            "raw": d,
        })

    query_tokens = _tokenize(query)
    if not query_tokens:
        return norm_docs[:top_k]

    # Compute IDF across corpus
    doc_token_sets = [_tokenize(d["text"]) for d in norm_docs]
    N = len(norm_docs)
    idf: Dict[str, float] = {}
    all_tokens = set(query_tokens)
    for s in doc_token_sets:
        all_tokens |= set(s)
    for token in all_tokens:
        df = sum(1 for s in doc_token_sets if token in s)
        idf[token] = math.log((N + 1) / (df + 1)) + 1.0

    scored_items: List[dict] = []

    for item in norm_docs:
        text_lower = item["text"].lower()
        title_lower = item["section_title"].lower()

        # 1. Base TF-IDF score
        base_score = _compute_tfidf_score(query_tokens, item["text"], idf)

        # 2. Specificity score: check domain term matches in title and text
        specificity_multiplier = 1.0
        domain_matches = 0
        for dterm in domain_terms:
            dterm_lower = dterm.lower()
            if dterm_lower in title_lower:
                domain_matches += 3  # High weight for section title match
            elif dterm_lower in text_lower:
                domain_matches += 1

        if domain_matches > 0:
            specificity_multiplier = 1.5 + (0.3 * min(domain_matches, 5))

        # 3. Exception score: boost clauses containing exception terms when query asks for exceptions
        exception_boost = 0.0
        if is_exception_query:
            matches = len(_EXCEPTION_MARKERS.findall(text_lower))
            if matches > 0:
                exception_boost = 0.25 + (0.05 * min(matches, 5))

        # 4. Section Title Direct Match Boost
        title_boost = 0.0
        for qtoken in query_tokens:
            if len(qtoken) > 3 and qtoken in title_lower:
                title_boost += 0.15

        final_score = (base_score * specificity_multiplier) + exception_boost + title_boost

        scored_items.append({
            **item,
            "base_score": round(base_score, 4),
            "specificity_multiplier": round(specificity_multiplier, 2),
            "exception_boost": round(exception_boost, 4),
            "score": round(final_score, 4),
        })

    scored_items.sort(key=lambda x: x["score"], reverse=True)
    return scored_items[:top_k]
