"""
router.py
FastAPI routes for document upload and processing.

Endpoints:
  POST /documents/upload
      Upload a PDF, DOCX, DOC, or TXT file.
      Returns extracted text, metadata, and per-page stats.
      Partial successes (e.g. some scanned pages) are flagged in the response
      rather than raising a 500, so callers can decide how to handle them.

  POST /documents/upload-and-ingest
      Upload a file AND index it into the RAG pipeline (Qdrant + ES) in one call.
      Returns the processing result plus ingest statistics.

  GET  /documents/supported-types
      List the file extensions and MIME types accepted by the service.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from .loaders import process_document, _SUPPORTED_EXTENSIONS, _MIME_TO_EXT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Document Processing"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class PageSummary(BaseModel):
    page_number: int
    word_count: int
    is_scanned: bool


class DocumentResponse(BaseModel):
    filename: str
    file_type: str
    content_type: str
    text: str
    pages: List[PageSummary]
    metadata: Dict[str, Any]
    page_count: int
    word_count: int
    char_count: int
    scanned_pages: int
    error: str | None = None


class IngestStats(BaseModel):
    chunks_indexed: int
    status: str


class UploadAndIngestResponse(DocumentResponse):
    ingest: IngestStats | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=DocumentResponse,
    summary="Upload and process a legal document",
)
async def upload_document(file: UploadFile = File(...)) -> DocumentResponse:
    """
    Upload a legal document (PDF, DOCX, DOC, TXT) and receive:
    - Full extracted and cleaned text
    - Per-page metadata (word count, scanned flag)
    - Document metadata (author, title, creation date, …)
    - Summary statistics (word count, char count, scanned page count)

    **Does not** index the document into the RAG database.
    Use `/documents/upload-and-ingest` for that.
    """
    _validate_file(file)

    result = await asyncio.to_thread(process_document, file)

    if result.get("error") and not result.get("text"):
        # Complete failure — no text extracted at all
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result["error"],
        )

    # Partial success (some pages may have failed) — return with error field set
    return DocumentResponse(**result)


@router.post(
    "/upload-and-ingest",
    response_model=UploadAndIngestResponse,
    summary="Upload, process, and index a legal document into the RAG pipeline",
)
async def upload_and_ingest(file: UploadFile = File(...)) -> UploadAndIngestResponse:
    """
    Combines document upload + RAG ingestion in a single call.

    Steps:
    1. Extract and clean text (same as `/upload`).
    2. Index text + metadata chunks into Qdrant (vector) and Elasticsearch (lexical).

    Returns the full processing result plus ingest statistics.
    """
    _validate_file(file)

    # Step 1: process
    result = await asyncio.to_thread(process_document, file)

    if result.get("error") and not result.get("text"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result["error"],
        )

    # Step 2: ingest into RAG pipeline
    ingest_result: IngestStats | None = None
    if result.get("text"):
        try:
            from rag.pipelines import ingest_document  # local import to avoid circular dep
            ingest_stats = await asyncio.to_thread(
                ingest_document,
                result["text"],
                result["metadata"],
            )
            ingest_result = IngestStats(
                chunks_indexed=ingest_stats.get("chunks_indexed", 0),
                status=ingest_stats.get("status", "unknown"),
            )
        except Exception as exc:
            logger.error("RAG ingestion failed after upload: %s", exc)
            ingest_result = IngestStats(chunks_indexed=0, status=f"failed: {exc}")

    return UploadAndIngestResponse(**result, ingest=ingest_result)


@router.get(
    "/supported-types",
    summary="List supported document types",
)
async def supported_types() -> Dict[str, Any]:
    """Return the file extensions and MIME types accepted by the upload endpoints."""
    return {
        "extensions": sorted(_SUPPORTED_EXTENSIONS),
        "mime_types": _MIME_TO_EXT,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_file(file: UploadFile) -> None:
    """Raise 400 if the file has no name or an unsupported extension."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )
    import os
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File type '{ext}' is not supported. "
                f"Accepted: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
            ),
        )
