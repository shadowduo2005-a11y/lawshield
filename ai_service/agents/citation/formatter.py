"""
formatter.py – formats Citation dataclass objects into distinct legal formatting styles.
"""
from __future__ import annotations

import logging
from typing import Optional
from .builder import Citation

logger = logging.getLogger(__name__)

class CitationFormatter:
    """
    Formatter responsible for turning a Citation object into a formatted string.
    """

    @staticmethod
    def format_bluebook(citation: Citation) -> str:
        """
        Formats case law into Bluebook Style: Name, Vol Reporter Page (Year)
        Formats statutory references into Bluebook: Act Name § Section (Year/Publisher)
        """
        # Case Law style
        if citation.volume and citation.reporter and citation.first_page:
            year_suffix = f" ({citation.year})" if citation.year else ""
            return f"{citation.source_title}, {citation.volume} {citation.reporter} {citation.first_page}{year_suffix}"
        
        # Statute style
        section_symbol = f"\u00a7 {citation.section}" if citation.section else ""
        parts = [citation.source_title, section_symbol]
        if citation.page:
            parts.append(f"at {citation.page}")
        
        formatted = ", ".join(filter(None, parts))
        if citation.year:
            formatted += f" ({citation.year})"
        return formatted

    @staticmethod
    def format_statutory(citation: Citation) -> str:
        """
        Formats statutory reference: Section X, Act Name, Page Y, Paragraph Z
        """
        parts = []
        if citation.section:
            parts.append(f"Section {citation.section}")
        parts.append(citation.source_title)
        if citation.page:
            parts.append(f"Page {citation.page}")
        if citation.paragraph:
            parts.append(f"Paragraph {citation.paragraph}")
        
        return ", ".join(parts)

    @staticmethod
    def format_indian(citation: Citation) -> str:
        """
        Formats using Indian Court Style:
        Case Law: Case Name, (Year) Vol SCC Page
        Statutes: Section X of the Act Name
        """
        if citation.volume and citation.reporter and citation.first_page:
            year_prefix = f"({citation.year}) " if citation.year else ""
            return f"{citation.source_title}, {year_prefix}{citation.volume} {citation.reporter} {citation.first_page}"

        if citation.section:
            return f"Section {citation.section} of the {citation.source_title}"
        
        return citation.source_title

    @staticmethod
    def format_inline(citation: Citation, index: int) -> str:
        """
        Formats inline markdown footnote reference (e.g. [^1]).
        """
        return f"[^{index}]"
