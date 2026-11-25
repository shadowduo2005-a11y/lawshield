"""
replacement.py
Manages the bidirectional mapping between original PII values and their
safe placeholder tokens (e.g. "<PERSON_1>") for a single masking context.
"""
from __future__ import annotations
from typing import Dict, Optional


class MaskingState:
    """
    Holds the bidirectional mapping between original PII values and masked
    placeholders for a single request or session turn.

    Design guarantees:
    - Same original value always maps to the same placeholder (within one state).
    - Case-insensitive deduplication: "John Doe" and "john doe" share one token.
    - Whitespace is normalised before lookup so " John  Doe " == "John Doe".
    - The state can be serialised/deserialised for persistence or logging.
    - Two states can be merged (e.g. across multi-turn sessions).
    """

    def __init__(self) -> None:
        # placeholder -> original value  (e.g. "<PERSON_1>" -> "John Doe")
        self._placeholder_to_original: Dict[str, str] = {}
        # normalised original -> placeholder  (case-insensitive dedup key)
        self._normalised_to_placeholder: Dict[str, str] = {}
        # per-entity-type counter for sequential numbering
        self._counts: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def get_or_create_placeholder(self, entity_type: str, original_value: str) -> str:
        """
        Returns a consistent placeholder token for *original_value*.

        Guarantees:
        - Leading/trailing whitespace is stripped before lookup.
        - Lookup is case-insensitive so the same person masked with different
          capitalisation always gets the same token.
        - The *stored* original value preserves the first-seen casing/spacing.
        """
        # Normalise entity name for the token (e.g. "email address" -> "EMAIL_ADDRESS")
        entity_name = entity_type.upper().replace(" ", "_").replace("-", "_")

        # Normalise the value for dedup lookup only; we keep the original as-is
        normalised_key = self._normalise(original_value)
        if not normalised_key:
            # Refuse to mask empty / whitespace-only strings
            return original_value

        if normalised_key in self._normalised_to_placeholder:
            return self._normalised_to_placeholder[normalised_key]

        # Create a new sequential placeholder
        count = self._counts.get(entity_name, 0) + 1
        self._counts[entity_name] = count
        placeholder = f"<{entity_name}_{count}>"

        # Store both directions
        self._placeholder_to_original[placeholder] = original_value.strip()
        self._normalised_to_placeholder[normalised_key] = placeholder

        return placeholder

    def get_original(self, placeholder: str) -> str:
        """
        Return the original value for a placeholder, or the placeholder itself
        if it is not found (safe fallback — never raises).
        """
        return self._placeholder_to_original.get(placeholder, placeholder)

    # ------------------------------------------------------------------
    # Convenience properties (backwards-compatible with old attribute names)
    # ------------------------------------------------------------------

    @property
    def mapping(self) -> Dict[str, str]:
        """Read-only view: placeholder -> original value."""
        return dict(self._placeholder_to_original)

    @property
    def reverse_mapping(self) -> Dict[str, str]:
        """Read-only view: normalised_original -> placeholder."""
        return dict(self._normalised_to_placeholder)

    @property
    def counts(self) -> Dict[str, int]:
        """Read-only view: entity_name -> current counter value."""
        return dict(self._counts)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """
        Serialise the state to a plain dict (JSON-safe).
        Useful for caching, logging, or persisting across requests.
        """
        return {
            "placeholder_to_original": dict(self._placeholder_to_original),
            "normalised_to_placeholder": dict(self._normalised_to_placeholder),
            "counts": dict(self._counts),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MaskingState":
        """Deserialise a state previously produced by :meth:`to_dict`."""
        state = cls()
        state._placeholder_to_original = data.get("placeholder_to_original", {})
        state._normalised_to_placeholder = data.get("normalised_to_placeholder", {})
        state._counts = data.get("counts", {})
        return state

    # ------------------------------------------------------------------
    # Merging
    # ------------------------------------------------------------------

    def merge(self, other: "MaskingState") -> "MaskingState":
        """
        Return a *new* MaskingState that combines self and *other*.

        Useful for multi-turn conversations where each turn produces its own
        state but restoration must span the entire history.

        Conflict resolution: *self* wins (existing mappings are preserved).
        """
        merged = MaskingState.from_dict(self.to_dict())
        for placeholder, original in other._placeholder_to_original.items():
            norm = self._normalise(original)
            if norm not in merged._normalised_to_placeholder:
                # Use the same placeholder key if possible, else create a new one
                if placeholder not in merged._placeholder_to_original:
                    merged._placeholder_to_original[placeholder] = original
                    merged._normalised_to_placeholder[norm] = placeholder
                else:
                    # Collision on token name — derive entity_type and re-generate
                    # e.g. "<PERSON_3>" -> entity_type = "PERSON"
                    parts = placeholder.strip("<>").rsplit("_", 1)
                    entity_name = parts[0] if parts else "UNKNOWN"
                    merged.get_or_create_placeholder(entity_name, original)
        return merged

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(value: str) -> str:
        """Strip whitespace, collapse internal runs, and lower-case."""
        return " ".join(value.split()).lower()

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._placeholder_to_original)

    def __bool__(self) -> bool:
        return True  # Always truthy — even an empty state is valid

    def __repr__(self) -> str:
        return (
            f"MaskingState("
            f"{len(self._placeholder_to_original)} entities masked, "
            f"types={list(self._counts.keys())})"
        )
