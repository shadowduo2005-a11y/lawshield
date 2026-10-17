import logging
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from chat.chat_service import ChatService
from memory.conversation import get_conversation

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)

# Friendly message shown to users when the API quota is exhausted
_QUOTA_MSG = (
    "I'm sorry — the AI service has temporarily hit its daily request limit. "
    "This typically resets within 24 hours. Please try again later, "
    "or contact the administrator to upgrade the API plan."
)


def _is_quota_error(exc: Exception) -> bool:
    """Return True when the exception is a provider quota / rate-limit / overload error."""
    msg = str(exc).upper()
    low = str(exc).lower()
    return (
        "RESOURCE_EXHAUSTED" in msg
        or "RATE_LIMIT" in msg
        or "429" in msg
        or "503" in msg
        or "UNAVAILABLE" in msg
        or "HIGH DEMAND" in msg
        or "OVERLOADED" in msg
        or "quota" in low
        or "exceeded your current quota" in low
        or "try again later" in low
    )


class ChatRequest(BaseModel):
    session_id: str
    message: str
    provider: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[str] = []


@router.post("/stream")
async def stream_chat(request: ChatRequest):
    """
    Stream the AI response using Server-Sent Events (SSE).

    ``chat_service.stream_chat`` yields raw strings (no ``data:`` prefix).
    This generator wraps each chunk in the SSE envelope exactly once:
        data: <chunk>\\n\\n

    Special sentinel values yielded by the service:
      • ``[Node: <name>]`` — progress update (agent pipeline step)
      • ``[FINAL]``        — signals the next chunk is the full answer
      • ``[DONE]``         — stream is complete
    """
    try:
        service = ChatService(provider_name=request.provider)

        async def event_generator():
            try:
                async for chunk in service.stream_chat(
                    request.session_id, request.message, request.history
                ):
                    # chat_service yields plain strings — wrap once into SSE format.
                    # chat_service already yields "[DONE]" as its last chunk, so we
                    # do NOT add another [DONE] here (that caused double responses).
                    yield f"data: {chunk}\n\n"
            except Exception as inner_exc:
                if _is_quota_error(inner_exc):
                    logger.warning("Quota exceeded during stream: %s", inner_exc)
                    yield f"data: [FINAL]\n\n"
                    yield f"data: {_QUOTA_MSG}\n\n"
                else:
                    logger.exception("Unhandled error during stream")
                    yield f"data: [FINAL]\n\n"
                    yield "data: An unexpected error occurred. Please try again.\n\n"
                # Only yield [DONE] from the error path since the normal path
                # gets [DONE] from chat_service itself
                yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Non-streaming chat endpoint. Returns the full response plus any sources.
    Handles quota errors gracefully by returning a user-friendly message
    instead of a raw 429 / 500 error.
    """
    try:
        service = ChatService(provider_name=request.provider)
        response_text = await service.chat(
            request.session_id, request.message, request.history
        )
        return ChatResponse(response=response_text, sources=[])

    except Exception as e:
        if _is_quota_error(e):
            logger.warning("Quota exceeded on /chat/ endpoint: %s", e)
            return ChatResponse(response=_QUOTA_MSG, sources=[])

        logger.exception("Unhandled error on /chat/ endpoint")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{session_id}")
async def clear_history(session_id: str):
    """Clear the in-memory conversation history for a session."""
    get_conversation(session_id).clear()
    return {"status": "success", "message": f"History cleared for {session_id}"}
