"""
exporter.py – exports citations to Markdown Table of Authorities, JSON,
inline footnotes, or appends them to documents.
"""
from __future__ import annotations

import json
import logging
from typing import List, Tuple

from .builder import Citation
from .formatter import CitationFormatter

logger = logging.getLogger(__name__)


class CitationExporter:
    """
    Exporter responsible for formatting lists of Citations into reports and final documents.
    """

    @staticmethod
    def export_table_of_authorities(citations: List[Citation], style: str = "statutory") -> str:
        """
        Generates a markdown Table of Authorities (or References bibliography).

        Parameters
        ----------
        citations : List[Citation]
            List of citation objects to export.
        style : str
            One of ``"statutory"``, ``"bluebook"``, or ``"indian"``.

        Returns
        -------
        str
            Markdown-formatted table of authorities, or empty string if no citations.
        """
        if not citations:
            return ""

        # Deduplicate citations using their formatted strings to avoid redundant entries
        unique_citations: List[str] = []
        seen: set = set()

        for cit in citations:
            formatted = CitationExporter._format_one(cit, style)
            if formatted not in seen:
                seen.add(formatted)
                unique_citations.append(formatted)

        header = "\n\n### 📚 Table of Authorities\n"
        body = "\n".join(f"{i}. {s}" for i, s in enumerate(unique_citations, start=1))
        return header + body

    @staticmethod
    def export_json(citations: List[Citation]) -> str:
        """
        Serializes a list of Citations into a clean JSON string.
        """
        return json.dumps([cit.to_dict() for cit in citations], indent=2)

    @staticmethod
    def export_footnotes(
        citations: List[Citation],
        style: str = "statutory",
    ) -> Tuple[List[str], str]:
        """
        Generates a set of inline footnote markers and a corresponding footnote
        section suitable for appending to a markdown document.

        Example output
        --------------
        markers  = ["[^1]", "[^2]"]
        footnote_block = "[^1]: Section 54, Income Tax Act\\n[^2]: Smith v. Jones, 123 F.3d 456 (2010)"

        Parameters
        ----------
        citations : List[Citation]
            Ordered list of citations (index corresponds to footnote number).
        style : str
            Formatting style passed to the CitationFormatter.

        Returns
        -------
        Tuple[List[str], str]
            ``(markers, footnote_block)`` where *markers* is a list of inline
            ``[^N]`` strings and *footnote_block* is the markdown footnote definitions.
        """
        if not citations:
            return [], ""

        markers: List[str] = []
        footnote_lines: List[str] = []
        seen: dict[str, int] = {}  # formatted string → footnote index

        for citation in citations:
            formatted = CitationExporter._format_one(citation, style)

            if formatted in seen:
                # Reuse existing footnote number for duplicate citations
                markers.append(f"[^{seen[formatted]}]")
            else:
                idx = len(seen) + 1
                seen[formatted] = idx
                markers.append(f"[^{idx}]")
                footnote_lines.append(f"[^{idx}]: {formatted}")

        footnote_block = "\n".join(footnote_lines)
        return markers, footnote_block

    @classmethod
    def append_to_document(
        cls,
        document: str,
        citations: List[Citation],
        style: str = "statutory",
    ) -> str:
        """
        Appends the formatted Table of Authorities to the end of the document.
        """
        table = cls.export_table_of_authorities(citations, style=style)
        if not table:
            return document

        stripped_doc = document.rstrip()
        return f"{stripped_doc}{table}\n"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_one(citation: Citation, style: str) -> str:
        """Dispatches to the correct CitationFormatter method."""
        if style == "bluebook":
            return CitationFormatter.format_bluebook(citation)
        if style == "indian":
            return CitationFormatter.format_indian(citation)
        return CitationFormatter.format_statutory(citation)
