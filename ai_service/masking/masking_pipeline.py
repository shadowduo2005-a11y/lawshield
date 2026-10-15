"""
masking_pipeline.py
Core PII masking pipeline built on top of Microsoft Presidio.

Key improvements over the naive implementation:
1. Overlapping-span resolution  — when two recognisers detect the same characters,
   the higher-confidence result wins and the dominated span is discarded.
2. Confidence filtering         — results below CONFIDENCE_THRESHOLD are dropped
   before any replacement, cutting false positives.
3. Short-token guard            — single-character and pure-whitespace detections
   are rejected to avoid masking individual letters like "I" as a PERSON.
4. Efficient restoration        — a single compiled-regex pass replaces all
   placeholders simultaneously instead of a loop of str.replace() calls.
5. Thread-safe singletons       — see ner.py.
6. Safe empty-input handling    — returns (text, empty_state) without touching
   Presidio when input is blank.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Tuple

from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from .ner import get_analyzer, SUPPORTED_ENTITIES, CONFIDENCE_THRESHOLD
from .replacement import MaskingState

logger = logging.getLogger(__name__)

_anonymizer: AnonymizerEngine | None = None
_anonymizer_lock = threading.Lock()


def get_anonymizer() -> AnonymizerEngine:
    """Return a shared thread-safe AnonymizerEngine instance."""
    global _anonymizer
    if _anonymizer is None:
        with _anonymizer_lock:
            if _anonymizer is None:
                _anonymizer = AnonymizerEngine()
    return _anonymizer

# Minimum token length to be considered a valid PII entity.
# "I", "a", single digits, etc. are skipped.
_MIN_TOKEN_LEN = 2

# Compiled pattern that matches every placeholder produced by MaskingState.
# Format: <ENTITY_TYPE_N>  where N is one or more digits.
_PLACEHOLDER_RE = re.compile(r"<([A-Z][A-Z0-9_]+_\d+)>")


# ---------------------------------------------------------------------------
# Overlap resolution
# ---------------------------------------------------------------------------

def _resolve_overlaps(results: list) -> list:
    """
    Given a flat list of Presidio RecognizerResult objects, return a subset
    with all overlapping/dominated spans removed.

    Strategy (greedy interval scheduling by score):
    1. Sort by score descending (higher confidence wins), then by span length
       descending (prefer longer matches when scores are equal).
    2. Walk the sorted list; keep a result only if its span does not overlap
       with any already-kept result.
    """
    # Sort: primary = score desc, secondary = span length desc
    sorted_results = sorted(
        results,
        key=lambda r: (r.score, r.end - r.start),
        reverse=True,
    )

    kept: list = []
    for candidate in sorted_results:
        overlaps = any(
            # Any overlap between [c.start, c.end) and [k.start, k.end)
            candidate.start < k.end and candidate.end > k.start
            for k in kept
        )
        if not overlaps:
            kept.append(candidate)

    return kept


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def mask_text(text: str, state: MaskingState | None = None) -> Tuple[str, MaskingState]:
    """
    Detect PII in *text* and replace each entity with a stable placeholder
    such as ``<PERSON_1>`` or ``<AADHAAR_NUMBER_1>``.

    Returns
    -------
    masked_text : str
        The input text with all detected PII replaced by placeholder tokens.
    state : MaskingState
        Bidirectional mapping required to restore the original values later.

    Notes
    -----
    - If *text* is empty or whitespace-only, it is returned unchanged with an
      empty :class:`MaskingState` (or the provided state).
    - The function is stateless unless a state is passed in.
    """
    if not text or not text.strip():
        return text, state if state is not None else MaskingState()

    if state is None:
        state = MaskingState()
    analyzer = get_analyzer()

    # -----------------------------------------------------------------------
    # 1. Detect entities
    # -----------------------------------------------------------------------
    try:
        raw_results = analyzer.analyze(
            text=text,
            entities=SUPPORTED_ENTITIES,
            language="en",
            score_threshold=CONFIDENCE_THRESHOLD,
        )
    except Exception as exc:
        logger.error("Presidio analysis failed: %s — returning text unmasked.", exc)
        return text, state

    if not raw_results:
        return text, state

    # -----------------------------------------------------------------------
    # 2. Filter out low-quality detections
    # -----------------------------------------------------------------------
    filtered = [
        r for r in raw_results
        if (
            r.score >= CONFIDENCE_THRESHOLD
            and (r.end - r.start) >= _MIN_TOKEN_LEN          # skip single-char hits
            and text[r.start:r.end].strip()                   # skip whitespace-only
        )
    ]

    if not filtered:
        return text, state

    # -----------------------------------------------------------------------
    # 3. Resolve overlapping spans
    # -----------------------------------------------------------------------
    resolved = _resolve_overlaps(filtered)

    # -----------------------------------------------------------------------
    # 4. Apply replacements via Presidio AnonymizerEngine
    # -----------------------------------------------------------------------
    anonymizer = get_anonymizer()
    entity_types = {r.entity_type for r in resolved}.union(SUPPORTED_ENTITIES)
    operators = {
        et: OperatorConfig(
            "custom",
            {"lambda": lambda val, entity=et: state.get_or_create_placeholder(entity, val)},
        )
        for et in entity_types
    }
    operators["DEFAULT"] = OperatorConfig(
        "custom",
        {"lambda": lambda val: state.get_or_create_placeholder("PII", val)},
    )

    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=resolved,
        operators=operators,
    )
    masked_text = anonymized.text

    logger.debug(
        "mask_text: masked %d entities (%d detected, %d after filtering, %d after overlap resolution).",
        len(resolved), len(raw_results), len(filtered), len(resolved),
    )

    return masked_text, state


def restore_text(masked_text: str, state: MaskingState) -> str:
    """
    Replace all placeholder tokens in *masked_text* with their original values
    using the bidirectional mapping in *state*.

    Uses a single compiled-regex substitution pass for efficiency — O(n) in
    the length of *masked_text* rather than O(k·n) from k calls to str.replace().

    Returns *masked_text* unchanged if it contains no known placeholders or if
    *state* has no mappings.
    """
    if not masked_text or not state:
        return masked_text

    mapping = state.mapping  # {placeholder: original}
    if not mapping:
        return masked_text

    def _replacer(match: re.Match) -> str:  # type: ignore[type-arg]
        placeholder = match.group(0)  # e.g. "<PERSON_1>"
        return mapping.get(placeholder, placeholder)

    return _PLACEHOLDER_RE.sub(_replacer, masked_text)


def mask_and_restore_passthrough(text: str) -> str:
    """
    Convenience helper: mask then immediately restore *text*.
    Useful in tests to verify the round-trip without keeping state.
    """
    masked, state = mask_text(text)
    return restore_text(masked, state)
