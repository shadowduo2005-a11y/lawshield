"""
loaders.py
Main entrypoint for document processing.

Processing pipeline for each uploaded file:
  1. Validate extension and MIME type.
  2. Save to a temporary file (guaranteed cleanup via context manager).
  3. Parse with the best available parser for the file type.
     - PDF:  PyMuPDF → pdfplumber (complex layout) → OCR (scanned pages)
     - DOCX: Unstructured → python-docx (fallback)
     - TXT:  direct read
  4. Clean extracted text (ligatures, control chars, whitespace).
  5. Extract metadata and enrich with text statistics.
  6. Return a normalised result dict.

The result dict schema:
  filename       str
  file_type      str   ("pdf" | "docx" | "txt")
  content_type   str
  text           str   full cleaned text
  pages          list  [{page_number, word_count, is_scanned}, …]
  metadata       dict  (see metadata.py for keys)
  page_count     int
  word_count     int
  char_count     int
  scanned_pages  int   number of pages that required OCR
  error          str | None
"""

from __future__ import annotations

import logging
import os
import tempfile
from contextlib import contextmanager
from typing import Any, Generator

from fastapi import UploadFile

from .cleaner import clean_text
from .metadata import (
    extract_metadata_from_pdf,
    extract_metadata_from_docx,
    extract_metadata_from_txt,
    enrich_with_text_stats,
)
from .parser import (
    PageResult,
    pages_to_text,
    parse_pdf_pymupdf,
    parse_pdf_pdfplumber,
    parse_pdf_with_ocr,
    parse_docx_unstructured,
    parse_txt,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported types
# ---------------------------------------------------------------------------

_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}

_MIME_TO_EXT: dict[str, str] = {
    "application/pdf":                                                    ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword":                                                 ".doc",
    "text/plain":                                                         ".txt",
}

# Minimum characters that a parsed page must contain before the page is
# considered text-bearing. Pages below this fall back to OCR.
_MIN_TEXT_FOR_PAGE = 20


# ---------------------------------------------------------------------------
# Temp file context manager (guarantees cleanup even on exception)
# ---------------------------------------------------------------------------

@contextmanager
def _temp_file(suffix: str, data: bytes) -> Generator[str, None, None]:
    """
    Write *data* to a temporary file with *suffix*, yield its path,
    then delete the file unconditionally on exit.
    """
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        yield path
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_document(upload_file: UploadFile) -> dict[str, Any]:
    """
    Process an uploaded document end-to-end.

    Safe to call from a thread pool (``asyncio.to_thread``).
    Never raises — all errors are captured in ``result["error"]``.
    """
    filename = upload_file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()

    result: dict[str, Any] = {
        "filename":      filename,
        "file_type":     ext.lstrip("."),
        "content_type":  upload_file.content_type or "",
        "text":          "",
        "pages":         [],
        "metadata":      {},
        "page_count":    0,
        "word_count":    0,
        "char_count":    0,
        "scanned_pages": 0,
        "error":         None,
    }

    # ── 1. Validate extension ────────────────────────────────────────────
    if ext not in _SUPPORTED_EXTENSIONS:
        result["error"] = (
            f"Unsupported file type '{ext}'. "
            f"Accepted: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
        )
        return result

    # ── 2. Read file bytes ───────────────────────────────────────────────
    try:
        file_bytes = upload_file.file.read()
    except Exception as exc:
        result["error"] = f"Failed to read uploaded file: {exc}"
        return result

    if not file_bytes:
        result["error"] = "Uploaded file is empty."
        return result

    # ── 3. Parse + extract ───────────────────────────────────────────────
    try:
        with _temp_file(suffix=ext, data=file_bytes) as tmp_path:
            if ext == ".pdf":
                pages, metadata = _process_pdf(tmp_path)
            elif ext in (".docx", ".doc"):
                pages, metadata = _process_docx(tmp_path)
            else:  # .txt
                pages, metadata = _process_txt(tmp_path)
    except Exception as exc:
        logger.exception("Unexpected error processing %s", filename)
        result["error"] = str(exc)
        return result

    # ── 4. Assemble result ───────────────────────────────────────────────
    full_text = pages_to_text(pages)
    cleaned   = clean_text(full_text)

    enrich_with_text_stats(metadata, cleaned)

    result["text"]          = cleaned
    result["metadata"]      = metadata
    result["page_count"]    = metadata.get("page_count", len(pages))
    result["word_count"]    = metadata["word_count"]
    result["char_count"]    = metadata["char_count"]
    result["scanned_pages"] = sum(1 for p in pages if p.is_scanned)
    result["pages"] = [
        {
            "page_number": p.page_number,
            "word_count":  p.word_count,
            "is_scanned":  p.is_scanned,
        }
        for p in pages
    ]

    logger.info(
        "Processed '%s': %d page(s), %d words, %d scanned page(s).",
        filename,
        result["page_count"],
        result["word_count"],
        result["scanned_pages"],
    )
    return result


# ---------------------------------------------------------------------------
# Format-specific helpers
# ---------------------------------------------------------------------------

def _process_pdf(tmp_path: str) -> tuple[list[PageResult], dict]:
    """
    Three-stage PDF extraction:
      1. PyMuPDF for all pages.
      2. pdfplumber for any page where PyMuPDF produced very little text.
      3. OCR (PaddleOCR) for pages that still have no selectable text.
    """
    # Stage 1: fast extraction
    pages = parse_pdf_pymupdf(tmp_path)

    if not pages:
        logger.warning("PyMuPDF returned no pages; falling back to pdfplumber.")
        pages = parse_pdf_pdfplumber(tmp_path)

    # Stage 2: pdfplumber for text-sparse pages
    sparse_indices = [i for i, p in enumerate(pages) if len(p.text.strip()) < _MIN_TEXT_FOR_PAGE]
    if sparse_indices:
        plumber_pages = parse_pdf_pdfplumber(tmp_path)
        plumber_map = {p.page_number: p for p in plumber_pages}
        for i in sparse_indices:
            pn = pages[i].page_number
            if pn in plumber_map and len(plumber_map[pn].text.strip()) > len(pages[i].text.strip()):
                pages[i] = plumber_map[pn]

    # Stage 3: OCR for pages still sparse after pdfplumber
    still_scanned = [i for i, p in enumerate(pages) if len(p.text.strip()) < _MIN_TEXT_FOR_PAGE]
    if still_scanned:
        logger.info("Running OCR on %d scanned page(s)…", len(still_scanned))
        ocr_pages = parse_pdf_with_ocr(tmp_path)
        ocr_map = {p.page_number: p for p in ocr_pages}
        for i in still_scanned:
            pn = pages[i].page_number
            if pn in ocr_map and ocr_map[pn].text.strip():
                pages[i] = ocr_map[pn]

    metadata = extract_metadata_from_pdf(tmp_path, page_count=len(pages))
    return pages, metadata


def _process_docx(tmp_path: str) -> tuple[list[PageResult], dict]:
    pages = parse_docx_unstructured(tmp_path)
    metadata = extract_metadata_from_docx(tmp_path)
    metadata["page_count"] = len(pages)
    return pages, metadata


def _process_txt(tmp_path: str) -> tuple[list[PageResult], dict]:
    pages = parse_txt(tmp_path)
    metadata = extract_metadata_from_txt(tmp_path)
    metadata["page_count"] = 1
    return pages, metadata
