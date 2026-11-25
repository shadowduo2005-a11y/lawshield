from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio

from .pipelines import ingest_document, ask_question_pipeline

router = APIRouter(prefix="/rag", tags=["RAG"])

class IngestRequest(BaseModel):
    text: str
    metadata: Dict[str, Any] = {}
    collection_name: str = "documents"

class AskRequest(BaseModel):
    query: str
    metadata_filter: Optional[Dict[str, Any]] = None
    collection_name: str = "documents"

@router.post("/ingest")
async def ingest(request: IngestRequest):
    """Index extracted text and metadata into the vector/search databases."""
    try:
        # In a production app, this should be sent to a background task (e.g., Celery)
        result = await asyncio.to_thread(ingest_document, request.text, request.metadata, request.collection_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ask")
async def ask(request: AskRequest):
    """Ask a question based on indexed documents."""
    try:
        result = await ask_question_pipeline(
            query=request.query,
            metadata_filter=request.metadata_filter,
            collection_name=request.collection_name
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
