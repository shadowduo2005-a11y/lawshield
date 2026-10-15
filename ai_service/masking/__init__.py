"""
masking package
Public interface for PII detection and masking.
"""
from .masking_pipeline import mask_text, restore_text, mask_and_restore_passthrough
from .replacement import MaskingState

__all__ = [
    "mask_text",
    "restore_text",
    "mask_and_restore_passthrough",
    "MaskingState",
]
