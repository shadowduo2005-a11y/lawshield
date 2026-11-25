"""
json.py – Shared JSON parsing utilities for agents.
"""

import json
import re

def parse_json_object(raw: str) -> dict:
    """
    Robustly extracts a JSON object from raw LLM text.

    Strategy:
    1. Strip markdown code-fence markers (```json … ```) if present.
    2. Try to json.loads the cleaned string directly.
    3. Fall back to finding the first `{` and last `}` in the text and
       parsing that substring (handles surrounding prose or whitespace).

    Raises ValueError if no valid JSON object can be extracted.
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

    raise ValueError(f"Could not extract a JSON object from LLM response: {raw[:300]!r}")

def parse_json_array(raw: str) -> list:
    """
    Robustly extracts a JSON array from raw LLM text.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"```", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract a JSON array from LLM response: {raw[:300]!r}")
