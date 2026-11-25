"""
metadata.py
Unified metadata extraction for PDF, DOCX, and TXT files.

Returns a normalised dict with consistent keys across all file types so
the rest of the pipeline never needs to branch on format.

Standard keys (always present, may be empty string / 0):
  file_type      str   e.g. "pdf", "docx", "txt"
  page_count     int
  word_count     int
  char_count     int
  title          str
  author         str
  subject        str
  creator        str   software that created the file
  producer       str   software that produced the PDF
  creation_date  str   ISO-8601 string where possible
  mod_date       str
  encrypted      bool  (PDF only)
  pdf_version    str   (PDF only)
  language       str   detected document language (best-effort)
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Date normalisation
# ---------------------------------------------------------------------------

def _normalise_pdf_date(raw: str) -> str:
    """
    Convert PDF date strings like "D:20230415120000+05'30'" to ISO-8601.
    Returns the raw string if parsing fails.
    """
    if not raw:
        return ""
    # Strip leading "D:" prefix
    s = raw.lstrip("D:").lstrip("d:")
    # Extract digits: YYYYMMDDHHmmSS
    digits = re.sub(r"\D", "", s[:14])
    if len(digits) >= 8:
        year, month, day = digits[:4], digits[4:6], digits[6:8]
        hh, mm = digits[8:10] or "00", digits[10:12] or "00"
        return f"{year}-{month}-{day}T{hh}:{mm}"
    return raw


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def extract_metadata_from_pdf(file_path: str, page_count: int = 0) -> dict[str, Any]:
    """Extract and normalise metadata from a PDF using PyMuPDF."""
    meta: dict[str, Any] = _base_meta("pdf")
    try:
        import fitz
        doc = fitz.open(file_path)
        raw = doc.metadata or {}

        meta["page_count"]    = page_count or doc.page_count
        meta["title"]         = raw.get("title", "").strip()
        meta["author"]        = raw.get("author", "").strip()
        meta["subject"]       = raw.get("subject", "").strip()
        meta["creator"]       = raw.get("creator", "").strip()
        meta["producer"]      = raw.get("producer", "").strip()
        meta["creation_date"] = _normalise_pdf_date(raw.get("creationDate", ""))
        meta["mod_date"]      = _normalise_pdf_date(raw.get("modDate", ""))
        meta["encrypted"]     = doc.is_encrypted
        meta["pdf_version"]   = f"1.{doc.pdf_version()}" if hasattr(doc, "pdf_version") else ""
        meta["file_size_bytes"] = os.path.getsize(file_path)

        doc.close()
    except Exception as exc:
        logger.error("PDF metadata extraction failed: %s", exc)
        meta["extraction_error"] = str(exc)
    return meta


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def extract_metadata_from_docx(file_path: str) -> dict[str, Any]:
    """Extract core properties from a DOCX file using python-docx."""
    meta: dict[str, Any] = _base_meta("docx")
    try:
        from docx import Document  # type: ignore
        doc = Document(file_path)
        props = doc.core_properties

        meta["title"]         = props.title or ""
        meta["author"]        = props.author or ""
        meta["subject"]       = props.subject or ""
        meta["creator"]       = props.last_modified_by or ""
        meta["creation_date"] = props.created.isoformat() if props.created else ""
        meta["mod_date"]      = props.modified.isoformat() if props.modified else ""
        meta["file_size_bytes"] = os.path.getsize(file_path)

        # Approximate page count from section properties (not always accurate)
        para_count = len(doc.paragraphs)
        meta["page_count"] = max(1, para_count // 40)  # rough heuristic

    except Exception as exc:
        logger.error("DOCX metadata extraction failed: %s", exc)
        meta["extraction_error"] = str(exc)
    return meta


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------

def extract_metadata_from_txt(file_path: str) -> dict[str, Any]:
    """Basic stats for plain-text files."""
    meta: dict[str, Any] = _base_meta("txt")
    try:
        meta["file_size_bytes"] = os.path.getsize(file_path)
        meta["page_count"] = 1
    except Exception as exc:
        logger.error("TXT metadata extraction failed: %s", exc)
        meta["extraction_error"] = str(exc)
    return meta


# ---------------------------------------------------------------------------
# Text stats (format-agnostic, called after extraction)
# ---------------------------------------------------------------------------

def enrich_with_text_stats(meta: dict[str, Any], text: str) -> dict[str, Any]:
    """Add word_count and char_count derived from the extracted text."""
    meta["word_count"] = len(text.split())
    meta["char_count"] = len(text)
    return meta


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _base_meta(file_type: str) -> dict[str, Any]:
    return {
        "file_type":       file_type,
        "page_count":      0,
        "word_count":      0,
        "char_count":      0,
        "title":           "",
        "author":          "",
        "subject":         "",
        "creator":         "",
        "producer":        "",
        "creation_date":   "",
        "mod_date":        "",
        "encrypted":       False,
        "pdf_version":     "",
        "file_size_bytes": 0,
        "language":        "",
    }
