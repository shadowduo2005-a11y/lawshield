"""
document_processing package
Public interface for document extraction and processing.
"""
from .loaders import process_document
from .cleaner import clean_text, clean_text_flat
from .parser import PageResult, pages_to_text
from .metadata import enrich_with_text_stats

__all__ = [
    "process_document",
    "clean_text",
    "clean_text_flat",
    "PageResult",
    "pages_to_text",
    "enrich_with_text_stats",
]
