import asyncio
from contextlib import suppress
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
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

_CONFIG_MSG = (
    "The AI service is not fully configured. Please ask the administrator to "
    "check the selected provider and its API key."
)

_AUTH_MSG = (
    "The AI provider rejected the configured API key. Please ask the "
    "administrator to update the AI service credentials."
)


def _sse_event(value: str) -> str:
    """Encode one value as a valid SSE event, including multiline answers."""
    normalized = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return "".join(f"data: {line}\n" for line in normalized.split("\n")) + "\n"


def _public_error_message(exc: Exception) -> str:
    text = str(exc).lower()
    if "no llm api key" in text or "api key is configured" in text:
        return _CONFIG_MSG
    if any(marker in text for marker in ("401", "403", "unauthorized", "invalid api key", "authentication")):
        return _AUTH_MSG
    return "The AI service could not complete this request. Please try again shortly."


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
    sources: List[str] = Field(default_factory=list)


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
            iterator = service.stream_chat(
                request.session_id, request.message, request.history
            ).__aiter__()
            next_chunk = None
            try:
                # Keep the Render -> EC2 connection active while a provider call is
                # running. asyncio.wait does not cancel the in-flight generator on
                # each heartbeat, unlike wait_for.
                next_chunk = asyncio.create_task(anext(iterator))
                while True:
                    done, _ = await asyncio.wait({next_chunk}, timeout=15)
                    if not done:
                        yield ": keep-alive\n\n"
                        continue

                    try:
                        chunk = next_chunk.result()
                    except StopAsyncIteration:
                        break

                    yield _sse_event(chunk)
                    next_chunk = asyncio.create_task(anext(iterator))
            except Exception as inner_exc:
                if _is_quota_error(inner_exc):
                    logger.warning("Quota exceeded during stream: %s", inner_exc)
                    yield _sse_event("[FINAL]")
                    yield _sse_event(_QUOTA_MSG)
                else:
                    logger.exception("Unhandled error during stream")
                    yield _sse_event("[FINAL]")
                    yield _sse_event(_public_error_message(inner_exc))
                # Only yield [DONE] from the error path since the normal path
                # gets [DONE] from chat_service itself
                yield _sse_event("[DONE]")
            finally:
                if next_chunk is not None and not next_chunk.done():
                    next_chunk.cancel()
                    with suppress(asyncio.CancelledError):
                        await next_chunk
                with suppress(Exception):
                    await iterator.aclose()

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
        raise HTTPException(status_code=503, detail=_public_error_message(e))


@router.delete("/history/{session_id}")
async def clear_history(session_id: str):
    """Clear the in-memory conversation history for a session."""
    get_conversation(session_id).clear()
    return {"status": "success", "message": f"History cleared for {session_id}"}
