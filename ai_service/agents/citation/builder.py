"""
builder.py – builds legal Citation models from unstructured text or metadata.

Extraction strategy (in order of priority):
1. Regex patterns for statutory references (Section X of the Act Name)
2. Regex patterns for case law citations (Name v. Name, Vol Reporter Page (Year))
3. LLM-based structured extraction as fallback when regex finds nothing

The LLM model is lazy-loaded so it is NOT instantiated on every ``CitationBuilder()``
call — only when the LLM fallback is actually required.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, asdict
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from llm.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """
    Structured model representing a legal citation.
    """
    source_title: str           # e.g., "Income Tax Act", "Smith v. Jones"
    section: Optional[str] = None       # e.g., "54"
    page: Optional[str] = None          # e.g., "324"
    paragraph: Optional[str] = None     # e.g., "5"
    volume: Optional[str] = None        # e.g., "123"
    reporter: Optional[str] = None      # e.g., "F.3d", "SCC"
    first_page: Optional[str] = None    # e.g., "456"
    year: Optional[str] = None          # e.g., "2010"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Compiled regex patterns (module-level for efficiency)
# ---------------------------------------------------------------------------

# Statutory: "Section 54 of the Income Tax Act" or "Section 80C, Income Tax Act, Page 12, Paragraph 3"
_STATUTE_RE = re.compile(
    r"Section\s+(\d+[A-Za-z0-9]*)\s*(?:of\s+the|,)\s*([A-Za-z\s]+?Act)"
    r"(?:,\s*Page\s*(\d+))?(?:,\s*Paragraph\s*(\d+))?",
    re.IGNORECASE,
)

# Case law: "Smith v. Jones, 123 F.3d 456 (2010)" or "A v. B, (2015) 4 SCC 100"
_CASE_RE = re.compile(
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+v\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),"
    r"\s*(?:\((\d{4})\)\s*)?(\d+)?\s*([A-Za-z][A-Za-z\.\d]+)\s*(\d+)(?:\s*\((\d{4})\))?",
    re.IGNORECASE,
)

# Prefixes to strip from case names (e.g. "See Smith v. Jones" → "Smith v. Jones")
_CITATION_PREFIX_RE = re.compile(
    r"^(?:see|cf|in|contra|re|ex\s+parte)\s+", re.IGNORECASE
)


class CitationBuilder:
    """
    Builder responsible for extracting and constructing Citation objects.

    The LLM provider is lazy-loaded: ``get_llm_provider()`` is called only when
    regex extraction fails and the LLM fallback is invoked.
    """

    def __init__(self, provider_name: str | None = None) -> None:
        self.provider_name = provider_name
        self._model = None  # Lazy-loaded

    @property
    def model(self):
        """Lazily initialises the LLM model on first access."""
        if self._model is None:
            self._model = get_llm_provider(self.provider_name).get_model()
        return self._model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_from_text(self, text: str) -> List[Citation]:
        """
        Parses unstructured text and extracts all legal citations found within.

        Uses regex patterns first for speed and determinism; falls back to an
        LLM-based structured extraction pass only when regex finds nothing.

        Parameters
        ----------
        text : str
            Raw legal text (contract clause, research snippet, etc.)

        Returns
        -------
        List[Citation]
            Deduplicated list of extracted citations.
        """
        citations: List[Citation] = []

        # ── 1. Statutory references ────────────────────────────────────────────
        for match in _STATUTE_RE.finditer(text):
            sec, act, pg, para = match.groups()
            citations.append(
                Citation(
                    source_title=act.strip(),
                    section=sec,
                    page=pg,
                    paragraph=para,
                )
            )

        # ── 2. Case law citations ──────────────────────────────────────────────
        for match in _CASE_RE.finditer(text):
            case, yr1, vol, rep, pg, yr2 = match.groups()
            cleaned_case = _CITATION_PREFIX_RE.sub("", case.strip())
            citations.append(
                Citation(
                    source_title=cleaned_case,
                    volume=vol,
                    reporter=rep,
                    first_page=pg,
                    year=yr2 or yr1,
                )
            )

        # ── 3. LLM fallback (only when regex finds nothing) ───────────────────
        if not citations:
            logger.info("No citations found via regex — invoking LLM fallback.")
            citations = self._extract_via_llm(text)

        return self._deduplicate(citations)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_via_llm(self, text: str) -> List[Citation]:
        """Uses the LLM to extract citations from text where regex fails."""
        logger.info("Extracting citations via LLM…")

        system_prompt = (
            "You are a legal citation parser. Extract all statutory and case law citations "
            "found in the user's text. For each citation, construct a JSON object matching "
            "this structure:\n"
            "{\n"
            '  "source_title": "Name of Act/Statute or Case Name",\n'
            '  "section": "section number or null",\n'
            '  "page": "page number or null",\n'
            '  "paragraph": "paragraph number or null",\n'
            '  "volume": "volume number or null",\n'
            '  "reporter": "reporter abbreviation or null",\n'
            '  "first_page": "first page number or null",\n'
            '  "year": "year or null"\n'
            "}\n\n"
            "Return a raw JSON list of these objects and nothing else."
        )

        try:
            response = self.model.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Text to parse:\n\n{text}"),
                ]
            )
            raw = response.content

            from utils.json import parse_json_array
            data = parse_json_array(raw)

            return [Citation(**item) for item in data]

        except Exception as exc:
            logger.error("Failed to extract citations via LLM: %s", exc)
            return []

    @staticmethod
    def _deduplicate(citations: List[Citation]) -> List[Citation]:
        """Removes duplicates by (source_title, section, volume, first_page) key."""
        seen = set()
        unique: List[Citation] = []
        for c in citations:
            key = (c.source_title, c.section, c.volume, c.first_page)
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique
