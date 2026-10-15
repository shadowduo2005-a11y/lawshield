"""
rag/debug.py — Structured RAG Retrieval Debugging Module.

Provides detailed inspection of the retrieval pipeline per query:
- Original & expanded/rewritten query
- Hybrid retrieval candidate chunks & scores (Vector, BM25, RRF)
- Reranker scores (Base score, Specificity multiplier, Exception boost)
- Final context chunks passed to LLM
- Generated answer
"""
from __future__ import annotations

import logging
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("rag.debug")


@dataclass
class RAGDebugSession:
    original_query: str
    expanded_query: str = ""
    rewritten_query: str = ""
    is_exception_query: bool = False
    domain_terms: List[str] = field(default_factory=list)
    retrieved_candidates: List[Dict[str, Any]] = field(default_factory=list)
    reranked_chunks: List[Dict[str, Any]] = field(default_factory=list)
    final_context_chunks: List[Dict[str, Any]] = field(default_factory=list)
    generated_answer: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_query": self.original_query,
            "expanded_query": self.expanded_query,
            "rewritten_query": self.rewritten_query,
            "is_exception_query": self.is_exception_query,
            "domain_terms": self.domain_terms,
            "retrieved_candidate_count": len(self.retrieved_candidates),
            "candidates": [
                {
                    "chunk_id": c.get("metadata", {}).get("chunk_id", "N/A"),
                    "section_number": c.get("metadata", {}).get("section_number", "N/A"),
                    "section_title": c.get("metadata", {}).get("section_title") or c.get("section_title", "N/A"),
                    "rrf_score": c.get("rrf_score", 0.0),
                    "text_snippet": c.get("text", "")[:120].replace("\n", " ") + "...",
                }
                for c in self.retrieved_candidates[:10]
            ],
            "reranked_chunks": [
                {
                    "rank": idx + 1,
                    "section_number": r.get("metadata", {}).get("section_number", "N/A"),
                    "section_title": r.get("section_title", "N/A"),
                    "final_score": r.get("score", 0.0),
                    "base_score": r.get("base_score", 0.0),
                    "specificity_multiplier": r.get("specificity_multiplier", 1.0),
                    "exception_boost": r.get("exception_boost", 0.0),
                    "text_snippet": r.get("text", "")[:150].replace("\n", " ") + "...",
                }
                for idx, r in enumerate(self.reranked_chunks)
            ],
            "final_context_count": len(self.final_context_chunks),
            "generated_answer_snippet": self.generated_answer[:200] + "...",
        }

    def format_text_report(self) -> str:
        lines = []
        lines.append("================================================================")
        lines.append("                  RAG RETRIEVAL DEBUG REPORT                   ")
        lines.append("================================================================")
        lines.append(f"Original Query: {self.original_query}")
        lines.append(f"Expanded Query: {self.expanded_query}")
        lines.append(f"Rewritten Query: {self.rewritten_query}")
        lines.append(f"Domain Terms Extracted: {self.domain_terms}")
        lines.append(f"Is Exception Query: {self.is_exception_query}")
        lines.append("")
        lines.append("----------------------------------------------------------------")
        lines.append(f"1. RETRIEVED CANDIDATE POOL ({len(self.retrieved_candidates)} chunks)")
        lines.append("----------------------------------------------------------------")
        for i, c in enumerate(self.retrieved_candidates[:8], 1):
            meta = c.get("metadata", {})
            sec_num = meta.get("section_number", "")
            sec_title = meta.get("section_title") or c.get("section_title", "General")
            snip = c.get("text", "")[:100].replace("\n", " ")
            lines.append(f"[{i}] Score: {c.get('rrf_score', 0.0):.4f} | Section {sec_num} ({sec_title}) | Snippet: {snip}...")

        lines.append("")
        lines.append("----------------------------------------------------------------")
        lines.append(f"2. RERANKED CHUNKS ({len(self.reranked_chunks)} passed to LLM context)")
        lines.append("----------------------------------------------------------------")
        for i, r in enumerate(self.reranked_chunks, 1):
            meta = r.get("metadata", {})
            sec_num = meta.get("section_number", "")
            sec_title = r.get("section_title") or meta.get("section_title", "General")
            snip = r.get("text", "")[:120].replace("\n", " ")
            lines.append(
                f"Rank #{i} | Final Score: {r.get('score', 0.0):.4f} (Base: {r.get('base_score', 0.0):.4f}, "
                f"SpecMult: {r.get('specificity_multiplier', 1.0):.2f}, ExceBoost: {r.get('exception_boost', 0.0):.4f}) "
                f"| Section {sec_num} ({sec_title})\n  Text: {snip}...\n"
            )

        lines.append("----------------------------------------------------------------")
        lines.append("3. GENERATED ANSWER")
        lines.append("----------------------------------------------------------------")
        lines.append(self.generated_answer)
        lines.append("================================================================")
        return "\n".join(lines)


def log_debug_session(session: RAGDebugSession) -> None:
    """Log formatted debug report at DEBUG level or print if required."""
    logger.debug("\n" + session.format_text_report())
