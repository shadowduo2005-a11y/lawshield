"""
rag/expansion.py — Query Expansion & Domain/Exception Term Extractor.

Enhances natural-language queries with legal domain synonyms and exception keywords
without diluting the original user intent.
"""
from __future__ import annotations

import re
from typing import TypedDict, List

# Domain synonym mapping for tech/legal terms
_DOMAIN_SYNONYMS = {
    "chatgpt": ["chatgpt", "artificial intelligence", "generative ai", "chatbots", "code assistants", "ai systems"],
    "ai": ["artificial intelligence", "generative ai", "chatbots", "code assistants", "ai systems"],
    "generative ai": ["generative ai", "artificial intelligence", "chatbots", "llm"],
    "chatbot": ["chatbots", "generative ai", "ai systems"],
    "code assistant": ["code assistants", "ai tools"],
    "competitor": ["competitor", "competing business", "covenant not to compete", "non-compete"],
    "backup": ["backup", "automated backups", "archival", "retention exception"],
    "delete": ["deletion", "destruction", "return or destroy", "erase"],
    "law": ["mandatory law", "applicable law", "statutory law", "governing law", "prevails", "conflicts"],
}

# Exception indicators that suggest the query asks about qualifications/exceptions
_EXCEPTION_TRIGGER_RE = re.compile(
    r"(?i)\b(exception|exceptions|unless|except|provided that|subject to|permitted|allowed|allow|condition|conditions|qualification|qualifications|override|overriding)\b"
)

_EXCEPTION_KEYWORDS = [
    "exception", "exceptions", "unless", "except", "provided that", "subject to", "conditions", "permitted", "allowed", "approved", "authorized"
]


class ExpandedQuery(TypedDict):
    original_query: str
    search_query: str
    domain_terms: List[str]
    exception_terms: List[str]
    is_exception_query: bool


def expand_query(query: str) -> ExpandedQuery:
    """Expand query with relevant domain terms and exception keywords."""
    query_lower = query.lower()
    domain_terms: List[str] = []
    
    for key, synonyms in _DOMAIN_SYNONYMS.items():
        if key in query_lower:
            for syn in synonyms:
                if syn not in domain_terms:
                    domain_terms.append(syn)

    is_exception_query = bool(_EXCEPTION_TRIGGER_RE.search(query_lower))
    exception_terms: List[str] = _EXCEPTION_KEYWORDS if is_exception_query else []

    # Build clean expanded query string for search
    extra_keywords = " ".join(domain_terms + (exception_terms[:4] if is_exception_query else []))
    search_query = f"{query} {extra_keywords}".strip() if extra_keywords else query

    return {
        "original_query": query,
        "search_query": search_query,
        "domain_terms": domain_terms,
        "exception_terms": exception_terms,
        "is_exception_query": is_exception_query,
    }
