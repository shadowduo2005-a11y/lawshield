"""
_utils.py – shared internal utilities for the evaluation package.

Provides a robust JSON extraction helper used across multiple evaluators
to handle LLM responses that may be wrapped in markdown code fences or
contain surrounding prose.
"""
from __future__ import annotations

import json
import re


def parse_json_object(raw: str) -> dict:
    """
    Robustly extracts a JSON object from raw LLM text.

    Strategy
    --------
    1. Strip markdown code-fence markers (```json … ```) if present.
    2. Try ``json.loads`` on the cleaned string directly.
    3. Find the first ``{`` and last ``}`` and parse that substring
       (handles surrounding prose or trailing whitespace).

    Raises ``ValueError`` if no valid JSON object can be extracted.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"```", "", cleaned).strip()

    # Attempt 1: direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Attempt 2: find outermost { … }
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not extract a JSON object from LLM response: {raw[:300]!r}"
    )
