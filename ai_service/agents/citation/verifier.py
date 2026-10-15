"""
verifier.py – verifies that citations are accurately grounded in the source documents.
"""
from __future__ import annotations

import logging
import re
from typing import List

from .builder import Citation

logger = logging.getLogger(__name__)


class CitationVerifier:
    """
    Verifier responsible for checking grounding and factuality of a Citation against source text.

    All methods are static — no LLM is required; verification is purely heuristic,
    using text-presence checks with word-boundary awareness to avoid false positives
    (e.g. section "54" matching "154" or "5400").
    """

    @staticmethod
    def _text_contains(needle: str, haystack: str) -> bool:
        """
        Case-insensitive, word-boundary–aware substring check.

        For short numeric tokens (section numbers, page numbers) a bare substring
        match is too permissive — '54' would match '154', '254', etc.  Using ``\b``
        word boundaries prevents these false positives.
        """
        if not needle:
            return True
        # Build a word-boundary–aware pattern for the needle
        pattern = r"\b" + re.escape(needle) + r"\b"
        return bool(re.search(pattern, haystack, re.IGNORECASE))

    @staticmethod
    def verify(citation: Citation, source_text: str) -> dict:
        """
        Cross-references the citation details against the source text.

        Returns
        -------
        dict
            A dictionary containing:
            - ``"verified"``: bool (True if all present details are found in context)
            - ``"warnings"``: List of warnings indicating ungrounded elements
            - ``"confidence"``: float (verification confidence score between 0.0 and 1.0)
        """
        if not source_text:
            return {
                "verified": False,
                "warnings": ["Source text is empty. Grounding verification failed."],
                "confidence": 0.0,
            }

        warnings: List[str] = []

        # ── 1. Check title / act / case name grounding ────────────────────────
        # Require at least half the significant words to appear in the source text
        title_words = [w for w in citation.source_title.split() if len(w) > 2]
        matching_words = [
            w for w in title_words if CitationVerifier._text_contains(w, source_text)
        ]
        title_grounded = bool(title_words) and len(matching_words) >= max(
            1, len(title_words) // 2
        )
        if not title_grounded:
            warnings.append(
                f"Title / Act Name '{citation.source_title}' is not grounded in source text."
            )

        # ── 2. Check section number grounding ─────────────────────────────────
        if citation.section:
            # Strip non-numeric prefix/suffix but keep the core identifier (e.g. "80C" → search "80C")
            clean_sec = re.sub(r"^section\s*", "", citation.section, flags=re.IGNORECASE).strip()
            if clean_sec and not CitationVerifier._text_contains(clean_sec, source_text):
                warnings.append(
                    f"Section '{citation.section}' is not grounded in source text."
                )

        # ── 3. Check page number grounding ───────────────────────────────────
        if citation.page:
            if not CitationVerifier._text_contains(citation.page, source_text):
                warnings.append(
                    f"Page '{citation.page}' is not grounded in source text."
                )

        # ── 4. Check paragraph grounding ─────────────────────────────────────
        if citation.paragraph:
            if not CitationVerifier._text_contains(citation.paragraph, source_text):
                warnings.append(
                    f"Paragraph '{citation.paragraph}' is not grounded in source text."
                )

        # ── 5. Check case reporter page grounding ─────────────────────────────
        if citation.reporter and citation.first_page:
            if not CitationVerifier._text_contains(citation.first_page, source_text):
                warnings.append(
                    f"Case reporter page '{citation.first_page}' is not grounded in source text."
                )

        # ── Confidence calculation ─────────────────────────────────────────────
        possible_checks = 1  # title is always checked
        failed_checks = 0 if title_grounded else 1

        for attr, label in [
            ("section", "section"),
            ("page", "page"),
            ("paragraph", "paragraph"),
            ("first_page", "reporter page"),
        ]:
            if getattr(citation, attr):
                possible_checks += 1
                if any(label in w.lower() for w in warnings):
                    failed_checks += 1

        confidence = round((possible_checks - failed_checks) / possible_checks, 2)
        verified = len(warnings) == 0

        logger.info(
            "Citation verification: title='%s', verified=%s, confidence=%.2f",
            citation.source_title,
            verified,
            confidence,
        )

        return {
            "verified": verified,
            "warnings": warnings,
            "confidence": confidence,
        }
