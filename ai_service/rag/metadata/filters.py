"""
Metadata Filter Extractor.

Uses an LLM to extract structured metadata filters (year, author, document_type)
from a natural-language query so that hybrid search can apply precise field filters.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from langchain_core.messages import HumanMessage

from llm.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

_KNOWN_KEYS = {"year", "document_type", "author", "jurisdiction"}


def extract_metadata_filters(query: str) -> dict:
    """Extract metadata filters from the query.

    Returns a (possibly empty) dict with keys from ``_KNOWN_KEYS``.
    """
    model = get_llm_provider().get_model()

    prompt = f"""You are a metadata extraction agent for a legal document search system.
Extract any explicit metadata clues from the query below.
Possible keys: year (integer), document_type (string), author (string), jurisdiction (string).
Return ONLY a JSON object.  Return {{}} if nothing is found.

Query: {query}
"""

    try:
        response = model.invoke([HumanMessage(content=prompt)])
        raw = response.content

        match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)

        # Sanitise: keep only known keys
        filtered = {k: v for k, v in data.items() if k in _KNOWN_KEYS and v}
        logger.debug("Extracted metadata filters: %s", filtered)
        return filtered

    except Exception as exc:
        logger.warning("Metadata extraction failed (%s); returning empty filters", exc)
        return {}
