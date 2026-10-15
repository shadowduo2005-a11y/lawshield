"""
retrieval.py – evaluates vector and lexical retrieval precision, recall, and F1.

All keyword matching uses word-boundary–aware regex to avoid false positives
(e.g. keyword "tax" matching inside "taxation" or "taxable").
"""
from __future__ import annotations

import logging
import re
from typing import List

logger = logging.getLogger(__name__)


def _keyword_in_text(keyword: str, text: str) -> bool:
    """
    Case-insensitive, word-boundary–aware keyword check.

    ``\b`` anchors prevent "tax" from matching inside "taxation" or "taxable",
    which would inflate retrieval recall on legal text.
    """
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return bool(re.search(pattern, text, re.IGNORECASE))


class RetrievalEvaluator:
    """
    Evaluates retrieval performance against expected ground-truth keywords.

    All methods are static — no state or LLM required.
    """

    @staticmethod
    def calculate_metrics(retrieved_chunks: List[str], expected_keywords: List[str]) -> dict:
        """
        Calculates retrieval precision, recall, and F1 score based on keyword grounding.

        Parameters
        ----------
        retrieved_chunks : List[str]
            List of text chunks returned by vector/lexical search.
        expected_keywords : List[str]
            List of key terms or phrases that MUST be present in the retrieved chunks.

        Returns
        -------
        dict
            A dictionary containing:
            - ``"retrieval_recall"``    : float – ratio of expected keywords found
            - ``"retrieval_precision"`` : float – ratio of relevant chunks
            - ``"retrieval_f1"``        : float – harmonic mean of precision and recall
        """
        if not expected_keywords:
            return {
                "retrieval_recall": 1.0,
                "retrieval_precision": 1.0,
                "retrieval_f1": 1.0,
            }

        if not retrieved_chunks:
            return {
                "retrieval_recall": 0.0,
                "retrieval_precision": 0.0,
                "retrieval_f1": 0.0,
            }

        joined_chunks = " ".join(retrieved_chunks)

        # ── Recall: fraction of expected keywords found across all chunks ──────
        hits = sum(1 for kw in expected_keywords if _keyword_in_text(kw, joined_chunks))
        recall = round(hits / len(expected_keywords), 2)

        # ── Precision: fraction of retrieved chunks containing ≥1 keyword ──────
        relevant_count = sum(
            1 for chunk in retrieved_chunks
            if any(_keyword_in_text(kw, chunk) for kw in expected_keywords)
        )
        precision = round(relevant_count / len(retrieved_chunks), 2)

        # ── F1: harmonic mean of precision and recall ─────────────────────────
        if precision + recall > 0:
            f1 = round(2 * precision * recall / (precision + recall), 2)
        else:
            f1 = 0.0

        logger.info(
            "Retrieval Metrics: Recall=%.2f, Precision=%.2f, F1=%.2f",
            recall,
            precision,
            f1,
        )
        return {
            "retrieval_recall": recall,
            "retrieval_precision": precision,
            "retrieval_f1": f1,
        }

    @staticmethod
    def calculate_mrr(
        retrieved_chunks: List[str], expected_keywords: List[str]
    ) -> float:
        """
        Calculates Mean Reciprocal Rank (MRR) of the first relevant retrieved chunk.

        MRR measures how highly the first relevant result is ranked.  A score of
        1.0 means the very first chunk was relevant; 0.5 means the second was first
        relevant, etc.

        Parameters
        ----------
        retrieved_chunks : List[str]
            Ordered list of retrieved text chunks (rank 1 first).
        expected_keywords : List[str]
            Keywords indicating relevance.

        Returns
        -------
        float
            MRR score in [0.0, 1.0].  0.0 if no chunk is relevant.
        """
        if not retrieved_chunks or not expected_keywords:
            return 0.0

        for rank, chunk in enumerate(retrieved_chunks, start=1):
            if any(_keyword_in_text(kw, chunk) for kw in expected_keywords):
                mrr = round(1.0 / rank, 4)
                logger.info("Retrieval MRR: %.4f (first relevant at rank %d)", mrr, rank)
                return mrr

        logger.info("Retrieval MRR: 0.0 (no relevant chunk found)")
        return 0.0
